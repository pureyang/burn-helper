# The screens B steps through after the animation, both opaque with the animation paused
# behind them (so they cost little CPU), and neither turns the screen off:
#   Desktop: usage left and who is waiting for you; A/C step through the waiting sessions,
#            one detail card each.
#   Debug:   everything on one page, then the connection and the Wi-Fi debug pages (A/C).
# Usage is always shown as what is LEFT, never what is used.

import gfx
import debugview
import net
import power
import scene as S

BG = (12, 14, 20)
FG = (230, 230, 230)
DIM = (130, 136, 150)
ACCENT = (217, 119, 87)
GOOD = (110, 220, 120)
WARN = (255, 214, 90)
BAD = (255, 110, 100)
MUTED = (60, 64, 76)

DESKTOP, DEBUG = 1, 2
PAGES = ("DEBUG", "CONNECTION", "WI-FI")      # Debug mode's pages
WIFI_PAGE = 2
LEVEL_NAMES = ("ASLEEP", "IDLE", "WALKING", "RUNNING", "SPRINTING")


class Ctx:
    """What the screens need, refreshed by the app every frame."""

    def __init__(self, st, link, tether):
        self.st = st
        self.link = link
        self.tether = tether
        self.source = None      # "usb", "net" or "relay"
        self.demo = 0
        self.wait_since = None  # ticks_ms when the badge first saw a session waiting
        self.wait_sel = None    # Desktop: index of the waiting session shown in detail, or None


def draw(view, page, c, t):
    if view == DESKTOP:
        desktop(c, t)
    elif view == DEBUG:
        debug(page, c, t)


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
    return {"usb": "USB CABLE", "net": "WI-FI", "relay": "INTERNET RELAY"}.get(c.source, "NONE")


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
    if c.link.via == "relay":
        return "INTERNET RELAY", age
    return ("%s:%d" % b if b else "SEARCHING"), age


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
def desktop(c, t):  # noqa: ARG001
    st = c.st
    wl = st.waiting_list
    if c.wait_sel is not None and 0 <= c.wait_sel < len(wl):
        _session(c, c.wait_sel)
        return
    header("DESKTOP", "%d WORKING" % st.agents if st.online else "OFFLINE")
    # usage left
    for label, p, left, y in (("5 HOURS", left5(st), st.left5, 10), ("WEEK", left7(st), st.left7, 34)):
        colour = pct_colour(p)
        big = "--" if p is None else "%d%% LEFT" % p
        gfx.text(label, 4, y, FG, font.sins)
        gfx.text(big, 156 - gfx.width(big, font.sins), y, colour, font.sins)
        gfx.meter(4, y + 12, 152, 3, None if p is None else p / 100.0, colour, MUTED)
        gfx.text(resets(left) or "NO RESET TIME YET", 4, y + 13, gfx.countdown_color(left, DIM), font.sins)
    gfx.box(4, 59, 152, 1, MUTED)
    # waiting for you
    if not st.online and not c.demo:
        gfx.text("NO DATA YET", 4, 59, BAD, font.sins)
        gfx.text(gfx.fit(st.net or "WAITING FOR THE BRIDGE", 152, font.sins), 4, 70, DIM, font.sins)
        footer("B: DEBUG   HOLD B: SETUP")
    elif st.waiting > 0:
        gfx.text("%d WAITING FOR YOU" % st.waiting, 4, 59, WARN, font.sins)
        y = 70
        shown = wl[:2] if len(wl) > 3 else wl
        for w in shown:
            a = duration(w["s"])
            gfx.text(gfx.fit(w["n"], 146 - gfx.width(a, font.sins), font.sins), 4, y, FG, font.sins)
            gfx.text(a, 156 - gfx.width(a, font.sins), y, WARN, font.sins)
            y += 11
        if len(wl) > len(shown):
            gfx.text("+%d MORE" % (len(wl) - len(shown)), 4, y, DIM, font.sins)
        elif not wl:
            gfx.text("ANSWER IN CLAUDE CODE", 4, y, DIM, font.sins)
        footer("A/C: SESSION DETAILS" if wl else "B: DEBUG")
    else:
        gfx.text("NOTHING WAITING FOR YOU", 4, 59, GOOD, font.sins)
        footer("B: DEBUG   HOLD B: SETUP")


def _session(c, i):
    """One waiting session in detail (A/C step through them)."""
    wl = c.st.waiting_list
    w = wl[i]
    header("WAITING %d/%d" % (i + 1, len(wl)), "", WARN)
    y = 11
    for ln in gfx.wrap(w["n"], 152, font.sins)[:2]:
        gfx.text(ln, 4, y, FG, font.sins)
        y += 11
    rows = (("WAITING", duration(w["s"]), WARN),
            ("NEEDS", w["w"] or "-", WARN),
            ("FOLDER", w["d"] or "-", FG),
            ("RUNNING", duration(w["a"]) if w["a"] else "-", FG))
    y = 37
    for k, v, colour in rows:
        gfx.text(k, 4, y, DIM, font.sins)
        gfx.text(gfx.fit(v, 96, font.sins), 60, y, colour, font.sins)
        y += 12
    footer("A/C: NEXT   B: DEBUG" if len(wl) > 1 else "A/C: BACK   B: DEBUG")


# ------------------------------------------------------------ Debug mode
def debug(page, c, t):
    right = "%d/%d" % (page + 1, len(PAGES))
    if page == WIFI_PAGE:
        debugview.draw(c.link, c.tether, c.source, t, page=right)
        return
    header(PAGES[page], right)
    if page == 0:
        _overview(c)
    else:
        _connection(c)
    footer("A/C: PAGE   B: ANIMATION")


def _overview(c):
    """Everything on one page (this was Desktop mode)."""
    st = c.st
    name, ip = wifi_name_ip(c)
    brg, age = bridge_text(c)
    rows = [
        "DATA " + data_row(c),
        "WIFI %s  %s" % (name[:10], ip),
        "BRDG %s %s" % (brg, age.replace(" AGO", "").lower()),
        "BUSY %d  WAIT %d  IDLE %d" % (st.busy, st.waiting, st.idle),
        "LEVEL " + activity(st),
        "TOOLS/MIN %d  TODAY %d" % (st.tpm, st.tools),
    ]
    for label, p, left in (("5H", left5(st), st.left5), ("7D", left7(st), st.left7)):
        when = gfx.countdown(left)
        rows.append("%s %s LEFT%s" % (label, "--" if p is None else "%d%%" % p,
                                      "" if left is None else (", RESET IN " + when if left > 0 else ", " + when)))
    rows.append("BATT " + power.text())
    if c.link.err and not c.demo:
        rows.append("ERR " + c.link.err[:22])
    y = 13
    for r in rows[:9]:
        gfx.text(gfx.fit(r, 154, font.sins), 4, y, FG, font.sins)
        y += 10


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
            ("BATTERY", power.text())]
    y = 13
    for k, v in rows:
        gfx.text(k, 4, y, DIM, font.sins)
        gfx.text(gfx.fit(v, 100, font.sins), 56, y, FG, font.sins)
        y += 11
