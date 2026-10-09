#!/usr/bin/env python3
"""Claude Code hook: forward a minimal activity event to the Tufty bridge.

Only session_id, event name, tool name, agent id and hostname leave this
machine. Tool inputs and outputs are never sent. Always exits 0.
"""
import json
import os
import socket
import sys
import urllib.request


def main():
    try:
        raw = sys.stdin.read(1024 * 1024)
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
        url = (os.environ.get("TUFTY_BRIDGE_URL") or "http://127.0.0.1:8787").rstrip("/") + "/hook"
        headers = {"Content-Type": "application/json"}
        token = os.environ.get("TUFTY_TOKEN")
        if token:
            headers["X-Tufty-Token"] = token
        req = urllib.request.Request(url, data=json.dumps(event).encode(), headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=0.5).close()
    except Exception:  # noqa: BLE001 - a hook must never fail the session
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
