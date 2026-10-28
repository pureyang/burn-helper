#!/usr/bin/env python3
"""The activity tiers: 1-10 one agent at a time, then 11-25, 26-50, 51-75, 76-100, then ULTRA."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import scene as S  # noqa: E402

expect = {0: 0, 1: 1, 2: 2, 9: 9, 10: 10, 11: 11, 25: 11, 26: 12, 50: 12, 51: 13, 75: 13,
          76: 14, 100: 14, 101: 15, 5000: 15}
for agents, tier in expect.items():
    assert S.tier_for(agents) == tier, (agents, S.tier_for(agents), tier)
assert len({S.tier_for(n) for n in range(1, 300)}) == 15, "there must be exactly 15 tiers"

for tier, level in ((1, S.WALK), (3, S.WALK), (4, S.RUN), (7, S.RUN), (8, S.SPRINT), (15, S.SPRINT)):
    assert S.gait_for(tier) == level, (tier, S.gait_for(tier))

st = S.Status()
st.update({"level": 1, "busy": 6, "subagents": 2, "waiting": 1,
           "waiting_list": [{"n": "api-server", "s": 95}, {"bad": 1}, "junk"]})
assert (st.agents, st.tier, st.level) == (8, 8, S.SPRINT), (st.agents, st.tier, st.level)
assert [(w["n"], w["s"]) for w in st.waiting_list] == [("api-server", 95), ("session", 0)], st.waiting_list
assert st.waiting_list[0]["d"] == "" and st.waiting_list[0]["w"] == "", "older bridges send no details"
st.update({"level": 0, "busy": 0, "subagents": 0})
assert (st.tier, st.level) == (0, S.SLEEP), "no agents: the bridge's asleep/idle level stands"
print("PASS 15 tiers (1-10, 11-25, 26-50, 51-75, 76-100, 100+), gaits, agent count, waiting list")
