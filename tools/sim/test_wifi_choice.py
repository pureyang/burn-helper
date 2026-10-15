#!/usr/bin/env python3
"""Which saved network the badge joins: curly-quote names, the last one that worked first, and
falling back to another saved network when one goes out of range."""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402

harness.install()
import net  # noqa: E402

HOTSPOT_ON_AIR = "Sam\u2019s iPhone"        # how an iPhone names its hotspot
HOME = "home-wifi"


class Radio:
    """A stand-in for network.WLAN: what is in range, and the joins asked of it."""

    def __init__(self):
        self.in_range = {HOME: -56, HOTSPOT_ON_AIR: -40}
        self.joins = []
        self.connected = None

    def active(self, *a):
        return True

    def config(self, *a, **k):
        return b"\x28\xcd\xc1\x00\x00\x01"

    def isconnected(self):
        return self.connected is not None and self.connected in self.in_range

    def scan(self):
        return [(name.encode(), b"\x00\x11\x22\x33\x44\x55", 6, rssi, 3, False) for name, rssi in self.in_range.items()]

    def connect(self, ssid, psk, bssid=None):
        self.joins.append(ssid)
        self.connected = ssid if ssid in self.in_range else None

    def disconnect(self):
        self.connected = None

    def status(self):
        return 3 if self.isconnected() else -2

    def ifconfig(self):
        return ("192.168.1.50", "255.255.255.0", "192.168.1.1", "1.1.1.1")


radio = Radio()
net.network = types.SimpleNamespace(WLAN=lambda kind: radio, STA_IF=0, hostname=lambda h: None,
                                    STAT_WRONG_PASSWORD=-3, STAT_NO_AP_FOUND=-2, STAT_CONNECT_FAIL=-1)
saved = [("Sam's iPhone", "hotspot1"), (HOME, "homepass")]     # phone setup puts the newest first
remembered = []


def run(link, frames=12):
    for _ in range(frames):
        link._wifi()


# 1. the last network that worked goes first, even though the hotspot is first in the list
link = net.Net(saved, last=HOME, on_join=remembered.append)
run(link)
assert link.state == "up" and radio.connected == HOME, (link.state, radio.joins)
assert radio.joins == [HOME], radio.joins

# 2. out of range of home: the next scan finds the hotspot under its curly-quote name and joins it,
#    by the exact name on the air
del radio.in_range[HOME]
run(link)
assert link.state == "up" and radio.connected == HOTSPOT_ON_AIR, (link.state, radio.joins, link.log[-4:])
assert radio.joins[-1] == HOTSPOT_ON_AIR and remembered == ["Sam's iPhone"], (radio.joins, remembered)
assert link.cands[0]["result"] == net.OK

# 3. home again with the hotspot off: back to home
radio.in_range = {HOME: -50}
radio.connected = None
run(link)
assert radio.connected == HOME and remembered[-1] == HOME, (radio.joins, remembered)
print("PASS Wi-Fi choice: the last network that worked first, curly-quote names matched and joined "
      "as they are on the air, and out of range it moves on to another saved network")
