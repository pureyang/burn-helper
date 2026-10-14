#!/usr/bin/env python3
"""Claude Code hook: forward a minimal activity event to the Burn Helper bridge.

Only session_id, event name, tool name, agent id and hostname leave this
machine, plus, for a notification, why Claude is waiting: "permission" (and for
which tool) or "input". When a session starts, gets a prompt, finishes a turn or
starts waiting, also its name (as Claude Code shows it) and folder name, so the
badge can say which session it is when this computer isn't the bridge. The
notification's text, prompts, tool inputs and outputs are never sent. Always
exits 0.
"""
import json
import os
import re
import socket
import sys
import urllib.request


def read_input(limit):
    """Claude Code's JSON on stdin, as UTF-8 whatever the system's default encoding (Windows)."""
    data = sys.stdin.buffer.read(limit) if hasattr(sys.stdin, "buffer") else sys.stdin.read(limit).encode()
    return data.decode("utf-8", "replace")


def env(name, default=None):
    """BURN_HELPER_<name>, or the older HEARTS_LEFT_<name> or TUFTY_<name>, or default."""
    return (os.environ.get("BURN_HELPER_" + name) or os.environ.get("HEARTS_LEFT_" + name)
            or os.environ.get("TUFTY_" + name) or default)


def why_waiting(d):
    """(why, tool) for a Notification: ("permission", "Bash"), ("input", None) or ("other", None)."""
    kind = str(d.get("notification_type") or "")
    msg = str(d.get("message") or "")
    if kind == "permission_prompt" or "permission" in msg.lower():
        m = re.search(r"permission to use ([A-Za-z0-9_]{1,32})", msg)
        return "permission", (m.group(1) if m else None)
    if kind == "idle_prompt" or "waiting for your input" in msg.lower():
        return "input", None
    return "other", None


NAMED_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "Notification")


def session_name(sid, sessions_dir=None):
    """The session's name as Claude Code shows it (set with /rename, or one it made up), from
    its session file on this computer, or None."""
    sessions_dir = sessions_dir or os.path.join(os.path.expanduser("~"), ".claude", "sessions")
    try:
        names = os.listdir(sessions_dir)
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue                       # never touch the .key files
        try:
            with open(os.path.join(sessions_dir, name), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("sessionId") == sid and d.get("name"):
            return str(d["name"])[:60]
    return None


def main():
    try:
        raw = read_input(1024 * 1024)
        d = json.loads(raw) if raw.strip() else {}
        if not isinstance(d, dict):
            d = {}
        event = {
            "session_id": d.get("session_id"),
            "event": d.get("hook_event_name"),
            "tool": d.get("tool_name"),
            "host": socket.gethostname(),
        }
        if d.get("agent_id"):
            event["agent_id"] = d.get("agent_id")
        if event["event"] == "Notification":
            event["why"], tool = why_waiting(d)
            event["tool"] = event["tool"] or tool
        if event["event"] in NAMED_EVENTS:
            # not on every tool call: these few are enough for the bridge to know the name early
            event["name"] = session_name(d.get("session_id"))
            event["folder"] = os.path.basename(str(d.get("cwd") or "").rstrip("/\\"))[:60] or None
        url = (env("BRIDGE_URL") or "http://127.0.0.1:8787").rstrip("/") + "/hook"
        headers = {"Content-Type": "application/json"}
        token = env("TOKEN")
        if token:
            headers["X-Burn-Helper-Token"] = token
        req = urllib.request.Request(url, data=json.dumps(event).encode(), headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=0.5).close()
    except Exception:  # noqa: BLE001 - a hook must never fail the session
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
