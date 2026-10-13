#!/usr/bin/env python3
"""The activity feed: what the bridge sends about what agents just did, and how the badge
picks the one animation to play."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
import harness  # noqa: E402

harness.install()
import burn_helper_bridge as B  # noqa: E402
import scene as S  # noqa: E402

# ---------------------------------------------------------------- the bridge
b = B.Bridge()
b.local = {"busy": 1, "shell": 0, "waiting": 0, "idle": 0, "sessions": 1, "waiting_list": []}
for event, tool in (("SessionStart", None), ("UserPromptSubmit", None), ("PostToolUse", "Read"),
                    ("PostToolUse", "Edit"), ("PostToolUse", "TodoWrite"), ("PostToolUse", "Bash"),
                    ("PostToolUseFailure", "Bash"), ("SubagentStart", None), ("SubagentStop", None),
                    ("PostToolUse", "WebSearch"), ("Notification", None), ("Stop", None)):
    b.on_hook({"session_id": "sid-1", "event": event, "tool": tool,
               "secret_path": "/Users/someone/private/file.txt"})
ev = b.status()["ev"]
kinds = [k for _, k, _ in ev]
# TodoWrite and Notification are not activities; of the 10 that are, the latest 6 go out
assert kinds == ["shell", "fail", "spawn", "back", "web", "done"], kinds
assert all(isinstance(n, int) and isinstance(age, int) and 0 <= age < 1000 for n, _, age in ev), ev
assert len(ev) <= B.ACTIVITY_KEPT, "only the latest few go out"
assert [n for n, _, _ in ev] == sorted(n for n, _, _ in ev), "oldest first"
blob = repr(b.status())
assert "private" not in blob and "TodoWrite" not in blob and "Bash" not in blob, "categories only"
b.activity = [(n, k, ts - 30) for n, k, ts in b.activity]
assert b.status()["ev"] == [], "old activity is not sent"
print("PASS bridge feed: categories only, latest %d, oldest first, nothing older than %d s"
      % (B.ACTIVITY_KEPT, B.ACTIVITY_MAX_AGE_S))

# ---------------------------------------------------------------- the badge
st = S.Status()
st.update({"hearts": 4, "ev": [[1, "edit", 100], [2, "read", 50]]})
assert st.pending is None and st.ev_seen == 2, "first contact: catch up quietly, play nothing"
st.update({"hearts": 4, "ev": [[2, "read", 1500], [3, "edit", 200], [4, "fail", 100], [5, "read", 10]]})
assert st.pending == "fail", "a failure beats edits and reads: %s" % st.pending
st.update({"hearts": 4, "ev": [[3, "edit", 2200], [4, "fail", 2100], [5, "read", 2010]]})
assert st.pending == "fail", "the same activity again is not new"
now = time.ticks_ms()
assert not st.next_act(now, free=False) and st.pending == "fail", "waits while the theme is busy"
assert st.next_act(now, free=True) and st.act == "fail" and st.act_seq == now and st.pending is None
st.update({"hearts": 4, "ev": [[6, "edit", 9000]]})
assert st.pending is None, "too old by the time it arrived"
st.update({"hearts": 4, "ev": [[1, "edit", 10]]})
assert st.pending is None and st.ev_seen == 1, "bridge restarted: resync without playing"
st.update({"hearts": 4, "ev": [[1, "edit", 10], [2, "shell", 10]]})
assert st.pending == "shell"
st.update({"hearts": 20, "ev": []})
assert st.pending == "refill", "hearts jumping back up means the 5-hour window reset"
st.pending_t = time.ticks_add(time.ticks_ms(), -S.ACT_FRESH_MS - 1)
assert not st.next_act(time.ticks_ms(), free=True) and st.pending is None, "stale: dropped"
st.update({"hearts": 20, "ev": [[3, "bogus", 5], ["x"], None]})
assert st.pending is None, "unknown or broken entries are ignored"
st = S.Status()
st.update({"hearts": 4, "ev": []})
st.update({"hearts": 4, "ev": [[7, "edit", 300]]})
assert st.pending == "edit", "a quiet feed at first contact: the next activity plays"
st = S.Status()
st.update({"hearts": 4})
st.update({"hearts": 4, "ev": [[7, "edit", 300]]})
assert st.pending is None, "an older bridge without the feed, then a first feed: catch up quietly"
print("PASS badge: plays the most telling new activity, one at a time, skips stale and repeats, "
      "resyncs after a bridge restart, refill when the hearts jump back up")
