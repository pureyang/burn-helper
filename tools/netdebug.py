#!/usr/bin/env python3
"""Print the badge's Wi-Fi diagnosis and recent network log (badge plugged in by USB).

    python3 tools/netdebug.py

The Hearts Left app must be running on the badge. Nothing is restarted.
Passwords are never printed, only their length.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
from badge import Badge  # noqa: E402


def main():
    b = Badge()
    try:
        for _ in range(3):
            b.read(0.3)
            b.write(b"@NETLOG\n")
            got = b.read(8.0, idle=0, until=b"@NETLOG-END")
            if b"@NETLOG-BEGIN" in got and b"@NETLOG-END" in got:
                body = got.split(b"@NETLOG-BEGIN", 1)[1].split(b"@NETLOG-END", 1)[0]
                print(body.decode(errors="replace").strip("\r\n").replace("\r", ""))
                return 0
            time.sleep(1.5)
        print("The badge did not answer. Is the Hearts Left app running (not the menu)?")
        return 1
    finally:
        b.close()


if __name__ == "__main__":
    sys.exit(main())
