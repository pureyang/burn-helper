#!/usr/bin/env python3
"""A bridge started on a computer joined to another bridge leaves the badge alone: no beacon and
no USB link, so a badge plugged in there for development stays paired with its own bridge."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge")
for k in ("BURN_HELPER_BRIDGE_URL", "HEARTS_LEFT_BRIDGE_URL", "TUFTY_BRIDGE_URL"):
    os.environ.pop(k, None)     # a joined computer's Claude Code sets it for every command
sys.path.insert(0, BRIDGE_DIR)
import burn_helper_bridge as B  # noqa: E402


def home_with(env):
    home = tempfile.mkdtemp()
    os.makedirs(os.path.join(home, ".claude"))
    if env is not None:
        with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
            json.dump({"env": env, "hooks": {}}, f)
    return home


assert B.joined_to(home_with(None)) is None, "no settings.json: not joined"
assert B.joined_to(home_with({})) is None, "the bridge computer itself has no address in env"
assert B.joined_to(home_with({"FOO": "1"})) is None
mac = "http://100.64.1.2:8787"
assert B.joined_to(home_with({"BURN_HELPER_BRIDGE_URL": mac})) == mac
for local in ("http://127.0.0.1:8787", "http://localhost:8787/", "http://[::1]:8787"):
    assert B.joined_to(home_with({"BURN_HELPER_BRIDGE_URL": local})) is None, local
broken = home_with({})
with open(os.path.join(broken, ".claude", "settings.json"), "w") as f:
    f.write("{not json")
assert B.joined_to(broken) is None, "a broken settings.json doesn't stop the bridge"
os.environ["BURN_HELPER_BRIDGE_URL"] = mac
assert B.joined_to(home_with(None)) == mac, "or the address in the environment"
del os.environ["BURN_HELPER_BRIDGE_URL"]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start(home, *flags):
    """The bridge's first lines of log, run in its own home on a spare port."""
    env = dict(os.environ, BURN_HELPER_HOME=home, BURN_HELPER_STATE_DIR=os.path.join(home, "state"))
    p = subprocess.Popen([sys.executable, os.path.join(BRIDGE_DIR, "burn_helper_bridge.py"), "--bind", "127.0.0.1",
                          "--port", str(free_port())] + list(flags), env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines, t0 = [], time.time()
    try:
        while time.time() - t0 < 10:
            line = p.stdout.readline()
            if not line:
                break
            lines.append(line)
            if "bridge id" in line:
                lines.append(p.stdout.readline())   # the line right after it
                break
    finally:
        p.terminate()
        p.wait(5)
    return "".join(lines)


out = start(home_with({"BURN_HELPER_BRIDGE_URL": mac}))
assert "joined to the bridge at %s: no beacon or USB link here" % mac in out, out
# --here overrides it (--no-usb and --no-beacon too, so this test can't reach a real badge)
out = start(home_with({"BURN_HELPER_BRIDGE_URL": mac}), "--here", "--no-usb", "--no-beacon")
assert "bridge id" in out and "joined to" not in out, out
out = start(home_with({}), "--no-usb", "--no-beacon")
assert "bridge id" in out and "joined to" not in out, out
print("ok: joined computers leave the badge to their bridge")
