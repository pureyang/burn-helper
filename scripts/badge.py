#!/usr/bin/env python3
"""Talk to the Tufty 2350 over USB serial using only the Python standard library.

    python3 scripts/badge.py exec "print(1+1)"     run a snippet in the raw REPL
    python3 scripts/badge.py run some_file.py       run a local file on the badge
    python3 scripts/badge.py ls /system/apps        list a directory
    python3 scripts/badge.py bootloader             reboot into BOOTSEL (for picotool)
    python3 scripts/badge.py disk                   reboot into USB disk mode
    python3 scripts/badge.py reset                  hard reset

Ctrl-C stops the running badge app. Some firmware builds arm a watchdog, so
snippets feed machine.WDT when one is requested with --wdt.
"""
import glob
import os
import select
import sys
import termios
import time
import tty


def find_port():
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if not ports:
        sys.exit("No /dev/cu.usbmodem* device found. Is the badge plugged in and awake?")
    return ports[0]


LOCK = os.path.expanduser("~/.claude/hearts-left/usb.lock")


def _lock():
    # Tell the bridge's USB tether to stay off the port while we use it.
    try:
        os.makedirs(os.path.dirname(LOCK), exist_ok=True)
        with open(LOCK, "w") as f:
            f.write(str(os.getpid()))
        time.sleep(0.3)
    except OSError:
        pass


def _unlock():
    try:
        with open(LOCK) as f:
            if f.read().strip() == str(os.getpid()):
                os.remove(LOCK)
    except OSError:
        pass


class Badge:
    def __init__(self, port=None):
        _lock()
        self.port = port or os.environ.get("BADGE_PORT") or find_port()
        self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        tty.setraw(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[4] = attrs[5] = termios.B115200
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def read(self, timeout=1.0, idle=0.4, until=None):
        out = b""
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if r:
                try:
                    chunk = os.read(self.fd, 4096)
                except (BlockingIOError, OSError):
                    chunk = b""
                if chunk:
                    out += chunk
                    if until and until in out:
                        break
                    end = max(end, time.time() + idle) if idle else end
        return out

    def write(self, data):
        while data:
            try:
                n = os.write(self.fd, data)
                data = data[n:]
            except BlockingIOError:
                time.sleep(0.01)

    def raw_repl(self):
        self.write(b"\r\x03\x03")
        self.read(0.6)
        self.write(b"\x01")
        got = self.read(2.0, until=b"raw REPL; CTRL-B to exit\r\n>")
        if b"raw REPL" not in got:
            self.write(b"\x03\x03\x01")
            got = self.read(2.0, until=b"raw REPL; CTRL-B to exit\r\n>")
        if b"raw REPL" not in got:
            raise RuntimeError("could not enter raw REPL: %r" % got[-200:])

    def exec(self, code, timeout=20.0):
        """Run code in the raw REPL. Returns (stdout, stderr) as str."""
        self.raw_repl()
        self.write(code.encode() + b"\x04")
        ack = self.read(2.0, until=b"OK")
        if b"OK" not in ack:
            raise RuntimeError("badge did not accept code: %r" % ack)
        out = self.read(timeout, idle=0, until=b"\x04>")
        # raw REPL replies: OK <stdout> \x04 <stderr> \x04 >
        body = out.split(b"\x04")
        stdout = body[0].decode(errors="replace") if body else ""
        stderr = body[1].decode(errors="replace") if len(body) > 1 else ""
        return stdout, stderr

    def soft_exit(self):
        self.write(b"\x02")

    def close(self):
        os.close(self.fd)
        _unlock()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, args = argv[1], argv[2:]
    wdt = "--wdt" in args
    args = [a for a in args if a != "--wdt"]
    prefix = "import machine\n_w=machine.WDT(timeout=8000)\n" if wdt else ""
    b = Badge()
    try:
        if cmd == "exec":
            out, err = b.exec(prefix + args[0])
        elif cmd == "run":
            out, err = b.exec(prefix + open(args[0]).read(), timeout=float(os.environ.get("BADGE_TIMEOUT", "60")))
        elif cmd == "ls":
            path = args[0] if args else "/"
            out, err = b.exec(prefix + "import os\nfor n in sorted(os.listdir(%r)):\n"
                              "  s=os.stat(%r.rstrip('/')+'/'+n)\n"
                              "  print(('d ' if s[0]&0x4000 else '- ')+str(s[6])+'\\t'+n)\n" % (path, path))
        elif cmd == "bootloader":
            b.raw_repl()
            b.write(b"import machine\nmachine.bootloader()\x04")
            print("Rebooting into BOOTSEL. Check with: picotool info")
            return 0
        elif cmd == "disk":
            b.raw_repl()
            b.write(b"import powman\npowman.reset_into_msc()\x04")
            print("Rebooting into USB disk mode. The badge mounts as a drive in a few seconds.")
            return 0
        elif cmd == "reset":
            b.raw_repl()
            b.write(b"import machine\nmachine.reset()\x04")
            print("Reset sent.")
            return 0
        else:
            print(__doc__)
            return 1
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write(err)
            return 2
        return 0
    finally:
        try:
            b.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv))
