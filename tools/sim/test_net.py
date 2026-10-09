#!/usr/bin/env python3
"""Run the badge's net.py on the Mac against a live bridge: beacon discovery + HTTP poll.

    python3 tools/sim/test_net.py        (bridge must be running on this Mac)
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "badge", "apps", "claude_buddy"))
_t0 = time.monotonic()
time.ticks_ms = lambda: int((time.monotonic() - _t0) * 1000)
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b
import net  # noqa: E402

n = net.Net([("fake", "x")])
n.state = "up"          # pretend Wi-Fi is up; exercise discovery + polling only
end = time.time() + 8
while time.time() < end and n.seq < 2:
    n._discover()
    n._poll()
    time.sleep(0.02)
print("bridge discovered via beacon:", n.bridge)
print("polls ok:", n.seq, "| fresh:", n.fresh(), "| err:", n.err or "none")
print("keys:", sorted((n.data or {}).keys()))
assert n.bridge and n.seq >= 1, "net.py could not discover/poll the bridge"
print("PASS")
