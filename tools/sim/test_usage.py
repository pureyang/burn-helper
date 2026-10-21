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
