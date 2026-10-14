#!/usr/bin/env python3
"""Usage reports from several sessions: the newest window wins, stale ones can't undo it."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
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
