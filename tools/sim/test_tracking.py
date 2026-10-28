#!/usr/bin/env python3
"""The optional history: session waits and daily usage in a local SQLite file."""
import io
import os
import sqlite3
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
import burn_helper_bridge as B  # noqa: E402
import stats  # noqa: E402
import tracking  # noqa: E402

tmp = tempfile.mkdtemp()
assert not tracking.is_enabled(tmp)
assert tracking.set_enabled(tmp, True) and tracking.is_enabled(tmp) and not tracking.set_enabled(tmp, True)

# waits: a session starts waiting, is seen a while, stops; another is still waiting at the end
db = os.path.join(tmp, "tracking.db")
t = tracking.Tracker(db)
now = time.time()
t.observe(now, [("aaaaaaaa11", "api-server", "MY-MAC", "PERMISSION: BASH")])
t.observe(now + 60, [("aaaaaaaa11", "api-server", "MY-MAC", "PERMISSION: BASH"),
                     ("bbbbbbbb22", "docs-site", "MY-LAPTOP", "YOUR REPLY")])
t.observe(now + 120, [("bbbbbbbb22", "docs-site", "MY-LAPTOP", "YOUR REPLY")])      # api-server answered
rows = t.db.execute("SELECT session, name, computer, why, seconds FROM waits ORDER BY started").fetchall()
assert rows[0][:4] == ("aaaaaaaa", "api-server", "MY-MAC", "PERMISSION: BASH") and abs(rows[0][4] - 120) < 1, rows
assert rows[1][4] is None, "still waiting"
t.event("tool")
t.event("tool")
t.event("prompt")
t.event("turn")
t.usage(40.0, 12.0)
t.usage(55.0, 13.0)
t.usage(30.0, None)
t.flushed = 0
t.observe(now + 125, [("bbbbbbbb22", "docs-site", "MY-LAPTOP", "YOUR REPLY")])
t.close()                                    # closes docs-site at the end, flushes the day

d = sqlite3.connect(db)
day = d.execute("SELECT tool_calls, prompts, turns, waits, wait_seconds, longest_wait, five_hour_peak, "
                "seven_day_used FROM daily").fetchall()
assert len(day) == 1 and day[0][:4] == (2, 1, 1, 2), day
# (the clock in close() is the real one, so the still-waiting session counts as 0 s here)
assert abs(day[0][4] - 120) < 1 and abs(day[0][5] - 120) < 1 and day[0][6] == 55.0 and day[0][7] == 13.0, day

# a bridge that stopped mid-wait: the open row is closed at the last time it was seen
t2 = tracking.Tracker(db)
t2.db.execute("INSERT INTO waits (session, name, started, seen) VALUES ('cccccccc', 'x', ?, ?)", (now, now + 30))
t2.db.commit()
t3 = tracking.Tracker(db)
assert t3.db.execute("SELECT seconds FROM waits WHERE session='cccccccc'").fetchone()[0] == 30
t3.close()

# the reader
out = io.StringIO()
stats.report(sqlite3.connect(db), 14, True, out=lambda s="": out.write(s + "\n"))
text = out.getvalue()
assert "api-server" in text and "docs-site" in text and "Waits" in text and "55%" in text, text

# the bridge feeds it: hook events and who is waiting
b = B.Bridge()
b.local = {"busy": 0, "shell": 0, "waiting": 1, "idle": 0, "sessions": 1,
           "waiting_list": [("my session", now - 10, "folder", "sess-1abcdef", now - 900, True)]}
b.tracker = tracking.Tracker(os.path.join(tmp, "bridge.db"))
b.on_hook({"session_id": "sess-1abcdef", "event": "PostToolUse", "tool": "Bash"})
b.on_hook({"session_id": "sess-1abcdef", "event": "Notification", "why": "permission", "tool": "Bash"})
b.track()
assert b.tracker.db.execute("SELECT name, why FROM waits").fetchall() == [("my session", "PERMISSION: BASH")]
b.local["waiting_list"] = []
b.track()
assert b.tracker.db.execute("SELECT COUNT(*) FROM waits WHERE ended IS NOT NULL").fetchone()[0] == 1
b.tracker.close()
assert sqlite3.connect(os.path.join(tmp, "bridge.db")).execute("SELECT tool_calls FROM daily").fetchone()[0] == 1
print("PASS tracking: waits opened and closed with their length, the day's counts and usage peak, "
      "an interrupted wait closed, the report, and the bridge feeding it")
