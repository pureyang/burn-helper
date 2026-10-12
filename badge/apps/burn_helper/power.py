# Battery and USB power: one cached reading for the screens, and a small log so the battery
# can be checked after the badge has run unplugged (python3 tools/netdebug.py shows it).
#
# The level comes from the firmware's badge.battery_level(), a LiPo curve on the voltage
# (4.10 V full, about 3.05 V empty). While USB charges the battery the voltage reads higher
# than the battery really is, so the level is only meaningful unplugged.

import time

LOG_FILE = "/state/burn_helper_power.log"
LOG_MAX = 8192
CACHE_MS = 2000
LOG_ON_BATTERY_MS = 60 * 1000
LOG_ON_USB_MS = 5 * 60 * 1000

_cache = [None, None]        # reading, ticks_ms it was taken
_log = [None, None]          # ticks_ms of the last log line, usb state at that line


def read():
    """(usb, charging, volts, percent), or None if the firmware cannot tell. Cached for 2 s."""
    now = time.ticks_ms()
    if _cache[1] is not None and time.ticks_diff(now, _cache[1]) < CACHE_MS:
        return _cache[0]
    try:
        r = (bool(badge.usb_connected()), bool(badge.is_charging()), badge.battery_voltage(),
             int(badge.battery_level()))
    except Exception:  # noqa: BLE001
        r = None
    _cache[0], _cache[1] = r, now
    return r


def text(short=False):
    """What the screens show: "41% 3.62V" on battery, "64% CHARGING" or "USB" on the cable."""
    r = read()
    if r is None:
        return "?"
    usb, charging, volts, pct = r
    if usb and charging:
        return "%d%% CHG" % pct if short else "%d%% CHARGING" % pct
    if usb:
        # not charging on USB: the battery is full, or there is none
        return "USB" if short else ("USB, FULL" if volts >= 4.0 else "USB POWER")
    return "%d%% %.2fV" % (pct, volts)


def _raw():
    """The battery voltage before the firmware's 1.1 V reference correction, and that reference."""
    try:
        import machine
        cf = 3.3 / 65536
        vb = machine.ADC(machine.Pin.board.VBAT_SENSE)
        vr = machine.ADC(machine.Pin.board.SENSE_1V1)
        b = r = 0
        for _ in range(10):
            b += vb.read_u16()
            r += vr.read_u16()
        return b / 10 * cf * 2, r / 10 * cf
    except Exception:  # noqa: BLE001
        return 0.0, 0.0


def tick(boot_ms):
    """Log a reading every minute on battery, every 5 minutes on USB, and at every plug/unplug."""
    now = time.ticks_ms()
    r = read()
    if r is None:
        return
    usb = r[0]
    every = LOG_ON_USB_MS if usb else LOG_ON_BATTERY_MS
    if _log[0] is not None and _log[1] == usb and time.ticks_diff(now, _log[0]) < every:
        return
    _log[0], _log[1] = now, usb
    naive, vref = _raw()
    line = "%6ds %s%s v=%.3f level=%d%% (before 1.1V correction %.3f, 1.1V rail reads %.3f)" % (
        time.ticks_diff(now, boot_ms) // 1000, "USB" if usb else "BATTERY",
        " charging" if r[1] else "", r[2], r[3], naive, vref)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def trim():
    """Keep the log small; call once at start."""
    try:
        import os
        if os.stat(LOG_FILE)[6] > LOG_MAX:
            with open(LOG_FILE) as f:
                keep = f.read()[-LOG_MAX // 2:]
            with open(LOG_FILE, "w") as f:
                f.write(keep)
        with open(LOG_FILE, "a") as f:
            f.write("---- app start ----\n")
    except Exception:  # noqa: BLE001
        pass


def recent(n=8):
    try:
        with open(LOG_FILE) as f:
            return [ln.rstrip("\n") for ln in f.read().split("\n")[-n - 1:] if ln]
    except Exception:  # noqa: BLE001
        return []
