#!/usr/bin/env python3
"""Render the connection-lost screens -> tools/sim/out/lost_*.png, and all of them on one contact
sheet at 3x, tools/sim/out/lost_sheet.png

    python3 tools/sim/preview_lost.py

Every theme in the first minute (both turns of its caption), on its lost page, and with the
back-online caption; then Desktop mode and the Debug pages while lost, and Desktop before any
data came, for comparison. Example data and placeholder network names only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import pvshim  # noqa: E402
import preview_views as PV  # noqa: E402
import scene as S  # noqa: E402
import views  # noqa: E402

OUT = os.path.join(HERE, "out")
M = 1000000
THEMES = ("hero", "gameshow", "chocolates")
T = 400000          # the frame time; the caption takes turns every S.LOST_CAPTION_MS


def status(gone_ms=None, net="BRIDGE NOT ANSWERING", trouble="bridge", t=T):
    """A busy badge (4 agents, a session waiting) whose data stopped gone_ms ago; None: still fresh."""
    st = S.Status()
    st.update({"level": 3, "busy": 3, "subagents": 1, "waiting": 1, "idle": 1, "sessions": 5, "tpm": 19,
               "tools_today": 1201, "hearts": 19, "clock": "12:41",
               "waiting_list": [{"n": "api-server refactor", "s": 40}],
               "five_hour": {"used": 5.0, "resets_at": 1}, "seven_day": {"used": 58.0, "resets_at": 1}})
    st.left5, st.left7 = (57 * 60 + 12) * M, (2 * 86400 + 3 * 3600) * M
    st.online = gone_ms is None
    if gone_ms is not None:
        st.seen_ms = t - gone_ms
        st.net, st.trouble = net, trouble
        S.track_lost(st, t)
    return st


def theme_shot(name, st, t=T):
    th = __import__("theme_" + name).Theme()
    th.build()
    th.ready = True
    for k in range(6, 0, -1):           # a few frames first, so it looks mid-animation
        harness.new_screen()
        th.draw(st, t - k * 50)
    scr = harness.new_screen()
    scr.pen = pvshim.color(0, 0, 0)
    scr.clear()
    th.draw(st, t)
    return scr


def view_shot(st, view, page=0, t=T):
    scr = harness.new_screen()
    c = views.Ctx(st, PV.link(), PV.FakeTether())
    c.source = "net"
    views.draw(view, page, c, t)
    return scr


def shots():
    """(file name, label, image) for every screen on the sheet."""
    out = []
    for name in THEMES:
        out.append(("%s_blip" % name, "%s: 23 s, how long" % name, theme_shot(name, status(23000), T)))
        out.append(("%s_blip_why" % name, "%s: 25 s, why" % name, theme_shot(name, status(25000), T + 2000)))
        out.append(("%s_lost" % name, "%s: lost page, 4:12" % name, theme_shot(name, status(252000))))
        if name != "hero":              # its caption takes turns: what to try (above), the usage as of
            out.append(("%s_lost_usage" % name, "%s: lost page, usage as of" % name,
                        theme_shot(name, status(255000), T + 3000)))
        if name == "hero":
            out.append(("%s_lost_wifi" % name, "%s: lost page, Wi-Fi down" % name,
                        theme_shot(name, status(3725000, "WI-FI FAILING: PRESS B x2", "wifi"))))
        back = status()
        back.waiting, back.waiting_list = 0, []    # (a waiting session's bar would take the caption)
        back.back_ms = T - 600
        out.append(("%s_back" % name, "%s: back online" % name, theme_shot(name, back)))
    out.append(("desktop_lost", "Desktop: lost 4M12S", view_shot(status(252000), views.DESKTOP)))
    out.append(("debug_lost", "Debug overview: lost", view_shot(status(252000), views.DEBUG, 0)))
    out.append(("connection_lost", "Debug connection: lost", view_shot(status(252000), views.DEBUG, 1)))
    never = S.Status()
    never.net = "SEARCHING FOR BRIDGE..."
    out.append(("desktop_never", "Desktop: no data since boot", view_shot(never, views.DESKTOP)))
    return out


def sheet(items, path, cols=4, scale=3):
    pad, label_h = 8, 16
    tw, th = 160 * scale, 120 * scale
    rows = (len(items) + cols - 1) // cols
    big = pvshim.image(cols * (tw + pad) + pad, rows * (th + pad + label_h) + pad)
    big.pen = pvshim.color(40, 40, 48)
    big.clear()
    big.font = pvshim.font.sins
    for i, (_, label, img) in enumerate(items):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad + label_h)
        big.pen = pvshim.color(220, 220, 220)
        big.text(label.upper(), x, y)
        big.blit(img, pvshim.rect(x, y + label_h, tw, th))
    big.to_png(path, 1)
    return path


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    items = shots()
    for fname, _, img in items:
        img.to_png(os.path.join(OUT, "lost_%s.png" % fname), 3)
    print(sheet(items, os.path.join(OUT, "lost_sheet.png")))
    print(len(items), "screens ->", os.path.join(OUT, "lost_*.png"))
