#!/usr/bin/env python3
"""The bridge's key: every request but the page and /health needs it, except from the bridge
computer itself; the installer's join lines carry it; the badge sends it with every poll.

Runs the real Handler on a spare local port with a stand-in bridge. Requests come from
127.0.0.1, so the test empties LOOPBACK to stand in for another computer.
"""
import http.client
import json
import os
import stat
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(0, os.path.join(ROOT, "badge", "apps", "burn_helper"))
for _name in ("BURN_HELPER_TOKEN", "HEARTS_LEFT_TOKEN", "TUFTY_TOKEN"):
    os.environ.pop(_name, None)
import portable  # noqa: E402
import burn_helper_bridge as B  # noqa: E402
import install  # noqa: E402

# ---------------------------------------------------------------- the key itself
state = tempfile.mkdtemp()
key = portable.bridge_key(state)
assert len(key) == portable.KEY_HEX and int(key, 16) >= 0, key
assert portable.bridge_key(state) == key, "made once, then kept"
if os.name != "nt":
    assert stat.S_IMODE(os.stat(os.path.join(state, "key")).st_mode) == 0o600, "readable by this user only"
assert portable.bridge_key(tempfile.mkdtemp(), make=False) is None
os.environ["BURN_HELPER_TOKEN"] = "set-by-hand"
assert portable.bridge_key(state) == "set-by-hand", "BURN_HELPER_TOKEN wins"
del os.environ["BURN_HELPER_TOKEN"]
print("PASS key: 128 random bits as hex, made once in the state folder (owner only), BURN_HELPER_TOKEN wins")


# ---------------------------------------------------------------- the bridge's HTTP side
class FakeBridge:
    themes = []
    pace = type("Pace", (), {"out": None})()

    def limit_mode(self):
        return "5h"

    def status(self):
        return {"level": 2, "waiting_names": ["secret-project"], "theme": "hero", "theme_seq": 1}

    def on_hook(self, d):
        pass

    def on_usage(self, d):
        return True

    def set_theme(self, t):
        self.themes.append(t)
        return True


B.BRIDGE = FakeBridge()
B.TOKEN = key
B.LOOPBACK = ()                  # these requests stand in for another computer's
srv = B.Server(("127.0.0.1", 0), B.Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def req(method, path, k=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"X-Burn-Helper-Token": k} if k is not None else {}
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    out = r.read()
    c.close()
    return r.status, out


assert req("GET", "/status")[0] == 403, "no key: nothing about your sessions"
assert req("GET", "/status", "x" * 32)[0] == 403, "wrong key"
assert req("GET", "/status", key[:-1])[0] == 403, "almost the key"
code, out = req("GET", "/status", key)
assert code == 200 and b"secret-project" in out, (code, out)
assert req("GET", "/status?k=" + key)[0] == 403, "a key in the address doesn't count (it ends up in logs)"
for path, body in (("/theme", {"theme": "hero"}), ("/hook", {"event": "Stop"}), ("/usage", {"rate_limits": {}})):
    assert req("POST", path, None, body)[0] == 403, path + " without the key"
    assert req("POST", path, key, body)[0] == 200, path + " with it"
assert FakeBridge.themes == ["hero"], "only the keyed /theme changed the theme"
code, out = req("GET", "/health")
assert code == 200 and json.loads(out)["ok"] and b"secret" not in out, "health stays open, says nothing"
code, out = req("GET", "/")
assert code == 200 and b"X-Burn-Helper-Token" in out and key.encode() not in out, "the page, never the key"
B.TOKEN = None
assert req("GET", "/status", "")[0] == 403, "no key saved: only this computer gets in"
B.LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
assert req("GET", "/status")[0] == 200, "this computer's own hooks and status line need no key"
B.TOKEN = key
print("PASS bridge: /status, /theme, /hook and /usage need the key from another computer; "
      "/ and /health don't and reveal nothing")

# ---------------------------------------------------------------- the installer
assert install.split_key("http://h:8787/#k=" + key) == ("http://h:8787", key)
assert install.split_key("http://h:8787") == ("http://h:8787", None)
lines = "\n".join(install.join_lines("192.168.1.20", "100.64.1.2", key=key))
assert "--join 'http://100.64.1.2:8787/#k=%s'" % key in lines, lines
assert "$env:BURN_HELPER_JOIN='http://100.64.1.2:8787/#k=%s'" % key in lines, lines
assert "phone panel" in lines and "Keep" in lines, lines
B.LOOPBACK = ()
url = "http://127.0.0.1:%d" % port
assert "answers." in install.check_bridge(url, key), install.check_bridge(url, key)
assert "needs its key" in install.check_bridge(url), install.check_bridge(url)
assert "turned this key down" in install.check_bridge(url, "nope"), install.check_bridge(url, "nope")
home = tempfile.mkdtemp()
import subprocess  # noqa: E402
r = subprocess.run([sys.executable, os.path.join(ROOT, "bridge", "install.py"), "--bridge",
                    "http://my-mac:8787/#k=" + key], env=dict(os.environ, BURN_HELPER_HOME=home),
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
with open(os.path.join(home, ".claude", "settings.json")) as f:
    env = json.load(f)["env"]
assert env == {"BURN_HELPER_BRIDGE_URL": "http://my-mac:8787", "BURN_HELPER_TOKEN": key}, env
srv.shutdown()
print("PASS install: join lines and the phone link carry the key after #k=; --bridge splits it into "
      "settings.json; the check says when the key is missing or wrong")

# ---------------------------------------------------------------- the badge
_t0 = time.monotonic()
for _name, _fn in (("ticks_ms", lambda: int((time.monotonic() - _t0) * 1000)),
                   ("ticks_diff", lambda a, b: a - b), ("ticks_add", lambda a, b: a + b)):
    if not hasattr(time, _name):
        setattr(time, _name, _fn)
import net  # noqa: E402

g = net.HttpGet("127.0.0.1", 9, "/status", key)
assert ("X-Burn-Helper-Token: %s\r\n" % key).encode() in g.req, g.req
assert b"Token" not in net.HttpGet("127.0.0.1", 9, "/status").req
g.buf = b"HTTP/1.0 403 Forbidden\r\n\r\n{}"
g.finish()
assert g.err == net.NEEDS_KEY and not g.ok
n = net.Net([("fake", "x")], key=key)
n.state, n.bridge, n.http_err = "up", ("192.168.4.49", 8787), net.NEEDS_KEY
assert n.label() == "PLUG INTO BRIDGE FOR KEY" and len(n.label()) <= 26
assert "plug the badge" in n.hint() and n.trouble() == "key", (n.hint(), n.trouble())
print("PASS badge: every poll carries the key; a 403 says to plug the badge into the bridge once")
