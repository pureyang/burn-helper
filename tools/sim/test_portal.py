#!/usr/bin/env python3
"""Exercise the badge's phone-setup portal request handling on the Mac (no radio)."""
import os, sys, tempfile, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_add = lambda a, b: a + b
time.ticks_diff = lambda a, b: a - b
sys.modules["machine"] = types.SimpleNamespace(unique_id=lambda: b"\x01\x02\x03\x04", reset=lambda: None)
sys.modules["network"] = types.SimpleNamespace()
import config  # noqa: E402
import portal  # noqa: E402

tmp = tempfile.mkdtemp()
config.NET_FILE = os.path.join(tmp, "net.json")


class FakeSock:
    def __init__(self, req):
        self.req = req
        self.out = b""

    def recv(self, n):
        d, self.req = self.req[:n], self.req[n:]
        return d

    def send(self, d):
        self.out += d
        return len(d)


p = portal.Portal.__new__(portal.Portal)
p.saved = False
p.phase = "serve"
p.new_ssid = p.new_psk = ""
p.srv = types.SimpleNamespace(close=lambda: None)
p.ap = types.SimpleNamespace(active=lambda v: None)
p.bssids = {}
p.notice = ""
p.results = {"My Phone's Hotspot": "never accepted the badge"}
p.scan = [("home-wifi", (-56, 6)), ('Cafe "Guest"', (-80, 11))]
p.mac = "28:cd:c1:00:00:00"

s = FakeSock(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
p.handle(s)
assert b"Hearts Left setup" in s.out and b"none" in s.out, s.out[:200]
assert b"data-n=\"home-wifi\"" in s.out and b"Cafe &quot;Guest&quot;" in s.out and b"28:cd:c1" in s.out

body = b"ssid=My+Phone%27s+Hotspot&psk=p%40ss+w%26rd+&bridge=192.168.1.20%3A8787"
s = FakeSock(b"POST /save HTTP/1.1\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
p.handle(s)
d = config.load_portal()
assert d["networks"][0] == ["My Phone's Hotspot", "p@ss w&rd"], d
assert config.bridge() == ("192.168.1.20", 8787)
assert config.networks()[0] == ("My Phone's Hotspot", "p@ss w&rd", "phone")
assert p.saved and p.phase == "wait" and p.new_ssid == "My Phone's Hotspot" and p.new_psk == "p@ss w&rd"

s = FakeSock(b"GET / HTTP/1.1\r\n\r\n")
p.handle(s)
assert b"My Phone's Hotspot" in s.out and b"last try: never accepted the badge" in s.out
assert b"password 9 characters" in s.out, "trailing space should be trimmed on save"

s = FakeSock(b"POST /forget HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
p.handle(s)
assert config.load_portal()["networks"] == []
print("PASS portal form parsing, trimming, scan list, save, list, forget")


# --- after "Save": the badge leaves hotspot mode, joins, shows the result, then hands back
class FakeSta:
    def __init__(self, behaviour):
        self.behaviour, self.connected, self.calls = behaviour, False, []

    def active(self, v): pass
    def connect(self, ssid, psk, **kw): self.calls.append((ssid, psk, kw))
    def isconnected(self): return self.connected
    def status(self): return {"ok": 3, "stuck": 1, "gone": -2}[self.behaviour] if not self.connected else 3
    def ifconfig(self): return ("192.168.4.48", "255.255.252.0", "192.168.4.1", "8.8.8.8")
    def disconnect(self): self.connected = False


def run_join(behaviour, bssids=None):
    q = portal.Portal.__new__(portal.Portal)
    q.phase, q.saved, q.outcome, q.lines, q.bssids = "wait", True, None, [], bssids or {}
    q.new_ssid, q.new_psk, q.due, q.j0 = "home-wifi", "secret-pw", 0, 0
    q.srv = types.SimpleNamespace(close=lambda: None)
    q.ap = types.SimpleNamespace(active=lambda v: None)
    sta = FakeSta(behaviour)
    portal.network.WLAN = lambda mode: sta
    portal.network.STA_IF = 0
    now = [1000]
    time.ticks_ms = lambda: now[0]
    q.tick()                                   # wait -> joining
    assert q.phase == "joining" and sta.calls, q.phase
    for _ in range(200):
        now[0] += 100
        if behaviour == "ok" and now[0] > 2500:
            sta.connected = True
        q.tick()
        if q.phase != "joining":
            break
    return q, sta, now


q, sta, now = run_join("ok", {"home-wifi": b"\x02\x00\x00\x00\x00\x01"})
assert q.outcome == "ok" and q.phase == "result" and "SUCCESS!" in q.lines and "IP 192.168.4.48" in q.lines, (q.phase, q.lines)
assert sta.calls[0][2].get("bssid") == b"\x02\x00\x00\x00\x00\x01", "should pin to the strongest access point"
assert not any("secret-pw" in l for l in q.lines), "password must never be shown"
now[0] += 4000; q.tick(); assert q.phase == "done", "should hand back to the main screen by itself"

q, sta, now = run_join("stuck")
assert q.outcome == "fail" and "WRONG PASSWORD?" in q.lines, q.lines
now[0] += 5000; q.tick(); assert q.phase == "done"

q, sta, now = run_join("gone")
assert q.outcome == "fail" and "NETWORK NOT SEEN" in q.lines, q.lines
print("PASS join after save: success, wrong password, network not seen; pinned BSSID; auto hand-back")


# --- hotspot name: the full name when it fits beside the QR code, else a shorter real one
import builtins


class FakeAp:
    def __init__(self): self.cfg = {}
    def config(self, **kw): self.cfg.update(kw)
    def active(self, v): pass
    def ifconfig(self): return ("192.168.4.1",)


class FakeSrv:
    def setsockopt(self, *a): pass
    def bind(self, *a): pass
    def listen(self, *a): pass
    def setblocking(self, *a): pass


class FakeSock2:
    SOL_SOCKET = SO_REUSEADDR = 0
    def socket(self): return FakeSrv()
    def __call__(self): return FakeSrv()


def make_portal(qr_modules):
    ap = FakeAp()
    fake_sta = types.SimpleNamespace(active=lambda v: None, scan=lambda: [], config=lambda k: b"\x28\xcd\xc1\x00\x00\x02")
    portal.network.WLAN = lambda mode: ap if mode == 1 else fake_sta
    portal.network.AP_IF, portal.network.STA_IF = 1, 0
    portal.socket = types.SimpleNamespace(socket=lambda: FakeSrv(), SOL_SOCKET=0, SO_REUSEADDR=0)
    sys.modules["machine"].unique_id = lambda: b"\x01\x02\x03\x04\xab\x12"
    portal.machine = sys.modules["machine"]
    builtins.screen.qr = lambda text, *a: types.SimpleNamespace(width=qr_modules, height=qr_modules, text=text)
    time.ticks_ms = lambda: 0
    return portal.Portal(), ap


config.save_portal({"networks": [["home", "pw"]], "bridge": ""})   # a saved network: secured hotspot
pt, ap = make_portal(29)
assert pt.ssid == "HeartsLeft-AB12", pt.ssid          # fits: keep the longer name
assert ap.cfg["ssid"] == pt.ssid and "S:HeartsLeft-AB12;" in pt.qr.text
pt, ap = make_portal(33)
assert pt.ssid == "Hearts-AB12", pt.ssid               # too wide: shorter, and it is the real name
assert ap.cfg["ssid"] == "Hearts-AB12" and "S:Hearts-AB12;" in pt.qr.text
assert len(pt.psk) == 8 and pt.psk.isdigit() and "P:" + pt.psk in pt.qr.text, pt.psk   # WPA2 minimum, digits only
print("PASS hotspot name: full when it fits, shorter real name otherwise; QR matches")

# --- nothing saved yet: open hotspot, no password anywhere
config.save_portal({"networks": [], "bridge": ""})
pt, ap = make_portal(29)
assert pt.open and pt.psk == "" and "key" not in ap.cfg and "password" not in ap.cfg, ap.cfg
assert pt.qr.text == "WIFI:T:nopass;S:HeartsLeft-AB12;;", pt.qr.text
shown = []
portal.gfx.text = lambda t, *a, **k: shown.append(t)
builtins.screen.blit = lambda *a, **k: None   # only the labels are checked here
pt.draw(0)
assert "NO WIFI PASS NEEDED" in shown and not any(t.startswith("WIFI PASS") for t in shown), shown
config.save_portal({"networks": [["home", "pw"]], "bridge": ""})
pt, ap = make_portal(29)
shown.clear(); pt.draw(0)
assert "WIFI PASS " + pt.psk in shown and ap.cfg["key"] == pt.psk, shown
print("PASS open hotspot with no saved Wi-Fi; secured and labelled WIFI PASS once one is saved")
