# Battery and USB power: an estimate of the battery's charge for the screens, and a small log so
# the battery can be checked after the badge has run unplugged (python3 tools/netdebug.py shows it).
#
# The firmware's badge.battery_level() turns the battery voltage straight into a percentage, and
# that goes wrong two ways. Its voltage is corrected against a "1.1 V" reference that really reads
# 1.164 V, so it is about 5% low, and further off as the 3.3 V supply sags on a nearly empty
# battery (it showed 0% for ten minutes while the badge kept running). And while USB charges the
# battery the voltage reads well above its real charge, so the level leapt from 1% to 50% in a
# minute. So the badge keeps its own estimate:
#   * the voltage is measured against the reference's real value, which also follows the sag,
#   * mapped through a discharge curve measured on this badge, at its own load,
#   * smoothed, so a short dip under load (Wi-Fi sending) doesn't move it,
#   * on battery it only goes down (up only slowly, to correct itself after charging),
#   * charging, it rises no faster than the battery can take charge, 100% when the charger stops,
#   * and it is kept across app restarts.

import time

LOG_FILE = "/state/burn_helper_power.log"
SOC_FILE = "/state/burn_helper_soc.json"
LOG_MAX = 8192
CACHE_MS = 2000
LOG_ON_BATTERY_MS = 60 * 1000
LOG_ON_USB_MS = 5 * 60 * 1000

REF_VOLTS = 1.164            # what the "1.1 V" rail really is on this badge (logged while healthy)
# true battery volts under the badge's own load -> percent left, measured from a full discharge
# (the bottom from timed log lines, the top from a fresh unplug at 4.13 V)
CURVE = ((3.07, 0.0), (3.27, 2.5), (3.37, 6.0), (3.39, 9.0), (3.456, 15.0), (3.52, 19.0), (3.58, 25.0),
         (3.64, 33.0), (3.69, 42.0), (3.74, 52.0), (3.80, 62.0), (3.87, 72.0), (3.95, 82.0),
         (4.05, 92.0), (4.13, 100.0))
CHARGE_OFFSET = 0.15         # charging lifts the battery's voltage about this much above its real charge
CHARGE_PCT_PER_MIN = 1.0     # at most this fast while charging (about 100 minutes from empty to full)
RISE_PCT_PER_MIN = 0.5       # on battery the estimate only creeps up, to correct itself after charging
SMOOTH = 0.08                # how much each 2-second reading moves the smoothed voltage
KEEP_SOC_MS = 10 * 60 * 1000 # a saved estimate older than this is not trusted after a restart

_cache = [None, None]        # reading, ticks_ms it was taken
_log = [None, None]          # ticks_ms of the last log line, usb state at that line
_est = {"v": None, "soc": None, "t": None, "saved": None}


def soc_from_volts(v):
    """Percent left for a true battery voltage on battery, from CURVE."""
    if v <= CURVE[0][0]:
        return 0.0
    for (v0, p0), (v1, p1) in zip(CURVE, CURVE[1:]):
        if v <= v1:
            return p0 + (p1 - p0) * (v - v0) / (v1 - v0)
    return 100.0


def estimate(soc, v, usb, charging, minutes):
    """The next estimate from the last one (None at first), the smoothed true voltage, the power
    state and the minutes since the last estimate."""
    if usb and not charging:
        # on the cable and not charging: the charger has finished (or there is no battery)
        return 100.0 if v >= 3.9 else soc_from_volts(v)
    target = soc_from_volts(v - CHARGE_OFFSET) if charging else soc_from_volts(v)
    if soc is None:
        return target
    if charging:
        return max(soc, min(target, soc + CHARGE_PCT_PER_MIN * minutes))
    if target < soc:
        return target
    return min(target, soc + RISE_PCT_PER_MIN * minutes)


def true_volts():
    """The battery voltage measured against the 1.1 V rail's real value, or None."""
    naive, ref = _raw()
    if not naive or not ref:
        return None
    return naive * REF_VOLTS / ref


def _load():
    try:
        import json
        with open(SOC_FILE) as f:
            d = json.loads(f.read())
        return d.get("soc"), d.get("at")
    except Exception:  # noqa: BLE001
        return None, None


def _save(soc):
    try:
        import json
        with open(SOC_FILE, "w") as f:
            f.write(json.dumps({"soc": round(soc, 1), "at": time.time()}))
    except Exception:  # noqa: BLE001
        pass


def read():
    """(usb, charging, volts, percent), or None if the firmware cannot tell. Cached for 2 s."""
    now = time.ticks_ms()
    if _cache[1] is not None and time.ticks_diff(now, _cache[1]) < CACHE_MS:
        return _cache[0]
    try:
        usb, charging = bool(badge.usb_connected()), bool(badge.is_charging())
        v = true_volts()
        if v is None:
            v = badge.battery_voltage()
    except Exception:  # noqa: BLE001
        _cache[0], _cache[1] = None, now
        return None
    e = _est
    e["v"] = v if e["v"] is None else e["v"] + SMOOTH * (v - e["v"])
    if e["soc"] is None:
        saved, at = _load()
        if saved is not None and at is not None and 0 <= time.time() - at < KEEP_SOC_MS / 1000:
            e["soc"] = float(saved)          # carry on from before the restart
    minutes = 0.0 if e["t"] is None else time.ticks_diff(now, e["t"]) / 60000.0
    e["soc"] = estimate(e["soc"], e["v"], usb, charging, minutes)
    e["t"] = now
    if e["saved"] is None or time.ticks_diff(now, e["saved"]) > 60000:
        _save(e["soc"])
        e["saved"] = now
    r = (usb, charging, e["v"], int(e["soc"] + 0.5))
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
        return "USB" if short else ("USB, FULL" if volts >= 3.9 else "USB POWER")
    return "%d%% %.2fV" % (pct, volts)


def _raw():
    """The battery voltage reckoned against a 3.3 V supply, and what the 1.1 V rail reads that way."""
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
    try:
        fw = "%.3f %d%%" % (badge.battery_voltage(), int(badge.battery_level()))
    except Exception:  # noqa: BLE001
        fw = "?"
    line = "%6ds %s%s v=%.3f soc=%d%% (raw %.3f, 1.1V rail reads %.3f, firmware says %s)" % (
        time.ticks_diff(now, boot_ms) // 1000, "USB" if usb else "BATTERY",
        " charging" if r[1] else "", r[2], r[3], naive, vref, fw)
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
