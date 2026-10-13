#!/usr/bin/env python3
"""Render Desktop mode (summary and each waiting session) and every Debug mode page
-> tools/sim/out/view_*.png

Uses example data and placeholder network names only.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import net, scene, views  # noqa: E402

OUT = os.path.join(HERE, "out")


class FakeTether:
    def fresh(self):
        return False


def status(waiting=0):
    st = scene.Status()
    st.online = True
    st.level, st.busy, st.idle, st.sessions, st.subagents = 3, 3, 2, 6, 1
    st.set_agents(4)
    st.tpm, st.tools, st.clock = 22, 402, "14:05"
    st.used5, st.used7, st.hearts, st.week = 58, 35, 8, 0.65
    st.left5, st.left7 = (65 * 60) * 1000000, (3 * 86400 + 4 * 3600) * 1000000
    st.waiting = waiting
    st.waiting_list = [
        {"n": "api-server refactor", "s": 95, "d": "api-server", "w": "PERMISSION: BASH", "a": 7800},
        {"n": "docs-site", "s": 12, "d": "docs-site", "w": "YOUR REPLY", "a": 1500},
        {"n": "fix flaky login test on ci", "s": 8, "d": "web-app", "w": "", "a": 0},
        {"n": "notes", "s": 3, "d": "notes", "w": "YOUR REPLY", "a": 60},
    ][:waiting]
    return st


def link():
    n = net.Net([("home-wifi", "secret-password", "phone")])
    n.state, n.ssid, n.ip, n.mac = "up", "home-wifi", "192.168.1.50", "28:cd:c1:00:00:02"
    n.bridge, n.seen, n.scan_total = ("192.168.1.20", 8787), {"home-wifi": (-54, 6, 2)}, 9
    n.cands[0]["result"] = net.OK
    return n


def render(name, view, page=0, waiting=0, sel=None):
    scr = harness.new_screen()
    c = views.Ctx(status(waiting), link(), FakeTether())
    c.source = "net"
    c.wait_sel = sel
    views.draw(view, page, c, 0)
    path = os.path.join(OUT, "view_%s.png" % name)
    scr.to_png(path, 3)
    return path


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(render("desktop", views.DESKTOP, waiting=2))
    print(render("desktop_clear", views.DESKTOP, waiting=0))
    print(render("desktop_many", views.DESKTOP, waiting=4))
    for i in range(3):
        print(render("desktop_session_%d" % (i + 1), views.DESKTOP, waiting=3, sel=i))
    for p, name in enumerate(("overview", "connection", "wifi")):
        print(render("debug_%d_%s" % (p + 1, name), views.DEBUG, page=p, waiting=1))
