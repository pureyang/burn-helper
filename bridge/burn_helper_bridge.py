#!/usr/bin/env python3
"""Burn Helper bridge: aggregates Claude Code activity and usage for the badge.

Sources:
  * ~/.claude/sessions/*.json   live session registry written by Claude Code
  * POST /hook                  events from bridge/cc_hook.py (tool calls, subagents, remote hosts)
  * POST /usage                 rate limits from bridge/cc_statusline.py (it answers with the weekly pace),
                                tagged with the Claude account it comes from (a short hash and a label)

Outputs:
  * GET /status                 JSON for the badge: counts, usage, and the names and folders of
                                sessions waiting on you
  * GET /                       phone control panel (the page only; its data comes from /status)
  * POST /theme                 pick the badge theme from a phone
  * GET /health                 "is a bridge here", for the installer; nothing about your sessions

From anywhere but this computer itself, every message both ways is sealed with the bridge's key
(seal.py: encrypted and signed), and one that isn't is turned down; only GET / and /health are
open, and they say nothing about your sessions. The key itself never crosses the network: it is
made on first start (portable.bridge_key) and reaches the badge over the USB cable only, other
computers through their join line, and a phone through the link `install.py --join-help` prints.
  * UDP beacon                  "TUFTYBRIDGE 1 <port> <bridge id>" broadcast to port 47800 every 2 s
                                (the TUFTY wire markers predate the Burn Helper name; kept so
                                badges and bridges of either age still talk)
  * USB tether                  "@TUFTY <status json>" lines written to the badge's USB serial
                                port every 2 s when it is plugged into this Mac (no Wi-Fi needed)

Standard library only. Python 3.9 compatible.
"""
import argparse
import datetime
import hmac
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pace  # noqa: E402
import seal  # noqa: E402
import portable  # noqa: E402
import tracking  # noqa: E402


def env(name, default=None):
    """BURN_HELPER_<name>, or the older HEARTS_LEFT_<name> or TUFTY_<name>, or default."""
    return (os.environ.get("BURN_HELPER_" + name) or os.environ.get("HEARTS_LEFT_" + name)
            or os.environ.get("TUFTY_" + name) or default)

# ---------------------------------------------------------------- tunables
DEFAULT_PORT = 8787
BEACON_PORT = 47800
BEACON_INTERVAL = 2.0
SCAN_INTERVAL = 2.0
PERSIST_INTERVAL = 5.0
MAX_BODY = 64 * 1024

LEVEL4_LOAD = 4.0
LEVEL4_TPM = 40
LEVEL3_LOAD = 2.0
LEVEL3_TPM = 15
RECENT_ACTIVE_S = 300          # level 1 window after the last activity
REMOTE_BUSY_S = 90             # remote session counts as busy this long after an event
SUBAGENT_EXPIRE_S = 600        # forget subagent counts after this long without events
# A local session whose file has said "busy" or "shell" this long, with no hook event from it
# either, is stuck (Claude Code left the status behind, or a background server is running in
# an otherwise idle session): count it as idle, not as an agent working.
STALE_S = 1800
REMOTE_EXPIRE_S = 3600         # forget remote sessions entirely after this long
TPM_WINDOW_S = 60
USB_INTERVAL = 2.0

THEMES = ("hero", "gameshow", "chocolates")
# theme ids used before the files were renamed (saved state, old phone panels)
LEGACY_THEMES = {"zelda": "hero", "runningman": "gameshow", "forrest": "chocolates"}
COUNTED_KINDS = ("interactive", "bg", "daemon-worker")
BUSY_EVENTS = ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SessionStart")
TOOL_EVENTS = ("PostToolUse", "PostToolUseFailure")
# What the agents just did, for the badge's one-shot animations. Only these category names
# leave the bridge: never file names, commands, URLs or prompts.
TOOL_ACTIVITY = {"Edit": "edit", "Write": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
                 "Read": "read", "Grep": "read", "Glob": "read", "LS": "read",
                 "Bash": "shell", "WebFetch": "web", "WebSearch": "web"}
EVENT_ACTIVITY = {"PostToolUseFailure": "fail", "Stop": "done", "UserPromptSubmit": "prompt",
                  "SubagentStart": "spawn", "SubagentStop": "back", "SessionStart": "arrive"}
ACTIVITY_KEPT = 6              # the latest few go out in /status
ACTIVITY_MAX_AGE_S = 10
# More than one Claude account: the main one (signed in to ~/.claude) drives the hearts as always;
# each other account gets a row of its own under the HUD, up to ACCOUNTS_MAX of them.
ACCOUNTS_MAX = 4
ACCOUNT_FORGET_S = 14 * 86400  # an account with no report for this long leaves the badge

HOME = os.path.expanduser(env("HOME") or "~")
SESSIONS_DIR = os.path.join(HOME, ".claude", "sessions")
# other accounts' config folders (CLAUDE_CONFIG_DIR=~/.claude-<name>, set up by install.py
# --add-account) keep their own sessions beside it, in ~/.claude-<name>/sessions (session_dirs)
STATE_DIR = os.path.expanduser(env("STATE_DIR") or os.path.join(HOME, ".claude", "burn-helper"))
OLD_STATE_DIRS = (os.path.join(HOME, ".claude", "hearts-left"), os.path.join(HOME, ".claude", "tufty-bridge"))
STATE_FILE = os.path.join(STATE_DIR, "state.json")
PACE_FILE = os.path.join(STATE_DIR, "pace.json")    # the weekly pace's history (bridge/pace.py)
# Internet relay (bridge/relay.py turns it on): a second listener on 127.0.0.1 that only
# Tailscale Funnel reaches, answering GET /status to callers with the key.
RELAY_FILE = os.path.join(STATE_DIR, "relay.json")
RELAY_PORT = 8788
RELAY = None          # {"url": "https://<mac>.<tailnet>.ts.net", "key": "<hex>"} when on
USB_LOCK = os.path.join(STATE_DIR, "usb.lock")   # held by scripts/badge.py while it uses the port
HOSTNAME = socket.gethostname()

VERBOSE = False


def log(msg):
    sys.stderr.write("[burn-helper %s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


def _num(v, default=None):
    try:
        if v is None or isinstance(v, bool):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def usage_state(raw5, raw7, five, now):
    """{"state", "age"}: how sure the usage shown is. age = seconds since any status line reported."""
    rx = max((w.get("rx") or 0) for w in (raw5, raw7) if w) if (raw5 or raw7) else 0
    age = int(now - rx) if rx else None
    if not (raw5 or raw7):
        state = "none"
    elif five and five.get("est"):
        state = "est"
    elif five and five.get("stale"):
        state = "stale"
    elif age is not None and age > 1800:
        state = "old"
    else:
        state = "ok"
    return {"state": state, "age": age}


def waiting_entries(loc, remote, why, now):
    """The badge's list of sessions waiting for you, longest wait first, at most 4, each by its
    Claude Code name. Without one (an older Claude Code, or a computer whose hook doesn't send
    names yet) a session goes by its folder, or by its computer's name, numbered only when two
    would look the same; `u` = 1 marks those, and the badge shows them in grey."""
    out = [{"n": n, "s": max(0, int(now - since)), "d": folder, "w": why.get(sid, ""),
            "a": max(0, int(now - started)) if started else 0, "i": sid[:6], "u": 0 if named else 1}
           for n, since, folder, sid, started, named in loc.get("waiting_list", [])]
    for sid, r in remote:
        computer = _plain(str(r.get("host") or "").split(".")[0]) or "other computer"
        name = r.get("name")        # its Claude Code name, from that computer's hook
        out.append({"n": name or r.get("folder") or computer, "s": max(0, int(now - r["ts"])),
                    "d": r.get("folder") or computer, "w": why.get(sid, ""), "a": 0, "i": sid[:6],
                    "u": 0 if name else 1})
    out = sorted(out, key=lambda w: -w["s"])[:4]
    seen = {}
    for w in out:
        if w["u"]:
            seen[w["n"]] = seen.get(w["n"], 0) + 1
    count = {}
    for w in out:
        if w["u"] and seen[w["n"]] > 1:
            count[w["n"]] = count.get(w["n"], 0) + 1
            w["n"] = "%s %d" % (w["n"], count[w["n"]])
    return out


def _plain(text, n=20):
    """Plain ASCII, spaces collapsed, at most n characters: safe for the badge's pixel fonts."""
    clean = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in str(text))
    return " ".join(clean.split())[:n]


def _badge_name(d):
    """The session's name as Claude Code shows it (set with /rename, or the one Claude Code made
    up), in plain ASCII and whole up to 40 characters; the badge fits it to its screen. Its
    folder name when it has none."""
    raw = d.get("name") or os.path.basename(str(d.get("cwd") or "").rstrip("/")) or "session"
    clean = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in str(raw))
    return " ".join(clean.split())[:40] or "session"

def session_dirs():
    """Every folder of session files to scan: ~/.claude's and each ~/.claude-<name>'s."""
    import glob
    home = os.path.dirname(os.path.dirname(SESSIONS_DIR))
    return [SESSIONS_DIR] + sorted(glob.glob(os.path.join(home, ".claude-*", "sessions")))


def merge_window(old, w, now):
    """One window of a status line's report ({"used_percentage", "resets_at"}) taken in over what
    was known: the new {"used", "resets_at", "rx"}, or None to keep the old one."""
    used = _num(w.get("used_percentage"))
    if used is None:
        return None
    resets = int(_num(w.get("resets_at"), 0) or 0)
    if old and resets and old.get("resets_at"):
        if resets < old["resets_at"]:
            return None             # an idle session still reporting a window that has ended
        if resets == old["resets_at"]:
            used = max(used, old["used"])   # same window: usage only goes up
    return {"used": round(used, 1), "resets_at": resets, "rx": now}


def account_id(v):
    """The status line's account tag: a short hex hash of the account id, or None."""
    v = str(v or "")[:16].lower()
    return v if len(v) >= 8 and all(c in "0123456789abcdef" for c in v) else None


def account_label(v):
    return _plain(v or "", 8).upper() or None


def load_window(w):
    if isinstance(w, dict) and _num(w.get("used")) is not None:
        return {"used": _num(w["used"]), "resets_at": int(_num(w.get("resets_at"), 0)), "rx": _num(w.get("rx"), 0)}
    return None


class Bridge:
    def __init__(self):
        self.lock = threading.RLock()
        # registry snapshot
        self.local = {"busy": 0, "shell": 0, "waiting": 0, "idle": 0, "sessions": 0}
        self._ps_cache = {}            # (pid, startedAt) -> bool
        # hook-derived
        self.tool_times = []           # epoch seconds of recent tool calls
        self.tools_today = 0
        self.tools_date = self._today()
        self.subagents = {}            # session_id -> [count, last_event_ts]
        self.remote = {}               # session_id -> {"state": busy|idle|waiting, "ts": float}
        self.why = {}                  # session_id -> "PERMISSION: BASH" / "YOUR REPLY", from its last notification
        self.tracker = None            # tracking.Tracker when the history is switched on
        self.activity = []             # [(number, "edit" | "read" | ..., ts)], the latest ACTIVITY_KEPT
        self.last_hook = {}            # session_id -> ts of its last hook event (to spot stuck statuses)
        self.activity_seq = 0
        # usage
        self.five_hour = None          # {"used": float, "resets_at": int, "rx": float}
        self.est_start = None          # when work first began after the 5-hour window ended (a new window
        #                                starts then, though no status line has reported it yet)
        self.seven_day = None
        self.has5 = None               # the last status line report had a 5-hour window (None: no report yet)
        self.pace = pace.Pace(PACE_FILE)    # the weekly pace: its history, ladder and latest verdict
        # accounts: the main one (the fields above) is claimed by the first tagged report from
        # ~/.claude (see is_main); others {hash: {"label", "five_hour", "seven_day", "has5", "seen",
        # "pace"}}, first seen first
        self.main_acct = None
        self.main_label = None
        self.others = {}
        # theme
        self.theme = None
        self.theme_seq = 0
        self.last_active = 0.0
        self._dirty = False
        self._last_persist = 0.0
        self.load_state()

    # ------------------------------------------------------------ persistence
    @staticmethod
    def _today():
        return datetime.date.today().isoformat()

    def load_state(self):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(d, dict):
            return
        if d.get("tools_date") == self._today():
            self.tools_today = int(_num(d.get("tools_today"), 0))
        for key in ("five_hour", "seven_day"):
            setattr(self, key, load_window(d.get(key)))
        self.main_acct = account_id(d.get("main_acct"))
        self.main_label = account_label(d.get("main_label"))
        for a in d.get("accounts") or []:
            acct = account_id(a.get("acct")) if isinstance(a, dict) else None
            if acct and acct != self.main_acct:
                self.others[acct] = {"label": account_label(a.get("label")) or "ACCT",
                                     "five_hour": load_window(a.get("five_hour")),
                                     "seven_day": load_window(a.get("seven_day")),
                                     "has5": a.get("has5") if isinstance(a.get("has5"), bool) else None,
                                     "seen": _num(a.get("seen"), 0), "pace": pace.Pace(self._pace_file(acct))}
        t = LEGACY_THEMES.get(d.get("theme"), d.get("theme"))
        self.theme = t if t in THEMES else None
        self.theme_seq = int(_num(d.get("theme_seq"), 0))
        self.last_active = _num(d.get("last_active"), 0.0)
        self.est_start = _num(d.get("est_start"), None)
        self.has5 = d.get("has5") if isinstance(d.get("has5"), bool) else None

    @staticmethod
    def _pace_file(acct):
        return os.path.join(STATE_DIR, "pace-%s.json" % acct)

    def persist(self, force=False):
        now = time.time()
        with self.lock:
            self.pace.save(force)          # its own file, written at most once a minute
            for a in self.others.values():
                a["pace"].save(force)
            if not (self._dirty or force):
                return
            if not force and now - self._last_persist < PERSIST_INTERVAL:
                return
            d = {"tools_today": self.tools_today, "tools_date": self.tools_date,
                 "five_hour": self.five_hour, "seven_day": self.seven_day, "est_start": self.est_start,
                 "has5": self.has5, "theme": self.theme, "theme_seq": self.theme_seq, "last_active": self.last_active,
                 "main_acct": self.main_acct, "main_label": self.main_label,
                 "accounts": [{"acct": k, "label": a["label"], "five_hour": a["five_hour"], "seven_day": a["seven_day"],
                               "has5": a["has5"], "seen": a["seen"]} for k, a in self.others.items()]}
            self._dirty = False
            self._last_persist = now
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(d, f)
            os.replace(tmp, STATE_FILE)
        except OSError as e:
            log("persist failed: %s" % e)

    # ------------------------------------------------------------ registry scan
    def _is_claude(self, pid, started):
        key = (pid, started)
        hit = self._ps_cache.get(key)
        if hit is not None:
            return hit
        cmd = portable.pid_command(pid).lower()
        if portable.WINDOWS:
            # only the program's path is known there: claude.exe, or node/bun running Claude Code
            name = os.path.basename(cmd)
            ok = "claude" in cmd or name in ("node.exe", "bun.exe")
        else:
            ok = "claude" in cmd
        self._ps_cache[key] = ok
        return ok

    def scan(self):
        counts = {"busy": 0, "shell": 0, "waiting": 0, "idle": 0, "sessions": 0, "stale": 0}
        now = time.time()
        waiting_list = []      # (display name, epoch seconds it started waiting)
        live_keys = set()
        paths = []
        for folder in session_dirs():
            try:
                paths += [os.path.join(folder, n) for n in os.listdir(folder)]
            except OSError:
                pass
        for path in paths:
            if not path.endswith(".json"):
                continue          # never touch the .key files
            try:
                with open(path) as f:
                    d = json.load(f)
            except (OSError, ValueError):
                continue
            if not isinstance(d, dict):
                continue
            pid = d.get("pid")
            if not portable.pid_alive(pid):
                continue
            started = d.get("startedAt")
            live_keys.add((pid, started))
            if not self._is_claude(pid, started):
                continue
            if d.get("kind", "interactive") not in COUNTED_KINDS:
                continue
            status = d.get("status")
            counts["sessions"] += 1
            if status in ("busy", "shell"):
                changed = d.get("statusUpdatedAt")
                seen = max(changed / 1000.0 if isinstance(changed, (int, float)) else 0.0,
                           self.last_hook.get(str(d.get("sessionId") or ""), 0.0))
                if now - seen > STALE_S:
                    counts["stale"] += 1
                    status = "idle"
            if status in ("busy", "shell", "waiting"):
                counts[status] += 1
                if status == "waiting":
                    since = d.get("statusUpdatedAt")
                    started = d.get("startedAt")
                    folder = os.path.basename(str(d.get("cwd") or "").rstrip("/"))
                    waiting_list.append((_badge_name(d), since / 1000.0 if isinstance(since, (int, float)) else time.time(),
                                         _plain(folder), str(d.get("sessionId") or ""),
                                         started / 1000.0 if isinstance(started, (int, float)) else None,
                                         bool(d.get("name"))))
            else:
                counts["idle"] += 1
        # drop cache entries for processes that went away
        for key in list(self._ps_cache):
            if key not in live_keys:
                del self._ps_cache[key]
        counts["waiting_list"] = sorted(waiting_list, key=lambda w: w[1])[:4]
        with self.lock:
            self.local = counts
            if counts["busy"] or counts["shell"]:
                self.last_active = time.time()
                self._dirty = True

    # ------------------------------------------------------------ inputs
    def on_hook(self, d):
        now = time.time()
        sid = str(d.get("session_id") or "")[:128]
        event = str(d.get("event") or "")[:64]
        host = str(d.get("host") or "")[:255]
        with self.lock:
            if sid:
                self.last_hook[sid] = now
                if len(self.last_hook) > 200:
                    for k in [k for k, ts in self.last_hook.items() if now - ts > STALE_S]:
                        del self.last_hook[k]
            today = self._today()
            if today != self.tools_date:
                self.tools_date, self.tools_today = today, 0
            if self.tracker is not None:
                if event in TOOL_EVENTS:
                    self.tracker.event("tool")
                elif event == "UserPromptSubmit":
                    self.tracker.event("prompt")
                elif event == "Stop":
                    self.tracker.event("turn")
            if (self.est_start is None and self.five_hour and event in BUSY_EVENTS
                    and self.five_hour.get("resets_at") and now > self.five_hour["resets_at"]
                    and (self.five_hour.get("rx") or 0) < self.five_hour["resets_at"] + 60):
                self.est_start = now
                self._dirty = True
            if event in TOOL_EVENTS:
                self.tool_times.append(now)
                self.tools_today += 1
            kind = EVENT_ACTIVITY.get(event) or (TOOL_ACTIVITY.get(str(d.get("tool") or ""))
                                                 if event == "PostToolUse" else None)
            if kind:
                self.activity_seq += 1
                self.activity = (self.activity + [(self.activity_seq, kind, now)])[-ACTIVITY_KEPT:]
            if sid:
                if event == "Notification":
                    why, tool = str(d.get("why") or ""), str(d.get("tool") or "")
                    tool = "".join(ch for ch in tool if ch.isalnum() or ch == "_")[:20].upper()
                    self.why[sid] = ("PERMISSION: " + tool if tool else "PERMISSION") if why == "permission" \
                        else ("A QUESTION" if why == "question" else ("YOUR REPLY" if why == "input" else ""))
                elif event in BUSY_EVENTS or event in ("Stop", "SessionEnd"):
                    self.why.pop(sid, None)            # it moved on: the old reason no longer applies
                if event == "SubagentStart":
                    c = self.subagents.get(sid, [0, now])
                    self.subagents[sid] = [c[0] + 1, now]
                elif event == "SubagentStop":
                    c = self.subagents.get(sid, [0, now])
                    self.subagents[sid] = [max(0, c[0] - 1), now]
                elif event in ("Stop", "SessionEnd"):
                    self.subagents.pop(sid, None)
                elif sid in self.subagents:
                    self.subagents[sid][1] = now
                if (host and host != HOSTNAME) or not os.path.isdir(SESSIONS_DIR):
                    # another computer, or a Claude Code without session files here: count the
                    # session from its hook events instead
                    old_state = self.remote.get(sid, {}).get("state", "idle")
                    if event in ("Stop", "SessionEnd"):
                        state = "idle"
                    elif event == "Notification":
                        # blocked on you: a permission prompt or a question. Claude Code's idle
                        # reminder ("waiting for your input", a minute after a turn ends) means the
                        # turn is done, as this computer's own session files would say.
                        why = str(d.get("why") or "")
                        state = "waiting" if why in ("permission", "question") else \
                            ("idle" if why == "input" else old_state)
                    elif event in BUSY_EVENTS or event == "SubagentStop":
                        state = "busy"
                    else:
                        state = old_state
                    if event == "SessionEnd":
                        self.remote.pop(sid, None)
                    else:
                        entry = {"state": state, "ts": now, "host": host or HOSTNAME}
                        old = self.remote.get(sid) or {}
                        for k in ("name", "folder"):   # sent with a few events (cc_hook.NAMED_EVENTS); kept
                            v = d.get(k) or old.get(k)
                            if v:
                                entry[k] = _plain(v, 40)
                        self.remote[sid] = entry
            if event not in ("Stop", "SessionEnd", "Notification"):
                self.last_active = now
            self._dirty = True

    def track(self):
        """Feed the history (when it is on): who is waiting right now, and the usage so far."""
        if self.tracker is None:
            return
        now = time.time()
        with self.lock:
            local = list(self.local.get("waiting_list", []))
            why = dict(self.why)
            remote = [(sid, dict(r)) for sid, r in self.remote.items()
                      if r["state"] == "waiting" and now - r["ts"] <= REMOTE_EXPIRE_S]
            five, seven = self.five_hour, self.seven_day
        waiting = [(sid, name, HOSTNAME.split(".")[0], why.get(sid, "")) for name, _, _, sid, _, _ in local]
        waiting += [(sid, r.get("name") or r.get("folder"), str(r.get("host") or "").split(".")[0], why.get(sid, ""))
                    for sid, r in remote]
        self.tracker.observe(now, waiting)
        w5, w7 = self._window(five, now, self.last_active, self.est_start, 5 * 3600), self._window(seven, now, self.last_active)
        self.tracker.usage(w5["used"] if w5 else None, w7["used"] if w7 else None)    # None: unknown, skipped

    def is_main(self, acct, default):
        """Whether a report tagged acct is the main account's (the lock is held). An untagged one,
        from an older status line, is. The main account is claimed by the first tagged report from
        a default config folder (~/.claude), or by any tagged report while nothing is known yet."""
        if acct is None or acct == self.main_acct:
            return True
        if self.main_acct is None and acct not in self.others and (
                default or (self.five_hour is None and self.seven_day is None)):
            self.main_acct = acct
            self._dirty = True
            return True
        return False

    def on_usage(self, d):
        rl = d.get("rate_limits")
        if not isinstance(rl, dict):
            return False
        now = time.time()
        changed = False
        acct, label = account_id(d.get("acct")), account_label(d.get("label"))
        with self.lock:
            if not self.is_main(acct, bool(d.get("default"))):
                return self._on_other(acct, label, rl, now)
            if label and label != self.main_label:
                self.main_label = label
                self._dirty = True
            if isinstance(rl.get("seven_day"), dict):
                # a plan without a 5-hour limit reports only the weekly window (the "auto" limit mode)
                has5 = isinstance(rl.get("five_hour"), dict) and _num(rl["five_hour"].get("used_percentage")) is not None
                if has5 != self.has5:
                    self.has5 = has5
                    changed = True
            for key in ("five_hour", "seven_day"):
                w = rl.get(key)
                new = merge_window(getattr(self, key), w, now) if isinstance(w, dict) else None
                if new is None:
                    continue
                setattr(self, key, new)
                if key == "five_hour":
                    self.est_start = None        # the new window is known now: no estimate needed
                changed = True
            if changed:
                self._dirty = True
            self.pace.report(now, self.five_hour, self.seven_day)
        return changed

    def _on_other(self, acct, label, rl, now):
        """A report from an account other than the main one (the lock is held)."""
        a = self.others.get(acct)
        if a is None:
            for k in [k for k, o in self.others.items() if now - o["seen"] > ACCOUNT_FORGET_S]:
                del self.others[k]
            if len(self.others) >= ACCOUNTS_MAX:      # full: the one quiet longest makes room
                del self.others[min(self.others, key=lambda k: self.others[k]["seen"])]
            a = self.others[acct] = {"label": label or "ACCT", "five_hour": None, "seven_day": None,
                                     "has5": None, "seen": now, "pace": pace.Pace(self._pace_file(acct))}
        a["seen"] = now
        if label:
            a["label"] = label
        if isinstance(rl.get("seven_day"), dict):
            a["has5"] = isinstance(rl.get("five_hour"), dict) and _num(rl["five_hour"].get("used_percentage")) is not None
        for key in ("five_hour", "seven_day"):
            w = rl.get(key)
            new = merge_window(a[key], w, now) if isinstance(w, dict) else None
            if new is not None:
                a[key] = new
        a["pace"].report(now, a["five_hour"], a["seven_day"])
        self._dirty = True
        return True

    def answer(self, d):
        """What /usage answers a status line with: its own account's weekly pace and limit mode."""
        with self.lock:
            a = self.others.get(account_id(d.get("acct")))
            if a is not None:
                return {"pace": a["pace"].out, "mode": self.acct_mode(a["has5"])}
            return {"pace": self.pace.out, "mode": self.limit_mode()}

    def pace_step(self):
        """Once a scan: the weekly pace takes in whether agents work and steps its ladder."""
        s = self.status()
        room = pace.room_enabled(STATE_DIR)
        now = time.time()
        with self.lock:
            self.pace.step(now, s["seven_day"], s["level"] >= 2, room)
            for k in [k for k, a in self.others.items() if now - a["seen"] > ACCOUNT_FORGET_S]:
                del self.others[k]
                self._dirty = True
            for a in self.others.values():
                a["pace"].step(now, self._window(a["seven_day"], now), s["level"] >= 2, room)

    def limit_mode(self):
        """What the hearts show: "5h", or "week" for a plan with only a weekly limit (pace.LIMIT_MODES)."""
        return self.acct_mode(self.has5)

    @staticmethod
    def acct_mode(has5):
        """The limit mode for an account whose last report had a 5-hour window (has5) or didn't."""
        mode = pace.limit_setting(STATE_DIR)
        if mode == "auto":
            mode = "week" if has5 is False else "5h"
        return mode

    def account_row(self, a, now):
        """Another account's row on the badge. Its hearts follow whichever of its limits has less
        left, and count down to that limit's reset: l label, h half hearts left (None: unknown), e
        half hearts likely left at the weekly reset (None: no forecast), r the reset (epoch s), w
        which limit ("5h" or "wk"), u how fresh its numbers are (ok, old or none)."""
        mode = self.acct_mode(a["has5"])
        five = self._window(a["five_hour"], now) if mode == "5h" else None
        seven = self._window(a["seven_day"], now)
        b = None
        for w in (five, seven):
            if w and w["used"] is not None and (b is None or w["used"] > b["used"]):
                b = w
        hearts = end = None
        if b is not None:
            hearts = max(0, min(20, int(round((100.0 - b["used"]) / 5.0))))
            pc = a["pace"].out
            if b is seven and pc and pc.get("f") is not None:
                end = max(0, min(hearts, int(round((100.0 - pc["f"]) / 5.0))))
        state = usage_state(a["five_hour"] if mode == "5h" else None, a["seven_day"], five, now)["state"]
        return {"l": a["label"], "h": hearts, "e": end, "r": b["resets_at"] if b else None,
                "w": "5h" if b is not None and b is five else "wk", "u": state}

    def set_theme(self, theme):
        theme = LEGACY_THEMES.get(theme, theme)
        if theme in ("auto", None, ""):
            theme = None
        elif theme not in THEMES:
            return False
        with self.lock:
            self.theme = theme
            self.theme_seq += 1
            self._dirty = True
        return True

    # ------------------------------------------------------------ output
    @staticmethod
    def _window(w, now, last_active=0.0, est_start=None, length=0):
        """A usage window as the badge should show it. Once its reset time has passed, usage is truly
        0 until your next message starts a new window. But if there has been work since and no status
        line has reported the new window yet (a session without a terminal, like a background one,
        never reports, and an interactive one reports a window only after its own first answer in
        it), the window's usage is unknown. Its end can still be estimated: the window began with
        the first work after the old one ended, so it ends `length` seconds after that. Those come
        back as used None, est 1; with no estimate possible, stale 1."""
        if not w:
            return None
        resets = int(w.get("resets_at") or 0)
        used = float(w.get("used") or 0.0)
        if resets and now > resets:
            if last_active > resets + 60 and (w.get("rx") or 0) < resets:
                if est_start and length and est_start > resets:
                    return {"used": None, "resets_at": int(est_start + length), "est": 1}
                return {"used": None, "resets_at": resets, "stale": 1}
            used = 0.0
        return {"used": round(used, 1), "resets_at": resets}

    def status(self):
        now = time.time()
        with self.lock:
            cutoff = now - TPM_WINDOW_S
            self.tool_times = [t for t in self.tool_times if t >= cutoff]
            tpm = len(self.tool_times)
            for sid in [s for s, c in self.subagents.items() if now - c[1] > SUBAGENT_EXPIRE_S or c[0] <= 0]:
                del self.subagents[sid]
            subagents = sum(c[0] for c in self.subagents.values())
            for sid in [s for s, r in self.remote.items() if now - r["ts"] > REMOTE_EXPIRE_S]:
                del self.remote[sid]
            remote_busy = sum(1 for r in self.remote.values()
                              if r["state"] == "busy" and now - r["ts"] <= REMOTE_BUSY_S)
            remote_waiting = sum(1 for r in self.remote.values()
                                 if r["state"] == "waiting" and now - r["ts"] <= REMOTE_EXPIRE_S)
            remote_live = sum(1 for r in self.remote.values() if r["state"] != "idle" or now - r["ts"] <= REMOTE_BUSY_S)
            remote_waiting_list = [(sid, dict(r)) for sid, r in self.remote.items()
                                   if r["state"] == "waiting" and now - r["ts"] <= REMOTE_EXPIRE_S]
            loc = dict(self.local)
            if self._today() != self.tools_date:
                self.tools_date, self.tools_today = self._today(), 0
            tools_today = self.tools_today
            mode = self.limit_mode()
            raw5 = self.five_hour if mode == "5h" else None      # weekly only: an old 5-hour window means nothing
            five = self._window(raw5, now, self.last_active, self.est_start, 5 * 3600)
            seven = self._window(self.seven_day, now, self.last_active)
            theme, theme_seq, last_active = self.theme, self.theme_seq, self.last_active
            pc = self.pace.out
            accounts = [self.account_row(a, now) for a in self.others.values()]
            label = self.main_label
            live = {w[3] for w in loc.get("waiting_list", [])}
            for sid in [s for s in self.why if s not in live and s not in self.remote]:
                del self.why[sid]
            why = dict(self.why)
            activity = [[n, kind, int((now - ts) * 1000)] for n, kind, ts in self.activity
                        if now - ts <= ACTIVITY_MAX_AGE_S]

        busy = loc["busy"] + loc["shell"] + remote_busy
        waiting = loc["waiting"] + remote_waiting
        load = loc["busy"] + 0.5 * loc["shell"] + remote_busy + 0.5 * subagents
        if load >= LEVEL4_LOAD or tpm >= LEVEL4_TPM:
            level = 4
        elif load >= LEVEL3_LOAD or tpm >= LEVEL3_TPM:
            level = 3
        elif load > 0:
            level = 2
        elif (last_active and now - last_active < RECENT_ACTIVE_S) or waiting > 0:
            level = 1
        else:
            level = 0

        basis = five or seven
        hearts = None
        if five is not None and five.get("est"):
            hearts = 20                    # a window just begun: full, marked as an estimate
        elif basis is not None and basis["used"] is not None:
            hearts = int(round((100.0 - basis["used"]) / 5.0))
            hearts = max(0, min(20, hearts))
        # weekly only: the hearts likely left when the week resets, at this pace (the pace's forecast)
        hearts_end = None
        if mode == "week" and hearts is not None and pc and pc.get("f") is not None:
            hearts_end = max(0, min(hearts, int(round((100.0 - pc["f"]) / 5.0))))

        return {
            "v": 1,
            "bridge": BRIDGE_ID or bridge_id(),      # which bridge this is (the badge pairs with it over USB)
            "join": JOIN_URL,                        # where another computer joins it (the installer finds it)
            "ts": int(now),
            "now_ms": int(time.time() * 1000),
            "level": level,
            "busy": busy,
            "waiting": waiting,
            # which sessions are waiting, longest first (the badge's waiting bar and Desktop mode):
            # n name, s seconds waiting, d folder, w what it needs, a session age, i the start of its
            # id and u 1 when it has no name of its own (the badge then shows "folder · id")
            "waiting_list": waiting_entries(loc, remote_waiting_list, why, now),
            "idle": loc["idle"],
            # what the agents just did: [number, category, ms ago], oldest first (badge animations)
            "ev": activity,
            "sessions": loc["sessions"] + remote_live,
            "subagents": subagents,
            "tpm": tpm,
            "tools_today": tools_today,
            "five_hour": five,
            "seven_day": seven,
            # why the hearts show what they show: ok (a recent report), old (no report for 30 minutes or
            # more), est (a new window the bridge has not been told about), stale, or none (never)
            "usage": usage_state(raw5, self.seven_day, five, now),
            # the weekly pace: is the week on course to reach its limit before the reset (bridge/pace.py)
            "pace": pc,
            # what the hearts show: "5h" (the 5-hour window) or "week" (a plan with only a weekly
            # limit; then hearts_end is how many half hearts are likely left at the reset)
            "mode": mode,
            "hearts": hearts,
            "hearts_end": hearts_end,
            # more than one Claude account: the main one's label (it drives everything above) and a
            # row for each other one (see account_row), first seen first
            "label": label,
            "accounts": accounts,
            "theme": theme,
            "theme_seq": theme_seq,
            "last_active": int(last_active or 0),
            "clock": time.strftime("%H:%M"),
        }


BRIDGE = None
TOKEN = None          # the bridge's key, set in main()
LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
SEALED = "application/x-burn-helper-sealed"
REPLAY_S = 120        # a sealed message older (or newer) than this is turned down
_seen = {}            # nonce -> when it may be forgotten: each sealed message is taken once
_seen_lock = threading.Lock()
START = time.time()


def fresh_nonce(nonce, t, now=None):
    """True the first time a sealed message's nonce comes by within REPLAY_S of its time t."""
    now = time.time() if now is None else now
    try:
        if abs(now - float(t)) > REPLAY_S:
            return False
    except (TypeError, ValueError):
        return False
    with _seen_lock:
        for k in [k for k, until in _seen.items() if until < now]:
            del _seen[k]
        if nonce in _seen:
            return False
        _seen[nonce] = now + 2 * REPLAY_S
    return True


class Handler(BaseHTTPRequestHandler):
    """On this computer (loopback), plain JSON as ever. From anywhere else every message both ways
    is sealed with the bridge's key (seal.py): what you work on and the key never cross the network
    in the clear, and a message that isn't sealed with the key, or comes by twice, is turned down."""
    server_version = "BurnHelperBridge/1"
    protocol_version = "HTTP/1.0"     # badge client reads until close
    sealed = False                    # this request came sealed, so the answer goes back sealed

    def log_message(self, fmt, *args):
        if VERBOSE:
            log("%s %s" % (self.client_address[0], fmt % args))

    def _local(self):
        return self.client_address[0] in LOOPBACK

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, separators=(",", ":"))
        if isinstance(body, str):
            body = body.encode("utf-8")
        if self.sealed and code == 200 and ctype == "application/json":
            body, ctype = seal.seal(TOKEN, body), SEALED
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            self._send(413, {"error": "body too large"})
            return None
        raw = self.rfile.read(n) if n else b""
        if seal.is_sealed(raw):
            # {"t": when it was sealed, "d": the message}: the time and the nonce stop a replay
            inner = seal.unseal(TOKEN, raw) if TOKEN else None
            try:
                env_ = json.loads(inner.decode("utf-8")) if inner is not None else None
            except (ValueError, UnicodeDecodeError):
                env_ = None
            if not isinstance(env_, dict) or not fresh_nonce(raw[len(seal.MAGIC):len(seal.MAGIC) + seal.NONCE],
                                                             env_.get("t")):
                self._send(403, {"error": "key needed"})
                return None
            self.sealed = True
            d = env_.get("d")
        elif not self._local():
            self._send(403, {"error": "key needed"})
            return None
        else:
            try:
                d = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                self._send(400, {"error": "bad json"})
                return None
        if not isinstance(d, dict):
            self._send(400, {"error": "expected object"})
            return None
        return d

    def do_GET(self):
        try:
            path = self.path.split("?", 1)[0]
            if path == "/status":
                if self._local():
                    self._send(200, BRIDGE.status())
                elif TOKEN:
                    self.sealed = True
                    self._send(200, BRIDGE.status())
                else:
                    self._send(403, {"error": "key needed"})
            elif path in ("/", "/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif path == "/health":
                self._send(200, {"ok": True, "uptime": int(time.time() - START), "join": JOIN_URL,
                                 "sealed": 1})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001 - never let a request kill the server
            log("GET error: %r" % e)
            self._send(500, {"error": "internal"})

    def do_POST(self):
        try:
            path = self.path.split("?", 1)[0]
            d = self._read_json()
            if d is None:
                return
            if path == "/hook":
                BRIDGE.on_hook(d)
                self._send(200, {"ok": True})
            elif path == "/usage":
                ok = BRIDGE.on_usage(d)
                # the status line shows its account's pace, and in weekly-only mode where the week likely ends
                self._send(200, dict(BRIDGE.answer(d), ok=ok))
            elif path == "/theme":
                ok = BRIDGE.set_theme(d.get("theme"))
                if ok:
                    s = BRIDGE.status()
                    self._send(200, {"ok": True, "theme": s["theme"], "theme_seq": s["theme_seq"]})
                else:
                    self._send(400, {"error": "unknown theme", "themes": list(THEMES) + ["auto"]})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            log("POST error: %r" % e)
            self._send(500, {"error": "internal"})


def bridge_id():
    """This bridge's id, made once and kept in the state folder. The badge learns it over the USB
    cable and from then on listens only to this bridge's beacon, so a second bridge on the same
    network can't pull it away."""
    path = os.path.join(STATE_DIR, "bridge_id")
    try:
        with open(path) as f:
            v = f.read().strip()
        if v:
            return v
    except OSError:
        pass
    import secrets as _secrets
    v = _secrets.token_hex(4)
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(v)
    except OSError:
        pass
    return v


BRIDGE_ID = None
JOIN_URL = None       # where other computers join this bridge (its Tailscale address when it has one)


def find_join_url(port):
    """Where other computers join this bridge: its Tailscale address, else its local one. Tailscale
    can start after the bridge at sign-in, so keep asking for a few minutes."""
    global JOIN_URL
    for _ in range(10):
        ip = portable.tailscale_ip()
        if ip:
            JOIN_URL = "http://%s:%d" % (ip, port)
            log("join address %s" % JOIN_URL)
            return
        JOIN_URL = "http://%s:%d" % (lan_ip(), port)
        time.sleep(30)
    log("join address %s (Tailscale isn't running here)" % JOIN_URL)


def joined_to(home=HOME):
    """The bridge this computer is joined to (install.py --bridge put its address in Claude Code's
    settings.json), or None. A bridge started here anyway must not take the badge: the badge pairs
    with whichever bridge feeds it over its USB cable, and then follows only that one on Wi-Fi."""
    url = env("BRIDGE_URL")
    if not url:
        try:
            with open(os.path.join(home, ".claude", "settings.json"), encoding="utf-8") as f:
                url = (json.load(f).get("env") or {}).get("BURN_HELPER_BRIDGE_URL")
        except (OSError, ValueError, AttributeError):
            url = None
    host = str(url or "").split("//")[-1].split("/")[0].rsplit(":", 1)[0].strip("[]")
    return None if host in ("", "127.0.0.1", "localhost", "::1") else url


def load_relay():
    try:
        with open(RELAY_FILE) as f:
            r = json.load(f)
        if isinstance(r, dict) and str(r.get("url", "")).startswith("https://") and len(str(r.get("key", ""))) >= 32:
            return {"url": str(r["url"]).rstrip("/"), "key": str(r["key"])}
    except (OSError, ValueError):
        pass
    return None


class RelayHandler(BaseHTTPRequestHandler):
    """The internet-facing side: read-only status, and only for callers with the key.

    Keeps connections open (HTTP/1.1) so a badge on the relay does one TLS handshake, not one
    per poll. Nothing here can change the bridge's state.
    """
    server_version = "BurnHelperRelay"
    sys_version = ""                  # do not advertise the Python version to the internet
    protocol_version = "HTTP/1.1"
    timeout = 20                      # drop idle connections; the badge polls every 5 s

    def log_message(self, fmt, *args):
        if VERBOSE:
            log("relay %s" % (fmt % args))

    def _send(self, code, body):
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self.close_connection = True

    def do_GET(self):
        try:
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._send(200, {"ok": True})
                return
            # the key only in a header: a key in the URL would end up in logs
            given = self.headers.get("X-Burn-Helper-Key") or ""
            if path != "/status" or RELAY is None or not hmac.compare_digest(given.encode(), RELAY["key"].encode()):
                self._send(404, {"error": "not found"})
                return
            self._send(200, BRIDGE.status())
        except Exception as e:  # noqa: BLE001 - never let a request kill the server
            log("relay error: %r" % e)
            self._send(500, {"error": "internal"})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        # HTTPServer.server_bind calls socket.getfqdn(), which can stall ~5 s on macOS.
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


class RelayServer(Server):
    """The relay faces the internet: cap open connections so nobody can tie up the bridge."""
    MAX_CONNECTIONS = 8

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(self.MAX_CONNECTIONS)
        Server.__init__(self, *args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)        # full: drop it rather than queue it
            return
        try:
            Server.process_request(self, request, client_address)
        except Exception:  # noqa: BLE001
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            Server.process_request_thread(self, request, client_address)
        finally:
            self.slots.release()


def scan_loop():
    last_summary = 0.0
    while True:
        try:
            BRIDGE.scan()
            BRIDGE.persist()
            BRIDGE.track()
            BRIDGE.pace_step()
            now = time.time()
            if now - last_summary >= 60:
                last_summary = now
                s = BRIDGE.status()
                pc = s["pace"]
                log("level=%d busy=%d waiting=%d sessions=%d stuck=%d subagents=%d tpm=%d today=%d hearts=%s theme=%s pace=%s" % (
                    s["level"], s["busy"], s["waiting"], s["sessions"], BRIDGE.local.get("stale", 0), s["subagents"],
                    s["tpm"], s["tools_today"], s["hearts"], s["theme"],
                    "%d/%d%%/%d" % (pc["s"], pc["p"], pc["f"]) if pc else None))
        except Exception as e:  # noqa: BLE001
            log("scan error: %r" % e)
        time.sleep(SCAN_INTERVAL)


def beacon_loop(port):
    msg = ("TUFTYBRIDGE 1 %d %s" % (port, BRIDGE_ID or bridge_id())).encode()
    sock = None
    while True:
        try:
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(msg, ("255.255.255.255", BEACON_PORT))
        except OSError:
            try:
                if sock:
                    sock.close()
            except OSError:
                pass
            sock = None
        time.sleep(BEACON_INTERVAL)


def find_badge_ports():
    """Serial ports of plugged-in Tufty badges, found by USB product name on macOS."""
    if not portable.MAC:
        return portable.find_ports()
    try:
        out = subprocess.run(["ioreg", "-p", "IOUSB", "-l", "-w0"], capture_output=True,
                             text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    ports = []
    for block in out.split("+-o ")[1:]:
        if "Tufty" not in block:
            continue
        for line in block.splitlines():
            if '"locationID" = ' in line:
                try:
                    loc = int(line.split("=")[1].strip())
                except ValueError:
                    continue
                prefix = "%x" % (loc >> 16)
                import glob
                ports += sorted(glob.glob("/dev/cu.usbmodem%s*" % prefix))
                break
    return ports


def usb_locked():
    try:
        with open(USB_LOCK) as f:
            pid = int(f.read().strip() or 0)
    except (OSError, ValueError):
        return False
    return portable.pid_alive(pid)


def usb_loop():
    missing = portable.serial_missing()
    if missing:
        log("usb: the USB cable link is off: %s. Wi-Fi still works." % missing)
        return
    fd = None
    port = None
    last_find = 0.0
    while True:
        try:
            if usb_locked():
                if fd is not None:
                    fd.close()
                    fd = None
                    log("usb: paused while a badge tool uses %s" % port)
                time.sleep(1.0)
                last_find = time.time() + 3   # give the badge time to reboot after a deploy
                continue
            if fd is None and time.time() - last_find > 5:
                last_find = time.time()
                ports = find_badge_ports()
                if ports:
                    port = ports[0]
                    fd = portable.Port(port, write_only=True)
                    log("usb: tethered to badge on %s" % port)
            if fd is not None:
                # the bridge's key, and the relay's address and key, go to the badge over the cable
                # only, never over Wi-Fi
                s = dict(BRIDGE.status(), key=TOKEN)
                if RELAY is not None:
                    s["relay"] = RELAY
                line = "@TUFTY " + json.dumps(s, separators=(",", ":")) + "\n"
                fd.write(line.encode(), wait=False)   # never stall the bridge on a busy port
        except OSError as e:
            if fd is not None:
                fd.close()
                fd = None
                log("usb: badge on %s went away (%s)" % (port, e.__class__.__name__))
        time.sleep(USB_INTERVAL)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    global BRIDGE, VERBOSE, RELAY, BRIDGE_ID, TOKEN
    ap = argparse.ArgumentParser(description="Burn Helper: Claude Code activity bridge for the badge")
    ap.add_argument("--port", type=int, default=int(env("PORT") or DEFAULT_PORT))
    ap.add_argument("--bind", default=env("BIND") or "0.0.0.0")
    ap.add_argument("--no-beacon", action="store_true", help="do not broadcast the UDP discovery beacon")
    ap.add_argument("--no-usb", action="store_true", help="do not push status to a USB-connected badge")
    ap.add_argument("--here", action="store_true",
                    help="be the badge's bridge although this computer is joined to another one")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--log", metavar="PATH", help="append the log here instead of printing it")
    args = ap.parse_args()
    VERBOSE = args.verbose
    if args.log or sys.stderr is None:
        # the Windows login item runs pythonw, which has no console to print to
        path = args.log or os.path.join(STATE_DIR, "bridge.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        sys.stderr = sys.stdout = open(path, "a", encoding="utf-8", buffering=1)
    for old in OLD_STATE_DIRS:
        if not os.path.exists(STATE_DIR) and os.path.isdir(old) and not env("STATE_DIR"):
            try:
                os.rename(old, STATE_DIR)
                log("moved state from %s to %s" % (old, STATE_DIR))
            except OSError:
                pass
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, "bridge.pid"), "w") as f:
            f.write(str(os.getpid()))      # so the installer can restart it where there is no launchd
    except OSError as e:
        log("could not write bridge.pid: %s" % e)
    BRIDGE_ID = bridge_id()
    log("bridge id %s" % BRIDGE_ID)
    joined = None if args.here else joined_to()
    if joined:
        # a badge on this computer's cable (being developed here, say) stays with its bridge
        args.no_beacon = args.no_usb = True
        log("this computer is joined to the bridge at %s: no beacon or USB link here, so the badge "
            "stays with that one (--here to be the badge's bridge anyway)" % joined)
    TOKEN = portable.bridge_key(STATE_DIR)
    if TOKEN:
        log("key: other computers, the badge and the phone panel need it (install.py --join-help)")
    else:
        log("key: could not be saved in %s, so only this computer can reach the bridge" % STATE_DIR)
    tracker = None
    if tracking.is_enabled(STATE_DIR):
        try:
            tracker = tracking.Tracker(os.path.join(STATE_DIR, "tracking.db"))
            log("history on: session waits and daily usage go to %s" % os.path.join(STATE_DIR, "tracking.db"))
        except Exception as e:  # noqa: BLE001
            log("history could not start (%r); carrying on without it" % (e,))
    threading.Thread(target=find_join_url, args=(args.port,), daemon=True).start()
    BRIDGE = Bridge()
    BRIDGE.tracker = tracker
    BRIDGE.scan()
    threading.Thread(target=scan_loop, daemon=True).start()
    if not args.no_beacon:
        threading.Thread(target=beacon_loop, args=(args.port,), daemon=True).start()
    if not args.no_usb:
        threading.Thread(target=usb_loop, daemon=True).start()
    RELAY = load_relay()
    if RELAY is not None:
        relay = RelayServer(("127.0.0.1", RELAY_PORT), RelayHandler)
        threading.Thread(target=relay.serve_forever, daemon=True).start()
        log("relay: %s -> 127.0.0.1:%d (Tailscale Funnel)" % (RELAY["url"], RELAY_PORT))
    httpd = Server((args.bind, args.port), Handler)
    try:
        import signal
        # launchd and `kill` end the bridge with SIGTERM: leave through the same door as Ctrl-C, so the
        # history (when on) writes out what it holds
        signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    except (ImportError, ValueError, OSError):
        pass
    log("listening on http://%s:%d/ (phone panel), badge JSON at /status, beacon %s" % (
        lan_ip(), args.port, "off" if args.no_beacon else "udp/%d" % BEACON_PORT))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        BRIDGE.persist(force=True)
        if tracker is not None:
            tracker.close()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Burn Helper</title>
<style>
:root{--bg:#101418;--card:#1b2128;--fg:#e8edf2;--dim:#8a96a3;--heart:#e8384f;--accent:#f2c14e;--on:#3a7d44}
@media (prefers-color-scheme: light){:root{--bg:#f4f1ea;--card:#fff;--fg:#1d232a;--dim:#5c6670;--on:#2f6b39}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 -apple-system,system-ui,sans-serif;padding:16px;max-width:520px;margin:0 auto}
h1{font-size:20px;margin:4px 0 12px}
.card{background:var(--card);border-radius:14px;padding:14px 16px;margin-bottom:12px}
.hearts{font-size:30px;letter-spacing:2px;color:var(--heart);line-height:1.1;word-break:break-all}
.cd{font-size:34px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:6px}.cd.soon{color:var(--accent)}.cd.now{color:var(--heart)}
.lvl{font-size:22px;font-weight:700}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px}
.k{color:var(--dim);font-size:13px}.v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:10px}
button{font:inherit;font-weight:600;padding:16px 10px;border-radius:12px;border:2px solid transparent;background:var(--bg);color:var(--fg);cursor:pointer}
button.on{border-color:var(--accent)}
.foot{color:var(--dim);font-size:12px;margin-top:8px}
.err{color:var(--heart)}
</style></head><body>
<h1>Burn Helper</h1>
<div class="card">
  <div class="k">Remaining 5-hour budget</div>
  <div class="hearts" id="hearts">…</div>
  <div class="k" id="usage">waiting for status line data</div>
  <div class="cd" id="cd5">--:--</div>
  <div class="k">until the 5-hour window resets · weekly resets in <span id="cd7">--</span></div>
</div>
<div class="card">
  <div class="lvl" id="level">…</div>
  <div class="grid" style="margin-top:10px">
    <div><div class="k">Busy agents</div><div class="v" id="busy">-</div></div>
    <div><div class="k">Waiting on you</div><div class="v" id="waiting">-</div></div>
    <div><div class="k">Open sessions</div><div class="v" id="sessions">-</div></div>
    <div><div class="k">Subagents</div><div class="v" id="subagents">-</div></div>
    <div><div class="k">Tool calls / min</div><div class="v" id="tpm">-</div></div>
    <div><div class="k">Tool calls today</div><div class="v" id="today">-</div></div>
  </div>
</div>
<div class="card">
  <div class="k" style="margin-bottom:8px">Badge theme</div>
  <div class="btns">
    <button data-t="hero">Zelda</button>
    <button data-t="gameshow">Running Man</button>
    <button data-t="chocolates">Forrest Gump</button>
    <button data-t="auto">Badge decides</button>
  </div>
</div>
<div class="foot" id="foot"></div>
<script>
const LEVELS=["Asleep","Awake","Walking","Running","Sprinting"];
function hearts(h){if(h===null||h===undefined)return"? ? ? ? ? ? ? ? ? ?";let s="";for(let i=0;i<10;i++){const r=h-i*2;s+=r>=2?"♥":r==1?"❥":"♡";}return s;}
function when(t){if(!t)return"";const d=new Date(t*1000);return d.toLocaleTimeString([], {hour:"numeric",minute:"2-digit"});}
function pct(w,label){if(!w)return"";return label+" "+Math.round(w.used)+"% used";}
let r5=null,r7=null,off=0;
function fmt(ms){if(ms===null)return"--:--";if(ms<=0)return ms>-60000?"RESET!":"FULL";const s=Math.floor(ms/1000),p=n=>String(n).padStart(2,"0");
if(s>=86400)return Math.floor(s/86400)+"d "+Math.floor(s%86400/3600)+"h";if(s>=3600)return Math.floor(s/3600)+"h "+p(Math.floor(s%3600/60))+"m";
if(s>=60)return Math.floor(s/60)+":"+p(s%60);if(s>=10)return (ms/1000).toFixed(3);return (ms/1000).toFixed(6);}
function frame(){const now=Date.now()+off+(performance.now()%1);const l5=r5?r5*1000-now:null,l7=r7?r7*1000-now:null;
const e=document.getElementById("cd5");e.textContent=fmt(l5);e.className="cd"+(l5!==null&&l5>-60000&&l5<=600000?(l5<=60000?" now":" soon"):"");
document.getElementById("cd7").textContent=fmt(l7);requestAnimationFrame(frame);}
requestAnimationFrame(frame);
// SEAL-JS: seal.py in JavaScript. Phone browsers keep crypto.subtle from plain-http pages, so
// SHA-256 is written out here; crypto.getRandomValues is allowed and makes the nonces.
const K256=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,
0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
function sha256(m){const l=m.length,n=((l+72)>>6)<<6,b=new Uint8Array(n);b.set(m);b[l]=0x80;const v=new DataView(b.buffer);
v.setUint32(n-8,Math.floor(l/0x20000000));v.setUint32(n-4,(l*8)>>>0);
const h=new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]),w=new Uint32Array(64);
for(let o=0;o<n;o+=64){for(let i=0;i<16;i++)w[i]=v.getUint32(o+i*4);
for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=((x>>>7|x<<25)^(x>>>18|x<<14)^(x>>>3))+w[i-7]+((y>>>17|y<<15)^(y>>>19|y<<13)^(y>>>10))+w[i-16];}
let [a,c,d,e,f,g,k,p]=h;
for(let i=0;i<64;i++){const t1=(p+((f>>>6|f<<26)^(f>>>11|f<<21)^(f>>>25|f<<7))+((f&g)^(~f&k))+K256[i]+w[i])|0,
t2=(((a>>>2|a<<30)^(a>>>13|a<<19)^(a>>>22|a<<10))+((a&c)^(a&d)^(c&d)))|0;p=k;k=g;g=f;f=(e+t1)|0;e=d;d=c;c=a;a=(t1+t2)|0;}
h[0]+=a;h[1]+=c;h[2]+=d;h[3]+=e;h[4]+=f;h[5]+=g;h[6]+=k;h[7]+=p;}
const out=new Uint8Array(32),ov=new DataView(out.buffer);for(let i=0;i<8;i++)ov.setUint32(i*4,h[i]);return out;}
function cat(...xs){const o=new Uint8Array(xs.reduce((s,x)=>s+x.length,0));let i=0;for(const x of xs){o.set(x,i);i+=x.length;}return o;}
function hmac(key,msg){const k=new Uint8Array(64);k.set(key);return sha256(cat(k.map(x=>x^0x5c),sha256(cat(k.map(x=>x^0x36),msg))));}
const TE=new TextEncoder(),MAGIC=TE.encode("BHS1");
function sealKeys(key){const raw=/^([0-9a-fA-F]{2})+$/.test(key)?new Uint8Array(key.match(/../g).map(x=>parseInt(x,16))):TE.encode(key);
return [hmac(raw,TE.encode("burn-helper seal enc")),hmac(raw,TE.encode("burn-helper seal mac"))];}
function stream(enc,nonce,data){const o=new Uint8Array(data.length);for(let i=0,n=0;i<data.length;i+=32,n++){
const c=new Uint8Array(4);new DataView(c.buffer).setUint32(0,n);const blk=hmac(enc,cat(nonce,c));
for(let j=0;j<32&&i+j<data.length;j++)o[i+j]=data[i+j]^blk[j];}return o;}
function seal(key,data,nonce){const [enc,mac]=sealKeys(key);nonce=nonce||crypto.getRandomValues(new Uint8Array(16));
const body=cat(MAGIC,nonce,stream(enc,nonce,data));return cat(body,hmac(mac,body));}
function isSealed(b){return b.length>=4&&MAGIC.every((x,i)=>b[i]===x);}
function unseal(key,box){if(!key||!isSealed(box)||box.length<52)return null;const [enc,mac]=sealKeys(key);
const body=box.subarray(0,box.length-32),tag=box.subarray(box.length-32),want=hmac(mac,body);let d=0;
for(let i=0;i<32;i++)d|=want[i]^tag[i];return d?null:stream(enc,body.subarray(4,20),body.subarray(20));}
// /SEAL-JS
// the key comes in the link's #k=... (a part of the address the browser never sends), is kept on
// this phone, and opens the bridge's sealed answers; it never leaves the phone. The address bar
// is cleared of it.
const KEY=(()=>{let k=(location.hash.match(/k=([0-9a-fA-F]+)/)||[])[1];
try{if(k)localStorage.setItem("bh_key",k);else k=localStorage.getItem("bh_key");}catch(e){}
if(location.hash)history.replaceState(null,"",location.pathname);return k||"";})();
function needKey(){const f=document.getElementById("foot");f.className="foot err";
f.textContent="This page needs the bridge's key. On the bridge computer run install.py --join-help and open the phone link it prints.";}
async function readReply(r){const b=new Uint8Array(await r.arrayBuffer());
if(!isSealed(b))return JSON.parse(new TextDecoder().decode(b));const p=unseal(KEY,b);
return p?JSON.parse(new TextDecoder().decode(p)):null;}
let theme=null;
async function tick(){
  try{
    const r=await fetch("/status",{cache:"no-store"});
    const s=r.status===403?null:await readReply(r);
    if(!s){needKey();return;}
    document.getElementById("hearts").textContent=hearts(s.hearts);
    const u=[pct(s.five_hour,"5h"),pct(s.seven_day,"7d")].filter(Boolean).join(" · ");
    document.getElementById("usage").textContent=u||"waiting for status line data";
    document.getElementById("level").textContent="Level "+s.level+": "+LEVELS[s.level];
    for(const k of["busy","waiting","sessions","subagents","tpm"])document.getElementById(k).textContent=s[k];
    document.getElementById("today").textContent=s.tools_today;
    theme=s.theme;r5=s.five_hour?s.five_hour.resets_at:null;r7=s.seven_day?s.seven_day.resets_at:null;if(s.now_ms)off=s.now_ms-Date.now();
    document.querySelectorAll("button").forEach(b=>b.classList.toggle("on",(b.dataset.t==="auto"&&!theme)||b.dataset.t===theme));
    document.getElementById("foot").textContent="Updated "+s.clock;document.getElementById("foot").className="foot";
  }catch(e){const f=document.getElementById("foot");f.textContent="Bridge unreachable";f.className="foot err";}
}
document.querySelectorAll("button").forEach(b=>b.addEventListener("click",async()=>{
  const d={theme:b.dataset.t};
  const body=KEY?seal(KEY,TE.encode(JSON.stringify({t:Math.floor(Date.now()/1000),d:d}))):JSON.stringify(d);
  await fetch("/theme",{method:"POST",headers:{"Content-Type":KEY?"application/x-burn-helper-sealed":"application/json"},body:body});tick();
}));
tick();setInterval(tick,3000);
</script></body></html>
"""

if __name__ == "__main__":
    main()
