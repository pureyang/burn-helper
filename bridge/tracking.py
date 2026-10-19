"""Optional history in a local SQLite file: how long sessions waited for you, and each day's usage.

Off unless you turn it on (the installer asks; `install.py --tracking on`). The database lives on
the bridge computer only, in the bridge's state folder (tracking.db), and is never sent anywhere:
the badge, /status and the relay do not see it. Read it with `python3 bridge/stats.py`.

Tables:
  waits   one row per time a session waited for you: when it began and ended, how long, which
          session (its Claude Code name), which computer, and what it needed.
  daily   one row per day: tool calls, prompts you sent, turns finished, how many times a session
          waited and for how long in all and at most, the 5-hour usage peak and the week's
          usage at the last report.
"""
import os
import sqlite3
import threading
import time

FLUSH_S = 30                 # how often the day's counters are written
SCHEMA = """
CREATE TABLE IF NOT EXISTS waits (
  id INTEGER PRIMARY KEY,
  session TEXT NOT NULL,      -- session id (first 8 characters)
  name TEXT,                  -- the session's Claude Code name, when known
  computer TEXT,
  why TEXT,                   -- what it needed: PERMISSION: BASH, A QUESTION, YOUR REPLY
  started REAL NOT NULL,      -- epoch seconds
  ended REAL,                 -- NULL while it is still waiting
  seconds REAL,
  seen REAL                   -- last time the bridge saw it waiting
);
CREATE INDEX IF NOT EXISTS waits_started ON waits (started);
CREATE TABLE IF NOT EXISTS daily (
  day TEXT PRIMARY KEY,       -- YYYY-MM-DD on the bridge computer
  tool_calls INTEGER NOT NULL DEFAULT 0,
  prompts INTEGER NOT NULL DEFAULT 0,
  turns INTEGER NOT NULL DEFAULT 0,
  waits INTEGER NOT NULL DEFAULT 0,
  wait_seconds REAL NOT NULL DEFAULT 0,
  longest_wait REAL NOT NULL DEFAULT 0,
  five_hour_peak REAL,        -- most of the 5-hour allowance used at any point that day, percent
  seven_day_used REAL         -- the week's usage at the day's last report, percent
);
"""


def enabled_file(state_dir):
    return os.path.join(state_dir, "tracking.enabled")


def is_enabled(state_dir):
    return os.path.exists(enabled_file(state_dir))


def set_enabled(state_dir, on):
    """Turn tracking on or off (the bridge reads it at start). Returns True if it changed."""
    path = enabled_file(state_dir)
    if on and not os.path.exists(path):
        os.makedirs(state_dir, exist_ok=True)
        with open(path, "w") as f:
            f.write("on\n")
        return True
    if not on and os.path.exists(path):
        os.remove(path)
        return True
    return False


class Tracker:
    def __init__(self, path, day=None):
        self.path = path
        self.day = day or (lambda: time.strftime("%Y-%m-%d"))
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.executescript(SCHEMA)
        # a bridge that stopped while something waited: close those at the last time it was seen
        self.db.execute("UPDATE waits SET ended = seen, seconds = seen - started WHERE ended IS NULL")
        self.db.commit()
        self.open = {}               # session id -> row id of its open wait
        self.today = {"day": None, "tool_calls": 0, "prompts": 0, "turns": 0, "peak5": None, "week": None}
        self.flushed = 0.0

    # ------------------------------------------------------------ what happened
    def event(self, kind):
        """A hook event: "tool" (a tool call), "prompt" or "turn"."""
        with self.lock:
            self._roll()
            key = {"tool": "tool_calls", "prompt": "prompts", "turn": "turns"}.get(kind)
            if key:
                self.today[key] += 1

    def usage(self, five_used, seven_used):
        with self.lock:
            self._roll()
            if five_used is not None:
                p = self.today["peak5"]
                self.today["peak5"] = five_used if p is None else max(p, five_used)
            if seven_used is not None:
                self.today["week"] = seven_used

    def observe(self, now, waiting):
        """Who is waiting right now: [(session id, name, computer, why)]. Called every scan; opens a
        row when a session starts waiting and closes it when it stops."""
        with self.lock:
            self._roll()
            now_ids = set()
            for sid, name, computer, why in waiting:
                sid = (sid or "?")[:8]
                now_ids.add(sid)
                if sid not in self.open:
                    cur = self.db.execute(
                        "INSERT INTO waits (session, name, computer, why, started, seen) VALUES (?,?,?,?,?,?)",
                        (sid, name, computer, why, now, now))
                    self.open[sid] = cur.lastrowid
                else:
                    self.db.execute("UPDATE waits SET seen = ?, name = COALESCE(?, name), why = COALESCE(?, why) "
                                    "WHERE id = ?", (now, name, why or None, self.open[sid]))
            for sid in [s for s in self.open if s not in now_ids]:
                self._close(self.open.pop(sid), now)
            if now - self.flushed >= FLUSH_S:
                self._flush(now)
            self.db.commit()

    # ------------------------------------------------------------ inside
    def _close(self, row_id, now):
        row = self.db.execute("SELECT started FROM waits WHERE id = ?", (row_id,)).fetchone()
        if not row:
            return
        secs = max(0.0, now - row[0])
        self.db.execute("UPDATE waits SET ended = ?, seconds = ?, seen = ? WHERE id = ?", (now, secs, now, row_id))
        day = time.strftime("%Y-%m-%d", time.localtime(row[0]))
        self.db.execute("INSERT OR IGNORE INTO daily (day) VALUES (?)", (day,))
        self.db.execute("UPDATE daily SET waits = waits + 1, wait_seconds = wait_seconds + ?, "
                        "longest_wait = MAX(longest_wait, ?) WHERE day = ?", (secs, secs, day))

    def _roll(self):
        """Write the counters out when the day changes."""
        d = self.day()
        if self.today["day"] is not None and self.today["day"] != d:
            self._flush(time.time())
            self.today.update(tool_calls=0, prompts=0, turns=0, peak5=None, week=None)
        self.today["day"] = d

    def _flush(self, now):
        t = self.today
        if t["day"] is None:
            return
        self.db.execute("INSERT OR IGNORE INTO daily (day) VALUES (?)", (t["day"],))
        # the counters are this process's totals for the day; add to what an earlier run left
        self.db.execute(
            "UPDATE daily SET tool_calls = tool_calls + ?, prompts = prompts + ?, turns = turns + ?, "
            "five_hour_peak = CASE WHEN ? IS NULL THEN five_hour_peak WHEN five_hour_peak IS NULL "
            "THEN ? ELSE MAX(five_hour_peak, ?) END, seven_day_used = COALESCE(?, seven_day_used) "
            "WHERE day = ?", (t["tool_calls"], t["prompts"], t["turns"], t["peak5"], t["peak5"], t["peak5"],
                              t["week"], t["day"]))
        t["tool_calls"] = t["prompts"] = t["turns"] = 0
        self.flushed = now

    def close(self):
        with self.lock:
            now = time.time()
            for rid in list(self.open.values()):
                self._close(rid, now)
            self.open.clear()
            self._flush(now)
            self.db.commit()
            self.db.close()
