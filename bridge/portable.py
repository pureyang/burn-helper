"""What differs between macOS, Linux and Windows: checking on processes and talking to the
badge over USB serial.

macOS and Linux need only the standard library. Windows needs pyserial for the USB cable
(py -m pip install --user pyserial); the Windows installer adds it. Without it the bridge
still works over Wi-Fi.
"""
import glob
import os
import sys
import time

WINDOWS = os.name == "nt"
MAC = sys.platform == "darwin"
RP2_VID = 0x2E8A        # Raspberry Pi, maker of the badge's RP2350 chip


# ---------------------------------------------------------------- processes
def pid_alive(pid):
    """True if a process with this id is running. Never signals it: on Windows os.kill(pid, 0)
    would end the process."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if WINDOWS:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5          # access denied: it exists
        code = wintypes.DWORD()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259            # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def pid_command(pid):
    """The process's command line (macOS, Linux) or program path (Windows), or "" if unknown."""
    if WINDOWS:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            return ""
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        k32.CloseHandle(h)
        return buf.value if ok else ""
    import subprocess
    try:
        return subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True,
                              text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def tailscale_ip():
    """This computer's Tailscale address (100.x.y.z), or None when Tailscale isn't running here."""
    import json
    import shutil
    import subprocess
    pf = os.environ.get("ProgramFiles") or "C:\\Program Files"
    for t in (shutil.which("tailscale"), "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
              "/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale",
              os.path.join(pf, "Tailscale", "tailscale.exe")):
        if not t or not os.path.exists(t):
            continue
        # the Mac app's binary starts its window unless told it is the command line (a login
        # item like the bridge has no terminal for it to notice)
        env = dict(os.environ, TAILSCALE_BE_CLI="1")
        try:
            st = json.loads(subprocess.run([t, "status", "--json"], capture_output=True, text=True,
                                           timeout=5, env=env).stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if st.get("BackendState") != "Running":
            return None
        return next((ip for ip in (st.get("Self") or {}).get("TailscaleIPs") or [] if "." in ip), None)
    return None


# ---------------------------------------------------------------- the bridge's key
KEY_HEX = 32            # 128 random bits, as hex: safe in a header, a URL fragment and a shell line


def bridge_key(state_dir, make=True):
    """The key every request to the bridge needs, except from the bridge computer itself:
    BURN_HELPER_TOKEN when set, else one made once and kept in <state_dir>/key (readable by this
    user only). A shorter one than ours is no key at all, so it is ignored. None when there is none
    and make is False, or it can't be saved."""
    key = (os.environ.get("BURN_HELPER_TOKEN") or os.environ.get("HEARTS_LEFT_TOKEN")
           or os.environ.get("TUFTY_TOKEN") or "").strip()
    if len(key) >= KEY_HEX:
        return key
    path = os.path.join(state_dir, "key")
    try:
        with open(path) as f:
            key = f.read().strip()
        if len(key) >= KEY_HEX:
            return key
    except OSError:
        pass
    if not make:
        return None
    import secrets
    key = secrets.token_hex(KEY_HEX // 2)
    try:
        os.makedirs(state_dir, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key + "\n")
    except OSError:
        return None
    return key


# ---------------------------------------------------------------- account names
# More than one Claude account: each one's label comes from the status line that reports it (its
# BURN_HELPER_LABEL, else its email's domain), so two computers on one account can send different
# ones. A name set on the bridge (install.py --name-account) wins over all of them, in the case it
# was typed: <state_dir>/names.json, {account tag or "main": name}. The bridge reads it as it changes.
NAME_MAX = 8            # what the badge's rows have room for
_names = {"at": None, "map": {}}


def clean_name(v):
    """A name for an account, or None: letters, digits, dashes, dots and underscores, case kept."""
    v = str(v or "").strip()
    return v if 0 < len(v) <= NAME_MAX and all(c.isalnum() and c.isascii() or c in "-._" for c in v) else None


def names_file(state_dir):
    return os.path.join(state_dir, "names.json")


def account_names(state_dir):
    """{account tag or "main": name}, read again only when the file changes."""
    import json
    path = names_file(state_dir)
    try:
        at = os.stat(path).st_mtime
    except OSError:
        _names.update(at=None, map={})
        return {}
    if at != _names["at"]:
        try:
            with open(path) as f:
                d = json.load(f)
            m = {str(k): clean_name(v) for k, v in d.items()} if isinstance(d, dict) else {}
        except (OSError, ValueError):
            m = {}
        _names.update(at=at, map={k: v for k, v in m.items() if v})
    return dict(_names["map"])


def set_name(state_dir, key, name):
    """Name an account (name None: clear it). The bridge picks it up as it goes."""
    import json
    names = account_names(state_dir)
    if name:
        names[key] = name
    else:
        names.pop(key, None)
    os.makedirs(state_dir, exist_ok=True)
    path = names_file(state_dir)
    with open(path + ".tmp", "w") as f:
        json.dump(names, f, indent=1, sort_keys=True)
    os.replace(path + ".tmp", path)
    _names["at"] = None


# ---------------------------------------------------------------- USB serial
def serial_missing():
    """Why USB serial can't work here, or None when it can."""
    if not WINDOWS:
        return None
    try:
        import serial  # noqa: F401
    except ImportError:
        return "pyserial is not installed (py -m pip install --user pyserial)"
    return None


def find_ports():
    """Serial ports that look like a badge (an RP2350 board), best first."""
    if WINDOWS:
        try:
            from serial.tools import list_ports
        except ImportError:
            return []
        found = [p for p in list_ports.comports() if p.vid == RP2_VID]
        found.sort(key=lambda p: ("tufty" not in (p.product or p.description or "").lower(), p.device))
        return [p.device for p in found]
    return sorted(glob.glob("/dev/cu.usbmodem*")) or sorted(glob.glob("/dev/ttyACM*"))


class Port:
    """A raw serial port that never blocks: read() returns what has arrived, write() sends."""

    def __init__(self, path, write_only=False):
        self.path = path
        self.fd = None
        self.s = None
        if WINDOWS:
            import serial
            self.s = serial.Serial(path, 115200, timeout=0, write_timeout=1)
            self.s.dtr = True               # MicroPython only sends while the host holds DTR
            return
        import termios
        import tty
        flags = (os.O_WRONLY if write_only else os.O_RDWR) | os.O_NOCTTY | os.O_NONBLOCK
        self.fd = os.open(path, flags)
        tty.setraw(self.fd)
        if not write_only:
            attrs = termios.tcgetattr(self.fd)
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def read(self, wait=0.05):
        """Bytes that arrive within `wait` seconds, or b""."""
        if self.s is not None:
            end = time.time() + wait
            while True:
                n = self.s.in_waiting
                if n:
                    return self.s.read(n)
                if time.time() >= end:
                    return b""
                time.sleep(0.01)
        import select
        r, _, _ = select.select([self.fd], [], [], wait)
        if not r:
            return b""
        try:
            return os.read(self.fd, 4096)
        except BlockingIOError:
            return b""

    def write(self, data, wait=True):
        """Send data. With wait=False, give up instead of waiting when the port is busy."""
        if self.s is not None:
            self.s.write(data)
            return
        while data:
            try:
                n = os.write(self.fd, data)
                data = data[n:]
            except BlockingIOError:
                if not wait:
                    return
                time.sleep(0.01)

    def close(self):
        try:
            if self.s is not None:
                self.s.close()
            else:
                os.close(self.fd)
        except OSError:
            pass
