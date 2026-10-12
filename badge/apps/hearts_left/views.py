# The screens B cycles through after the animation: Desktop mode (everything on one screen),
# Paged mode (one topic per page, A/C turn pages) and Waiting focus (which sessions need you).
# They are opaque and the animation is paused behind them, so they cost little CPU. Usage is
# always shown as what is LEFT, never what is used. None of them turns the screen off.

import gfx
import debugview
import net
import scene as S

BG = (12, 14, 20)
FG = (230, 230, 230)
DIM = (130, 136, 150)
ACCENT = (217, 119, 87)
GOOD = (110, 220, 120)
WARN = (255, 214, 90)
BAD = (255, 110, 100)
MUTED = (60, 64, 76)

DESKTOP, PAGED, WAITING = 1, 2, 3
PAGES = ("STATUS", "USAGE LEFT", "CONNECTION", "WI-FI")
WIFI_PAGE = 3
LEVEL_NAMES = ("ASLEEP", "IDLE", "WALKING", "RUNNING", "SPRINTING")


class Ctx:
    """What the screens need, refreshed by the app every frame."""

    def __init__(self, st, link, tether):
        self.st = st
        self.link = link
        self.tether = tether
        self.source = None      # "usb" or "net"
        self.demo = 0
        self.wait_since = None  # ticks_ms when the badge first saw a session waiting


def draw(view, page, c, t):
    if view == DESKTOP:
        desktop(c, t)
    elif view == PAGED:
        paged(page, c, t)
    elif view == WAITING:
        waiting(c, t)


# ------------------------------------------------------------ shared pieces
def left5(st):
    """Percent of the 5-hour limit left, or None when unknown."""
    if st.used5 is not None:
        return max(0, min(100, int(100 - st.used5 + 0.5)))
    if st.hearts is not None:
        return st.hearts * 5
    return None


def left7(st):
    if st.used7 is not None:
        return max(0, min(100, int(100 - st.used7 + 0.5)))
    if st.week is not None:
        return int(st.week * 100 + 0.5)
    return None


def pct_colour(p):
    if p is None:
        return DIM
    return GOOD if p > 50 else (WARN if p > 20 else BAD)


def header(title, right="", colour=ACCENT):
    gfx.box(0, 0, 160, 120, BG)
    gfx.box(0, 0, 160, 11, colour)
    gfx.text(title, 3, -1, BG, font.sins)
    if right:
        gfx.text(right, 157 - gfx.width(right, font.sins), -1, BG, font.sins)


def footer(s):
    gfx.text(s, 4, 107, (120, 120, 130), font.sins)


def data_row(c):
    if c.demo:
        return "DEMO%s" % (" (NO TAG)" if c.demo == 2 else "")
    if not c.st.online:
        return "OFFLINE"
    return {"usb": "USB CABLE", "net": "WI-FI"}.get(c.source, "NONE")


def wifi_name_ip(c):
    """(name, ip) for display. Demo mode never shows the real network."""
    if c.demo:
        return "home-wifi", "192.168.1.50"
    if c.link.state == "up":
        return c.link.ssid, c.link.ip
    return (c.link.label() or c.link.state), ""


def bridge_text(c):
    if c.demo:
        return "192.168.1.20:8787", "1S AGO"
    b = c.link.bridge
    age = "" if c.link.ok_t is None else "%dS AGO" % (net.since(c.link.ok_t) // 1000)
    return ("%s:%d" % b if b else "SEARCHING"), age


def battery():
    try:
        return "USB POWER" if badge.usb_connected() else "%d%%" % badge.battery_level()
    except Exception:  # noqa: BLE001
        return "?"


def resets(left):
    if left is None:
        return ""
    return ("RESETS IN " + gfx.countdown(left)) if left > 0 else gfx.countdown(left)


def activity(st):
    """"6/15 RUNNING", "12/15 26-50 SPRINTING", or ASLEEP / IDLE when nothing is working."""
    name = LEVEL_NAMES[st.level] if 0 <= st.level < len(LEVEL_NAMES) else "?"
    if not st.tier:
        return name
    if st.tier >= 15:
        return "15/15 ULTRA"
    band = S.TIER_TEXT.get(st.tier)
    return "%d/15 %s%s" % (st.tier, (band + " ") if band else "", name)


def duration(s):
    if s < 60:
        return "%dS" % s
    if s < 3600:
        return "%dM%02dS" % (s // 60, s % 60)
    return "%dH%02dM" % (s // 3600, s % 3600 // 60)


# ------------------------------------------------------------ Desktop mode
def desktop(c, t):
    st = c.st
    header("DESKTOP MODE")
    name, ip = wifi_name_ip(c)
    brg, age = bridge_text(c)
    rows = [
        "DATA " + data_row(c),
        "WIFI %s  %s" % (name[:10], ip),
        "BRDG %s %s" % (brg, age.replace(" AGO", "").lower()),
        "BUSY %d  WAIT %d  IDLE %d" % (st.busy, st.waiting, st.idle),
        "TOOLS/MIN %d  TODAY %d" % (st.tpm, st.tools),
    ]
    for label, p, left in (("5H", left5(st), st.left5), ("7D", left7(st), st.left7)):
        when = gfx.countdown(left)
        rows.append("%s %s LEFT%s" % (label, "--" if p is None else "%d%%" % p,
                                      "" if left is None else (", RESET IN " + when if left > 0 else ", " + when)))
    rows.append("BATT %s  %s" % (battery().replace(" POWER", ""), st.clock))
    rows.insert(4, "LEVEL " + activity(st))
    if c.link.err and not c.demo:
        rows.append("ERR " + c.link.err[:22])
    y = 13
    for r in rows[:9]:
        gfx.text(gfx.fit(r, 154, font.sins), 4, y, FG, font.sins)
        y += 10
    footer("HOLD B: PHONE SETUP")


# ------------------------------------------------------------ Paged mode
def paged(page, c, t):
    right = "%d/%d" % (page + 1, len(PAGES))
    if page == WIFI_PAGE:
        debugview.draw(c.link, c.tether, c.source, t, page=right)
        return
    header(PAGES[page], right)
    if page == 0:
        _status(c)
    elif page == 1:
        _usage(c)
    else:
        _connection(c)
    footer("A/C: PAGE   B: NEXT")


def _status(c):
    st = c.st
    cols = (("WORKING", st.busy, GOOD), ("WAITING", st.waiting, WARN), ("IDLE", st.idle, DIM))
    for i, (label, n, colour) in enumerate(cols):
        cx = 27 + i * 53
        gfx.ctext(label, cx, 13, DIM, font.sins)
        gfx.ctext(str(n), cx, 25, colour if n else DIM, font.futile)
    rows = ["LEVEL " + activity(st),
            "TOOLS/MIN %d   TODAY %d" % (st.tpm, st.tools),
            "SESSIONS %d   SUBAGENTS %d" % (st.sessions, st.subagents)]
    y = 54
    for r in rows:
        gfx.text(r, 4, y, FG, font.sins)
        y += 12
    if not st.online:
        gfx.text(gfx.fit("NO DATA: " + (st.net or "WAITING FOR BRIDGE"), 154, font.sins), 4, 92, BAD, font.sins)


def _usage(c):
    st = c.st
    blocks = (("5-HOUR LIMIT", left5(st), st.left5, 14), ("WEEKLY LIMIT", left7(st), st.left7, 59))
    for label, p, left, y in blocks:
        colour = pct_colour(p)
        gfx.text(label, 4, y, FG, font.sins)
        big = "--" if p is None else "%d%%" % p
        gfx.text(big, 156 - gfx.width(big, font.unfair), y - 1, colour, font.unfair)
        gfx.meter(4, y + 20, 152, 6, None if p is None else p / 100.0, colour, MUTED)
        gfx.text(resets(left) or "NO RESET TIME YET", 4, y + 28, gfx.countdown_color(left, DIM), font.sins)
    if left5(st) is None and left7(st) is None:
        gfx.text("NO USAGE DATA YET", 4, 96, DIM, font.sins)


def _connection(c):
    name, ip = wifi_name_ip(c)
    brg, age = bridge_text(c)
    signal = ""
    if not c.demo and c.link.state == "up":
        info = c.link.seen.get(c.link.ssid)
        signal = "%d DBM" % info[0] if info else ""
    elif c.demo:
        signal = "-54 DBM"
    rows = [("DATA", data_row(c)),
            ("WI-FI", name),
            ("IP", ip or "-"),
            ("SIGNAL", signal or "-"),
            ("BRIDGE", brg),
            ("UPDATED", age or "NEVER"),
            ("BATTERY", battery()),
            ("CLOCK", c.st.clock or "-")]
    y = 13
    for k, v in rows:
        gfx.text(k, 4, y, DIM, font.sins)
        gfx.text(gfx.fit(v, 100, font.sins), 56, y, FG, font.sins)
        y += 11


# ------------------------------------------------------------ Waiting focus
def waiting(c, t):
    st = c.st
    n = st.waiting
    if n <= 0:
        header("WAITING FOCUS", "", MUTED)
        gfx.ctext("ALL CLEAR", 80, 26, GOOD, font.badgewaremax)
        gfx.ctext("NOTHING IS WAITING FOR YOU", 80, 54, DIM, font.sins)
        busy = st.agents
        gfx.ctext("%d AGENT%s WORKING" % (busy, "" if busy == 1 else "S"), 80, 68, FG, font.sins)
        footer("B: BACK TO ANIMATION")
        return
    header("WAITING FOR YOU", "", WARN)
    gfx.ctext(str(n), 80, 13, WARN, font.futile)
    gfx.ctext("SESSION NEEDS YOU" if n == 1 else "SESSIONS NEED YOU", 80, 38, FG, font.sins)
    ages = [a for _, a in st.waiting_list]
    longest = max(ages) if ages else (None if c.wait_since is None else net.since(c.wait_since) // 1000)
    if longest is not None:
        gfx.ctext("LONGEST WAIT " + duration(longest), 80, 50, DIM, font.sins)
    y = 64
    if st.waiting_list:
        for name, age in st.waiting_list[:3]:
            a = duration(age)
            gfx.text(gfx.fit(name, 150 - gfx.width(a, font.sins) - 8, font.sins), 6, y, FG, font.sins)
            gfx.text(a, 154 - gfx.width(a, font.sins), y, WARN, font.sins)
            y += 12
    else:
        gfx.ctext("ANSWER IT IN CLAUDE CODE", 80, y, DIM, font.sins)
    footer("B: BACK TO ANIMATION")
