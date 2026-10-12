#!/usr/bin/env python3
"""Render one frame per beat of the hidden 20-second video demo -> docs/img/video_storyboard.png

Runs the badge's own demo code (VIDEO_STEPS and demo_status in the app's __init__.py) on a
simulated clock, so the storyboard always matches what the badge plays.
"""
import os, re, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)
import simulate as sm  # noqa: E402  (installs the simulator)
import pvshim  # noqa: E402
import scene as S  # noqa: E402

APP = os.path.join(os.path.dirname(TOOLS), "badge", "apps", "burn_helper", "__init__.py")
OUT = os.path.join(os.path.dirname(TOOLS), "docs", "img", "video_storyboard.png")
BEATS = ((1.5, "0-3 s  asleep"), (3.7, "3-4.5 s  wakes up"), (5.5, "4.5-7 s  1 agent: walks"),
         (7.7, "7-8.5 s  5 agents: runs"), (9.2, "8.5-10 s  9 agents: sprints"),
         (11.5, "10-13 s  a session needs you"), (14.0, "13-15 s  40 agents: sparks"),
         (15.5, "15-16 s  88 agents: red edge"), (18.5, "16-20 s  128: hyperspace"))


def demo_code():
    src = open(APP).read()
    m = re.search(r"# Two demos, both on the hero theme only.*?(?=\n\n\ndef lights)", src, re.S)
    return m.group(0)


def main():
    clock = {"ms": 0}
    ns = {"S": S, "st": S.Status(), "view": 0, "demo": 0, "demo_t0": 0,
          "time": types.SimpleNamespace(ticks_ms=lambda: clock["ms"], ticks_diff=lambda a, b: a - b,
                                        ticks_us=lambda: 0),
          "views": types.SimpleNamespace(WAITING=3), "prefs": {"theme": "hero"}, "switch": lambda **k: None}
    exec(demo_code(), ns)
    ns["set_demo"](2)
    theme = sm.load("hero")
    cols, scale, pad = 3, 2, 6
    big = pvshim.image(cols * (160 * scale + pad) + pad, 3 * (120 * scale + pad + 14) + pad)
    big.pen = pvshim.color(40, 40, 48)
    big.clear()
    big.font = pvshim.font.sins
    for i, (sec, label) in enumerate(BEATS):
        clock["ms"] = int(sec * 1000)
        ns["demo_status"](clock["ms"])
        theme.last_t = None
        img = sm.render(theme, ns["st"], clock["ms"] + 5000)
        x = pad + (i % cols) * (160 * scale + pad)
        y = pad + (i // cols) * (120 * scale + pad + 14)
        big.pen = pvshim.color(220, 220, 220)
        big.text(label, x, y)
        big.blit(img, pvshim.rect(x, y + 14, 160 * scale, 120 * scale))
    big.to_png(OUT, 1)
    print(OUT)


if __name__ == "__main__":
    main()
