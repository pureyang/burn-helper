#!/usr/bin/env python3
"""Claude Code status line: show remaining usage as hearts and report it to the Burn Helper bridge.

Prints one line such as:
    ♥♥♥♥♥♥❥♡♡♡ 5h 38% (resets in 1h23m) · 7d 12% ✓ (in 3d4h) · ctx 45% · Opus 5.5

The bridge answers the report with the weekly pace (bridge/pace.py), shown after the week's
percent: ✓ on course to last the week, ≈ at this pace it runs out (when, if within 3 days and
likely), ! the same, sooner and surer, ✗ the weekly limit is reached. Nothing when no bridge answers.
"""
import json
import os
import socket
import sys
import time
import urllib.request


def read_input(limit):
    """Claude Code's JSON on stdin, as UTF-8 whatever the system's default encoding (Windows)."""
    data = sys.stdin.buffer.read(limit) if hasattr(sys.stdin, "buffer") else sys.stdin.read(limit).encode()
    return data.decode("utf-8", "replace")


def env(name, default=None):
    """BURN_HELPER_<name>, or the older HEARTS_LEFT_<name> or TUFTY_<name>, or default."""
    return (os.environ.get("BURN_HELPER_" + name) or os.environ.get("HEARTS_LEFT_" + name)
            or os.environ.get("TUFTY_" + name) or default)

FULL, HALF, EMPTY = "♥", "❥", "♡"


def hearts(used):
    half_units = max(0, min(20, int(round((100.0 - used) / 5.0))))
    out = ""
    for i in range(10):
        r = half_units - i * 2
        out += FULL if r >= 2 else (HALF if r == 1 else EMPTY)
    return out


def left(ts, now):
    """Time until a reset: "2h13m", "13m", "42s". The status line only redraws
    every few seconds, so finer ticking lives on the badge and the phone panel."""
    try:
        s = int(float(ts) - now)
    except (TypeError, ValueError, OverflowError):
        return ""
    if s <= 0:
        return "now"
    if s >= 86400:
        return "%dd%dh" % (s // 86400, s % 86400 // 3600)
    if s >= 3600:
        return "%dh%02dm" % (s // 3600, s % 3600 // 60)
    if s >= 60:
        return "%dm" % (s // 60)
    return "%ds" % s


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
    """Send the rate limits to the bridge; returns its weekly pace, or None."""
    rl = d.get("rate_limits")
    if not isinstance(rl, dict) or not rl:
        return None
    body = {"session_id": d.get("session_id"), "host": socket.gethostname(), "rate_limits": rl}
    url = (env("BRIDGE_URL") or "http://127.0.0.1:8787").rstrip("/") + "/usage"
    headers = {"Content-Type": "application/json"}
    token = env("TOKEN")
    if token:
        headers["X-Burn-Helper-Token"] = token
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=0.3) as r:
            got = json.loads(r.read(8192).decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001
        return None
    p = got.get("pace") if isinstance(got, dict) else None
    return p if isinstance(p, dict) else None


def day_hour(ts):
    """"Sun 4pm": local time to the nearest hour."""
    try:
        t = time.localtime(float(ts) + 1800)
    except (TypeError, ValueError, OverflowError):
        return ""
    return "%s %d%s" % (time.strftime("%a", t), t.tm_hour % 12 or 12, "am" if t.tm_hour < 12 else "pm")


def pace_text(p):
    """What goes after the week's percent: the pace's sign and, when there is something to say, a
    few words. Every forecast says "at this pace" and carries a ~."""
    s = p.get("s")
    if s == 3:
        return "✗"
    if s in (1, 2):
        when = day_hour(p.get("eta")) if p.get("eta") else ""
        out = "at this pace out ~" + when if when else "at this pace it runs out"
        early = num(p.get("early"))
        if s == 2 and early and early > 0:
            out += ", %s before reset" % (left(time.time() + early, time.time()) if early >= 172800
                                         else "%dh" % max(1, early // 3600))
        return ("! " if s == 2 else "≈ ") + out
    if p.get("room"):
        win = num(p.get("win"))
        return "✓ " + ("~%.1f full 5h windows left" % win if win else "%d%% left" % (p.get("left") or 0))
    if p.get("eased"):
        return "✓ pace eased"
    return "✓"


def line(d, pace=None):
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
    u7, r7 = used_of(seven)
    basis = u5 if u5 is not None else u7
    if basis is not None:
        parts.append(hearts(basis))
    if u5 is not None:
        s = "5h %d%%" % round(u5)
        if r5 and r5 > now:
            s += " (resets in %s)" % left(r5, now)
        parts[-1] += " " + s
    if u7 is not None:
        s = "7d %d%%" % round(u7)
        mark = pace_text(pace) if isinstance(pace, dict) else ""
        if mark:
            s += " " + mark
        if r7 and r7 > now and not (pace and pace.get("s") == 2):
            s += " (%s %s)" % ("resets in" if pace and pace.get("s") == 1 else "in", left(r7, now))
        parts.append(s)
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
        raw = read_input(4 * 1024 * 1024)
        d = json.loads(raw) if raw.strip() else {}
        if not isinstance(d, dict):
            d = {}
    except Exception:  # noqa: BLE001
        d = {}
    pace = None
    try:
        pace = report(d)          # first: its answer carries the weekly pace
    except Exception:  # noqa: BLE001
        pass
    out = ""
    try:
        out = line(d, pace)
    except Exception:  # noqa: BLE001
        out = ""
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write((out + "\n").encode("utf-8"))      # the hearts, even on Windows
        else:
            sys.stdout.write(out + "\n")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
