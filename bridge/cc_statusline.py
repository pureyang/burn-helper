#!/usr/bin/env python3
"""Claude Code status line: show remaining usage as hearts and report it to the Tufty bridge.

Prints one line such as:
    ♥♥♥♥♥♥❥♡♡♡ 5h 38% (resets 3:10pm) · 7d 12% · ctx 45% · Opus 5.5
"""
import json
import os
import socket
import sys
import time
import urllib.request

FULL, HALF, EMPTY = "♥", "❥", "♡"


def hearts(used):
    half_units = max(0, min(20, int(round((100.0 - used) / 5.0))))
    out = ""
    for i in range(10):
        r = half_units - i * 2
        out += FULL if r >= 2 else (HALF if r == 1 else EMPTY)
    return out


def clock(ts):
    try:
        t = time.localtime(float(ts))
        h = t.tm_hour % 12 or 12
        return "%d:%02d%s" % (h, t.tm_min, "am" if t.tm_hour < 12 else "pm")
    except (TypeError, ValueError, OverflowError):
        return ""


def num(v):
    try:
        if v is None or isinstance(v, bool):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def report(d):
    rl = d.get("rate_limits")
    if not isinstance(rl, dict) or not rl:
        return
    body = {"session_id": d.get("session_id"), "host": socket.gethostname(), "rate_limits": rl}
    url = (os.environ.get("TUFTY_BRIDGE_URL") or "http://127.0.0.1:8787").rstrip("/") + "/usage"
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("TUFTY_TOKEN")
    if token:
        headers["X-Tufty-Token"] = token
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=0.3).close()
    except Exception:  # noqa: BLE001
        pass


def line(d):
    parts = []
    rl = d.get("rate_limits") if isinstance(d.get("rate_limits"), dict) else {}
    now = time.time()
    five = rl.get("five_hour") if isinstance(rl.get("five_hour"), dict) else None
    seven = rl.get("seven_day") if isinstance(rl.get("seven_day"), dict) else None

    def used_of(w):
        u = num(w.get("used_percentage")) if w else None
        r = num(w.get("resets_at")) if w else None
        if u is not None and r and now > r:
            u = 0.0
        return u, r

    u5, r5 = used_of(five)
    u7, _ = used_of(seven)
    basis = u5 if u5 is not None else u7
    if basis is not None:
        parts.append(hearts(basis))
    if u5 is not None:
        s = "5h %d%%" % round(u5)
        if r5:
            s += " (resets %s)" % clock(r5)
        parts[-1] += " " + s
    if u7 is not None:
        parts.append("7d %d%%" % round(u7))
    cw = d.get("context_window") if isinstance(d.get("context_window"), dict) else {}
    ctx = num(cw.get("used_percentage"))
    if ctx is not None:
        parts.append("ctx %d%%" % round(ctx))
    model = d.get("model") if isinstance(d.get("model"), dict) else {}
    if model.get("display_name"):
        parts.append(str(model["display_name"]))
    return " · ".join(parts)


def main():
    try:
        raw = sys.stdin.read(4 * 1024 * 1024)
        d = json.loads(raw) if raw.strip() else {}
        if not isinstance(d, dict):
            d = {}
    except Exception:  # noqa: BLE001
        d = {}
    out = ""
    try:
        out = line(d)
    except Exception:  # noqa: BLE001
        out = ""
    try:
        sys.stdout.write(out + "\n")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001
        pass
    try:
        report(d)
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
