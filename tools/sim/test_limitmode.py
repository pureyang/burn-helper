#!/usr/bin/env python3
"""The two limit modes: "5h" (the hearts are the 5-hour limit) and "week" (a plan with only a weekly
limit: the hearts are the week, and the ones likely spent by the reset go dark now and then)."""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import burn_helper_bridge as B  # noqa: E402
import cc_statusline as SL  # noqa: E402
import pace  # noqa: E402
import scene as S  # noqa: E402

for _name, _fn in (("ticks_us", lambda: int(time.time() * 1e6)), ("ticks_ms", lambda: int(time.time() * 1000)),
                   ("ticks_diff", lambda a, b: a - b), ("ticks_add", lambda a, b: a + b)):
    if not hasattr(time, _name):
        setattr(time, _name, _fn)

now = int(time.time())
B.STATE_DIR = tempfile.mkdtemp()          # not the real bridge's choice


def bridge():
    b = B.Bridge()
    b.five_hour = b.seven_day = b.est_start = b.has5 = None     # (a fresh bridge loads the saved state)
    b.pace.out = None
    return b


# auto: 5-hour mode until a report comes without a 5-hour window
b = bridge()
assert b.limit_mode() == "5h"
b.on_usage({"rate_limits": {"five_hour": {"used_percentage": 30, "resets_at": now + 3600},
                            "seven_day": {"used_percentage": 40, "resets_at": now + 3 * 86400}}})
s = b.status()
assert b.has5 is True and s["mode"] == "5h" and s["hearts"] == 14 and s["hearts_end"] is None, s
b.on_usage({"rate_limits": {"seven_day": {"used_percentage": 41, "resets_at": now + 3 * 86400}}})
b.pace.out = {"f": 72, "s": 0}
s = b.status()
assert b.has5 is False and s["mode"] == "week", s
assert s["five_hour"] is None, "the old 5-hour window means nothing now"
assert s["hearts"] == 12 and s["hearts_end"] == 6, (s["hearts"], s["hearts_end"])
b.pace.out = {"f": 130, "s": 1}
assert b.status()["hearts_end"] == 0, "on course to run out: none left at the reset"
b.pace.out = {"f": 30, "s": 0}
assert b.status()["hearts_end"] == 12, "never more than there are now"
b.pace.out = None
assert b.status()["hearts_end"] is None, "no forecast yet"
print("PASS limit mode auto: 5h while Claude Code reports a 5-hour window, week once it reports only the week")

# the choice on the bridge computer wins over auto
assert pace.set_limit(B.STATE_DIR, "5h") and b.limit_mode() == "5h"
assert b.status()["hearts"] == 14, "5h chosen: the last 5-hour window, as before"
b.has5 = True
assert pace.set_limit(B.STATE_DIR, "week") and b.limit_mode() == "week"
assert not pace.set_limit(B.STATE_DIR, "week")
assert pace.set_limit(B.STATE_DIR, "auto") and b.limit_mode() == "5h" and pace.limit_setting(B.STATE_DIR) == "auto"
with open(pace.limit_file(B.STATE_DIR), "w") as f:
    f.write("weekly??\n")
assert pace.limit_setting(B.STATE_DIR) == "auto", "a file it can't read is auto"
os.remove(pace.limit_file(B.STATE_DIR))
print("PASS limit mode chosen: --limit 5h / week / auto on the bridge computer")

# the badge: week mode's hearts, clock and meter
b = bridge()
b.on_usage({"rate_limits": {"seven_day": {"used_percentage": 40, "resets_at": now + 2 * 86400}}})
b.pace.out = {"s": 0, "p": 3, "f": 70, "even": 70, "left": 60, "win": 1.4}
st = S.Status()
st.update(b.status())
st.online = True
st.tick()
assert st.mode == "week" and st.hearts == 12 and st.hearts_end == 6
assert S.life_left(st) == st.left7 and S.cd_life(st) == S.gfx.countdown(st.left7)
assert abs(st.week - 2 / 7.0) < 0.01, "the meter is the week's time left"
assert S.pct7(st) == 60
lit = [S.icon_units(st, st.hearts, t) for t in range(0, S.BURN_MS, 50)]
assert set(lit) == {12, 6} and lit.count(6) * 50 == S.BURN_OFF_MS, "the likely-spent hearts go dark 0.7 s in 2 s"
st.online = False
assert S.icon_units(st, st.hearts, S.BURN_MS - 1) == 12, "not while the data is lost"
st.online = True
assert all("5H WINDOWS" not in x[0] for x in S.pace_lines(st)), "no 5-hour windows on a weekly-only plan"
assert S.last_usage(st).endswith("WEEK 60%"), S.last_usage(st)
st5 = S.Status()
st5.update(dict(b.status(), mode="5h", hearts_end=6))
assert st5.hearts_end is None and S.icon_units(st5, 12, S.BURN_MS - 1) == 12, "5h mode: no forecast on the hearts"
print("PASS badge week mode: weekly hearts and clock, the time-left meter, the likely-spent hearts go dark")

# the status line: a bar where the week likely ends, and no 5-hour figures
d = {"rate_limits": {"five_hour": {"used_percentage": 10, "resets_at": now + 3600},
                     "seven_day": {"used_percentage": 40, "resets_at": now + 2 * 86400}}}
out = SL.line(d, {"s": 0, "f": 70}, "week")
assert out.startswith("♥♥♥│♥♥♥♡♡♡♡ · 7d 40% ✓ ends ~70%"), out
assert "5h" not in out
out = SL.line(d, {"s": 0, "f": 70}, "5h")
assert out.startswith("♥♥♥♥♥♥♥♥♥♡ 5h 10%") and "│" not in out, out
out = SL.line({"rate_limits": {"seven_day": {"used_percentage": 40, "resets_at": now + 86400}}}, {"s": 1, "f": 120, "eta": now + 3600}, "week")
assert out.startswith("│♥♥♥♥♥♥♡♡♡♡ · 7d 40% ≈ at this pace out"), out
print("PASS status line: week mode marks where the week likely ends; 5h mode unchanged")
