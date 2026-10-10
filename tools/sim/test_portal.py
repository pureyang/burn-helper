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
p.reboot_at = None
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
assert p.saved and p.reboot_at is not None

s = FakeSock(b"GET / HTTP/1.1\r\n\r\n")
p.handle(s)
assert b"My Phone's Hotspot" in s.out and b"last try: never accepted the badge" in s.out
assert b"password 9 characters" in s.out, "trailing space should be trimmed on save"

s = FakeSock(b"POST /forget HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
p.handle(s)
assert config.load_portal()["networks"] == []
print("PASS portal form parsing, trimming, scan list, save, list, forget")
