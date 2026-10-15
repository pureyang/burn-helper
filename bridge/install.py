#!/usr/bin/env python3
r"""Install or remove the Burn Helper integration for Claude Code.

On the computer that runs the bridge (the badge talks to it), a Mac or a Windows PC:
    python3 bridge/install.py              add hooks + status line, start the bridge at login
    python3 bridge/install.py --dry-run    show the settings.json diff and login item, change nothing
    python3 bridge/install.py --uninstall  remove only what this script added
(On Windows: py bridge\install.py ...) The login item is a launchd agent on macOS and a
value under HKCU\...\CurrentVersion\Run on Windows, which starts the bridge with the
windowless pythonw.exe; neither needs admin rights.

On any other computer where you run Claude Code (Windows, Linux or a Mac), so its
sessions show on the badge too:
    python bridge/install.py --bridge http://<bridge-computer>:8787
This adds the hooks and status line only, and puts the bridge's address in settings.json's
"env", where every Claude Code session (and so every hook) picks it up. See
docs/other-computers.md.

Set BURN_HELPER_HOME to point at a different home directory (used for testing).
With it set, launchctl, the registry and the bridge process are never touched, and
BURN_HELPER_TEST_OS=windows makes this behave as on Windows. Installs from older versions
(the com.heartsleft.bridge and com.lexco.tufty-bridge login items) are replaced.
"""
import argparse
import difflib
import json
import ntpath
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portable  # noqa: E402

TEST_HOME = os.environ.get("BURN_HELPER_HOME") or os.environ.get("HEARTS_LEFT_HOME") or os.environ.get("TUFTY_HOME")
MAC = sys.platform == "darwin"
WINDOWS = os.name == "nt"
if TEST_HOME and os.environ.get("BURN_HELPER_TEST_OS") == "windows":
    MAC, WINDOWS = False, True             # tests only: rehearse a Windows install on any computer
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
INSTALL_SH = "https://raw.githubusercontent.com/pureyang/burn-helper/main/install.sh"
INSTALL_PS1 = "https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1"
BRIDGE = os.path.join(HERE, "burn_helper_bridge.py")
LABEL = "com.burnhelper.bridge"
OLD_LABELS = ("com.heartsleft.bridge", "com.lexco.tufty-bridge")
EVENTS = ("PostToolUse", "PostToolUseFailure", "UserPromptSubmit", "Stop", "SubagentStart",
          "SubagentStop", "Notification", "SessionStart", "SessionEnd")
TOOL_EVENTS = ("PostToolUse", "PostToolUseFailure")

HOME = os.path.expanduser(TEST_HOME or "~")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
PLIST = os.path.join(HOME, "Library", "LaunchAgents", LABEL + ".plist")
LOGFILE = os.path.join(HOME, "Library", "Logs", "burn-helper.log")
# the bridge's state folder (as in burn_helper_bridge.py), where it writes its process id
STATE_DIR = os.path.expanduser(os.environ.get("BURN_HELPER_STATE_DIR") or os.environ.get("HEARTS_LEFT_STATE_DIR")
                               or os.environ.get("TUFTY_STATE_DIR") or os.path.join(HOME, ".claude", "burn-helper"))
PID_FILE = os.path.join(STATE_DIR, "bridge.pid")
# Windows: the login item and the log
RUN_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
RUN_VALUE = "Burn Helper bridge"
LOCAL_APPDATA = (None if TEST_HOME else os.environ.get("LOCALAPPDATA")) or os.path.join(HOME, "AppData", "Local")
WIN_LOG = os.path.join(LOCAL_APPDATA, "burn-helper", "burn-helper.log")


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


# ---------------------------------------------------------------- Windows: login item and process
def pythonw(py, exists=os.path.exists):
    """The windowless pythonw.exe next to python.exe, so the bridge runs without a console."""
    w = ntpath.join(ntpath.dirname(py), "pythonw.exe")
    return w if exists(w) else py


def login_command(py, bridge, log, exists=os.path.exists):
    """What Windows runs at sign-in (the Run value): quoted, so spaces in paths are fine."""
    return '"%s" "%s" --log "%s"' % (pythonw(py, exists), bridge, log)


def set_run_value(cmd):
    if TEST_HOME:
        print("(BURN_HELPER_HOME set: skipping the registry: Run value %r = %s)" % (RUN_VALUE, cmd))
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, cmd)
    print("Added the login item: HKCU\\%s\\%s" % (RUN_KEY, RUN_VALUE))


def delete_run_value():
    if TEST_HOME:
        print("(BURN_HELPER_HOME set: skipping the registry: delete Run value %r)" % RUN_VALUE)
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, RUN_VALUE)
        print("Removed the login item: HKCU\\%s\\%s" % (RUN_KEY, RUN_VALUE))
    except FileNotFoundError:
        pass


def running_bridge_pid():
    """The process id the running bridge wrote, if that process is still a Python."""
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    if not portable.pid_alive(pid) or "python" not in portable.pid_command(pid).lower():
        return None                       # gone, or the number now belongs to something else
    return pid


def stop_bridge():
    """Stop a running bridge (Windows; launchd does this on macOS). True if one was running."""
    if TEST_HOME:
        print("(BURN_HELPER_HOME set: skipping stopping the bridge)")
        return False
    pid = running_bridge_pid()
    if pid is None:
        return False
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    for _ in range(30):                   # wait for it to let go of port 8787
        if not portable.pid_alive(pid):
            break
        time.sleep(0.1)
    return True


def start_bridge():
    """Start the bridge in the background, hidden, outliving this window (Windows)."""
    if TEST_HOME:
        print("(BURN_HELPER_HOME set: skipping starting the bridge)")
        return True
    os.makedirs(os.path.dirname(WIN_LOG), exist_ok=True)
    argv = [pythonw(PY), BRIDGE, "--log", WIN_LOG]
    detached = 0x00000008 | 0x00000200    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    for breakaway in (0x01000000, 0):     # CREATE_BREAKAWAY_FROM_JOB, where the console allows it
        try:
            subprocess.Popen(argv, creationflags=detached | breakaway, close_fds=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    return False


def remove_local_bridge(domain):
    """Joining another bridge: stop and remove this computer's own bridge, if it has one. The badge
    talks to one bridge; a second one on the network pulls it back and forth. True if there was one."""
    if WINDOWS:
        had = stop_bridge()
        delete_run_value()
        return had
    if MAC:
        had = False
        for label in (LABEL,) + OLD_LABELS:
            if os.path.exists(os.path.join(HOME, "Library", "LaunchAgents", label + ".plist")):
                remove_agent(domain, label)
                had = True
        return had
    return False


def restart_bridge():
    """Restart the bridge so it reads its settings again (relay.py uses this). True if it did."""
    if MAC:
        r = subprocess.run(["launchctl", "kickstart", "-k", "gui/%d/%s" % (os.getuid(), LABEL)],
                           capture_output=True, text=True)
        return r.returncode == 0
    if WINDOWS:
        stop_bridge()
        return start_bridge()
    return False


def this_computer():
    """(address on the local network, Tailscale address or None): where other computers reach this
    bridge. The Tailscale IP, not its name: with the relay on, public DNS answers the name with
    the relay's address, so a computer not using Tailscale's DNS would get the wrong one."""
    import socket
    lan = None
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        lan = s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    name = None
    try:
        import relay
        t = relay.find_tailscale()
        if t:
            out = subprocess.run([t, "status", "--json"], capture_output=True, text=True, timeout=5).stdout
            st = json.loads(out)
            if st.get("BackendState") == "Running":
                ips = (st.get("Self") or {}).get("TailscaleIPs") or []
                name = next((ip for ip in ips if "." in ip), None)
    except Exception:  # noqa: BLE001
        pass
    return lan, name


def join_lines(lan, name, port=8787, windows=WINDOWS):
    """What to run on another computer so that it reports to this bridge."""
    url = "http://%s:%d" % (name or lan or "<this-computer>", port)
    again = "%s %s --join-help" % ("py" if windows else "python3", os.path.join(HERE, "install.py"))
    lines = ["To add another computer, so its Claude Code agents show on the badge too, run the join",
             "line on it (not the bridge line you just ran: there is only one bridge):",
             "",
             "  Mac or Linux, in Terminal:",
             "    curl -fsSL %s | bash -s -- --join %s" % (INSTALL_SH, url),
             "  Windows, in PowerShell:",
             "    $env:BURN_HELPER_JOIN='%s'; irm %s | iex" % (url, INSTALL_PS1),
             ""]
    if name and lan:
        lines += ["%s is this computer's Tailscale address, so this works from anywhere for computers on" % name,
                  "your tailnet. One that isn't on it can use http://%s:%d while on this network." % (lan, port)]
    elif lan:
        lines += ["%s is this computer's address on this network, and it can change. With Tailscale on" % lan,
                  "both computers, use this computer's Tailscale address instead (tailscale ip -4): it works",
                  "from anywhere."]
    lines.append("To see this again: " + again)
    return lines


def find_bridge(wait=4.0, port=47800):
    """Another computer's bridge on this network, heard by its beacon (every 2 s): the address to
    join it at, or None. This computer's own bridge (same id) doesn't count."""
    import socket
    import urllib.request
    own = None
    try:
        with open(os.path.join(STATE_DIR, "bridge_id")) as f:
            own = f.read().strip() or None
    except OSError:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(("", port))
    except OSError:
        s.close()
        return None
    end = time.time() + wait
    try:
        while time.time() < end:
            s.settimeout(max(0.05, end - time.time()))
            try:
                data, addr = s.recvfrom(128)
            except (socket.timeout, OSError):
                break
            parts = data.split()
            if not data.startswith(b"TUFTYBRIDGE") or len(parts) < 3:
                continue
            bid = parts[3].decode(errors="replace") if len(parts) > 3 else ""
            if own and bid == own:
                continue
            url = "http://%s:%s" % (addr[0], parts[2].decode(errors="replace"))
            try:
                with urllib.request.urlopen(url + "/status", timeout=3) as r:
                    return json.load(r).get("join") or url
            except Exception:  # noqa: BLE001
                return url
    finally:
        s.close()
    return None


def check_bridge(url):
    """Ask the bridge at url whether it is there. Returns a line to print."""
    import urllib.request
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=5) as r:
            ok = json.load(r).get("ok")
        if ok:
            return "The bridge at %s answers." % url
    except Exception as e:  # noqa: BLE001
        return ("Can't reach the bridge at %s yet (%s). Check that the bridge computer is on, that this "
                "computer can reach it (same network, or both on your tailnet) and, for a Windows bridge, "
                "its firewall rule. The hooks are installed either way." % (url, e.__class__.__name__))
    return "Something answered at %s, but it isn't a Burn Helper bridge." % url


def diff(old_text, settings):
    new_text = json.dumps(settings, indent=2) + "\n"
    return "".join(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True),
                                        fromfile=SETTINGS, tofile=SETTINGS + " (new)"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-launchd", action="store_true", help="only edit settings.json (no login item)")
    ap.add_argument("--bridge", metavar="URL",
                    help="the bridge runs on another computer: send this computer's events there")
    ap.add_argument("--token", help="the bridge's BURN_HELPER_TOKEN, if you set one")
    ap.add_argument("--join-help", action="store_true",
                    help="print what to run on another computer to add it to this bridge")
    ap.add_argument("--find-bridge", action="store_true",
                    help="print the join address of a bridge already on this network, if there is one")
    args = ap.parse_args()
    if args.join_help:
        print("\n".join(join_lines(*this_computer())))
        return 0
    if args.find_bridge:
        url = find_bridge()
        if url:
            print(url)
        return 0 if url else 1
    if args.bridge:
        if not args.bridge.startswith(("http://", "https://")):
            args.bridge = "http://" + args.bridge
        if args.bridge.rstrip("/").count(":") < 2:
            args.bridge = args.bridge.rstrip("/") + ":8787"
        args.no_launchd = True               # the bridge runs elsewhere
    elif not (MAC or WINDOWS) and not args.uninstall:
        sys.exit("The bridge runs on a Mac or a Windows PC. On this computer, point the hooks at one:\n"
                 "    python3 bridge/install.py --bridge http://<bridge-computer>:8787")
    if not (MAC or WINDOWS):
        args.no_launchd = True

    settings, old_text = load_settings()
    original = json.loads(old_text) if old_text.strip() else {}
    domain = "gui/%d" % os.getuid() if MAC else ""

    if args.uninstall:
        new = strip_ours(settings)
        if args.dry_run:
            print(diff(old_text, new) or "settings.json: nothing to remove")
            if WINDOWS:
                print("Would remove the login item HKCU\\%s\\%s and stop the bridge" % (RUN_KEY, RUN_VALUE))
            else:
                print("Would remove", PLIST, "and run launchctl bootout", domain + "/" + LABEL)
            return 0
        if new != original:
            write_settings(new, old_text)
        else:
            print("settings.json: nothing of ours to remove")
        if not args.no_launchd:
            if WINDOWS:
                delete_run_value()
                if stop_bridge():
                    print("Stopped the bridge.")
            else:
                for label in (LABEL,) + OLD_LABELS:
                    remove_agent(domain, label)
        return 0

    new, notes = add_ours(settings, args.bridge, args.token)
    if args.dry_run:
        print(diff(old_text, new) or "settings.json: already up to date")
        if not args.no_launchd:
            if WINDOWS:
                print("\nWould add the login item HKCU\\%s\\%s:\n  %s"
                      % (RUN_KEY, RUN_VALUE, login_command(PY, BRIDGE, WIN_LOG)))
                print("Would stop a running bridge and start it now, logging to", WIN_LOG)
            else:
                print("\nWould write %s:\n%s" % (PLIST, plist_text()))
                print("Would run: launchctl bootout %s/%s ; launchctl bootstrap %s %s" % (domain, LABEL, domain, PLIST))
        for n in notes:
            print("Note:", n)
        return 0

    if new != original:
        write_settings(new, old_text)
    else:
        print("settings.json already up to date")
    if not args.no_launchd and WINDOWS:
        set_run_value(login_command(PY, BRIDGE, WIN_LOG))
        if stop_bridge():
            print("Stopped the bridge that was running.")
        if start_bridge():
            print("Bridge started. Logs:", WIN_LOG)
        else:
            print("Could not start the bridge; it starts at your next sign-in. Logs:", WIN_LOG)
        notes.append("Windows Firewall must let the badge reach this PC: inbound TCP port 8787 on a Private "
                     "network (install.ps1 offers to add the rule).")
    elif not args.no_launchd:
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
    if args.bridge and remove_local_bridge(domain):
        notes.append("This computer was running a bridge of its own. It is stopped and removed: the badge "
                     "talks to one bridge, and two on one network pull it back and forth.")
    for n in notes:
        print("Note:", n)
    if args.bridge:
        print("This computer now reports to the bridge at %s." % args.bridge)
        print(check_bridge(args.bridge))
        print("Restart open Claude Code sessions so they pick up the new address.")
    else:
        print("Open sessions pick up the hooks automatically; restart them if events do not arrive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
