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
GOOD = (86, 180, 233)       # Okabe-Ito sky blue, yellow and orange (light, for the dark screen),
WARN = (239, 226, 122)      # never red and green; every one comes with a number or words
BAD = (245, 160, 90)
MUTED = (60, 64, 76)

DESKTOP, DEBUG = 1, 2
PAGES = ("DEBUG", "CONNECTION", "WI-FI")      # Debug mode's pages
WIFI_PAGE = 2
LEVEL_NAMES = ("ASLEEP", "IDLE", "WALKING", "RUNNING", "SPRINTING")
PACE_NAMES = ("CALM", "WATCH", "HEADS-UP", "OUT")


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
left5 = S.pct5      # percent of each limit left, or None when unknown
left7 = S.pct7


def end_pct(st):
    """Percent of the week likely left at the reset, at this pace (the pace's forecast), or None."""
    pc = st.pace
    return None if pc is None else max(0, min(100, 100 - pc["f"]))


def week_end(st):
    """end_pct, for the weekly meter's stripes: None once the limit is reached or the week unknown."""
    pc = st.pace
    return None if pc is None or pc["s"] == S.PACE_OUT or st.week is None or not st.online else end_pct(st)


def pace_turns(st, striped):
    """The weekly pace's lines for a WEEK line to take turns with. Where its meter is striped, the
    calm one (PACE: ~84% LEFT AT RESET) goes: the stripes already show it."""
    return [x for x in S.pace_lines(st) if not (striped and x[0].startswith("PACE: "))]


def forecast_meter(x, y, w, h, p, end, colour):
    """A meter of p percent left. With end, the percent likely left at the reset at this pace, the
    part this pace likely uses before then is striped: solid is what is likely still there at the
    reset, stripes what goes before it, grey what is used. Pattern as well as colour."""
    gfx.box(x, y, w, h, MUTED)
    if p is None:
        return
    nw = (w * max(0, min(100, p)) + 50) // 100
    ew = nw if end is None else min(nw, (w * max(0, min(100, end)) + 50) // 100)
    if ew:
        gfx.box(x, y, ew, h, colour)
    for r in range(h):
        # 2 pixels on, 2 off, one further along on each row down: diagonal stripes
        for c in range(ew - (ew + r) % 4, nw, 4):
            a, b = max(c, ew), min(c + 2, nw)
            if b > a:
                gfx.box(x + a, y + r, b - a, 1, colour)


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


LOW_BANNER_MS, LOW_BANNER_EVERY_MS = 6000, 45000    # low: shown for 6 s of every 45 s


def battery_banner(w, t):
    """Whether the battery warning `w` (from power.warning) is on screen at tick t: critical stays,
    low comes round now and then so it does not sit on the scene all the time."""
    return w is not None and (w[0] >= 2 or t % LOW_BANNER_EVERY_MS < LOW_BANNER_MS)


def draw_battery_warning(w):
    """A banner over any screen: the charge, and the time left when the badge knows it. Orange, with
    words, never red and green. The critical one has a thicker border."""
    gfx.box(6, 38, 148, 30, (0, 0, 0))
    gfx.box(6, 38, 148, 3 if w[0] >= 2 else 1, BAD)
    gfx.ctext(w[1], 80, 43, (255, 255, 255), font.sins)
    gfx.ctext(w[2], 80, 55, BAD, font.sins)


def data_row(c, t):
    if c.demo:
        return "DEMO%s" % (" (NO TAG)" if c.demo == 2 else "")
    lost = S.lost_ms(c.st, t)
    if lost is not None:
        return "LOST %s AGO" % duration(lost // 1000)
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


def resets(left, est=False):
    if left is None:
        return ""
    return (("RESETS IN ~" if est else "RESETS IN ") + gfx.countdown(left)) if left > 0 else gfx.countdown(left)


def no_report(st):
    """Why there is no usage to show, in a few words (the bridge's usage state)."""
    return {"none": "NO USAGE REPORT YET", "stale": "WAITING FOR A REPORT"}.get(st.usage_state, "NO RESET TIME YET")


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
    wl = st.waiting_list
    if c.wait_sel is not None and 0 <= c.wait_sel < len(wl):
        _session(c, c.wait_sel)
        return
    # the battery on the right: its charge, and the time left once learnt from a real run unplugged
    header("DESKTOP MODE", power.text(short=True))
    lost = None if c.demo else S.lost_ms(st, t)
    if st.accounts:
        # more than one Claude account: each one's usage, named (see the accounts section below)
        usage = [_main_usage(st, lost)] + [_other_usage(st, a, lost) for a in st.accounts]
        if len(usage) == 2:
            for u, y in zip(usage, (10, 34)):
                _usage_block(st, u, y, t, lost)
            y = 59
        else:
            y = 11
            for u in usage:
                _usage_line(u, y, lost)
                y += ACCOUNT_LINE_H
            y += 1
        gfx.box(4, y, 152, 1, MUTED)
        _waiting(c, st, lost, y)
        return
    # usage left; while the connection is lost, dimmed and as of the last data. In "week" mode (a
    # plan with only a weekly limit) the week, then where it likely ends at this pace
    week = st.mode == "week"
    rows = (("WEEK", left7(st), st.left7, 10), ("AT RESET", end_pct(st), None, 34)) if week else \
        (("5 HOURS", left5(st), st.left5, 10), ("WEEK", left7(st), st.left7, 34))
    for label, p, left, y in rows:
        colour = pct_colour(p) if lost is None else DIM
        est = label == "5 HOURS" and st.est5
        big = "--" if p is None else ("~%d%%" if est or label == "AT RESET" else "%d%%") % p
        if p is not None:
            big += " " + (S.as_of(st) if lost is not None and st.seen_clock else "LEFT")
        gfx.text(label, 4, y, FG, font.sins)
        gfx.text(big, 156 - gfx.width(big, font.sins), y, colour, font.sins)
        forecast_meter(4, y + 12, 152, 3, p, week_end(st) if label == "WEEK" and lost is None else None, colour)
        line, ink = resets(left, est) or no_report(st), gfx.countdown_color(left, DIM)
        if label == "WEEK" and lost is None:
            # the weekly pace's lines in turn with the reset (but what the stripes show)
            turns = pace_turns(st, week_end(st) is not None) if left is not None and not week else []
            k = (t // S.PACE_LINE_MS) % (len(turns) + 1)
            if k:
                line, ink = turns[k - 1]
        elif label == "AT RESET":
            # the pace's lines in turn (but the calm one, which is the number above); "AT THIS PACE"
            # says what the number is
            turns = [x for x in S.pace_lines(st) if not x[0].startswith("PACE: ")] if lost is None else []
            line, ink = turns[(t // S.PACE_LINE_MS) % len(turns)] if turns else ("AT THIS PACE", DIM)
        if y == 10 and lost is None and st.usage_state == "old" and st.usage_age and (t // S.PACE_LINE_MS) % 2:
            # no status line has reported for 30 minutes or more: the numbers may be behind
            a = st.usage_age
            line, ink = "LAST REPORT %s AGO" % ("%dH%02dM" % (a // 3600, a % 3600 // 60) if a >= 3600 else "%dM" % (a // 60)), WARN
        gfx.text(gfx.fit(line, 152, font.sins), 4, y + 13, ink, font.sins)
    gfx.box(4, 59, 152, 1, MUTED)
    _waiting(c, st, lost, 59)


def _waiting(c, st, lost, y):
    """Desktop mode's lower part, from y down to the footer: who is waiting for you, or why there
    is no data. It lists as many waiting sessions as there is room for."""
    room = max(0, (105 - (y + 11)) // 11)       # lines under the title before the footer
    working = "%d WORKING" % st.agents
    if lost is not None:
        # had data, and it stopped: say how long ago and why; nothing is claimed as waiting
        lines = (("CONNECTION LOST %s AGO" % duration(lost // 1000), S.LOST), (S.lost_reason(st), FG),
                 (S.lost_advice(st), DIM))
        for k, (s, ink) in enumerate(lines[:room + 1]):
            gfx.text(gfx.fit(s, 152, font.sins), 4, y + 11 * k, ink, font.sins)
        footer("B: DEBUG   HOLD B: SETUP")
    elif not st.online and not c.demo:
        gfx.text("NO DATA YET", 4, y, BAD, font.sins)
        if room:
            gfx.text(gfx.fit(st.net or "WAITING FOR THE BRIDGE", 152, font.sins), 4, y + 11, DIM, font.sins)
        footer("B: DEBUG   HOLD B: SETUP")
    elif st.waiting > 0:
        wl = st.waiting_list
        gfx.text("%d WAITING FOR YOU" % st.waiting, 4, y, WARN, font.sins)
        gfx.text(working, 156 - gfx.width(working, font.sins), y, DIM, font.sins)
        y += 11
        shown = wl if len(wl) <= room else wl[:max(0, room - 1)]
        for w in shown:
            a = duration(w["s"])
            gfx.text(gfx.fit(S.session_label(w), 146 - gfx.width(a, font.sins), font.sins), 4, y,
                     DIM if w.get("u") else FG, font.sins)
            gfx.text(a, 156 - gfx.width(a, font.sins), y, WARN, font.sins)
            y += 11
        if len(wl) > len(shown) and shown:
            gfx.text("+%d MORE" % (len(wl) - len(shown)), 4, y, DIM, font.sins)
        elif not wl and room:
            gfx.text("ANSWER IN CLAUDE CODE", 4, y, DIM, font.sins)
        footer("A/C: SESSION DETAILS" if wl else "B: DEBUG")
    else:
        gfx.text("NOTHING WAITING", 4, y, GOOD, font.sins)
        gfx.text(working, 156 - gfx.width(working, font.sins), y, DIM, font.sins)
        footer("B: DEBUG   HOLD B: SETUP")


# More than one Claude account: Desktop mode names each one. With two, each gets the block one
# limit has on its own (its label and limit, the percent left, a meter, a line under it); with
# three to five, one line each (label, limit, percent, countdown) over a thin meter. Every account
# shows whichever of its limits has less left, as its row on the animation does; the main account
# (the one the theme's hearts follow) is first, and its line also takes turns with its other
# limit and the weekly pace. On a weekly limit, the part of the meter likely used before the
# reset is striped (forecast_meter). Grey while the data is lost or an account's numbers are old.
ACCOUNT_LINE_H = 15
LIMIT_NAMES = {"5h": ("5 HOURS", "5H"), "wk": ("WEEK", "WK")}


def _main_usage(st, lost):
    """The main account's usage, as _usage_block and _usage_line draw it."""
    p5 = None if st.mode == "week" else left5(st)
    p7 = left7(st)
    use5 = p5 is not None and (p7 is None or p5 < p7)
    p, left, est = (p5, st.left5, st.est5) if use5 else (p7, st.left7, False)
    turns = [(resets(left, est) or no_report(st), gfx.countdown_color(left, DIM))]
    if lost is None:
        other = p7 if use5 else p5
        if other is not None:
            turns.append(("%s %d%% LEFT" % ("WEEK" if use5 else "5 HOURS", other), pct_colour(other)))
        if st.left7 is not None:
            turns += pace_turns(st, not use5 and week_end(st) is not None)
        if st.usage_state == "old" and st.usage_age:
            a = st.usage_age
            turns.append(("LAST REPORT %s AGO" % ("%dH%02dM" % (a // 3600, a % 3600 // 60) if a >= 3600
                                                  else "%dM" % (a // 60)), WARN))
    return {"label": st.label or "MAIN", "w": "5h" if use5 else "wk", "p": p, "est": est, "left": left,
            "turns": turns, "end": None if use5 else week_end(st), "grey": False}


def _other_usage(st, a, lost):
    """Another account's usage, from its row (an older bridge sends no percent: its hearts give one)."""
    p, est = a.get("p"), False
    if p is None and a["h"] is not None:
        p, est = a["h"] * 5, True
    # where its week likely ends (an older bridge sends it in half hearts only)
    end = None if a["w"] != "wk" else (a.get("q") if a.get("q") is not None else
                                       (None if a["e"] is None else a["e"] * 5))
    left = st.left_of(a["r"])
    none = "NO USAGE REPORT YET" if a["u"] == "none" else "NO RESET TIME YET"
    turns = [(resets(left) or none, gfx.countdown_color(left, DIM))]
    if lost is None:
        if a["u"] == "old":
            turns.append(("LAST REPORT OVER 30M AGO", WARN))
        elif end == 0:
            # the stripes show where it likely ends; a run-out is also said in words
            turns.append(("AT THIS PACE IT RUNS OUT", S.PACE_INK[2]))
    return {"label": a["l"], "w": a["w"], "p": p, "est": est, "left": left, "turns": turns, "end": end,
            "grey": a["u"] in ("old", "none")}


def _end(u, lost):
    """The account's stripes: none while the data is lost or its numbers are old."""
    return None if lost is not None or u["grey"] else u["end"]


def _usage_colour(u, lost):
    return DIM if lost is not None or u["grey"] else pct_colour(u["p"])


def _name(u, y, short, right):
    """An account's label (white) and its limit (grey) at the left of row y, clear of x = right."""
    limit = LIMIT_NAMES[u["w"]][1 if short else 0]
    label = gfx.fit(u["label"], right - 8 - gfx.width(" " + limit, font.sins), font.sins)
    gfx.text(label, 4, y, DIM if u["grey"] else FG, font.sins)
    gfx.text(limit, 4 + gfx.width(label + " ", font.sins), y, DIM, font.sins)


def _usage_block(st, u, y, t, lost):
    """One account in Desktop mode with two accounts: as a limit on its own, named."""
    p, colour = u["p"], _usage_colour(u, lost)
    big = "--" if p is None else ("~%d%%" if u["est"] else "%d%%") % p
    if p is not None:
        big += " " + (S.as_of(st) if lost is not None and st.seen_clock else "LEFT")
    bx = 156 - gfx.width(big, font.sins)
    _name(u, y, False, bx)
    gfx.text(big, bx, y, colour, font.sins)
    forecast_meter(4, y + 12, 152, 3, p, _end(u, lost), colour)
    turns = u["turns"]
    line, ink = turns[(t // S.PACE_LINE_MS) % len(turns)]
    gfx.text(gfx.fit(line, 152, font.sins), 4, y + 13, ink, font.sins)


def _usage_line(u, y, lost):
    """One account in Desktop mode with three or more: one line and a thin meter."""
    p, colour = u["p"], _usage_colour(u, lost)
    cd = S.short_cd(u["left"])
    pct = "--" if p is None else ("~%d%%" if u["est"] else "%d%%") % p
    cx = 156 - gfx.width(cd, font.sins)
    px = cx - 6 - gfx.width(pct, font.sins)
    _name(u, y, True, px)
    gfx.text(pct, px, y, colour, font.sins)
    gfx.text(cd, cx, y, DIM if u["grey"] or lost is not None else gfx.countdown_color(u["left"], DIM), font.sins)
    forecast_meter(4, y + 12, 152, 2, p, _end(u, lost), colour)


def _session(c, i):
    """One waiting session in detail (A/C step through them)."""
    wl = c.st.waiting_list
    w = wl[i]
    header("WAITING %d/%d" % (i + 1, len(wl)), "", WARN)
    y = 11
    for ln in gfx.wrap(S.session_label(w), 152, font.sins)[:2]:
        gfx.text(ln, 4, y, DIM if w.get("u") else FG, font.sins)
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
        _overview(c, t)
    else:
        _connection(c, t)
    footer("A/C: PAGE   B: ANIMATION")


def _overview(c, t):
    """Everything on one page (this was Desktop mode)."""
    st = c.st
    name, ip = wifi_name_ip(c)
    brg, age = bridge_text(c)
    rows = [
        "DATA " + data_row(c, t),
        "WIFI %s  %s" % (name[:10], ip),
        "BRDG %s %s" % (brg, age.replace(" AGO", "").lower()),
        "BUSY %d  WAIT %d  IDLE %d" % (st.busy, st.waiting, st.idle),
        "LEVEL " + activity(st),
        "TOOLS/MIN %d  TODAY %d" % (st.tpm, st.tools),
    ]
    for label, p, left in ((("7D", left7(st), st.left7),) if st.mode == "week" else
                           (("5H", left5(st), st.left5), ("7D", left7(st), st.left7))):
        when = gfx.countdown(left)
        est = label == "5H" and st.est5
        rows.append("%s %s LEFT%s%s" % (
            label, "--" if p is None else ("~%d%%" if est else "%d%%") % p,
            "" if left is None else (", RESET IN " + ("~" if est else "") + when if left > 0 else ", " + when),
            ", " + no_report(st)[:22] if left is None and label == "5H" else ""))
    if st.mode == "week":
        rows.append("MODE WEEKLY ONLY, END %s" % ("--" if st.hearts_end is None else "%d/20" % st.hearts_end))
    pc = st.pace
    if pc is not None:
        # the step, the chance of running out, the likely use at the reset, the caption up now
        rows.append("PACE %s %d%% ~%d%%%s%s" % (PACE_NAMES[pc["s"]] if 0 <= pc["s"] < 4 else "?", pc["p"], pc["f"],
                                                {"": "", "eased": " EASED", "room": " ROOM"}.get(pc["cap"], " CAP"),
                                                " LEARNING" if pc["learn"] else ""))
    if c.link.err and not c.demo:
        rows.append("ERR " + c.link.err[:22])
    rows.append("BATT " + power.text())
    y = 12
    for r in rows[:10]:
        gfx.text(gfx.fit(r, 154, font.sins), 4, y, FG, font.sins)
        y += 9


def battery_left():
    """The Connection page's estimate of time left unplugged, and how sure it is."""
    left = power.time_left()
    if left is None:
        return "ON USB" if power.read() and power.read()[0] else "-"
    return "%s (%s)" % (power.left_text(left[0]), "LEARNT" if left[1] else "LEARNING")


def _connection(c, t):
    name, ip = wifi_name_ip(c)
    brg, age = bridge_text(c)
    signal = ""
    if not c.demo and c.link.state == "up":
        info = c.link.seen.get(c.link.ssid)
        signal = "%d DBM" % info[0] if info else ""
    elif c.demo:
        signal = "-54 DBM"
    rows = [("DATA", data_row(c, t)),
            ("WI-FI", name),
            ("IP", ip or "-"),
            ("SIGNAL", signal or "-"),
            ("BRIDGE", brg),
            ("UPDATED", age or "NEVER"),
            ("BATTERY", power.text()),
            ("TIME LEFT", battery_left())]
    y = 13
    for k, v in rows:
        gfx.text(k, 4, y, DIM, font.sins)
        gfx.text(gfx.fit(v, 100, font.sins), 56, y, FG, font.sins)
        y += 11
