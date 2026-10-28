#!/usr/bin/env python3
"""Draw the Burn Helper logo: a pixel glove with flames behind it, holding a terminal.

    python3 tools/make_icon.py

Writes the badge launcher icon (badge/apps/burn_helper/icon.png, 24x24, transparent) and
a larger copy for the README (docs/img/logo.png). Both come from the grids below, so they
always match. The glove has no face and no nose on purpose: it nods to a helping hand
without copying anyone's mascot.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sim"))
import harness  # noqa: E402
harness.install()
import pvshim  # noqa: E402

GLOVE = ["....oo.oo.oo.oo.."] + ["...o" + "wwo" * 4 + "."] * 5 + [
    ".ooo" + "w" * 11 + "o.",
    "o" + "w" * 14 + "o.",
    "o" + "w" * 14 + "o.",
    ".oo" + "w" * 12 + "o.",
    "...o" + "w" * 11 + "o.",
    "...o" + "w" * 11 + "o.",
    "...o" + "c" * 11 + "o.",
    "...o" + "w" * 11 + "o.",
    "...o" + "c" * 11 + "o.",
    "..." + "o" * 13 + "."]
FLAME = ["..r..", ".rr..", ".ryr.", "rryyr", "ryyyr", ".ryr."]
TERMINAL = ["oooooooooooo", "obbbbbbbbbbo", "oddddddddddo", "odgddddddddo",
            "oddgdddddddo", "odgdddggggdo", "oddddddddddo", "oooooooooooo"]
COLOURS = {"o": (20, 20, 24), "w": (244, 244, 240), "c": (52, 120, 220), "r": (226, 64, 44),
           "y": (252, 186, 48), "b": (120, 120, 132), "d": (24, 26, 32), "g": (90, 220, 120)}
# where each part sits on the 24x24 grid (column, row of its top-left cell)
GX, GY = 0, 7
PARTS = ((FLAME, GX + 3, GY - 4), (FLAME, GX + 7, GY - 6), (FLAME, GX + 11, GY - 4),
         (GLOVE, GX, GY), (TERMINAL, GX + 11, GY + 5))


def draw(size=24):
    img = pvshim.image(size, size)
    for grid, x0, y0 in PARTS:          # in order: flames behind, then the glove, then the terminal
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch != ".":
                    img.pen = pvshim.color(*COLOURS[ch])
                    img.rectangle(x0 + x, y0 + y, 1, 1)
    return img


if __name__ == "__main__":
    logo = draw()
    icon = os.path.join(harness.APP, "icon.png")
    big = os.path.join(os.path.dirname(HERE), "docs", "img", "logo.png")
    logo.to_png(icon, 1, alpha=True)
    logo.to_png(big, 8, alpha=True)
    print(icon)
    print(big)
