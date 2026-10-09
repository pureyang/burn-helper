# Phone setup portal: the badge becomes a Wi-Fi hotspot with a tiny web form.
#
# Join the hotspot from your phone (scan the QR code on screen), open
# http://192.168.4.1 and add a Wi-Fi network (home, office or your phone's own
# hotspot) and optionally a fixed bridge address. Saved to
# /state/claude_buddy_net.json, then the badge restarts and uses it.

import json
import socket
import select
import time
import machine
import network
import config
import gfx

PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Tufty setup</title><style>body{font-family:-apple-system,system-ui,sans-serif;max-width:420px;margin:24px auto;padding:0 16px;background:#111;color:#eee}
input,button{font-size:18px;width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;border-radius:8px;border:1px solid #555;background:#222;color:#eee}
button{background:#d97757;border:0;color:#111;font-weight:600}small{color:#999}li{margin:4px 0}</style></head><body>
<h2>Tufty badge setup</h2><p>Add the Wi-Fi network the badge should join. It tries these first, then the one in secrets.py.</p>
<form method=post action=/save><label>Wi-Fi name (SSID)<input name=ssid required></label>
<label>Password<input name=psk type=password></label>
<label>Bridge address <small>(optional, e.g. 192.168.1.20:8787; blank = auto-discover)</small><input name=bridge value="%BRIDGE%"></label>
<button>Save and restart badge</button></form><h3>Saved networks</h3><ul>%LIST%</ul>
<form method=post action=/forget><button style="background:#444;color:#eee">Forget saved networks</button></form></body></html>"""

DONE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1"></head>
<body style="font-family:system-ui;background:#111;color:#eee;padding:24px"><h2>Saved.</h2><p>The badge restarts and joins the network. Reconnect your phone to your usual Wi-Fi.</p></body></html>"""


def _unquote(s):
    s = s.replace("+", " ")
    out = b""
    i = 0
    b = s.encode()
    while i < len(b):
        if b[i] == 37 and i + 2 < len(b):
            try:
                out += bytes([int(b[i + 1:i + 3], 16)])
                i += 3
                continue
            except ValueError:
                pass
        out += b[i:i + 1]
        i += 1
    return out.decode()


def _form(body):
    d = {}
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[_unquote(k)] = _unquote(v)
    return d


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


class Portal:
    def __init__(self):
        uid = machine.unique_id()
        self.ssid = "Tufty-Claude-%02X%02X" % (uid[-2], uid[-1])
        self.psk = "buddy%02x%02x%02x" % (uid[-3], uid[-2], uid[-1])
        self.ap = network.WLAN(network.AP_IF)
        try:
            self.ap.config(ssid=self.ssid, key=self.psk)
        except Exception:  # noqa: BLE001
            self.ap.config(ssid=self.ssid, password=self.psk)
        self.ap.active(True)
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("0.0.0.0", 80))
        self.srv.listen(2)
        self.srv.setblocking(False)
        self.reboot_at = None
        self.saved = False
        self.qr = screen.qr("WIFI:T:WPA;S:%s;P:%s;;" % (self.ssid, self.psk), 0, 0, 1)
        self.t0 = time.ticks_ms()

    def ip(self):
        try:
            return self.ap.ifconfig()[0]
        except Exception:  # noqa: BLE001
            return "192.168.4.1"

    def tick(self):
        if self.reboot_at is not None and time.ticks_diff(time.ticks_ms(), self.reboot_at) > 0:
            self.close()
            machine.reset()
        try:
            cl, _ = self.srv.accept()
        except OSError:
            return
        try:
            cl.settimeout(3)
            self.handle(cl)
        except Exception:  # noqa: BLE001
            pass
        try:
            cl.close()
        except Exception:  # noqa: BLE001
            pass

    def handle(self, cl):
        req = b""
        while b"\r\n\r\n" not in req and len(req) < 4096:
            chunk = cl.recv(512)
            if not chunk:
                break
            req += chunk
        head, _, body = req.partition(b"\r\n\r\n")
        lines = head.decode().split("\r\n")
        method, path = (lines[0].split(" ") + ["", ""])[:2]
        length = 0
        for ln in lines[1:]:
            if ln.lower().startswith("content-length:"):
                length = int(ln.split(":", 1)[1].strip() or 0)
        while len(body) < min(length, 2048):
            chunk = cl.recv(512)
            if not chunk:
                break
            body += chunk
        d = config.load_portal()
        if method == "POST" and path == "/save":
            f = _form(body.decode())
            ssid = f.get("ssid", "").strip()
            if ssid:
                nets = [n for n in d.get("networks", []) if n[0] != ssid]
                d["networks"] = [[ssid, f.get("psk", "")]] + nets[:4]
            d["bridge"] = f.get("bridge", "").strip()
            config.save_portal(d)
            self.saved = True
            self.reboot_at = time.ticks_add(time.ticks_ms(), 2500)
            return self.send(cl, DONE)
        if method == "POST" and path == "/forget":
            config.save_portal({"networks": [], "bridge": d.get("bridge", "")})
            d = config.load_portal()
        items = "".join("<li>%s</li>" % _esc(n[0]) for n in d.get("networks", [])) or "<li><small>none</small></li>"
        self.send(cl, PAGE.replace("%LIST%", items).replace("%BRIDGE%", _esc(d.get("bridge", ""))))

    def send(self, cl, html):
        data = html.encode()
        cl.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(data))
        i = 0
        while i < len(data):
            i += cl.send(data[i:i + 1024])

    def close(self):
        try:
            self.srv.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.ap.active(False)
        except Exception:  # noqa: BLE001
            pass

    def draw(self, t):
        gfx.box(0, 0, 160, 120, (20, 18, 24))
        gfx.box(0, 0, 160, 13, (217, 119, 87))
        gfx.text("PHONE SETUP", 4, -1, (20, 18, 24), font.sins)
        q = self.qr
        s = 3 if q.width * 3 <= 84 else 2
        qs = q.width * s
        gfx.box(2, 18, qs + 8, qs + 8, (255, 255, 255))
        screen.blit(q, rect(6, 22, qs, qs))
        x = qs + 14
        y = 15
        for line in ("1. SCAN TO JOIN", "   WI-FI:", self.ssid[-9:], "2. OPEN", self.ip(), "3. ADD NETWORK"):
            gfx.text(line, x, y, (230, 230, 230), font.sins)
            y += 10
        gfx.text("PASS " + self.psk, 4, 94, (250, 200, 120), font.sins)
        msg = "SAVED! RESTARTING..." if self.saved else "B: CANCEL"
        gfx.text(msg, 4, 106, (150, 150, 160), font.sins)
