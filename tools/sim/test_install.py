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
