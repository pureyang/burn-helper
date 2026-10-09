# Networking for the badge: Wi-Fi with fallbacks, bridge discovery and a
# non-blocking HTTP poll. Everything is driven from tick(), called once per
# frame, and nothing here may raise: an exception inside the run() loop would
# drop the badge into the firmware's fatal-error screen.

import json
import socket
import select
import time

try:
    import network
except ImportError:  # desktop simulator
    network = None

try:
    import errno
    EINPROGRESS = errno.EINPROGRESS
    EAGAIN = errno.EAGAIN
except (ImportError, AttributeError):
    EINPROGRESS = 115
    EAGAIN = 11
BEACON_PORT = 47800
POLL_MS = 2500
HTTP_TIMEOUT_MS = 4000
JOIN_TIMEOUT_MS = 20000
RETRY_ALL_MS = 15000
FRESH_MS = 12000


def ticks():
    return time.ticks_ms()


def since(t0):
    return time.ticks_diff(time.ticks_ms(), t0)


class HttpGet:
    """One HTTP/1.0 GET, advanced a little on every step() call."""

    def __init__(self, host, port, path):
        self.done = False
        self.ok = False
        self.body = None
        self.err = None
        self.t0 = ticks()
        self.buf = b""
        self.sent = False
        self.req = ("GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n" % (path, host)).encode()
        self.sock = None
        try:
            addr = socket.getaddrinfo(host, port)[0][-1]
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setblocking(False)
            self.sock = s
            try:
                s.connect(addr)
            except OSError as e:
                if e.args[0] not in (EINPROGRESS, EAGAIN):
                    raise
            self.poller = select.poll()
            self.poller.register(s, select.POLLOUT | select.POLLIN)
        except Exception as e:  # noqa: BLE001
            self.fail(e)

    def fail(self, e):
        self.err = e
        self.done = True
        self.close()

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:  # noqa: BLE001
                pass
            self.sock = None

    def step(self):
        if self.done:
            return
        if since(self.t0) > HTTP_TIMEOUT_MS:
            self.fail("timeout")
            return
        try:
            for _sock, ev in self.poller.poll(0):
                if ev & (select.POLLERR | select.POLLHUP) and not ev & select.POLLIN:
                    self.fail("connection refused")
                    return
                if not self.sent and ev & select.POLLOUT:
                    self.sock.send(self.req)
                    self.sent = True
                    self.poller.modify(self.sock, select.POLLIN)
                if self.sent and ev & select.POLLIN:
                    while True:
                        try:
                            chunk = self.sock.recv(1024)
                        except OSError as e:
                            if e.args[0] == EAGAIN:
                                break
                            raise
                        if not chunk:
                            self.finish()
                            return
                        self.buf += chunk
                        if len(self.buf) > 16384:
                            self.fail("response too large")
                            return
        except Exception as e:  # noqa: BLE001
            self.fail(e)

    def finish(self):
        self.close()
        self.done = True
        head, _, body = self.buf.partition(b"\r\n\r\n")
        line = head.split(b"\r\n", 1)[0]
        if b" 200 " not in line + b" ":
            self.err = "HTTP " + line.decode()[:24]
            return
        try:
            self.body = json.loads(body)
            self.ok = True
        except Exception as e:  # noqa: BLE001
            self.err = e


class Net:
    def __init__(self, networks, bridge=None, hostname="tufty-claude"):
        self.networks = [n for n in networks if n and n[0]]
        self.fixed_bridge = bridge          # (host, port) or None
        self.bridge = bridge
        self.hostname = hostname
        self.wlan = None
        self.state = "init"                 # init | joining | up | down | none
        self.idx = 0
        self.join_t0 = 0
        self.down_t0 = 0
        self.ssid = ""
        self.ip = ""
        self.udp = None
        self.beacon_t = None
        self.http = None
        self.poll_t0 = None
        self.ok_t = None
        self.data = None
        self.seq = 0                        # bumps on every fresh status
        self.err = ""
        self.extra_query = ""
        if not self.networks:
            self.state = "none"

    # -------------------------------------------------- public
    def tick(self):
        try:
            self._wifi()
            if self.state == "up":
                self._discover()
                self._poll()
        except Exception as e:  # noqa: BLE001
            self.err = repr(e)[:40]

    def fresh(self):
        return self.ok_t is not None and since(self.ok_t) < FRESH_MS

    def label(self):
        if self.state == "none":
            return "NO WI-FI SET UP: HOLD B"
        if self.state in ("init", "joining"):
            return "JOINING %s..." % self.ssid.upper()
        if self.state == "down":
            return "WI-FI NOT FOUND, RETRYING"
        if self.bridge is None:
            return "SEARCHING FOR BRIDGE..."
        if not self.fresh():
            return "BRIDGE NOT ANSWERING"
        return ""

    def stop(self):
        self._close_udp()
        if self.http:
            self.http.close()
            self.http = None
        if self.wlan:
            try:
                self.wlan.disconnect()
                self.wlan.active(False)
            except Exception:  # noqa: BLE001
                pass
        self.wlan = None
        self.state = "init" if self.networks else "none"

    # -------------------------------------------------- wifi
    def _join(self, i):
        self.idx = i % len(self.networks)
        ssid, psk = self.networks[self.idx]
        self.ssid = ssid
        try:
            self.wlan.disconnect()
        except Exception:  # noqa: BLE001
            pass
        self.wlan.connect(ssid, psk)
        self.join_t0 = ticks()
        self.state = "joining"

    def _wifi(self):
        if self.state == "none" or network is None:
            return
        if self.wlan is None:
            try:
                network.hostname(self.hostname)
            except Exception:  # noqa: BLE001
                pass
            self.wlan = network.WLAN(network.STA_IF)
            self.wlan.active(True)
            if self.wlan.isconnected():
                self._up()
                return
            self._join(0)
            return
        if self.state == "up":
            if not self.wlan.isconnected():
                self._close_udp()
                self._join(self.idx)
            return
        if self.state == "down":
            if since(self.down_t0) > RETRY_ALL_MS:
                self._join(0)
            return
        # joining
        if self.wlan.isconnected():
            self._up()
            return
        st = self.wlan.status()
        failed = st in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND, network.STAT_CONNECT_FAIL)
        if failed or since(self.join_t0) > JOIN_TIMEOUT_MS:
            if self.idx + 1 < len(self.networks):
                self._join(self.idx + 1)
            else:
                self.state = "down"
                self.down_t0 = ticks()
                try:
                    self.wlan.disconnect()
                except Exception:  # noqa: BLE001
                    pass

    def _up(self):
        self.state = "up"
        try:
            self.ip = self.wlan.ifconfig()[0]
        except Exception:  # noqa: BLE001
            self.ip = "?"

    # -------------------------------------------------- discovery
    def _close_udp(self):
        if self.udp is not None:
            try:
                self.udp.close()
            except Exception:  # noqa: BLE001
                pass
            self.udp = None

    def _discover(self):
        if self.udp is None:
            try:
                u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                except Exception:  # noqa: BLE001
                    pass
                u.bind(("0.0.0.0", BEACON_PORT))
                u.setblocking(False)
                self.udp = u
            except Exception as e:  # noqa: BLE001
                self.err = "udp " + repr(e)[:30]
                return
        for _ in range(4):
            try:
                data, addr = self.udp.recvfrom(64)
            except OSError:
                return
            if data.startswith(b"TUFTYBRIDGE"):
                try:
                    port = int(data.split()[2])
                except Exception:  # noqa: BLE001
                    port = 8787
                self.beacon_t = ticks()
                if self.fixed_bridge is None:
                    host = addr[0] if isinstance(addr, tuple) else socket.inet_ntop(socket.AF_INET, addr[4:8])
                    self.bridge = (host, port)

    # -------------------------------------------------- polling
    def _poll(self):
        if self.http is not None:
            self.http.step()
            if self.http.done:
                if self.http.ok and isinstance(self.http.body, dict):
                    self.data = self.http.body
                    self.ok_t = ticks()
                    self.seq += 1
                    self.err = ""
                else:
                    self.err = str(self.http.err)[:40]
                self.http = None
            return
        if self.bridge is None:
            return
        if self.poll_t0 is not None and since(self.poll_t0) < POLL_MS:
            return
        self.poll_t0 = ticks()
        self.http = HttpGet(self.bridge[0], self.bridge[1], "/status" + self.extra_query)
