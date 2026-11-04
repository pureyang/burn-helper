#!/usr/bin/env python3
"""The bridge's key and sealing: from anywhere but the bridge computer, every message both ways is
encrypted and signed with the key (seal.py), so someone watching the network sees neither what you
work on nor the key, and can't change or replay what they saw.

Runs the real Handler on a spare local port with a stand-in bridge. Requests come from
127.0.0.1, so the test empties LOOPBACK to stand in for another computer. The phone panel's
JavaScript copy of seal.py is checked against the Python one with node, when node is installed.
"""
import hashlib
import hmac
import http.client
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRIDGE_DIR = os.path.join(ROOT, "bridge")
BADGE_DIR = os.path.join(ROOT, "badge", "apps", "burn_helper")
sys.path.insert(0, BRIDGE_DIR)
for _name in ("BURN_HELPER_TOKEN", "HEARTS_LEFT_TOKEN", "TUFTY_TOKEN", "BURN_HELPER_BRIDGE_URL"):
    os.environ.pop(_name, None)
import portable  # noqa: E402
import seal  # noqa: E402
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

# ---------------------------------------------------------------- seal.py
with open(os.path.join(BRIDGE_DIR, "seal.py"), "rb") as a, open(os.path.join(BADGE_DIR, "seal.py"), "rb") as b:
    assert a.read() == b.read(), "bridge/seal.py and the badge's seal.py must be the same file"
for k, m in ((b"k" * 32, b""), (b"short", b"x" * 1000), (bytes(range(64)), b"abc")):
    assert seal.hmac256(k, m) == hmac.new(k, m, hashlib.sha256).digest(), "HMAC as in RFC 2104"
msg = json.dumps({"waiting": ["secret-project"], "n": list(range(300))}).encode()
box = seal.seal(key, msg)
assert seal.unseal(key, box) == msg and seal.is_sealed(box)
assert b"secret" not in box and key.encode() not in box, "nothing readable on the wire"
assert seal.seal(key, msg) != box, "a fresh nonce every time"
assert seal.unseal("0" * 32, box) is None, "another key opens nothing"
for i in (5, len(box) // 2, len(box) - 1):
    bad = bytearray(box)
    bad[i] ^= 1
    assert seal.unseal(key, bytes(bad)) is None, "any changed byte is caught (at %d)" % i
assert seal.unseal(key, box[:-1]) is None and seal.unseal(key, b"{}") is None and seal.unseal(None, box) is None
assert seal.reply(key, b'{"ok": true}') == {"ok": True} and seal.reply(key, seal.seal(key, b'{"a": 1}')) == {"a": 1}
assert seal.reply("0" * 32, seal.seal(key, b'{"a": 1}')) is None
print("PASS seal: encrypt-then-MAC with SHA-256 only; tampering, truncation and other keys are caught; "
      "the bridge's and the badge's copies match")

# ---------------------------------------------------------------- the phone panel's JavaScript copy
node = shutil.which("node")
if node:
    js = B.PAGE[B.PAGE.index("// SEAL-JS"):B.PAGE.index("// /SEAL-JS")]
    nonce = bytes(range(16))
    lengths = [0, 1, 55, 56, 63, 64, 65, 119, 1000]
    script = js + """
const hex=b=>Array.from(b,x=>x.toString(16).padStart(2,"0")).join("");
const unhex=h=>new Uint8Array(h.match(/../g)||[]).map((_,i,a)=>a[i]);
const fromHex=h=>new Uint8Array((h.match(/../g)||[]).map(x=>parseInt(x,16)));
const a=JSON.parse(process.argv[1]);
const sums=a.lengths.map(n=>hex(sha256(new Uint8Array(n).map((_,i)=>i*7&255))));
const sealed=hex(seal(a.key,TE.encode(a.msg),fromHex(a.nonce)));
const opened=new TextDecoder().decode(unseal(a.key,fromHex(a.box)));
const wrong=unseal("0".repeat(32),fromHex(a.box));
console.log(JSON.stringify({sums,sealed,opened,wrong}));
"""
    arg = json.dumps({"key": key, "msg": "hello panel", "nonce": nonce.hex(), "box": box.hex(),
                      "lengths": lengths})
    out = subprocess.run([node, "-e", script, arg], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["sums"] == [hashlib.sha256(bytes(i * 7 & 255 for i in range(n))).hexdigest() for n in lengths], got
    assert got["sealed"] == seal.seal(key, b"hello panel", nonce).hex(), "the panel seals as the bridge does"
    assert got["opened"] == msg.decode() and got["wrong"] is None, "and opens what the bridge seals"
    print("PASS phone panel: its JavaScript SHA-256 and seal match Python's byte for byte")
else:
    print("SKIP phone panel JavaScript (no node here)")


# ---------------------------------------------------------------- the bridge's HTTP side
class FakeBridge:
    themes = []
    hooks = []
    pace = type("Pace", (), {"out": None})()

    def status(self):
        return {"level": 2, "waiting_names": ["secret-project"], "theme": "hero", "theme_seq": 1}

    def limit_mode(self):
        return "5h"

    def on_hook(self, d):
        self.hooks.append(d)

    def on_usage(self, d):
        return True

    def answer(self, d):
        return {"pace": None, "mode": "5h"}

    def set_theme(self, t):
        self.themes.append(t)
        return True


B.BRIDGE = FakeBridge()
B.TOKEN = key
B.LOOPBACK = ()                  # these requests stand in for another computer's
srv = B.Server(("127.0.0.1", 0), B.Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def req(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = dict(headers or {})
    if isinstance(body, dict):
        body = json.dumps(body).encode()
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    out = r.read()
    c.close()
    return r.status, out


code, out = req("GET", "/status")
assert code == 200 and seal.is_sealed(out) and b"secret" not in out, "what crosses the network is sealed"
assert json.loads(seal.unseal(key, out))["waiting_names"] == ["secret-project"], "the key opens it"
assert req("GET", "/status", headers={"X-Burn-Helper-Token": key})[1] != out, "sealed afresh each time"
for path, d in (("/theme", {"theme": "hero"}), ("/hook", {"event": "Stop", "name": "secret"}),
                ("/usage", {"rate_limits": {}})):
    assert req("POST", path, d)[0] == 403, path + ": plain from another computer is turned down"
    assert req("POST", path, d, {"X-Burn-Helper-Token": key})[0] == 403, path + ": a key in a header no longer counts"
    box = seal.envelope(key, d)
    code, out = req("POST", path, box)
    assert code == 200 and seal.reply(key, out).get("ok"), (path, code, out)
    assert seal.is_sealed(out), path + ": the answer goes back sealed"
    assert req("POST", path, box)[0] == 403, path + ": the same message again is a replay"
assert FakeBridge.themes == ["hero"] and len(FakeBridge.hooks) == 1, "only the sealed, first-time posts counted"
assert req("POST", "/hook", seal.envelope("0" * 32, {"event": "Stop"}))[0] == 403, "sealed with another key"
old = seal.seal(key, json.dumps({"t": int(time.time()) - B.REPLAY_S - 5, "d": {"event": "Stop"}}).encode())
assert req("POST", "/hook", old)[0] == 403, "too old"
code, out = req("GET", "/health")
assert code == 200 and json.loads(out)["ok"] and b"secret" not in out, "health stays open, says nothing"
code, out = req("GET", "/")
assert code == 200 and b"// SEAL-JS" in out and key.encode() not in out, "the page, never the key"
B.TOKEN = None
assert req("GET", "/status")[0] == 403, "no key saved: only this computer gets in"
B.LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
code, out = req("GET", "/status")
assert code == 200 and json.loads(out)["level"] == 2, "this computer's own hooks and status line: plain, no key"
assert req("POST", "/hook", {"event": "Stop"})[0] == 200
B.TOKEN = key
print("PASS bridge: everything to and from another computer is sealed; plain, header-keyed, replayed, "
      "stale or wrongly keyed posts are turned down; / and /health reveal nothing")

# ---------------------------------------------------------------- the hook and the status line, from another computer
B.LOOPBACK = ()
url = "http://127.0.0.1:%d" % port
env = dict(os.environ, BURN_HELPER_BRIDGE_URL=url, BURN_HELPER_TOKEN=key)
n = len(FakeBridge.hooks)
r = subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "cc_hook.py")], env=env, timeout=20,
                   input=json.dumps({"session_id": "s1", "hook_event_name": "Stop"}), text=True)
assert len(FakeBridge.hooks) == n + 1 and FakeBridge.hooks[-1]["session_id"] == "s1", FakeBridge.hooks
os.environ.update(BURN_HELPER_BRIDGE_URL=url, BURN_HELPER_TOKEN=key)
import cc_statusline as SL  # noqa: E402
got = SL.report({"rate_limits": {"seven_day": {"used_percentage": 10, "resets_at": time.time() + 9e4}}})
assert got and got.get("mode") == "5h", got
del os.environ["BURN_HELPER_BRIDGE_URL"], os.environ["BURN_HELPER_TOKEN"]
print("PASS clients: a joined computer's hook and status line seal what they send and open the answer")

# ---------------------------------------------------------------- the installer
assert install.split_key("http://h:8787/#k=" + key) == ("http://h:8787", key)
assert install.split_key("http://h:8787") == ("http://h:8787", None)
lines = "\n".join(install.join_lines("192.168.1.20", "100.64.1.2", key=key))
assert "--join 'http://100.64.1.2:8787/#k=%s'" % key in lines, lines
assert "$env:BURN_HELPER_JOIN='http://100.64.1.2:8787/#k=%s'" % key in lines, lines
assert "phone panel" in lines and "Keep" in lines, lines
assert "answers." in install.check_bridge(url, key), install.check_bridge(url, key)
assert "needs its key" in install.check_bridge(url), install.check_bridge(url)
assert "isn't the bridge's" in install.check_bridge(url, "0" * 32), install.check_bridge(url, "0" * 32)
home = tempfile.mkdtemp()
r = subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "install.py"), "--bridge",
                    "http://my-mac:8787/#k=" + key], env=dict(os.environ, BURN_HELPER_HOME=home),
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
with open(os.path.join(home, ".claude", "settings.json")) as f:
    senv = json.load(f)["env"]
assert senv == {"BURN_HELPER_BRIDGE_URL": "http://my-mac:8787", "BURN_HELPER_TOKEN": key}, senv
srv.shutdown()
print("PASS install: join lines and the phone link carry the key after #k=; --bridge splits it into "
      "settings.json; the check says when the key is missing or wrong")

# ---------------------------------------------------------------- the badge
sys.path.insert(0, BADGE_DIR)
_t0 = time.monotonic()
for _name, _fn in (("ticks_ms", lambda: int((time.monotonic() - _t0) * 1000)),
                   ("ticks_diff", lambda a, b: a - b), ("ticks_add", lambda a, b: a + b)):
    if not hasattr(time, _name):
        setattr(time, _name, _fn)
import net  # noqa: E402

g = net.HttpGet("127.0.0.1", 9, "/status", key)
assert key.encode() not in g.req and b"Token" not in g.req, "the badge never sends the key"
status = json.dumps({"level": 3, "waiting_names": ["secret-project"]}).encode()
g.buf = b"HTTP/1.0 200 OK\r\n\r\n" + seal.seal(key, status)
g.finish()
assert g.ok and g.body["level"] == 3, (g.err, g.body)
g = net.HttpGet("127.0.0.1", 9, "/status")
g.buf = b"HTTP/1.0 200 OK\r\n\r\n" + seal.seal(key, status)
g.finish()
assert not g.ok and g.err == net.NEEDS_KEY, "no key yet: it says so"
g = net.HttpGet("127.0.0.1", 9, "/status", key)
g.buf = b'HTTP/1.0 200 OK\r\n\r\n{"level": 1}'
g.finish()
assert g.ok and g.body["level"] == 1, "an older bridge's plain answer still works"
n = net.Net([("fake", "x")], key=key)
n.state, n.bridge, n.http_err = "up", ("192.168.4.49", 8787), net.NEEDS_KEY
assert n.label() == "PLUG INTO BRIDGE FOR KEY" and len(n.label()) <= 26
assert "plug the badge" in n.hint() and n.trouble() == "key", (n.hint(), n.trouble())
print("PASS badge: it opens the bridge's sealed answers with the key from USB, never sends the key, "
      "and says to plug it in when it can't")
