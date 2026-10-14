# Wi-Fi debug screen (the last page of Debug mode: press B twice). Shows what the badge sees and why a
# network is failing, in plain words. The same text is available on the Mac
# with: python3 tools/netdebug.py

import gfx

BG = (12, 14, 20)
FG = (220, 224, 232)
DIM = (130, 136, 150)
GOOD = (110, 220, 120)
BAD = (255, 110, 100)
WARN = (255, 214, 90)
ACCENT = (217, 119, 87)


SHORT = {"connected": "OK", "wrong password": "BAD PW", "never accepted the badge": "STUCK",
         "joined but no IP address (DHCP)": "NO IP", "connect failed": "FAILED"}
SHORT["not visible (5 GHz only / out of range?)"] = "NOT SEEN"


def _fnt():
    return font.desert


def draw(link, tether, source, t, page=None):  # noqa: ARG001
    """page: "3/3" when shown as a page of Debug mode (changes the title and footer)."""
    f = _fnt()
    gfx.box(0, 0, 160, 120, BG)
    gfx.box(0, 0, 160, 11, ACCENT)
    gfx.text("WI-FI DEBUG" + (" " + page if page else ""), 3, 0, BG, f)
    st = link.state.upper()
    gfx.text(st, 157 - gfx.width(st, f), 0, BG, f)
    y = 12
    lh = 9

    def line(s, c=FG, x=3):
        nonlocal y
        gfx.text(gfx.fit(s, 157 - x, f), x, y, c, f)
        y += lh

    line("MAC " + (link.mac or "?"), DIM)
    if link.state == "up":
        line("ON %s  IP %s" % (link.ssid, link.ip), GOOD)
    elif link.status is not None and link.state == "joining":
        from net import STATUS_TEXT, since
        line("TRY %d: %s %s %ds" % (link.attempts, link.ssid, STATUS_TEXT.get(link.status, "?"),
                                    since(link.join_t0) // 1000), WARN)
    else:
        line("SCAN: %d NETWORKS VISIBLE" % link.scan_total, DIM)
    shown = 0
    for c in link.cands:
        if shown >= 3:
            break
        if c["variant"] and not c["tries"]:
            continue
        shown += 1
        info = link.seen.get(c["ssid"])
        vis = "CH%d %d" % (info[1], info[0]) if info else ""
        trying = link.cur is not None and link.cands[link.cur] is c and link.state == "joining"
        res = "TRYING" if trying else SHORT.get(c["result"], c["result"] or "-")
        col = GOOD if res == "OK" else (WARN if res == "TRYING" else (DIM if res == "-" else BAD))
        name = gfx.fit(c["ssid"] + ("*" if c["variant"] else ""), 58, f)
        gfx.text(name, 3, y, FG, f)
        gfx.text(vis, 64, y, DIM, f)
        gfx.text(res, 157 - gfx.width(res, f), y, col, f)
        y += lh
    b = link.bridge
    if tether.fresh():
        line("DATA VIA USB CABLE", GOOD)
    else:
        beacon = "BEACON NEVER" if link.beacon_t is None else "BEACON OK"
        line("BRIDGE %s %s" % ("%s:%d" % b if b else "?", beacon if link.state == "up" else ""), DIM)
    rows = gfx.wrap(link.hint(), 154, f)[:4]
    y = 110 - 9 * len(rows)
    gfx.box(0, y - 2, 160, 120 - y + 2, (34, 28, 16))
    for r in rows:
        line(r, WARN)
    gfx.text("UP:RESCAN A/C:PAGE B:NEXT" if page else "UP: RESCAN NOW   B: CLOSE", 3, 111, DIM, f)
