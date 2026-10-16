#!/usr/bin/env python3
"""The battery estimate, replayed against a real discharge log from the badge: no 0% while it
still has an hour in it, no bounce from a dip under load, and no leap when it is plugged in."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402

harness.install()
import power  # noqa: E402

# (seconds, raw volts against 3.3 V, what the 1.1 V rail read), one a minute on battery, from the
# badge's power log as it ran down to the last minutes before it was plugged in
LOG = [(27191, 3.456, 1.164), (27551, 3.448, 1.164), (27611, 3.416, 1.164), (27851, 3.403, 1.165),
       (27911, 3.433, 1.164), (27972, 3.396, 1.164), (28212, 3.386, 1.164), (28272, 3.420, 1.164),
       (28632, 3.413, 1.164), (29052, 3.475, 1.192), (29472, 3.390, 1.163), (30013, 3.368, 1.164),
       (30373, 3.348, 1.165), (30733, 3.349, 1.179), (31033, 3.358, 1.197), (31274, 3.340, 1.207),
       (31514, 3.363, 1.234), (31754, 3.352, 1.260), (31814, 3.359, 1.273)]
END = 31848                         # plugged in here, still running


def true(raw, rail):
    return raw * power.REF_VOLTS / rail


soc, v, t0 = None, None, None
seen = []
for (t, raw, rail), nxt in zip(LOG, LOG[1:] + [(END, LOG[-1][1], LOG[-1][2])]):
    for k in range(t, nxt[0], 2):            # a reading every 2 s until the next log line
        v = true(raw, rail) if v is None else v + power.SMOOTH * (true(raw, rail) - v)
        soc = power.estimate(soc, v, False, False, 0 if t0 is None else (k - t0) / 60.0)
        t0 = k
        seen.append((k, soc))
start = seen[0][1]
assert 10 <= start <= 20, "about 15% left, 77 minutes before the end: %.1f" % start
assert all(b <= a + 0.5 for (_, a), (_, b) in zip(seen, seen[1:])), "on battery it never jumps up"
mins_at_zero = sum(2 for _, s in seen if s < 0.5) / 60.0
assert mins_at_zero < 3, "0%% only in its last minutes, not for %.1f min" % mins_at_zero
assert min(s for k, s in seen if k < 31000) >= 2, "still a few percent with 14 minutes left"

# plugged in near empty: the voltage leaps under charge, the estimate doesn't
charge_v = [3.10, 3.70, 3.80, 3.85, 3.88, 3.90]       # true volts, a minute apart, charging
for minute, cv in enumerate(charge_v, 1):
    soc = power.estimate(soc, cv, True, True, 1.0)
    assert soc <= start and soc <= minute * power.CHARGE_PCT_PER_MIN + 1, (minute, soc)
for _ in range(120):                                  # two hours on the charger, ending at 4.2 V
    soc = power.estimate(soc, 4.20, True, True, 1.0)
assert soc >= 90, "topping up: about 92%%, until the charger says it is done: %.1f" % soc
assert power.estimate(soc, 4.18, True, False, 1.0) == 100.0, "the charger stopped: full"
# unplugged at full: the voltage settles a little, the estimate doesn't drop to match at once
soc = 100.0
soc = power.estimate(soc, 4.08, False, False, 1.0)
assert 90 <= soc <= 100, soc
print("PASS battery: about 15%% with 77 minutes left, never up on battery, %.1f min at 0%%, no leap "
      "when plugged in (+%.0f%%/min at most), 100%% when the charger stops"
      % (mins_at_zero, power.CHARGE_PCT_PER_MIN))
