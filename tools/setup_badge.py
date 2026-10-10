#!/usr/bin/env python3
"""Get a Pimoroni Tufty 2350 ready for Hearts Left, step by step.

    python3 tools/setup_badge.py             ask before anything that changes the badge
    python3 tools/setup_badge.py --yes       no questions (flashes if needed; Wi-Fi via phone later)
    python3 tools/setup_badge.py --no-flash  never replace firmware; stop if the badge needs it
    python3 tools/setup_badge.py --dry-run   only report what it would do

1. Find the badge on USB (or in bootloader mode).
2. Look at what it runs. A conference build or anything other than stock
   Pimoroni firmware gets a verified full backup in backup/<date>/ and then the
   stock Tufty 2350 v3.1.1 firmware (downloaded from Pimoroni, checksum-pinned).
3. Ask for a 2.4 GHz Wi-Fi network (or skip: hold B on the badge later to set
   it up from a phone) and write badge/secrets.py.
4. Copy the Hearts Left app onto the badge and check that it starts.

Questions are read from /dev/tty, so this also works under `curl ... | bash`.
"""
import argparse
import getpass
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "bridge"))
from badge import Badge  # noqa: E402

FW_NAME = "tufty-v3.1.1-micropython-with-filesystem.uf2"
FW_URL = "https://github.com/pimoroni/tufty2350/releases/download/v3.1.1/" + FW_NAME
FW_SHA256 = "2ea56534250abc1bb7b484f92ccd4fbfebe428f161daa00169a48b45da2fe74a"
SECRETS = os.path.join(REPO, "badge", "secrets.py")

INSPECT = """
import os, sys
def ls(p):
    try:
        return sorted(os.listdir(p))
    except OSError:
        return []
print(repr({'version': sys.version, 'apps': ls('/system/apps'), 'lib': ls('/system/lib')}))
"""

ARGS = None


def say(msg):
    print("♥ " + msg, flush=True)


def tty_line(prompt, secret=False):
    """Read one line from the terminal, even when stdin is a pipe. None if there is no terminal."""
    try:
        if secret:
            return getpass.getpass(prompt)
        with open("/dev/tty", "r+") as t:
            t.write(prompt)
            t.flush()
            return t.readline().strip()
    except (OSError, EOFError):
        return None


def ask(question, default=True):
    if ARGS.yes:
        return True
    ans = tty_line("%s [%s] " % (question, "Y/n" if default else "y/N"))
    if ans is None:
        say("No terminal to ask on; rerun with --yes to accept, or run it from a terminal.")
        return False
    if not ans:
        return default
    return ans.lower() in ("y", "yes")


def picotool():
    p = shutil.which("picotool") or ("/opt/homebrew/bin/picotool" if os.path.exists("/opt/homebrew/bin/picotool") else None)
    if p:
        return p
    brew = shutil.which("brew") or ("/opt/homebrew/bin/brew" if os.path.exists("/opt/homebrew/bin/brew") else None)
    if not brew:
        sys.exit("picotool is needed to flash the badge. Install Homebrew (https://brew.sh), then rerun.")
    if ARGS.dry_run:
        say("Would install picotool with Homebrew.")
        return "picotool"
    if not ask("picotool (Raspberry Pi's flashing tool) is missing. Install it with Homebrew?"):
        sys.exit("Stopped: picotool is needed to flash the badge.")
    subprocess.run([brew, "install", "picotool"], check=True)
    return shutil.which("picotool") or "/opt/homebrew/bin/picotool"


def serial_port():
    try:
        from hearts_left_bridge import find_badge_ports
        ports = find_badge_ports()
    except Exception:  # noqa: BLE001
        ports = []
    return ports[0] if ports else None


def in_bootloader():
    p = shutil.which("picotool") or "/opt/homebrew/bin/picotool"
    if not os.path.exists(p) and not shutil.which("picotool"):
        return False
    r = subprocess.run([p, "info"], capture_output=True, text=True)
    return "Program Information" in r.stdout or "no program" in r.stdout.lower()


def wait_for_badge(timeout=120):
    said = False
    end = time.time() + timeout
    while time.time() < end:
        port = serial_port()
        if port:
            return "serial", port
        if in_bootloader():
            return "bootloader", None
        if not said:
            say("Plug the Tufty 2350 into this Mac with a USB-C data cable (press RESET if the screen is off)...")
            said = True
        time.sleep(2)
    sys.exit("No badge found. Check the cable (some only charge), then rerun.")


def inspect(port):
    import ast
    try:
        b = Badge(port)
        try:
            out, err = b.exec(INSPECT, timeout=10)
        finally:
            b.close()
        for line in reversed(out.strip().splitlines()):
            if line.startswith("{"):
                return ast.literal_eval(line)
    except Exception as e:  # noqa: BLE001
        say("Could not read the badge's files (%s)." % e.__class__.__name__)
    return None


def needs_flash(info):
    """(needs flash, reason)."""
    if info is None:
        return True, "it is not running MicroPython that this installer understands"
    if "network_runtime.mpy" in info["lib"] or any("badgelink" in n.lower() for n in info["lib"]):
        return True, "it runs a conference build (BadgeLink), not stock Pimoroni firmware"
    if "menu" not in info["apps"]:
        return True, "it does not look like stock Tufty 2350 firmware"
    return False, "it already runs stock Pimoroni firmware"


def firmware():
    os.makedirs(os.path.join(REPO, "firmware"), exist_ok=True)
    path = os.path.join(REPO, "firmware", FW_NAME)
    if not (os.path.exists(path) and sha256(path) == FW_SHA256):
        say("Downloading Pimoroni Tufty 2350 firmware v3.1.1...")
        tmp = path + ".part"
        urllib.request.urlretrieve(FW_URL, tmp)
        if sha256(tmp) != FW_SHA256:
            os.remove(tmp)
            sys.exit("The firmware download did not match its checksum; stopped without flashing.")
        os.replace(tmp, path)
    return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
        sys.exit("%s failed:\n  %s" % (what, "\n  ".join(tail)))
    return r.stdout


def to_bootloader(port):
    if port:
        b = Badge(port)
        try:
            b.raw_repl()
            b.write(b"import machine\nmachine.bootloader()\x04")
        finally:
            b.close()
    for _ in range(30):
        time.sleep(1)
        if in_bootloader():
            return
    sys.exit("The badge did not enter bootloader mode. Hold HOME, tap RESET, release HOME, then rerun.")


def backup_and_flash(port):
    tool = picotool()
    fw = firmware()
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    dest = os.path.join(REPO, "backup", stamp)
    os.makedirs(dest, mode=0o700, exist_ok=True)
    img = os.path.join(dest, "flash-full.bin")
    to_bootloader(port)
    say("Backing up all 16 MB of the badge's flash to %s ..." % img)
    run([tool, "save", "-a", img], "Backup")
    os.chmod(img, 0o600)
    run([tool, "verify", "-o", "0x10000000", img], "Backup check")
    say("Backup verified. Restore any time with: picotool load -v -x %s" % img)
    say("Flashing stock firmware...")
    run([tool, "load", "-v", "-x", fw], "Flashing")
    for _ in range(40):
        time.sleep(1)
        p = serial_port()
        if p:
            time.sleep(3)
            return p
    sys.exit("The badge did not come back after flashing. Unplug it, plug it back in, and rerun.")


def wifi():
    if os.path.exists(SECRETS):
        say("Using the Wi-Fi settings in badge/secrets.py.")
        return
    if ARGS.dry_run:
        say("Would ask for a 2.4 GHz Wi-Fi network and write badge/secrets.py.")
        return
    ssid = None
    if not ARGS.yes:
        say("The badge needs a 2.4 GHz Wi-Fi network on the same network as this Mac.")
        say("Leave it blank to skip: hold B on the badge later to add one from your phone.")
        ssid = tty_line("  Wi-Fi name (SSID): ")
    psk = ""
    if ssid:
        psk = (tty_line("  Wi-Fi password: ", secret=True) or "").strip()
    offset = -time.timezone // 3600   # standard-time offset; REGION applies daylight saving
    text = ('# Private: installed as /system/secrets.py by tools/deploy.py. Git-ignored.\n'
            'WIFI_SSID = %r\nWIFI_PASSWORD = %r\nWIFI_EXTRA = []\nBRIDGE = ""\n'
            'REGION = "us"\nTIMEZONE = %d\n') % (ssid or "", psk, offset)
    fd = os.open(SECRETS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.write(fd, text.encode())
    os.close(fd)
    say("Saved badge/secrets.py%s." % (" for %s" % ssid if ssid else " (no network yet)"))


def deploy():
    say("Copying the Hearts Left app onto the badge (about 40 seconds)...")
    r = subprocess.run([sys.executable, os.path.join(HERE, "deploy.py"), "--all"])
    if r.returncode != 0:
        sys.exit("Copying the app failed; rerun the installer.")


def check_running():
    end = time.time() + 45
    while time.time() < end:
        time.sleep(5)
        port = serial_port()
        if not port:
            continue
        try:
            b = Badge(port)
            try:
                b.read(0.3)
                b.write(b"@NETLOG\n")
                got = b.read(5.0, idle=0, until=b"@NETLOG-END")
            finally:
                b.close()
            if b"@NETLOG-END" in got:
                return True
        except Exception:  # noqa: BLE001
            pass
    return False


def main(argv):
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", "-y", action="store_true")
    ap.add_argument("--no-flash", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ARGS = ap.parse_args(argv)

    kind, port = wait_for_badge(8 if ARGS.dry_run else 120)
    if kind == "bootloader":
        flash, why = True, "it is in bootloader mode"
    else:
        info = inspect(port)
        flash, why = needs_flash(info)
        if info is not None and ("hearts_left" in info["apps"] or "claude_buddy" in info["apps"]):
            why += ", with Hearts Left installed"
    say("Found the badge: %s." % why)

    if flash:
        if ARGS.no_flash:
            sys.exit("Stopped: the badge needs stock firmware and --no-flash was given.")
        if ARGS.dry_run:
            say("Would back up the badge's flash to backup/<date>/ and flash stock Tufty firmware v3.1.1.")
        else:
            if not ask("Back up the badge and replace its firmware with stock Pimoroni v3.1.1? "
                       "(the backup can restore it exactly)"):
                sys.exit("Stopped before changing the badge.")
            port = backup_and_flash(port)
            say("Stock firmware installed.")
    wifi()
    if ARGS.dry_run:
        say("Would copy the Hearts Left app onto the badge and restart it.")
        return 0
    deploy()
    if check_running():
        say("Hearts Left is running on the badge.")
    else:
        say("The app was copied but did not answer yet; give it a minute, or press RESET.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
