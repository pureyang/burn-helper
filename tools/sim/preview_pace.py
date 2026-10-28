#!/usr/bin/env python3
"""Render the weekly pace on the badge -> tools/sim/out/pace_*.png, and all of them on one contact
sheet at 3x, tools/sim/out/pace_sheet.png

    python3 tools/sim/preview_pace.py

Every theme calm (only the tick), with both lines of its watch and heads-up captions, and with
the "pace eased" and (opt-in) room-left captions; then each Desktop mode line, and the Debug
overview. Example data only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import preview_lost as PL  # noqa: E402
import scene as S  # noqa: E402
import views  # noqa: E402

OUT = os.path.join(HERE, "out")
M = 1000000
THEMES = ("hero", "gameshow", "chocolates")
LINE0, LINE1 = 396100, 399100       # frame times showing a caption's first and second line

# (used, hours into the week, pace): the week's stories, as the bridge would send them
CALM = (58, 119.7, {"s": 0, "p": 1, "f": 65, "even": 71, "win": 1.6, "learn": 0})
WATCH = (64, 81, {"s": 1, "p": 72, "f": 104, "at": "SUN 4PM", "early": 21 * 3600, "even": 48, "win": 1.3})
WARN = (88, 140, {"s": 2, "p": 93, "f": 112, "at": "SUN 6PM", "early": 19 * 3600, "even": 83, "win": 0.4})
EASED = (70, 128, {"s": 0, "p": 22, "f": 86, "even": 76, "eased": 1, "win": 1.1})
ROOM = (65, 160, {"s": 0, "p": 0, "f": 67, "even": 95, "room": 1, "win": 1.3})
OUT_ = (100, 150, {"s": 3, "p": 100, "f": 100, "even": 89})


def status(story, cap="", hearts=12):
    used, hours, pc = story
    st = S.Status()
    pc = dict(pc, left=100 - used, cap=cap)
    st.update({"level": 3, "busy": 3, "subagents": 1, "waiting": 0, "idle": 1, "sessions": 5, "tpm": 19,
               "tools_today": 1201, "hearts": hearts, "clock": "14:05",
               "five_hour": {"used": (20 - hearts) * 5.0, "resets_at": 1}, "seven_day": {"used": float(used), "resets_at": 1},
               "pace": pc})
    st.online = True
    st.left5, st.left7 = (2 * 3600 + 14 * 60) * M, int((168 - hours) * 3600) * M
    return st


def desktop_at(st, k):
    """Desktop mode at the k-th turn of the WEEK line (0 the reset, then each pace line)."""
    n = len(S.pace_lines(st)) + 1
    return PL.view_shot(st, views.DESKTOP, 0, (100 * n + k) * S.PACE_LINE_MS + 100)


def shots():
    out = []
    for name in THEMES:
        out.append(("%s_calm" % name, "%s: calm, the tick" % name, PL.theme_shot(name, status(CALM), LINE0)))
        for i, t in enumerate((LINE0, LINE1)):
            out.append(("%s_watch_%d" % (name, i), "%s: watch %d/2" % (name, i + 1),
                        PL.theme_shot(name, status(WATCH, "watch"), t)))
        for i, t in enumerate((LINE0, LINE1)):
            out.append(("%s_warn_%d" % (name, i), "%s: heads-up %d/2" % (name, i + 1),
                        PL.theme_shot(name, status(WARN, "warn", 6), t)))
        out.append(("%s_eased" % name, "%s: pace eased" % name, PL.theme_shot(name, status(EASED, "eased"), LINE0)))
        out.append(("%s_room" % name, "%s: room left (opt-in)" % name, PL.theme_shot(name, status(ROOM, "room"), LINE0)))
    out.append(("desktop_calm", "Desktop: calm, left at reset", desktop_at(status(CALM), 1)))
    out.append(("desktop_calm2", "Desktop: calm, windows left", desktop_at(status(CALM), 2)))
    out.append(("desktop_calm_reset", "Desktop: calm, the reset", desktop_at(status(CALM), 0)))
    out.append(("desktop_watch", "Desktop: watch", desktop_at(status(WATCH), 1)))
    out.append(("desktop_warn", "Desktop: heads-up", desktop_at(status(WARN, hearts=6), 1)))
    out.append(("desktop_eased", "Desktop: pace eased", desktop_at(status(EASED), 1)))
    out.append(("desktop_room", "Desktop: room left (opt-in)", desktop_at(status(ROOM), 1)))
    out.append(("desktop_out", "Desktop: limit reached", desktop_at(status(OUT_, hearts=0), 1)))
    out.append(("debug_pace", "Debug overview: watch", PL.view_shot(status(WATCH, "watch"), views.DEBUG, 0)))
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    items = shots()
    for fname, _, img in items:
        img.to_png(os.path.join(OUT, "pace_%s.png" % fname), 3)
    print(PL.sheet(items, os.path.join(OUT, "pace_sheet.png")))
    print(len(items), "screens ->", os.path.join(OUT, "pace_*.png"))
