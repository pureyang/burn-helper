#!/usr/bin/env python3
"""Render the Wi-Fi debug screen for a few failure states -> tools/sim/out/debug_*.png"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import net, debugview, usb  # noqa: E402

OUT = os.path.join(HERE, "out")


class FakeTether:
    def fresh(self):
        return False


def make(state):
    n = net.Net([("home-wifi", "fourteenchars! ", "phone"), ("conference-wifi", "ninechars", "secrets")])
    n.mac = "28:cd:c1:xx:xx:xx"
    n.scan_total = 14
    n.scan_t = 1
    n.seen = {"home-wifi": (-56, 6, 3), "neighbour": (-77, 11, 1)}
    n.cands[2]["result"] = net.NOT_SEEN
    if state == "stuck":
        n.state = "down"
        n.attempts = 4
        n.cands[0].update(result=net.STUCK, tries=2)
        n.cands[1].update(result=net.STUCK, tries=2)
    elif state == "joining":
        n.state = "joining"
        n.attempts = 1
        n.cur = 0
        n.ssid = "home-wifi"
        n.status = 1
        n.cands[0].update(tries=1)
    elif state == "nobeacon":
        n.state = "up"
        n.ssid = "home-wifi"
        n.ip = "192.168.4.77"
        n.up_t = -60000
        n.cur = 0
        n.cands[0].update(result=net.OK, tries=1)
    return n


for st in ("stuck", "joining", "nobeacon"):
    scr = harness.new_screen()
    n = make(st)
    debugview.draw(n, FakeTether(), None, 0)
    scr.to_png(os.path.join(OUT, "debug_%s.png" % st), 3)
    print(st, "->", n.hint())
    print("   label:", n.label())
print("\n".join(make("stuck").dump()))
