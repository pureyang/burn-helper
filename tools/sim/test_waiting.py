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

# a session on another computer that is waiting shows under that computer's name
b.on_hook({"session_id": "pc-session-9", "event": "Notification", "why": "input", "host": "YANG-HP.local"})
w = b.status()["waiting_list"]
pc = [x for x in w if x["i"] == "pc-ses"]
assert pc and pc[0]["n"] == "YANG-HP" and pc[0]["u"] == 1 and pc[0]["w"] == "YOUR REPLY", w
assert [x["s"] for x in w] == sorted((x["s"] for x in w), reverse=True), "longest wait first"

# once the session moves on, its reason is forgotten
b.on_hook({"session_id": "sid-1abcdef", "event": "PostToolUse", "tool": "Bash"})
assert [x for x in b.status()["waiting_list"] if x["i"] == "sid-1a"][0]["w"] == "", "a stale reason must not linger"
assert B._plain("café  bar\tbaz") == "caf  bar baz".replace("  ", " "), B._plain("café  bar\tbaz")
print("PASS waiting details: reason from the hook (no message text), folder, wait and session age")
