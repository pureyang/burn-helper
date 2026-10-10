# Phone setup portal: the badge becomes a Wi-Fi hotspot with a tiny web form.
#
# Join the hotspot from your phone (scan the QR code on screen), open
# http://192.168.4.1 and add a Wi-Fi network (home, office or your phone's own
# hotspot) and optionally a fixed bridge address. Saved to
# /state/hearts_left_net.json, then the badge restarts and uses it.

import json
import socket
import select
import time
import machine
import network
import config
import gfx

PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Hearts Left setup</title><style>body{font-family:-apple-system,system-ui,sans-serif;max-width:440px;margin:24px auto;padding:0 16px;background:#111;color:#eee}
input,button{font-size:18px;width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;border-radius:8px;border:1px solid #555;background:#222;color:#eee}
button{background:#d97757;border:0;color:#111;font-weight:600}small,.dim{color:#999}li{margin:6px 0}
.net{display:flex;justify-content:space-between;padding:10px;margin:4px 0;border-radius:8px;background:#1d1d1d;cursor:pointer}
.bad{color:#ff8a80}.ok{color:#8be38b}label.cb{display:flex;gap:8px;align-items:center;margin:-8px 0 14px}label.cb input{width:auto;margin:0}</style></head><body>
<h2>Hearts Left setup</h2>
<p class=dim>The badge only does <b>2.4 GHz</b> Wi-Fi with a WPA2 password. These are the networks it can hear right now; tap one to use it.</p>
%SCAN%
<form method=post action=/save><label>Wi-Fi name (SSID)<input id=ssid name=ssid required autocapitalize=none autocorrect=off spellcheck=false></label>
<label>Password<input id=psk name=psk type=password autocapitalize=none autocorrect=off spellcheck=false></label>
<label class=cb><input type=checkbox onclick="document.getElementById('psk').type=this.checked?'text':'password'">Show password (check it is exactly right)</label>
<label>Bridge address <small>(optional, e.g. 192.168.1.20:8787; blank = auto-discover)</small><input name=bridge value="%BRIDGE%" autocapitalize=none autocorrect=off spellcheck=false></label>
<button>Save and restart badge</button></form><h3>Saved networks</h3><ul>%LIST%</ul>
<form method=post action=/forget><button style="background:#444;color:#eee">Forget saved networks</button></form>
<p class=dim>Badge MAC address: %MAC% (add it to your router's allow list if it filters devices).</p></body></html>"""

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
    def __init__(self, results=None):
        self.results = results or {}
        self.scan = []
        self.mac = "?"
        try:
            import binascii
            sta = network.WLAN(network.STA_IF)
            sta.active(True)
            self.mac = binascii.hexlify(sta.config("mac"), ":").decode()
            best = {}
            for r in sta.scan():
                name = r[0].decode()
                if name and (name not in best or r[3] > best[name][0]):
                    best[name] = (r[3], r[2])
            self.scan = sorted(best.items(), key=lambda kv: -kv[1][0])[:12]
        except Exception:  # noqa: BLE001
            pass
        uid = machine.unique_id()
        self.ssid = "HeartsLeft-%02X%02X" % (uid[-2], uid[-1])
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
                # phone keyboards add trailing spaces; WPA passphrases never need them
                d["networks"] = [[ssid, f.get("psk", "").strip()]] + nets[:4]
            d["bridge"] = f.get("bridge", "").strip()
            config.save_portal(d)
            self.saved = True
            self.reboot_at = time.ticks_add(time.ticks_ms(), 2500)
            return self.send(cl, DONE)
        if method == "POST" and path == "/forget":
            config.save_portal({"networks": [], "bridge": d.get("bridge", "")})
            d = config.load_portal()
        items = ""
        for n in d.get("networks", []):
            r = self.results.get(n[0], "")
            cls = "ok" if r == "connected" else "bad"
            items += "<li>%s <small>(password %d characters)</small>%s</li>" % (
                _esc(n[0]), len(n[1]), " <span class=%s>last try: %s</span>" % (cls, _esc(r)) if r else "")
        items = items or "<li><small>none</small></li>"
        scan = ""
        for name, (rssi, ch) in self.scan:
            bars = "&#9679;" * (4 if rssi > -60 else 3 if rssi > -70 else 2 if rssi > -80 else 1)
            scan += ("<div class=net onclick=\"document.getElementById('ssid').value=this.dataset.n;"
                     "document.getElementById('psk').focus()\" data-n=\"%s\"><span>%s</span>"
                     "<small>%s ch%d</small></div>") % (_esc(name), _esc(name), bars, ch)
        scan = scan or "<p class=dim>(scan found nothing)</p>"
        page = PAGE.replace("%LIST%", items).replace("%BRIDGE%", _esc(d.get("bridge", "")))
        self.send(cl, page.replace("%SCAN%", scan).replace("%MAC%", _esc(self.mac)))

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
