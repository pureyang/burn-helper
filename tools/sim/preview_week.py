#!/usr/bin/env python3
"""Render "week" mode (a plan with only a weekly limit) -> tools/sim/out/week_*.png, and all of
them on one contact sheet at 3x, tools/sim/out/week_sheet.png

    python3 tools/sim/preview_week.py

Every theme with the hearts (lights, chocolates) as the week: on course to end with some left, and
on course to run out; each both lit and with the ones likely spent by the reset gone dark. Then
Desktop mode and the Debug overview. Example data only.
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
LIT, DARK = 400100, 401500          # frame times with the likely-spent hearts lit, and gone dark

# (used, hours into the week, pace), as the bridge would send them
ON_COURSE = (40, 98, {"s": 0, "p": 4, "f": 70, "even": 58, "learn": 0})
RUNS_OUT = (62, 70, {"s": 1, "p": 74, "f": 108, "at": "SUN 4PM", "early": 20 * 3600, "even": 42})


def status(story, cap=""):
    used, hours, pc = story
    hearts = int(round((100 - used) / 5.0))
    st = S.Status()
    st.update({"level": 3, "busy": 3, "subagents": 1, "waiting": 0, "idle": 1, "sessions": 5, "tpm": 19,
               "tools_today": 1201, "hearts": hearts, "clock": "14:05", "mode": "week",
               "hearts_end": max(0, min(hearts, int(round((100 - pc["f"]) / 5.0)))),
               "five_hour": None, "seven_day": {"used": float(used), "resets_at": 1},
               "pace": dict(pc, left=100 - used, cap=cap)})
    st.online = True
    st.left7 = int((168 - hours) * 3600) * M
    return st


def shots():
    out = []
    for name in THEMES:
        for story, tag, cap in ((ON_COURSE, "course", "on course"), (RUNS_OUT, "out", "runs out")):
            out.append(("%s_%s_lit" % (name, tag), "%s: %s" % (name, cap), PL.theme_shot(name, status(story), LIT)))
            out.append(("%s_%s_dark" % (name, tag), "%s: %s, where it ends" % (name, cap),
                        PL.theme_shot(name, status(story), DARK)))
    out.append(("desktop", "Desktop: week, at reset", PL.view_shot(status(ON_COURSE), views.DESKTOP, 0, 100)))
    out.append(("desktop_out", "Desktop: runs out", PL.view_shot(status(RUNS_OUT), views.DESKTOP, 0, 100)))
    out.append(("debug", "Debug overview", PL.view_shot(status(ON_COURSE), views.DEBUG, 0)))
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    items = shots()
    for fname, _, img in items:
        img.to_png(os.path.join(OUT, "week_%s.png" % fname), 3)
    print(PL.sheet(items, os.path.join(OUT, "week_sheet.png")))
    print(len(items), "screens ->", os.path.join(OUT, "week_*.png"))
