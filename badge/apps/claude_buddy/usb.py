# USB tether: when the badge is plugged into the Mac running the bridge, the
# bridge writes "@TUFTY {status json}" lines to the USB serial port. Read them
# here without blocking, so the badge works with no Wi-Fi at all.

import json
import select
import sys
import time

FRESH_MS = 8000
MARK = "@TUFTY "


class UsbLink:
    def __init__(self):
        self.buf = ""
        self.data = None
        self.ok_t = None
        self.seq = 0
        self.err = ""
        self.shot_req = False
        try:
            self.poller = select.poll()
            self.poller.register(sys.stdin, select.POLLIN)
        except Exception as e:  # noqa: BLE001
            self.poller = None
            self.err = repr(e)[:40]

    def fresh(self):
        return self.ok_t is not None and time.ticks_diff(time.ticks_ms(), self.ok_t) < FRESH_MS

    def tick(self):
        if self.poller is None:
            return
        try:
            n = 0
            while n < 1500 and self.poller.poll(0):
                c = sys.stdin.read(1)
                n += 1
                if not c:
                    break
                if c == "\n":
                    self._line(self.buf)
                    self.buf = ""
                elif c != "\r":
                    self.buf += c
                    if len(self.buf) > 4096:
                        self.buf = ""
        except Exception as e:  # noqa: BLE001
            self.err = repr(e)[:40]

    def _line(self, line):
        if line.startswith("@SHOT"):
            self.shot_req = True
            return
        i = line.find(MARK)
        if i < 0:
            return
        try:
            d = json.loads(line[i + len(MARK):])
        except ValueError:
            return
        if isinstance(d, dict):
            self.data = d
            self.ok_t = time.ticks_ms()
            self.seq += 1


def send_screenshot(info=""):
    """Reply to "@SHOT": the current frame as base64 PNG on the USB serial port."""
    import binascii
    import screenshot
    screenshot.save("/shot.png")
    with open("/shot.png", "rb") as f:
        data = f.read()
    sys.stdout.write("\n@INFO %s\n@PNG " % info)
    for i in range(0, len(data), 768):
        sys.stdout.write(binascii.b2a_base64(data[i:i + 768]).decode().strip())
        sys.stdout.write(" ")
    sys.stdout.write("\n@END\n")
