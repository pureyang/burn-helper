#!/usr/bin/env python3
"""Install or remove the Burn Helper integration for Claude Code.

On the Mac that runs the bridge (the badge talks to it):
    python3 bridge/install.py              add hooks + status line, start the bridge at login
    python3 bridge/install.py --dry-run    show the settings.json diff and plist, change nothing
    python3 bridge/install.py --uninstall  remove only what this script added

On any other computer where you run Claude Code (Windows, Linux or another Mac), so its
sessions show on the badge too:
    python bridge/install.py --bridge http://<mac>:8787
This adds the hooks and status line only, and puts the bridge's address in settings.json's
"env", where every Claude Code session (and so every hook) picks it up. See
docs/other-computers.md.

Set BURN_HELPER_HOME to point at a different home directory (used for testing).
With it set, launchctl is never called. Installs from older versions (the
com.heartsleft.bridge and com.lexco.tufty-bridge login items) are replaced.
"""
import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAC = sys.platform == "darwin"
WINDOWS = os.name == "nt"
PY = "/usr/bin/python3" if MAC else sys.executable


def command(script, py=PY, here=HERE, windows=WINDOWS):
    """The command line Claude Code runs. On Windows: quoted, with forward slashes, which
    work the same whichever shell runs it."""
    path = os.path.join(here, script)
    if windows:
        return '"%s" "%s"' % (py.replace("\\", "/"), path.replace("\\", "/"))
    return "%s %s" % (py, path)


HOOK_CMD = command("cc_hook.py")
STATUS_CMD = command("cc_statusline.py")
ENV_KEYS = ("BURN_HELPER_BRIDGE_URL", "BURN_HELPER_TOKEN")      # set by --bridge / --token
BRIDGE = os.path.join(HERE, "burn_helper_bridge.py")
LABEL = "com.burnhelper.bridge"
OLD_LABELS = ("com.heartsleft.bridge", "com.lexco.tufty-bridge")
EVENTS = ("PostToolUse", "PostToolUseFailure", "UserPromptSubmit", "Stop", "SubagentStart",
          "SubagentStop", "Notification", "SessionStart", "SessionEnd")
TOOL_EVENTS = ("PostToolUse", "PostToolUseFailure")

TEST_HOME = os.environ.get("BURN_HELPER_HOME") or os.environ.get("HEARTS_LEFT_HOME") or os.environ.get("TUFTY_HOME")
HOME = os.path.expanduser(TEST_HOME or "~")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
PLIST = os.path.join(HOME, "Library", "LaunchAgents", LABEL + ".plist")
LOGFILE = os.path.join(HOME, "Library", "Logs", "burn-helper.log")


def is_ours(cmd):
    # Match by script name wherever the repo lives, so reinstalling from another
    # clone (the one-line installer uses ~/burn-helper) replaces the old entries.
    if not isinstance(cmd, str):
        return False
    cmd = cmd.replace("\\", "/")
    return "/bridge/cc_hook.py" in cmd or "/bridge/cc_statusline.py" in cmd


def our_hook():
    return {"type": "command", "command": HOOK_CMD, "async": True, "timeout": 5}


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return {}, ""
    data = json.loads(text) if text.strip() else {}
    if not isinstance(data, dict):
        sys.exit("settings.json is not a JSON object; refusing to edit it")
    return data, text


def strip_ours(settings):
    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        for event in list(hooks):
            groups = hooks[event]
            if not isinstance(groups, list):
                continue
            kept = []
            for g in groups:
                if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                    inner = [h for h in g["hooks"] if not (isinstance(h, dict) and is_ours(h.get("command")))]
                    if not inner:
                        continue
                    g = dict(g, hooks=inner)
                kept.append(g)
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        if not hooks:
            del settings["hooks"]
    sl = settings.get("statusLine")
    if isinstance(sl, dict) and is_ours(sl.get("command")):
        del settings["statusLine"]
    env = settings.get("env")
    if isinstance(env, dict):
        for k in ENV_KEYS:
            env.pop(k, None)
        if not env:
            del settings["env"]
    return settings


def add_ours(settings, bridge_url=None, token=None):
    notes = []
    settings = strip_ours(settings)          # idempotent: remove then add once
    if bridge_url:
        env = settings.setdefault("env", {})
        env["BURN_HELPER_BRIDGE_URL"] = bridge_url
        if token:
            env["BURN_HELPER_TOKEN"] = token
    hooks = settings.setdefault("hooks", {})
    for event in EVENTS:
        group = {"hooks": [our_hook()]}
        if event in TOOL_EVENTS:
            group = {"matcher": "", "hooks": [our_hook()]}
        hooks.setdefault(event, []).append(group)
    if "statusLine" in settings:
        notes.append("A status line is already configured, so it was left alone. Usage hearts need "
                     "cc_statusline.py to run; add its POST to your own status line command if you want them.")
    else:
        settings["statusLine"] = {"type": "command", "command": STATUS_CMD, "refreshInterval": 60}
    return settings, notes


def plist_text():
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>%(label)s</string>
  <key>ProgramArguments</key>
  <array><string>%(py)s</string><string>%(bridge)s</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>%(log)s</string>
  <key>StandardErrorPath</key><string>%(log)s</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
""" % {"label": LABEL, "py": PY, "bridge": BRIDGE, "log": LOGFILE}


def write_settings(settings, old_text):
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    if os.path.exists(SETTINGS):
        bak = SETTINGS + ".bak-burn-helper-" + time.strftime("%Y%m%d-%H%M%S")
        n = 1
        while os.path.exists(bak):
            n += 1
            bak = SETTINGS + ".bak-burn-helper-" + time.strftime("%Y%m%d-%H%M%S") + "-%d" % n
        shutil.copy2(SETTINGS, bak)
        print("Backed up settings to", bak)
    tmp = SETTINGS + ".tmp-burn-helper"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(settings, indent=2) + "\n")
    os.replace(tmp, SETTINGS)
    print("Updated", SETTINGS)


def launchctl(*args):
    if TEST_HOME:
        print("(BURN_HELPER_HOME set: skipping launchctl %s)" % " ".join(args))
        return 0
    r = subprocess.run(["launchctl"] + list(args), capture_output=True, text=True)
    return r.returncode


def remove_agent(domain, label):
    plist = os.path.join(HOME, "Library", "LaunchAgents", label + ".plist")
    launchctl("bootout", domain + "/" + label)
    if os.path.exists(plist):
        os.remove(plist)
        print("Removed", plist)


def diff(old_text, settings):
    new_text = json.dumps(settings, indent=2) + "\n"
    return "".join(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True),
                                        fromfile=SETTINGS, tofile=SETTINGS + " (new)"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-launchd", action="store_true", help="only edit settings.json")
    ap.add_argument("--bridge", metavar="URL",
                    help="the bridge runs on another computer (your Mac): send this computer's events there")
    ap.add_argument("--token", help="the bridge's BURN_HELPER_TOKEN, if you set one")
    args = ap.parse_args()
    if args.bridge:
        if not args.bridge.startswith(("http://", "https://")):
            args.bridge = "http://" + args.bridge
        if args.bridge.rstrip("/").count(":") < 2:
            args.bridge = args.bridge.rstrip("/") + ":8787"
        args.no_launchd = True               # the bridge runs elsewhere
    elif not MAC and not args.uninstall:
        sys.exit("The bridge runs on a Mac. On this computer, point the hooks at it instead:\n"
                 "    python bridge/install.py --bridge http://<your-mac>:8787")
    if not MAC:
        args.no_launchd = True

    settings, old_text = load_settings()
    original = json.loads(old_text) if old_text.strip() else {}
    domain = "gui/%d" % os.getuid() if MAC else ""

    if args.uninstall:
        new = strip_ours(settings)
        if args.dry_run:
            print(diff(old_text, new) or "settings.json: nothing to remove")
            print("Would remove", PLIST, "and run launchctl bootout", domain + "/" + LABEL)
            return 0
        if new != original:
            write_settings(new, old_text)
        else:
            print("settings.json: nothing of ours to remove")
        if not args.no_launchd:
            for label in (LABEL,) + OLD_LABELS:
                remove_agent(domain, label)
        return 0

    new, notes = add_ours(settings, args.bridge, args.token)
    if args.dry_run:
        print(diff(old_text, new) or "settings.json: already up to date")
        if not args.no_launchd:
            print("\nWould write %s:\n%s" % (PLIST, plist_text()))
            print("Would run: launchctl bootout %s/%s ; launchctl bootstrap %s %s" % (domain, LABEL, domain, PLIST))
        for n in notes:
            print("Note:", n)
        return 0

    if new != original:
        write_settings(new, old_text)
    else:
        print("settings.json already up to date")
    if not args.no_launchd:
        os.makedirs(os.path.dirname(PLIST), exist_ok=True)
        os.makedirs(os.path.dirname(LOGFILE), exist_ok=True)
        with open(PLIST, "w") as f:
            f.write(plist_text())
        print("Wrote", PLIST)
        for label in OLD_LABELS:
            remove_agent(domain, label)
        launchctl("bootout", domain + "/" + LABEL)
        rc = launchctl("bootstrap", domain, PLIST)
        if rc not in (0, None):
            print("launchctl bootstrap returned %s; check %s" % (rc, LOGFILE))
        else:
            print("Bridge started. Logs:", LOGFILE)
    for n in notes:
        print("Note:", n)
    if args.bridge:
        print("This computer now reports to the bridge at %s." % args.bridge)
        print("Restart open Claude Code sessions so they pick up the new address.")
    else:
        print("Open sessions pick up the hooks automatically; restart them if events do not arrive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
