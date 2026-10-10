#!/usr/bin/env python3
"""Render the Hearts Left themes on the desktop, no badge needed.

    python3 tools/simulate.py                 # contact sheet per theme -> tools/sim/out/
    python3 tools/simulate.py zelda           # one theme
    python3 tools/simulate.py --frames zelda 3   # animation frames for level 3

The drawing code is the same module the badge runs; only the picovector API is
replaced by tools/sim/pvshim.py, which follows the pixel rules measured on the
device.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sim"))
import harness  # noqa: E402

harness.install()
import pvshim  # noqa: E402
import scene  # noqa: E402

OUT = os.path.join(HERE, "sim", "out")
THEMES = ["zelda", "runningman", "forrest"]

M = 1000000  # microseconds
SCENARIOS = [
    # label, t (ms), status fields (left5/left7 = microseconds until the window resets)
    ("0 asleep", 1000, dict(level=0, hearts=20, week=0.92, busy=0, sessions=2, tools=0, left5=-3600 * M)),
    ("1 idle", 2000, dict(level=1, hearts=17, week=0.8, busy=0, sessions=3, tools=14, left5=(2 * 3600 + 13 * 60) * M)),
    ("2 walk", 3100, dict(level=2, hearts=13, week=0.7, busy=1, sessions=3, tools=128, tpm=6, left5=(13 * 60 + 42) * M)),
    ("3 run", 4200, dict(level=3, hearts=9, week=0.55, busy=3, sessions=5, tools=402, tpm=22, left5=42173000)),
    ("4 sprint", 5300, dict(level=4, hearts=5, week=0.3, busy=6, sessions=8, tools=1337, tpm=48, subagents=4, left5=9173248)),
    ("4 sprint (alt)", 7350, dict(level=4, hearts=3, week=0.2, busy=5, sessions=8, tools=2048, tpm=55, subagents=3, left5=4 * 60 * M)),
    ("waiting", 6000, dict(level=2, hearts=11, week=0.6, busy=1, waiting=2, sessions=4, tools=250, tpm=4, left5=(65 * 60) * M)),
    ("offline", 6600, dict(level=0, hearts=None, week=None, online=False, net="SEARCHING FOR BRIDGE...")),
]


def status(**kw):
    st = scene.Status()
    st.online = True
    st.net = ""
    for k, v in kw.items():
        setattr(st, k, v)
    return st


def load(name):
    mod = __import__("theme_" + name)
    return mod.Theme()


def render(theme, st, t, warm=True):
    scr = harness.new_screen()
    if warm:
        # run a few frames first so scroll positions look mid-animation
        for k in range(6, 0, -1):
            harness.new_screen()
            theme.draw(st, t - k * 50)
        scr = harness.new_screen()
    scr.pen = pvshim.color(0, 0, 0)
    scr.clear()
    theme.draw(st, t)
    return scr


def sheet(name):
    theme = load(name)
    cols = 4
    scale = 2
    tiles = []
    for label, t, kw in SCENARIOS:
        theme.last_t = None
        tiles.append((label, render(theme, status(**kw), t)))
    rows = (len(tiles) + cols - 1) // cols
    pad = 6
    tw, th = 160 * scale, 120 * scale
    big = pvshim.image(cols * (tw + pad) + pad, rows * (th + pad + 14) + pad)
    big.pen = pvshim.color(40, 40, 48)
    big.clear()
    big.font = pvshim.font.sins
    for i, (label, img) in enumerate(tiles):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad + 14)
        big.pen = pvshim.color(220, 220, 220)
        big.text(label, x, y)
        big.blit(img, pvshim.rect(x, y + 14, tw, th))
    path = os.path.join(OUT, "sheet_%s.png" % name)
    big.to_png(path, 1)
    # also the individual 2x screens, handy for the README
    for (label, img) in tiles:
        img.to_png(os.path.join(OUT, "%s_%s.png" % (name, label.split()[0] + ("b" if "alt" in label else ""))), 2)
    return path


def frames(name, level):
    theme = load(name)
    kw = dict(SCENARIOS[min(level, 4)][2])
    st = status(**kw)
    n = 8
    big = pvshim.image(n * 162, 122)
    for i in range(n):
        img = render(theme, st, 5000 + i * 70, warm=(i == 0))
        big.blit(img, pvshim.vec2(1 + i * 162, 1))
    path = os.path.join(OUT, "frames_%s_%d.png" % (name, level))
    big.to_png(path, 2)
    return path


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    if argv and argv[0] == "--frames":
        print(frames(argv[1], int(argv[2])))
        return
    for name in (argv or THEMES):
        try:
            print(sheet(name))
        except ImportError as e:
            print("skip", name, e)


if __name__ == "__main__":
    main(sys.argv[1:])
