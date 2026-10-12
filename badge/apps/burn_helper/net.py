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
JOIN_TIMEOUT_MS = 12000   # a right password joins in about 3 s; a wrong one hangs in "joining"
RETRY_ALL_MS = 15000
FRESH_MS = 12000
NO_BEACON_MS = 10000
RELAY_POLL_MS = 5000      # the internet relay is polled less often than the bridge on the LAN
LOG_FILE = "/state/burn_helper_net.log"
LOG_MAX = 16384

# wlan.status() codes (cyw43) and what they mean to a person
STATUS_TEXT = {0: "idle", 1: "joining", 2: "linked, waiting for IP", 3: "connected",
               -1: "connect failed", -2: "network not found", -3: "wrong password"}
# per-network verdicts after an attempt
OK = "connected"
BAD_PW = "wrong password"
STUCK = "never accepted the badge"
NOT_SEEN = "not visible (5 GHz only / out of range?)"
NO_IP = "joined but no IP address (DHCP)"
FAILED = "connect failed"


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
    """Wi-Fi + bridge link with a diagnosis of every failure (see debug screen)."""

    def __init__(self, networks, bridge=None, hostname="burn-helper", relay=None):
        self.cands = []
        for n in networks:
            if not n or not n[0]:
                continue
            ssid, psk = n[0], n[1]
            src = n[2] if len(n) > 2 else ""
            self.cands.append({"ssid": ssid, "psk": psk, "src": src, "variant": "", "result": "", "tries": 0})
            if psk != psk.strip():
                # phone keyboards love adding a trailing space; also try without it
                self.cands.append({"ssid": ssid, "psk": psk.strip(), "src": src, "variant": "trimmed",
                                   "result": "", "tries": 0})
        self.networks = self.cands            # truthy when anything is configured
        self.fixed_bridge = bridge             # (host, port) or None
        self.bridge = bridge
        self.relay = relay                     # {"url", "key"} of the Mac's internet relay, or None
        self.rclient = None                    # relay.Client while the relay is in use
        self.rpoll_t0 = None
        self.via = None                        # "lan" or "relay": where the last good status came from
        self.force_relay = False               # testing: ignore the LAN bridge (USB "@RELAY 1")
        self.hostname = hostname
        self.wlan = None
        self.state = "init" if self.cands else "none"   # init|scan|joining|up|down|none
        self.cur = None                        # index into cands
        self.join_t0 = 0
        self.down_t0 = 0
        self.ssid = ""
        self.ip = ""
        self.gw = ""
        self.mac = ""
        self.seen = {}                         # ssid -> (best rssi, channel, access points)
        self.best_bssid = {}                   # ssid -> bssid of its strongest access point
        self.pinned = False                    # current join is pinned to best_bssid
        self.scan_total = 0
        self.scan_t = None
        self.status = None
        self.attempts = 0
        self.up_t = None
        self.udp = None
        self.beacon_t = None
        self.http = None
        self.poll_t0 = None
        self.ok_t = None
        self.data = None
        self.seq = 0
        self.err = ""
        self.http_err = ""
        self.extra_query = ""
        self.log = []
        self.boot_t = ticks()
        self._trim_logfile()
        self.note("boot: %d network candidate(s)" % len(self.cands))

    # -------------------------------------------------- logging
    def note(self, msg):
        line = "%5ds %s" % (since(self.boot_t) // 1000, msg)
        self.log.append(line)
        if len(self.log) > 40:
            self.log.pop(0)
        try:
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
        except Exception:  # noqa: BLE001
            pass

    def _trim_logfile(self):
        try:
            import os
            if os.stat(LOG_FILE)[6] > LOG_MAX:
                with open(LOG_FILE) as f:
                    keep = f.read()[-LOG_MAX // 2:]
                with open(LOG_FILE, "w") as f:
                    f.write(keep)
            with open(LOG_FILE, "a") as f:
                f.write("---- app start ----\n")
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------- public
    def tick(self):
        try:
            self._wifi()
            if self.state == "up":
                self._discover()
                self._poll()
        except Exception as e:  # noqa: BLE001
            self.err = repr(e)[:40]
            self.note("error: " + self.err)

    def fresh(self):
        return self.ok_t is not None and since(self.ok_t) < FRESH_MS

    def set_relay(self, relay):
        """New relay address and key (they arrive over USB from the bridge)."""
        if relay != self.relay:
            self.relay = relay
            self._close_relay()
            self.note("relay set to %s" % (relay["url"] if relay else "none"))

    def _close_relay(self):
        if self.rclient is not None:
            self.rclient.close()
            self.rclient = None

    def _lan_bridge(self):
        """The bridge on this network, if it is there: fixed, or heard by beacon in the last 10 s."""
        if self.force_relay:
            return None
        if self.fixed_bridge is not None:
            return self.fixed_bridge
        if self.bridge is not None and self.beacon_t is not None and since(self.beacon_t) < NO_BEACON_MS:
            return self.bridge
        return None

    def _use_relay(self):
        return (self.relay is not None and self._lan_bridge() is None and self.up_t is not None
                and (self.force_relay or since(self.up_t) > NO_BEACON_MS))

    def results(self):
        out = {}
        for c in self.cands:
            if c["result"]:
                out[c["ssid"]] = c["result"]
        return out

    def hint(self):
        """One plain-language diagnosis of what is wrong right now."""
        if self.state == "none":
            return "No Wi-Fi saved. Hold B for phone setup."
        if self.state == "up":
            if self.via == "relay" and self.fresh():
                return "All good, through the internet relay."
            if self._use_relay():
                return ("Away from the Mac's network: using the internet relay%s" %
                        (" (%s)" % self.http_err if self.http_err else "..."))
            if self.fixed_bridge is None and self.beacon_t is None and self.up_t is not None \
                    and since(self.up_t) > NO_BEACON_MS:
                return ("On Wi-Fi but no bridge beacon: is the Mac on this same network? "
                        "Plug the badge into the Mac once to set up the internet relay.")
            if self.bridge is not None and not self.fresh() and self.http_err:
                return "Bridge %s:%d not answering (%s)" % (self.bridge[0], self.bridge[1], self.http_err)
            if self.fresh():
                return "All good."
            return "Connected, waiting for the bridge..."
        verdicts = [c for c in self.cands if c["result"]]
        if self.seen is not None and self.scan_t is not None and not any(c["ssid"] in self.seen for c in self.cands):
            return "None of your networks are visible. Badge is 2.4 GHz only."
        for want in (BAD_PW, STUCK, NO_IP, FAILED):
            for c in verdicts:
                if c["result"] == want:
                    if want == STUCK:
                        return ("%s is in range but never let the badge in: almost always a "
                                "wrong password (hold B to retype). Else: WPA2 off or MAC filter." % c["ssid"])
                    if want == BAD_PW:
                        return "%s: wrong password. Hold B to re-enter it." % c["ssid"]
                    if want == NO_IP:
                        return "%s joined but gave no IP address (DHCP)" % c["ssid"]
                    return "%s: connect failed" % c["ssid"]
        if self.state == "scan":
            return "Scanning for networks..."
        return "Joining %s..." % self.ssid

    def label(self):
        """Short caption for the themes (about 26 characters)."""
        if self.state == "none":
            return "NO WI-FI: HOLD B TO SET UP"
        if self.state == "scan":
            return "SCANNING WI-FI..."
        if self.state in ("init", "joining"):
            bad = [c for c in self.cands if c["result"] in (BAD_PW, STUCK)]
            if bad and (since(self.boot_t) // 3000) % 2:
                return "WI-FI FAILING: PRESS B x2"
            return "JOINING %s..." % self.ssid.upper()[:14]
        if self.state == "down":
            return "WI-FI FAILING: PRESS B x2"
        if self.fresh():
            return ""
        if self._use_relay():
            return "REACHING THE RELAY..."
        if self.bridge is None:
            return "SEARCHING FOR BRIDGE..."
        if not self.fresh():
            return "BRIDGE NOT ANSWERING"
        return ""

    def stop(self):
        self._close_udp()
        self._close_relay()
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
        self.state = "init" if self.cands else "none"
        self.note("wifi stopped")

    def rescan(self):
        if self.state not in ("none", "up"):
            self.state = "scan"

    # -------------------------------------------------- wifi
    def _scan(self):
        self.seen = {}
        self.best_bssid = {}
        try:
            res = self.wlan.scan()
        except Exception as e:  # noqa: BLE001
            self.note("scan failed: %r" % e)
            res = []
        self.scan_total = len(res)
        for r in res:
            try:
                name = r[0].decode()
            except Exception:  # noqa: BLE001
                continue
            if not name:
                continue
            old = self.seen.get(name)
            if old is None or r[3] > old[0]:
                self.best_bssid[name] = r[1]
            if old is None:
                self.seen[name] = (r[3], r[2], 1)
            else:
                best = old if old[0] >= r[3] else (r[3], r[2], 0)
                self.seen[name] = (best[0], best[1], old[2] + 1)
        self.scan_t = ticks()
        mine = []
        for c in self.cands:
            info = self.seen.get(c["ssid"])
            if c["variant"]:
                continue
            if info:
                mine.append("%s ch%d %ddBm" % (c["ssid"], info[1], info[0]))
            else:
                mine.append("%s NOT VISIBLE" % c["ssid"])
                c["result"] = NOT_SEEN
        self.note("scan: %d networks; %s" % (self.scan_total, "; ".join(mine)))

    def _next(self, start):
        """Index of the next visible candidate at or after start, or None."""
        for i in range(start, len(self.cands)):
            if self.cands[i]["ssid"] in self.seen:
                return i
        return None

    def _join(self, i, pin=True):
        c = self.cands[i]
        self.cur = i
        self.ssid = c["ssid"]
        c["tries"] += 1
        self.attempts += 1
        try:
            self.wlan.disconnect()
        except Exception:  # noqa: BLE001
            pass
        # Combined 2.4/5 GHz and mesh networks share one name: the radio only hears the 2.4 GHz
        # side, so aim at its strongest access point first, then let it pick any.
        bssid = self.best_bssid.get(c["ssid"]) if pin else None
        self.pinned = bssid is not None
        try:
            if bssid is not None:
                self.wlan.connect(c["ssid"], c["psk"], bssid=bssid)
            else:
                self.wlan.connect(c["ssid"], c["psk"])
        except Exception as e:  # noqa: BLE001
            self.pinned = False
            self.note("pinned join not accepted (%r); joining by name" % (e,))
            self.wlan.connect(c["ssid"], c["psk"])
        self.join_t0 = ticks()
        self.status = None
        self.state = "joining"
        self.note("join %s%s%s (password %d chars)" % (c["ssid"], " [trimmed]" if c["variant"] else "",
                                                       " [strongest AP]" if self.pinned else "", len(c["psk"])))

    def _verdict(self, st, timed_out):
        if st == network.STAT_WRONG_PASSWORD:
            return BAD_PW
        if st == network.STAT_NO_AP_FOUND:
            return NOT_SEEN
        if st == network.STAT_CONNECT_FAIL:
            return FAILED
        if timed_out and st == 2:
            return NO_IP
        if timed_out:
            return STUCK
        return ""

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
            try:
                import binascii
                self.mac = binascii.hexlify(self.wlan.config("mac"), ":").decode()
            except Exception:  # noqa: BLE001
                self.mac = "?"
            if self.wlan.isconnected():
                self._up()
                return
            self.state = "scan"        # scan on the next frame so "SCANNING" gets drawn first
            return
        if self.state == "scan":
            self._scan()
            i = self._next(0)
            if i is None:
                self.state = "down"
                self.down_t0 = ticks()
                self.note("none of the saved networks are visible; retry in %ds" % (RETRY_ALL_MS // 1000))
            else:
                self._join(i)
            return
        if self.state == "up":
            if not self.wlan.isconnected():
                self.note("lost connection to %s" % self.ssid)
                self._close_udp()
                self.up_t = None
                self.state = "scan"
            return
        if self.state == "down":
            if since(self.down_t0) > RETRY_ALL_MS:
                self.state = "scan"
            return
        # joining
        if self.wlan.isconnected():
            self._up()
            return
        st = self.wlan.status()
        if st != self.status:
            self.note("status %d (%s) after %dms" % (st, STATUS_TEXT.get(st, "?"), since(self.join_t0)))
            self.status = st
        timed_out = since(self.join_t0) > JOIN_TIMEOUT_MS
        verdict = self._verdict(st, timed_out)
        if verdict:
            c = self.cands[self.cur]
            info = self.seen.get(c["ssid"])
            if self.pinned and verdict in (STUCK, FAILED) and info and info[2] > 1:
                self.note("%s: strongest AP did not accept; trying any AP" % c["ssid"])
                self._join(self.cur, pin=False)
                return
            c["result"] = verdict
            self.note("%s: %s" % (c["ssid"], verdict))
            nxt = self._next(self.cur + 1)
            if nxt is not None:
                self._join(nxt)
            else:
                self.state = "down"
                self.down_t0 = ticks()
                try:
                    self.wlan.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                self.note("all networks failed; retry in %ds" % (RETRY_ALL_MS // 1000))

    def _up(self):
        self.state = "up"
        self.up_t = ticks()
        try:
            cfg = self.wlan.ifconfig()
            self.ip = cfg[0]
            self.gw = cfg[2]
        except Exception:  # noqa: BLE001
            self.ip = "?"
        if self.cur is not None:
            self.cands[self.cur]["result"] = OK
        self.note("connected to %s: ip %s gateway %s" % (self.ssid, self.ip, self.gw))

    # -------------------------------------------------- diagnostics
    def dump(self):
        """Everything the debug screen knows, as text lines (also sent over USB)."""
        out = ["state %s  attempts %d  mac %s" % (self.state, self.attempts, self.mac)]
        if self.state == "up":
            out.append("ssid %s  ip %s  gw %s" % (self.ssid, self.ip, self.gw))
        elif self.status is not None:
            out.append("%s %s: status %d (%s) for %ds" % (
                "joining" if self.state == "joining" else "last join", self.ssid, self.status,
                STATUS_TEXT.get(self.status, "?"), since(self.join_t0) // 1000))
        for c in self.cands:
            info = self.seen.get(c["ssid"])
            vis = "ch%d %ddBm x%d" % (info[1], info[0], info[2]) if info else "not seen"
            out.append("net %s%s [%s] pw %d chars%s | %s | tries %d | %s" % (
                c["ssid"], " (trimmed)" if c["variant"] else "", c["src"] or "?", len(c["psk"]),
                " ENDS WITH SPACE" if c["psk"] != c["psk"].rstrip() else "", vis, c["tries"], c["result"] or "-"))
        out.append("scan: %d networks visible" % self.scan_total)
        b = self.bridge
        out.append("bridge %s  beacon %s  last ok %s  http %s" % (
            "%s:%d" % b if b else "unknown",
            "never" if self.beacon_t is None else "%ds ago" % (since(self.beacon_t) // 1000),
            "never" if self.ok_t is None else "%ds ago" % (since(self.ok_t) // 1000),
            self.http_err or "-"))
        if self.relay is not None:
            c = self.rclient
            out.append("relay %s  via %s  handshakes %d  %s" % (
                self.relay["url"].split("://", 1)[-1].split(".", 1)[0], self.via or "-",
                c.handshakes if c else 0, "forced" if self.force_relay else ""))
        out.append("hint: " + self.hint())
        return out

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
                if self.beacon_t is None:
                    self.note("heard bridge beacon from %r" % (addr,))
                self.beacon_t = ticks()
                if self.fixed_bridge is None:
                    host = addr[0] if isinstance(addr, tuple) else socket.inet_ntop(socket.AF_INET, addr[4:8])
                    self.bridge = (host, port)

    # -------------------------------------------------- polling
    def _poll(self):
        if self._use_relay():
            self._poll_relay()
            return
        self._close_relay()
        if self.http is not None:
            self.http.step()
            if self.http.done:
                if self.http.ok and isinstance(self.http.body, dict):
                    if self.ok_t is None:
                        self.note("first status from bridge %s:%d" % self.bridge)
                    self.data = self.http.body
                    self.via = "lan"
                    self.ok_t = ticks()
                    self.seq += 1
                    self.err = ""
                    self.http_err = ""
                else:
                    e = str(self.http.err)[:40]
                    if e != self.http_err:
                        self.note("bridge poll failed: " + e)
                    self.http_err = e
                self.http = None
            return
        if self.bridge is None:
            return
        if self.poll_t0 is not None and since(self.poll_t0) < POLL_MS:
            return
        self.poll_t0 = ticks()
        self.http = HttpGet(self.bridge[0], self.bridge[1], "/status" + self.extra_query)

    def _poll_relay(self):
        """Away from home: the same status, over HTTPS through the Mac's Tailscale Funnel."""
        if self.rclient is None:
            import relay
            self.rclient = relay.Client(self.relay["url"], self.relay["key"])
            self.note("no bridge on this network: using the internet relay")
        c = self.rclient
        if not c.done:
            c.step()
            if c.done:
                if c.ok and isinstance(c.body, dict):
                    if self.via != "relay":
                        self.note("first status through the internet relay")
                    self.data = c.body
                    self.via = "relay"
                    self.ok_t = ticks()
                    self.seq += 1
                    self.err = ""
                    self.http_err = ""
                else:
                    e = str(c.err)[:40]
                    if e != self.http_err:
                        self.note("relay poll failed: " + e)
                    self.http_err = e
            return
        if self.rpoll_t0 is not None and since(self.rpoll_t0) < RELAY_POLL_MS:
            return
        self.rpoll_t0 = ticks()
        c.start("/status")
