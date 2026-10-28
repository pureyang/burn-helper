"""Shared pieces for prototyping the weekly-reset ladder (tools/sim/proto_reset_<theme>.py).

The ladder is the same on every theme; each theme draws its own version of every stage. Each
prototype renders FRAMES frames per stage into tools/sim/out/proto/reset_<theme>_<stage>_<i>.png
and writes tools/sim/out/proto/reset_<theme>.json: a list of
  {"key", "title", "desc", "left", "frames": [file names], "notes"}
in STAGES order. tools/sim/reset_page.py builds the approval page from those.
Prototype only: nothing here touches badge/.
"""
import json
import os

import proto_common as P
import scene as S

FRAMES = 4
M = 1000000
# key, label, microseconds left to the weekly reset when the frames are drawn, frame spread (ms)
STAGES = (
    ("day", "Under 24 hours", 20 * 3600 * M, 700),
    ("six", "Under 6 hours", 5 * 3600 * M + 40 * 60 * M, 1100),       # the HUD alternates 5-hour / weekly
    ("hour", "Under 1 hour", 48 * 60 * M, 450),                        # caption + a pulsing meter
    ("ten", "Under 10 minutes", 9 * 60 * M + 20 * M, 350),             # the interstitial
    ("minute", "Under 1 minute", 41 * M + 380000, 300),                # full-screen countdown
    ("ten_s", "Under 10 seconds", 6 * M + 120000, 250),                # flashing numbers
    ("zero", "At the reset", -1 * M, 600),                             # the celebration
)
KEYS = [s[0] for s in STAGES]


def status(left7_us, hearts=9, agents=3):
    st = P.status(agents=agents, hearts=hearts)
    st.left7 = left7_us
    st.left5 = (2 * 3600 + 20 * 60) * M          # the 5-hour window, nowhere near its reset
    st.week = 0.35
    return st


def out_name(theme, key, i):
    return "reset_%s_%s_%d.png" % (theme, key, i)


def write_manifest(theme, items):
    os.makedirs(P.OUT, exist_ok=True)
    path = os.path.join(P.OUT, "reset_%s.json" % theme)
    with open(path, "w") as f:
        json.dump(items, f, indent=1)
    return path
