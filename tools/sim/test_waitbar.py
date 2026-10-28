#!/usr/bin/env python3
"""The waiting bar's timing: names that fit take turns; a long one holds, scrolls once, rests."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402

harness.install()
import scene as S  # noqa: E402

over = {"short": -20, "long": 48}           # pixels wider than the bar's room
wl = [{"i": "short"}, {"i": "long"}]


def at(t):
    return S.wait_turn(wl, t, lambda w: over[w["i"]])


S._turn.update(key=None)
cyc, hold, end, speed = S.WAIT_CYCLE_MS, S.WAIT_HOLD_MS, S.WAIT_END_MS, S.WAIT_SCROLL_PX_S
assert at(0) == (0, 0) and at(cyc - 40) == (0, 0), "a name that fits never moves"
assert at(cyc) == (1, 0), "then the next one"
assert at(cyc + hold - 40)[1] == 0, "a long name stays at its start first"
assert at(cyc + hold + 1000) == (1, speed), "then scrolls at WAIT_SCROLL_PX_S"
scroll = over["long"] * 1000 // speed
assert at(cyc + hold + scroll + end - 40) == (1, over["long"]), "and rests at its end"
assert at(cyc + hold + scroll + end) == (0, 0), "then the first one again"

S._turn.update(key=None)
one = [{"i": "long"}]
assert S.wait_turn(one, 0, lambda w: 48) == (0, 0)
assert S.wait_turn(one, hold + scroll + end, lambda w: 48) == (0, 0), "alone: back to its start"

S._turn.update(key=None)
at(0)
at(cyc)                                     # on the second session
wl = [{"i": "long"}, {"i": "short"}, {"i": "new"}]
over["new"] = 0
assert at(cyc + 80) == (0, 0), "a new list starts from the longest wait"
print("PASS waiting bar: %.1f s per name that fits; a long one holds %.1f s, scrolls %d px/s, rests %.1f s"
      % (cyc / 1000.0, hold / 1000.0, speed, end / 1000.0))
