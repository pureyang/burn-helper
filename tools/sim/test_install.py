#!/usr/bin/env python3
"""bridge/install.py: the --bridge mode for other computers, and Windows command lines."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge")
sys.path.insert(0, BRIDGE)
import install  # noqa: E402

home = tempfile.mkdtemp()
settings_path = os.path.join(home, ".claude", "settings.json")
os.makedirs(os.path.dirname(settings_path))
mine = {"env": {"FOO": "1"}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say done"}]}]}}
with open(settings_path, "w") as f:
    json.dump(mine, f)


def run(*args):
    r = subprocess.run([sys.executable, os.path.join(BRIDGE, "install.py")] + list(args),
                       env=dict(os.environ, BURN_HELPER_HOME=home), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    with open(settings_path) as f:
        return json.load(f), r.stdout


s, out = run("--bridge", "my-mac")
assert s["env"] == {"FOO": "1", "BURN_HELPER_BRIDGE_URL": "http://my-mac:8787"}, s["env"]
assert all(e in s["hooks"] for e in install.EVENTS) and "cc_statusline.py" in s["statusLine"]["command"]
assert any(h["command"] == "say done" for g in s["hooks"]["Stop"] for h in g["hooks"]), "keeps the user's own hooks"
assert "launchctl" not in out and "LaunchAgents" not in out, "no login item when the bridge runs elsewhere"
s2, out = run("--bridge", "http://my-mac:8787")
assert s2 == s and "already up to date" in out, "running it again changes nothing"
s, _ = run("--bridge", "http://my-mac:8787", "--token", "abc")
assert s["env"]["BURN_HELPER_TOKEN"] == "abc"
s, _ = run("--uninstall", "--no-launchd")
assert s == mine, "uninstall leaves exactly what was there before: %s" % s

win = install.command("cc_hook.py", py="C:\\Program Files\\Python312\\python.exe",
                      here="C:\\Users\\me\\burn-helper\\bridge", windows=True)
assert win == '"C:/Program Files/Python312/python.exe" "C:/Users/me/burn-helper/bridge/cc_hook.py"', win
assert install.is_ours(win) and install.is_ours('"C:\\Users\\me\\burn-helper\\bridge\\cc_statusline.py"')
assert not install.is_ours("say done")
print("PASS install --bridge: env + hooks + status line, idempotent, token, clean uninstall; "
      "quoted forward-slash commands on Windows")

# ---------------------------------------------------------------- the bridge on a Windows PC
py = "C:\\Program Files\\Python312\\python.exe"
bridge = "C:\\Users\\me\\burn-helper\\bridge\\burn_helper_bridge.py"
log = "C:\\Users\\me\\AppData\\Local\\burn-helper\\burn-helper.log"
cmd = install.login_command(py, bridge, log, exists=lambda p: True)
assert cmd == ('"C:\\Program Files\\Python312\\pythonw.exe" "C:\\Users\\me\\burn-helper\\bridge\\burn_helper_bridge.py" '
               '--log "C:\\Users\\me\\AppData\\Local\\burn-helper\\burn-helper.log"'), cmd
assert install.login_command(py, bridge, log, exists=lambda p: False).startswith('"%s" ' % py), "no pythonw: python.exe"

import relay  # noqa: E402
ts = "C:\\Program Files\\Tailscale\\tailscale.exe"
assert relay.find_tailscale(which=lambda n: None, exists=lambda p: p == ts, windows=True,
                            program_files="C:\\Program Files") == ts
assert relay.find_tailscale(which=lambda n: "C:\\bin\\tailscale.exe", exists=lambda p: False,
                            windows=True) == "C:\\bin\\tailscale.exe", "on PATH wins"
assert relay.find_tailscale(which=lambda n: None, exists=lambda p: False, windows=True) is None
assert relay.find_tailscale(which=lambda n: None, exists=lambda p: p == relay.TS_APP, windows=False) == relay.TS_APP

# a whole install, rehearsed as Windows (registry and processes are skipped under BURN_HELPER_HOME)
whome = tempfile.mkdtemp()
wsettings = os.path.join(whome, ".claude", "settings.json")
os.makedirs(os.path.dirname(wsettings))
with open(wsettings, "w") as f:
    json.dump(mine, f)


def run_win(*args):
    r = subprocess.run([sys.executable, os.path.join(BRIDGE, "install.py")] + list(args),
                       env=dict(os.environ, BURN_HELPER_HOME=whome, BURN_HELPER_TEST_OS="windows"),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    with open(wsettings) as f:
        return json.load(f), r.stdout


wlog = os.path.join(whome, "AppData", "Local", "burn-helper", "burn-helper.log")
s, out = run_win("--dry-run")
assert "Would add the login item HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Burn Helper bridge" in out, out
assert '--log "%s"' % wlog in out and "launchctl" not in out and "plist" not in out, out
assert s == mine, "a dry run changes nothing"
s, out = run_win()
hook = s["hooks"]["Stop"][-1]["hooks"][0]["command"]
assert hook.startswith('"') and "/bridge/cc_hook.py\"" in hook, hook
assert "skipping the registry: Run value 'Burn Helper bridge'" in out and "Bridge started. Logs: %s" % wlog in out, out
assert "Windows Firewall" in out and "launchctl" not in out, out
s, out = run_win("--uninstall")
assert s == mine and "delete Run value" in out, (s, out)
print("PASS bridge on Windows: login item runs pythonw with --log, Tailscale found in Program Files, "
      "install / dry run / uninstall rehearsed")

# ---------------------------------------------------------------- joining a bridge
lines = "\n".join(install.join_lines("192.168.1.20", "100.64.1.2"))
assert "bash -s -- --join http://100.64.1.2:8787" in lines, lines
assert "$env:BURN_HELPER_JOIN='http://100.64.1.2:8787'; irm " in lines and "install.ps1 | iex" in lines
assert "http://192.168.1.20:8787" in lines, "names the local address too"
lines = "\n".join(install.join_lines("192.168.1.20", None, windows=True))
assert "--join http://192.168.1.20:8787" in lines and "can change" in lines and "py " in lines, lines

import http.server  # noqa: E402
import threading  # noqa: E402


class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok": true}' if self.path == "/health" else b"{}"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Health)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d" % srv.server_address[1]
assert "answers" in install.check_bridge(url), install.check_bridge(url)
srv.shutdown()
assert "Can't reach" in install.check_bridge("http://127.0.0.1:9"), "nothing listening"
print("PASS join: the lines to run on other computers, Tailscale address first; the bridge check")

# ---------------------------------------------------------------- finding a bridge already on the network
import socket as _socket  # noqa: E402
import time  # noqa: E402
import tempfile as _tempfile  # noqa: E402


class Status(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"join": "http://100.64.1.2:8787", "bridge": "their-id"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Status)
threading.Thread(target=srv.serve_forever, daemon=True).start()
TEST_PORT = 47899                              # not the real beacon port: real bridges stay out of it


def beacon(bid):
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    for _ in range(6):
        s.sendto(("TUFTYBRIDGE 1 %d %s" % (srv.server_address[1], bid)).encode(), ("127.0.0.1", TEST_PORT))
        time.sleep(0.25)
    s.close()


install.STATE_DIR = _tempfile.mkdtemp()
threading.Thread(target=beacon, args=("their-id",), daemon=True).start()
assert install.find_bridge(wait=2.0, port=TEST_PORT) == "http://100.64.1.2:8787", "joins at the address it advertises"
with open(os.path.join(install.STATE_DIR, "bridge_id"), "w") as f:
    f.write("their-id")
threading.Thread(target=beacon, args=("their-id",), daemon=True).start()
assert install.find_bridge(wait=1.5, port=TEST_PORT) is None, "this computer's own bridge doesn't count"
srv.shutdown()
print("PASS find bridge: another computer's bridge is found by its beacon and joined at its advertised "
      "address; this computer's own bridge is not")

# joining removes this computer's own bridge, if it had one (on a Mac: its login item)
agents = os.path.join(home, "Library", "LaunchAgents")
os.makedirs(agents, exist_ok=True)
plist = os.path.join(agents, "com.burnhelper.bridge.plist")
with open(plist, "w") as f:
    f.write("<plist/>")
_, out = run("--bridge", "http://my-mac:8787")
assert not os.path.exists(plist) and "running a bridge of its own" in out, out
print("PASS join removes a bridge this computer was running, so there is only one")

# the optional history: --tracking on / off writes the switch the bridge reads, a join doesn't
import tracking as _tracking  # noqa: E402
_tr_state = _tempfile.mkdtemp()
install.STATE_DIR = _tr_state
_, out = run("--tracking", "on", "--dry-run")
assert not _tracking.is_enabled(_tr_state) and "Would turn the history on" in out, out
for flag, want in (("on", True), ("off", False)):
    env = dict(os.environ, BURN_HELPER_HOME=home, BURN_HELPER_STATE_DIR=_tr_state)
    r = subprocess.run([sys.executable, os.path.join(BRIDGE, "install.py"), "--tracking", flag],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0 and _tracking.is_enabled(_tr_state) == want, (flag, r.stdout, r.stderr)
    assert ("History on" in r.stdout) == want, r.stdout
env = dict(os.environ, BURN_HELPER_HOME=home, BURN_HELPER_STATE_DIR=_tr_state)
r = subprocess.run([sys.executable, os.path.join(BRIDGE, "install.py"), "--bridge", "my-mac", "--tracking", "on"],
                   env=env, capture_output=True, text=True)
assert not _tracking.is_enabled(_tr_state) and "kept by the bridge" in r.stdout, r.stdout
print("PASS install --tracking: on and off write the switch, a dry run changes nothing, joining leaves it alone")

# the weekly pace's opt-in room-left note: --room-left on / off, the same way
import pace as _pace  # noqa: E402
_, out = run("--room-left", "on", "--dry-run")
assert not _pace.room_enabled(_tr_state) and "Would turn the room-left note on" in out, out
for flag, want in (("on", True), ("off", False)):
    r = subprocess.run([sys.executable, os.path.join(BRIDGE, "install.py"), "--room-left", flag],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0 and _pace.room_enabled(_tr_state) == want, (flag, r.stdout, r.stderr)
r = subprocess.run([sys.executable, os.path.join(BRIDGE, "install.py"), "--bridge", "my-mac", "--room-left", "on"],
                   env=env, capture_output=True, text=True)
assert not _pace.room_enabled(_tr_state) and "the bridge's to say" in r.stdout, r.stdout
print("PASS install --room-left: opt-in, on the bridge computer only")
