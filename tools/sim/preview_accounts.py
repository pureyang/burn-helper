#!/usr/bin/env python3
"""Render more than one Claude account -> tools/sim/out/accounts_*.png, and all of them on one
contact sheet at 3x, tools/sim/out/accounts_sheet.png

    python3 tools/sim/preview_accounts.py

Every theme with one other account (a row under the HUD) and with four (the most there is room
for: one 5-hour limit nearly out, one week on course to run out, one with old numbers); then one
theme while the data is lost. Example labels and data only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import preview_lost as PL  # noqa: E402
import time  # noqa: E402
if not hasattr(time, "ticks_us"):                 # the shim has ticks_ms only; the rows' clocks need this too
    time.ticks_us = lambda: time.ticks_ms() * 1000
import scene as S  # noqa: E402

OUT = os.path.join(HERE, "out")
THEMES = ("hero", "gameshow", "chocolates")
NOW = 1800000000
LIT, DARK = 400100, 401500          # frame times with the likely-spent hearts lit, and gone dark

ACME = {"l": "ACME", "h": 14, "e": None, "r": NOW + 2 * 3600 + 14 * 60, "w": "5h", "u": "ok"}
MORE = [
    {"l": "ACME", "h": 2, "e": None, "r": NOW + 65 * 60, "w": "5h", "u": "ok"},         # 5-hour nearly out
    {"l": "WORK", "h": 9, "e": 0, "r": NOW + 44 * 3600, "w": "wk", "u": "ok"},           # runs out before the reset
    {"l": "SIDE", "h": 17, "e": 12, "r": NOW + 5 * 86400 + 3 * 3600, "w": "wk", "u": "ok"},
    {"l": "TEAM", "h": 12, "e": None, "r": NOW + 3 * 86400, "w": "wk", "u": "old"},      # no report for a while
]


def status(accounts):
    st = S.Status()
    st.update({"level": 3, "busy": 3, "subagents": 1, "waiting": 0, "idle": 1, "sessions": 5, "tpm": 19,
               "tools_today": 1201, "hearts": 8, "clock": "14:05", "mode": "week", "hearts_end": 4,
               "label": "GMAIL", "accounts": accounts, "now_ms": NOW * 1000,
               "five_hour": None, "seven_day": {"used": 60.0, "resets_at": NOW + 2 * 86400},
               "pace": {"s": 0, "p": 4, "f": 80, "even": 70}})
    st.online = True
    st.tick()
    return st


def shots():
    out = []
    for name in THEMES:
        out.append(("%s_two" % name, "%s: 2 accounts" % name, PL.theme_shot(name, status([ACME]), LIT)))
        out.append(("%s_five_lit" % name, "%s: 5 accounts" % name, PL.theme_shot(name, status(MORE), LIT)))
        out.append(("%s_five_dark" % name, "%s: 5, likely spent dark" % name, PL.theme_shot(name, status(MORE), DARK)))
    st = status(MORE)
    st.online, st.seen_ms = False, PL.T - 20000
    S.track_lost(st, PL.T)
    out.append(("hero_lost", "hero: data lost", PL.theme_shot("hero", st)))
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    items = shots()
    for fname, _, img in items:
        img.to_png(os.path.join(OUT, "accounts_%s.png" % fname), 3)
    print(PL.sheet(items, os.path.join(OUT, "accounts_sheet.png")))
    print(len(items), "screens ->", os.path.join(OUT, "accounts_*.png"))
