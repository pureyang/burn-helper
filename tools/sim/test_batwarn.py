#!/usr/bin/env python3
"""The low-battery warning: when it shows, what it says, that the lines fit the banner, and a
picture of it over a theme and Desktop mode -> tools/sim/out/batwarn_*.png"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402

harness.install()
import gfx  # noqa: E402
import power  # noqa: E402
import preview_views as PV  # noqa: E402
import proto_common as P  # noqa: E402
import views  # noqa: E402

OUT = os.path.join(HERE, "out")


def r(pct, usb=False, charging=False):
    return (usb, charging, 3.3, pct)


# never on USB or charging, and not above the low mark
for pct in (100, 50, 21):
    assert power.warning(r(pct), None) is None, pct
for pct in (20, 10, 0):
    assert power.warning(r(pct, usb=True), None) is None, "no warning on the cable"
    assert power.warning(r(pct, usb=True, charging=True), None) is None
assert power.warning(None, None) is None, "the firmware cannot tell: say nothing"

# low, then critical, and the time left only when the badge has one
w = power.warning(r(20), None)
assert w == (1, "LOW BATTERY 20%", "PLUG IN SOON"), w
w = power.warning(r(18), (100, False))
assert w == (1, "LOW BATTERY 18%", "PLUG IN: ~1H40M LEFT"), w
w = power.warning(r(10), (55, True))
assert w == (2, "BATTERY 10%: PLUG IN NOW", "~55M LEFT"), w
w = power.warning(r(0), None)
assert w[0] == 2 and w[2] == "IT WILL TURN OFF SOON", w

# a low warning comes round for 6 s of every 45 s; a critical one stays
low, crit = power.warning(r(15), None), power.warning(r(5), None)
on = [views.battery_banner(low, t) for t in range(0, 90000, 1000)]
assert on[:6] == [True] * 6 and on[6:45] == [False] * 39 and on[45:51] == [True] * 6, on
assert all(views.battery_banner(crit, t) for t in range(0, 90000, 1000))
assert not views.battery_banner(None, 0)

# every line fits inside the banner (148 px wide, 4 px a side)
harness.new_screen()
lines = []
for pct in (20, 18, 10, 7, 0):
    for left in (None, (9 * 60 + 59, True), (45, False)):
        w = power.warning(r(pct), left)
        lines += [w[1], w[2]]
for s in lines:
    assert gfx.width(s, font.sins) <= 140, (s, gfx.width(s, font.sins))

# the pictures: a theme and Desktop mode, low and critical
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    theme = __import__("theme_hero").Theme()
    for name, pct, left in (("low", 18, (100, True)), ("critical", 7, (30, True))):
        w = power.warning(r(pct), left)
        scr = P.render(theme, P.status(agents=3), 5000)
        views.draw_battery_warning(w)
        scr.to_png(os.path.join(OUT, "batwarn_hero_%s.png" % name), 3)
        scr = harness.new_screen()
        c = views.Ctx(PV.status(1), PV.link(), PV.FakeTether())
        c.source = "net"
        views.draw(views.DESKTOP, 0, c, 0)
        views.draw_battery_warning(w)
        scr.to_png(os.path.join(OUT, "batwarn_desktop_%s.png" % name), 3)
print("ok")
