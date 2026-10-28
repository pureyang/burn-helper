#!/usr/bin/env python3
"""The two demo modes, beat by beat, with frames -> tools/sim/out/demo_script.html

    python3 tools/sim/demo_script.py

Runs the badge's own demo code (the demo section of the app's __init__.py) on a simulated
clock and draws the hero theme at each beat, so the page always matches what the badge plays.
"""
import html
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator)
import proto_page  # noqa: E402
import scene as S  # noqa: E402
import theme_hero  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(HERE)), "badge", "apps", "burn_helper", "__init__.py")
T0 = 10000          # the simulated clock when the demo starts (so warm-up frames stay positive)

# (from s, to s, what is on the badge, the activity animation if any, frame times in s)
DEMO1 = (
    (0, 2, "Asleep under the stars", None, (0.5, 1.0, 1.4, 1.8)),
    (2, 3.8, "A session starts: the hero steps out of a cave", "arrive", (2.1, 2.6, 3.1, 3.6)),
    (3.9, 5.4, "You send a prompt: a \"!\" and a new quest scroll. 1 agent walks", "prompt", (4.0, 4.4, 4.9, 5.3)),
    (5.6, 7.0, "Edits a file: sword combo on a slime. 2 agents", "edit", (5.8, 6.2, 6.5, 6.8)),
    (7.3, 8.9, "Reads: the lens of truth finds a rupee, while Navi calls (1 session waiting)", "read",
     (7.5, 7.9, 8.3, 8.7)),
    (9.2, 10.8, "Runs a command: a bomb. 4 agents, now running", "shell", (9.4, 9.9, 10.3, 10.6)),
    (11.1, 12.5, "On the web: the hookshot reels in a page", "web", (11.2, 11.6, 12.0, 12.4)),
    (12.8, 14.8, "A subagent: the boomerang flies out and comes back (2 sessions waiting)", "spawn",
     (13.0, 13.4, 14.2, 14.6)),
    (15.1, 16.5, "Another edit: sword combo, 8 agents sprinting", "edit", (15.3, 15.7, 16.0, 16.3)),
    (16.8, 17.8, "A tool call fails: knocked back, \"OUCH!\"", "fail", (16.9, 17.1, 17.3, 17.6)),
    (18.1, 21.4, "More edits and a bomb at 10 agents, then 11-25", "edit", (18.3, 18.9, 20.2, 20.9)),
    (21.7, 23.3, "Reads again, sparks from 26-50 agents (1 session waiting)", "read", (21.9, 22.3, 22.7, 23.1)),
    (23.4, 25.4, "Finishes its turn: item get, \"QUEST COMPLETE!\", 76-100 agents", "done", (23.6, 24.1, 24.6, 25.1)),
    (25.9, 30, "Over 100 agents: hyperspace, then it starts over", None, (26.4, 27.4, 28.4, 29.6)),
    (75, 77, "Every 90 seconds the 5-hour countdown runs out: a heart container, the hearts refill", "refill",
     (75.2, 75.8, 76.3, 76.8)),
)

DEMO2 = (
    (0, 3, "Asleep under the stars, \"LINK IS ASLEEP... ZZZ\"", None, (0.6, 1.3, 2.0, 2.7)),
    (3, 4.8, "A session starts: steps out of a cave, \"A NEW SESSION BEGINS\"", "arrive", (3.1, 3.6, 4.1, 4.6)),
    (4.8, 5.6, "1 agent: walks", None, (4.85, 5.05, 5.25, 5.45)),
    (5.6, 7.0, "Edits a file: sword combo on a slime", "edit", (5.8, 6.2, 6.5, 6.8)),
    (7, 8.5, "5 agents: runs", None, (7.2, 7.6, 8.0, 8.3)),
    (8.5, 10, "9 agents: sprints, sword out", None, (8.6, 8.9, 9.3, 9.7)),
    (10, 12.4, "A session needs you: \"HEY! LISTEN!\", the waiting counter goes to 1", None, (10.3, 10.9, 11.5, 12.1)),
    (12.4, 13.9, "You answer: a new quest scroll, \"A NEW QUEST!\" (40 agents from 13 s: sparks)", "prompt",
     (12.5, 12.9, 13.3, 13.8)),
    (14, 16, "Turn done: item get, \"QUEST COMPLETE!\" (88 agents from 15 s: pulsing edge)", "done",
     (14.2, 14.7, 15.2, 15.8)),
    (16, 20, "128 agents: hyperspace; the hearts are almost gone and the countdown runs out", None,
     (16.5, 17.5, 18.5, 19.6)),
)


def demo_runner():
    """The app's demo code with a simulated clock. Returns (namespace, clock)."""
    src = open(APP).read()
    code = re.search(r"# Two demos, both on the hero theme only.*?(?=\n\n\ndef lights)", src, re.S).group(0)
    clock = {"ms": T0}
    ns = {"S": S, "st": S.Status(), "view": 0, "demo": 0, "demo_t0": 0,
          "time": types.SimpleNamespace(ticks_ms=lambda: clock["ms"], ticks_diff=lambda a, b: a - b,
                                        ticks_add=lambda a, b: a + b, ticks_us=lambda: 0),
          "views": types.SimpleNamespace(DESKTOP=1), "prefs": {"theme": "hero"}, "switch": lambda **k: None}
    exec(code, ns)
    return ns, clock


def frames_for(kind, beats, tag):
    ns, clock = demo_runner()
    ns["set_demo"](kind)
    theme = theme_hero.Theme()
    out = []
    for i, (a, b, what, act, times) in enumerate(beats):
        files = []
        for j, sec in enumerate(times):
            clock["ms"] = T0 + int(sec * 1000)
            ns["demo_status"](clock["ms"])
            theme.last_t = None
            theme.action = None
            theme.act_seen = 0
            scr = P.render(theme, ns["st"], clock["ms"])
            if kind == 1:
                # the DEMO tag the app draws over demo 1
                import gfx
                gfx.text("DEMO", 136, 96, (255, 255, 255), font.sins, shadow=(0, 0, 0))
            files.append(P.save(scr, tag, "%02d" % i, j))
        out.append((a, b, what, act, files))
    return out


def fmt(a, b):
    def s(x):
        return ("%.1f" % x).rstrip("0").rstrip(".")
    return "%s-%s s" % (s(a), s(b))


def table(rows):
    body = []
    for a, b, what, act, files in rows:
        label = dict((k, v) for k, v, _ in P.ACTIVITIES).get(act, "")
        body.append('<tr><td class="time">%s</td><td>%s%s</td><td>%s</td></tr>' % (
            fmt(a, b), html.escape(what),
            '<span class="chip">%s</span>' % html.escape(label) if label else "",
            proto_page.anim(files, what)))
    return ('<div class="tablewrap"><table><thead><tr><th scope="col">Time</th><th scope="col">On the badge</th>'
            '<th scope="col">Frames</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(body))


# screenshots pulled from the badge itself while the demos ran (tools/deploy.py --shot-only), if present
DEVICE = (("badge_d1_arrive.png", "Demo 1: out of the cave"), ("badge_d1_edit.png", "Demo 1: sword combo"),
          ("badge_d1_shell.png", "Demo 1: bomb"), ("badge_d1_spawn.png", "Demo 1: boomerang, Navi calling"),
          ("badge_d1_fail.png", "Demo 1: knocked back"), ("badge_d1_done.png", "Demo 1: quest complete"),
          ("badge_d2_edit.png", "Demo 2: sword combo"), ("badge_d2_prompt.png", "Demo 2: a new quest"),
          ("badge_d2_done.png", "Demo 2: quest complete, 88 agents"))


def device_strip():
    have = [(f, c) for f, c in DEVICE if os.path.exists(os.path.join(P.OUT, f))]
    if not have:
        return ""
    cards = "".join('<article class="card small">%s<div class="meta"><p>%s</p></div></article>'
                    % (proto_page.anim([f], c), html.escape(c)) for f, c in have)
    return ('<h3>On the badge</h3><p class="lede">Screenshots from the badge while both demos ran: about 14 ms to '
            'draw a frame, a steady 25 frames a second.</p><div class="grid today">%s</div>' % cards)


def build():
    d1 = frames_for(1, DEMO1, "demo1")
    d2 = frames_for(2, DEMO2, "demo2")
    style = proto_page.TEMPLATE.split("<style>", 1)[1].split("</style>", 1)[0]
    script = proto_page.TEMPLATE.split("<script>", 1)[1].split("</script>", 1)[0]
    page = PAGE.replace("@@STYLE@@", style + EXTRA_CSS).replace("@@SCRIPT@@", script)
    page = page.replace("@@DEMO1@@", table(d1)).replace("@@DEMO2@@", table(d2)).replace("@@DEVICE@@", device_strip())
    out = os.path.join(HERE, "out", "demo_script.html")
    with open(out, "w") as f:
        f.write(page)
    print(out, len(page) // 1024, "KB")


EXTRA_CSS = """
td.time { white-space: nowrap; font-weight: 600; font-variant-numeric: tabular-nums; }
td .anim { width: 176px; max-width: none; }
td:last-child { width: 200px; }
.chip { display: inline-block; margin-left: 8px; font-size: 12px; font-weight: 600; background: var(--chip);
  border-radius: 6px; padding: 1px 7px; }
table { min-width: 560px; }
td { vertical-align: middle; }
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Burn Helper Demo Script</title>
<style>@@STYLE@@</style>
</head>
<body>
<main>
<h1>Demo modes, beat by beat</h1>
<p class="lede">Both demos run on the hero theme and now include the activity animations. Each row is a beat
with four frames from it, drawn by the simulator from the badge's own demo code, so this is what the badge
plays.</p>
<nav class="top" aria-label="Demos"><a href="#demo1">Demo 1: the 30-second ramp</a>
<a href="#demo2">Demo 2: the 20-second video take</a></nav>
<div class="controls"><button id="play" type="button" aria-pressed="true">Pause animations</button>
<span>Each screen cycles through 4 frames of its beat.</span></div>
@@DEVICE@@

<section class="theme" id="demo1">
  <h2>Demo 1 <small>hold UP for 2 s; shows a DEMO tag; loops every 30 s</small></h2>
  <p class="lede">From asleep through all 15 activity levels to hyperspace, with an activity animation every
  couple of seconds and sessions waiting now and then. The usage runs on its own 90-second window, so every
  third loop the countdown runs out and the hearts refill.</p>
  @@DEMO1@@
</section>

<section class="theme" id="demo2">
  <h2>Demo 2 <small>hold UP + DOWN for 3 s; no tag; loops every 20 s</small></h2>
  <p class="lede">The take for the launch video (docs/video.md). The animations sit between the walk, run
  and sprint beats so each one still gets its moment on camera.</p>
  @@DEMO2@@
</section>

<p class="foot">Rendered with tools/sim/demo_script.py.</p>
</main>
<script>@@SCRIPT@@</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
