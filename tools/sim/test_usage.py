#!/usr/bin/env python3
"""Usage reports from several sessions: the newest window wins, stale ones can't undo it."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import burn_helper_bridge as B  # noqa: E402

now = int(time.time())


def report(b, used, resets):
    b.on_usage({"rate_limits": {"five_hour": {"used_percentage": used, "resets_at": resets}}})
    return b.five_hour["used"], b.five_hour["resets_at"]


b = B.Bridge()
b.five_hour = None
assert report(b, 30, now + 3600) == (30, now + 3600)
assert report(b, 0, now - 11 * 3600) == (30, now + 3600), "an idle session's ended window is ignored"
assert report(b, 12, now + 3600) == (30, now + 3600), "same window, older reading: keep the higher use"
assert report(b, 41, now + 3600) == (41, now + 3600)
assert report(b, 5, now + 5 * 3600) == (5, now + 5 * 3600), "a later window replaces the old one"
print("PASS usage: the newest window wins; stale sessions can't move the countdown back")

# a window that ended while work went on and nobody has reported the new one: unknown, not full
b = B.Bridge()
b.five_hour = {"used": 30.0, "resets_at": now - 3600, "rx": now - 7200}
b.seven_day = {"used": 11.0, "resets_at": now + 86400, "rx": now - 7200}
b.last_active = now - 3000                     # work an hour after the window ended
s = b.status()
assert s["five_hour"] == {"used": None, "resets_at": now - 3600, "stale": 1} and s["hearts"] is None, s["five_hour"]
assert s["seven_day"]["used"] == 11.0
b.last_active = now - 7000                     # idle since before it ended: it really is back to full
s = b.status()
assert s["five_hour"]["used"] == 0.0 and s["hearts"] == 20
b.last_active = now - 3000
b.on_usage({"rate_limits": {"five_hour": {"used_percentage": 21, "resets_at": now + 14000}}})
assert b.status()["hearts"] == 16, "a report of the new window ends the unknown"
import scene as _S  # noqa: E402
st = _S.Status()
st.update({"hearts": None, "five_hour": {"used": None, "resets_at": now - 3600, "stale": 1}, "seven_day": {"used": None, "resets_at": 1, "stale": 1}})
assert st.hearts is None and st.reset5 is None and st.week is None
print("PASS usage: an ended window nobody has reported on is unknown (grey hearts, no FULL), not 100%")

# an ended window with work since: the bridge estimates the new window from the first work after the
# reset, shows full hearts marked as an estimate, and says why
b = B.Bridge()
b.five_hour = {"used": 42.0, "resets_at": now - 1800, "rx": now - 1830}
b.seven_day = {"used": 11.0, "resets_at": now + 86400, "rx": now - 60}
b.on_hook({"session_id": "s1", "event": "UserPromptSubmit"})            # the first work after the reset
assert b.est_start and abs(b.est_start - time.time()) < 2
b.last_active = time.time()
s = b.status()
assert s["five_hour"]["est"] == 1 and s["five_hour"]["used"] is None, s["five_hour"]
assert abs(s["five_hour"]["resets_at"] - (b.est_start + 5 * 3600)) < 2 and s["hearts"] == 20, s
assert s["usage"]["state"] == "est", s["usage"]
for _name, _fn in (("ticks_us", lambda: int(time.time() * 1e6)), ("ticks_ms", lambda: int(time.time() * 1000)),
                   ("ticks_diff", lambda a, b: a - b), ("ticks_add", lambda a, b: a + b)):
    if not hasattr(time, _name):
        setattr(time, _name, _fn)
st = _S.Status()
st.update(s)
st.tick()
assert st.est5 and st.hearts == 20 and st.left5 is not None and st.left5 > 4 * 3600 * 1000000
assert _S.cd5(st).startswith("~") and st.usage_state == "est"
b.on_usage({"rate_limits": {"five_hour": {"used_percentage": 6, "resets_at": now + 17000}}})
assert b.est_start is None and b.status()["usage"]["state"] == "ok" and b.status()["hearts"] == 19
b2 = B.Bridge()
b2.five_hour = b2.seven_day = b2.est_start = None          # (a fresh bridge loads the real saved state)
assert b2.status()["usage"] == {"state": "none", "age": None} and b2.status()["hearts"] is None
print("PASS usage: an estimated new window (full hearts, a ~ countdown) with the reason, replaced by the first real report")
