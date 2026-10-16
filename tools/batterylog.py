#!/usr/bin/env python3
"""Copy the badge's whole battery log to this computer and sum up each run on battery.

    python3 tools/batterylog.py             save it next to you and print the runs
    python3 tools/batterylog.py -o FILE     save it as FILE

The badge must be plugged in by USB with the Burn Helper app running; this stops the app for a
moment to read the file, then restarts it. The log has a line a minute on battery and every five
minutes on USB: share it when the battery estimate or the time left looks wrong.
"""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
from badge import Badge  # noqa: E402

LOG = "/state/burn_helper_power.log"
READ = """
f = open(%r)
f.seek(%d)
print(f.read(%d), end='')
f.close()
"""
CHUNK = 4096
LINE = re.compile(r"^\s*(\d+)s (BAT|USB|CHG|BATTERY|USB charging|USB)\b.*?v=([\d.]+) (?:soc=(\d+)|level=(\d+)%)")


def fetch():
    b = Badge()
    try:
        out, pos = "", 0
        while True:
            text, err = b.exec(READ % (LOG, pos, CHUNK), timeout=20)
            if err.strip():
                raise RuntimeError(err.strip())
            out += text
            if len(text) < CHUNK:
                return out
            pos += CHUNK
    finally:
        b.write(b"\x04")          # soft reset: the app starts again
        b.close()


def runs(text):
    """Runs on battery: [(minutes, first estimate, last estimate, first volts, last volts)]."""
    found, cur = [], []
    for line in text.splitlines():
        m = LINE.match(line)
        on_battery = bool(m) and m.group(2) in ("BAT", "BATTERY")
        if on_battery:
            soc = int(m.group(4) or m.group(5))
            cur.append((int(m.group(1)), soc, float(m.group(3))))
            continue
        if cur and (m or "app start" in line):
            found.append(cur)
            cur = []
    if cur:
        found.append(cur)
    return [((r[-1][0] - r[0][0]) / 60.0, r[0][1], r[-1][1], r[0][2], r[-1][2]) for r in found if len(r) > 1]


def main(argv):
    path = argv[argv.index("-o") + 1] if "-o" in argv else \
        "burn-helper-battery-%s.log" % datetime.datetime.now().strftime("%Y%m%d-%H%M")
    text = fetch()
    with open(path, "w") as f:
        f.write(text)
    print("Saved %d lines to %s" % (text.count("\n"), path))
    for minutes, s0, s1, v0, v1 in runs(text):
        used = s0 - s1
        rate = used / (minutes / 60.0) if minutes else 0
        print("on battery %3dh%02dm: %3d%% -> %3d%% (%.2f V -> %.2f V)%s" % (
            minutes // 60, minutes % 60, s0, s1, v0, v1, ", %.1f%% an hour" % rate if used > 0 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
