#!/usr/bin/env python3
"""Sessions whose status is stuck on "busy" or "shell" stop counting as agents working."""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
import burn_helper_bridge as B  # noqa: E402

tmp = tempfile.mkdtemp()
B.SESSIONS_DIR = tmp
now_ms = int(time.time() * 1000)
hour = 3600 * 1000
sessions = {
    "stuck": ("busy", now_ms - 90 * hour),      # said busy for days, nothing since
    "fresh": ("busy", now_ms - 60 * 1000),      # busy for a minute: working
    "server": ("shell", now_ms - 26 * hour),    # a background shell for a day: not an agent
    "long": ("busy", now_ms - 2 * hour),        # a long turn, but its hooks still arrive
}
for i, (sid, (status, ts)) in enumerate(sessions.items()):
    with open(os.path.join(tmp, "%d.json" % i), "w") as f:
        json.dump({"pid": os.getpid(), "sessionId": sid, "status": status, "statusUpdatedAt": ts,
                   "startedAt": now_ms - 100 * hour, "kind": "interactive"}, f)
b = B.Bridge()
b._is_claude = lambda pid, started: True
b.on_hook({"session_id": "long", "event": "PostToolUse", "tool": "Bash"})
b.scan()
assert b.local["busy"] == 2 and b.local["shell"] == 0, b.local
assert b.local["stale"] == 2 and b.local["idle"] == 2 and b.local["sessions"] == 4, b.local
print("PASS stuck sessions: busy or shell for %d min with no hook events counts as idle" % (B.STALE_S // 60))
