#!/usr/bin/env python3
"""What the bridge says about sessions waiting for you, and what the hook sends it."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
import burn_helper_bridge as B  # noqa: E402
import cc_hook  # noqa: E402

# the hook: only a category and a tool name leave the Mac, never the notification text
assert cc_hook.why_waiting({"message": "Claude needs your permission to use Bash"}) == ("permission", "Bash")
assert cc_hook.why_waiting({"notification_type": "permission_prompt", "message": "x"}) == ("permission", None)
assert cc_hook.why_waiting({"message": "Claude is waiting for your input"}) == ("input", None)
assert cc_hook.why_waiting({"message": "something else entirely"}) == ("other", None)

b = B.Bridge()
now = time.time()
b.local = {"busy": 0, "shell": 0, "waiting": 2, "idle": 0, "sessions": 2,
           "waiting_list": [("api-server refactor", now - 95, "api-server", "sid-1abcdef", now - 7800, True),
                            ("docs-site", now - 12, "docs-site", "sid-2abcdef", None, False)]}
b.on_hook({"session_id": "sid-1abcdef", "event": "Notification", "why": "permission", "tool": "Bash"})
b.on_hook({"session_id": "sid-2abcdef", "event": "Notification", "why": "input"})
w = b.status()["waiting_list"]
assert w[0]["n"] == "api-server refactor" and 94 <= w[0]["s"] <= 96, w[0]
assert w[0]["d"] == "api-server" and w[0]["w"] == "PERMISSION: BASH" and 7799 <= w[0]["a"] <= 7801, w[0]
assert w[1]["w"] == "YOUR REPLY" and w[1]["a"] == 0, w[1]
assert w[0]["u"] == 0 and w[1]["u"] == 1 and w[1]["i"] == "sid-2a", "unnamed: the badge shows folder and id"

# a session waiting on another computer: its own name from that computer's hook, else the computer's
b.on_hook({"session_id": "pc-session-9", "event": "Notification", "why": "question", "host": "MY-LAPTOP.local",
           "name": "math homework helper", "folder": "math"})
b.on_hook({"session_id": "pc-session-8", "event": "Notification", "why": "permission", "tool": "Bash",
           "host": "MY-LAPTOP.local"})
w = b.status()["waiting_list"]
pc = [x for x in w if x["i"] == "pc-ses"]
named = [x for x in pc if x["n"] == "math homework helper"]
assert named and named[0]["u"] == 0 and named[0]["d"] == "math" and named[0]["w"] == "A QUESTION", w
assert [x for x in pc if x["n"] == "MY-LAPTOP" and x["u"] == 1], "no name sent: the computer's name"
b.on_hook({"session_id": "pc-session-9", "event": "PostToolUse", "tool": "Read", "host": "MY-LAPTOP.local"})
b.on_hook({"session_id": "pc-session-9", "event": "Notification", "why": "permission", "host": "MY-LAPTOP.local"})
assert [x for x in b.status()["waiting_list"] if x["n"] == "math homework helper"], "the name is kept"

# a name learnt from an earlier event (a prompt) is used when that session starts waiting
b3 = B.Bridge()
b3.local = {"busy": 0, "shell": 0, "waiting": 0, "idle": 0, "sessions": 0, "waiting_list": []}
b3.on_hook({"session_id": "pc-session-7", "event": "UserPromptSubmit", "host": "MY-LAPTOP.local",
            "name": "laptop chores", "folder": "chores"})
b3.on_hook({"session_id": "pc-session-7", "event": "Notification", "why": "question", "host": "MY-LAPTOP.local"})
assert [x for x in b3.status()["waiting_list"] if x["n"] == "laptop chores" and x["u"] == 0], b3.status()["waiting_list"]

# no names at all: readable labels, numbered when two look alike, never a hex id
b2 = B.Bridge()
b2.local = {"busy": 0, "shell": 0, "waiting": 0, "idle": 0, "sessions": 0, "waiting_list": []}
for sid in ("old-hook-1", "old-hook-2"):
    b2.on_hook({"session_id": sid, "event": "Notification", "why": "permission", "host": "OTHER-PC"})
names = sorted(x["n"] for x in b2.status()["waiting_list"])
assert names == ["OTHER-PC 1", "OTHER-PC 2"], names
assert B._badge_name({"name": "a session renamed with a long name"}) == "a session renamed with a long name"
assert [x["s"] for x in w] == sorted((x["s"] for x in w), reverse=True), "longest wait first"

# once the session moves on, its reason is forgotten
b.on_hook({"session_id": "sid-1abcdef", "event": "PostToolUse", "tool": "Bash"})
assert [x for x in b.status()["waiting_list"] if x["i"] == "sid-1a"][0]["w"] == "", "a stale reason must not linger"
assert B._plain("café  bar\tbaz") == "caf  bar baz".replace("  ", " "), B._plain("café  bar\tbaz")
print("PASS waiting details: reason from the hook (no message text), folder, wait and session age")

# a joined computer's session that finished its turn: Claude Code's idle reminder is not "waiting"
b4 = B.Bridge()
b4.local = {"busy": 0, "shell": 0, "waiting": 0, "idle": 0, "sessions": 0, "waiting_list": []}
b4.on_hook({"session_id": "done-1", "event": "UserPromptSubmit", "host": "OTHER-PC", "name": "finished one"})
b4.on_hook({"session_id": "done-1", "event": "Stop", "host": "OTHER-PC"})
b4.on_hook({"session_id": "done-1", "event": "Notification", "why": "input", "host": "OTHER-PC"})
st4 = b4.status()
assert st4["waiting"] == 0 and st4["waiting_list"] == [], st4["waiting_list"]
b4.on_hook({"session_id": "done-1", "event": "Notification", "why": "permission", "tool": "Bash", "host": "OTHER-PC"})
assert b4.status()["waiting"] == 1, "a permission prompt is waiting"
b4.on_hook({"session_id": "done-1", "event": "PostToolUse", "tool": "Bash", "host": "OTHER-PC"})
assert b4.status()["waiting"] == 0, "answered: the tool ran"
assert cc_hook.why_waiting({"notification_type": "elicitation_dialog", "message": "x"}) == ("question", None)

# the hook on another computer looks its session's name up in its own session files
import json as _json  # noqa: E402
import tempfile  # noqa: E402
_tmp = tempfile.mkdtemp()
with open(os.path.join(_tmp, "1.json"), "w") as _f:
    _json.dump({"sessionId": "abc", "name": "math homework helper"}, _f)
with open(os.path.join(_tmp, "1.key"), "w") as _f:
    _f.write("never read")
assert cc_hook.session_name("abc", _tmp) == "math homework helper" and cc_hook.session_name("zzz", _tmp) is None
print("PASS names: Claude Code's session names, whole; other computers send theirs with the waiting event")
