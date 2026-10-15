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
        try:
            st = json.loads(subprocess.run([t, "status", "--json"], capture_output=True, text=True,
                                           timeout=5).stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if st.get("BackendState") != "Running":
            return None
        return next((ip for ip in (st.get("Self") or {}).get("TailscaleIPs") or [] if "." in ip), None)
    return None


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
