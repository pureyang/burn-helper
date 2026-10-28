#!/usr/bin/env python3
"""Build the animation proposal page -> tools/sim/out/animations.html

    python3 tools/sim/proto_page.py

Renders today's animations for every theme, then adds the proposed activity animations from
tools/sim/out/proto/<theme>.json (written by tools/sim/proto_<theme>.py). The page is one
self-contained file with the frames embedded.
"""
import base64
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402
import scene as S  # noqa: E402

THEMES = (("hero", "Hero", "a Zelda II style field"),
          ("gameshow", "Game show", "The Running Man game show"),
          ("chocolates", "Chocolates", "Forrest Gump's run across America"))

# (key, label, what it shows, status kwargs, base time ms, frame step ms)
EXISTING = (
    ("asleep", "Asleep", "No activity for a while.", dict(level=S.SLEEP, agents=0, tpm=0), 4000, 400),
    ("idle", "Idle", "Recent activity, nothing working right now.", dict(level=S.IDLE, agents=0, tpm=0), 4000, 400),
    ("walk", "1 agent", "Walks. Each extra agent up to 10 adds speed and speed lines.", dict(agents=1, tpm=6), 4000, 110),
    ("run", "5 agents", "Runs (4 to 7 agents).", dict(agents=5, tpm=20), 4000, 70),
    ("sprint", "9 agents", "Sprints (8 or more).", dict(agents=9, tpm=40), 4100, 160),
    ("waiting", "Waiting for you", "A session needs you: the character calls for you.", dict(agents=2, waiting=1), 6000, 350),
    ("sparks", "26-50 agents", "The bands past 10 add sparks, then heat haze.", dict(agents=40, tpm=50), 5000, 90),
    ("edge", "76-100 agents", "A pulsing edge on top.", dict(agents=88, tpm=55), 5000, 90),
    ("ultra", "100+ agents", "ULTRA: hyperspace.", dict(agents=128, tpm=60), 5000, 90),
    ("low", "Usage running low", "Few hearts left: they blink and the caption counts down to the refill.",
     dict(agents=3, hearts=3, week=0.2), 9000, 300),
)


def load(name):
    mod = __import__("theme_" + name)
    return mod.Theme()


def render_existing(name):
    th = load(name)
    out = []
    for key, label, desc, kw, t0, step in EXISTING:
        st = P.status(**{k: v for k, v in kw.items() if k != "level"})
        if "level" in kw:
            st.level = kw["level"]
        th.last_t = None
        frames = []
        for i in range(4):
            scr = P.render(th, st, t0 + i * step, warm=(i == 0))
            frames.append(P.save(scr, "now_" + name, key, i))
        out.append({"key": key, "title": label, "desc": desc, "frames": frames})
    return out


def data_uri(fname):
    with open(os.path.join(P.OUT, fname), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def anim(frames, alt, big=False):
    """An animated screen: the frames cycle on the page (a strip when motion is reduced)."""
    imgs = "".join('<img src="%s" alt="%s" width="160" height="120"%s>'
                   % (data_uri(f), html.escape(alt) if i == 0 else "", "" if i == 0 else ' aria-hidden="true"')
                   for i, f in enumerate(frames))
    return '<div class="anim%s" data-n="%d">%s</div>' % (" big" if big else "", len(frames), imgs)


def card(item, theme_label):
    notes = item.get("notes") or ""
    trig = item.get("trigger")
    return ("<article class=\"card\">%s<div class=\"meta\"><h4>%s</h4>%s<p>%s</p>%s</div></article>" % (
        anim(item["frames"], "%s: %s" % (theme_label, item["title"])),
        html.escape(item["title"]),
        '<p class="trig"><span>%s</span> %s</p>' % (html.escape(item.get("activity", "")), html.escape(trig)) if trig else "",
        html.escape(item["desc"]),
        '<p class="notes">%s</p>' % html.escape(notes) if notes else ""))


def build():
    now = {name: render_existing(name) for name, _, _ in THEMES}
    proposed = {}
    for name, _, _ in THEMES:
        path = os.path.join(P.OUT, name + ".json")
        proposed[name] = json.load(open(path)) if os.path.exists(path) else []

    # the activity table: one row per activity, the proposal's title per theme
    rows = []
    for key, label, trigger in P.ACTIVITIES:
        cells = []
        for name, _, _ in THEMES:
            it = next((x for x in proposed[name] if x["key"] == key), None)
            cells.append('<td><a href="#%s-%s">%s</a></td>' % (name, key, html.escape(it["title"])) if it else "<td>-</td>")
        rows.append("<tr><th scope=\"row\">%s<span>%s</span></th>%s</tr>"
                    % (html.escape(label), html.escape(trigger), "".join(cells)))

    sections = []
    for name, label, what in THEMES:
        today = "".join('<article class="card small">%s<div class="meta"><h4>%s</h4><p>%s</p></div></article>'
                        % (anim(x["frames"], "%s today: %s" % (label, x["title"])), html.escape(x["title"]),
                           html.escape(x["desc"])) for x in now[name])
        ideas = "".join('<div id="%s-%s">%s</div>' % (name, it["key"], card(it, label)) for it in proposed[name]) \
            or "<p class=\"empty\">Prototypes not rendered yet.</p>"
        sections.append("""
<section class="theme" id="%s">
  <h2>%s <small>%s</small></h2>
  <h3>Today</h3>
  <div class="grid today">%s</div>
  <h3>One-shot animations for what the agents do</h3>
  <div class="grid ideas">%s</div>
</section>""" % (name, label, html.escape(what), today, ideas))

    page = TEMPLATE.replace("@@ROWS@@", "".join(rows)).replace("@@SECTIONS@@", "".join(sections))
    page = page.replace("@@THEADS@@", "".join("<th scope=\"col\"><a href=\"#%s\">%s</a></th>" % (n, l) for n, l, _ in THEMES))
    out = os.path.join(HERE, "out", "animations.html")
    with open(out, "w") as f:
        f.write(page)
    print(out, len(page) // 1024, "KB")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Burn Helper Animations</title>
<style>
:root {
  --bg: #f6f4f1; --panel: #ffffff; --ink: #1d1b19; --dim: #6b6660; --line: #d9d3cb;
  --accent: #c2653f; --chip: #efe9e1; --screen: #0c0e14; --bezel: #2b2b30;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #15161a; --panel: #1e2026; --ink: #ecebe8; --dim: #9a9690; --line: #34363e;
    --accent: #e08a6c; --chip: #2a2c33; --screen: #0c0e14; --bezel: #3a3a42;
  }
}
:root[data-theme="dark"] {
  --bg: #15161a; --panel: #1e2026; --ink: #ecebe8; --dim: #9a9690; --line: #34363e;
  --accent: #e08a6c; --chip: #2a2c33; --screen: #0c0e14; --bezel: #3a3a42;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 28px; margin: 0 0 6px; letter-spacing: -0.01em; }
h2 { font-size: 22px; margin: 0 0 4px; }
h2 small { font-size: 14px; color: var(--dim); font-weight: 400; margin-left: 6px; }
h3 { font-size: 13px; margin: 22px 0 10px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.06em; }
h4 { font-size: 15px; margin: 0 0 4px; }
p { margin: 0 0 8px; }
a { color: inherit; }
.lede { color: var(--dim); max-width: 50em; margin-bottom: 20px; }
nav.top { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 24px; }
nav.top a, button { font: 600 13px/1 inherit; font-family: inherit; color: var(--ink); text-decoration: none;
  padding: 7px 12px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel); cursor: pointer; }
nav.top a:hover, button:hover { border-color: var(--accent); }
.how { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; margin: 0 0 28px; }
.how div { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px; font-size: 14px; }
.how b { display: block; margin-bottom: 4px; }
.tablewrap { overflow-x: auto; margin: 0 0 30px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); }
table { border-collapse: collapse; width: 100%; min-width: 640px; font-size: 14px; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
thead th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dim); }
tbody th span { display: block; font-weight: 400; color: var(--dim); font-size: 12px; font-family: ui-monospace, Menlo, monospace; }
tbody tr:last-child > * { border-bottom: 0; }
td a { text-decoration: none; border-bottom: 1px dotted var(--dim); }
.theme { margin: 36px 0 0; padding-top: 8px; border-top: 2px solid var(--line); }
.grid { display: grid; gap: 14px; }
.today { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
.ideas { grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; height: 100%; }
.ideas .card { display: grid; grid-template-columns: 176px 1fr; gap: 12px; align-items: start; }
.card .meta p { font-size: 13.5px; color: var(--dim); }
.card.small .meta { margin-top: 8px; }
.card.small .meta p { font-size: 13px; }
.trig { font-family: ui-monospace, Menlo, monospace; font-size: 12px !important; }
.trig span { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-weight: 600; color: var(--ink);
  background: var(--chip); border-radius: 6px; padding: 1px 6px; margin-right: 4px; font-size: 12px; }
.notes { font-size: 12.5px !important; border-left: 2px solid var(--line); padding-left: 8px; }
.anim { position: relative; width: 100%; max-width: 176px; aspect-ratio: 4 / 3; background: var(--screen);
  border: 8px solid var(--bezel); border-radius: 6px; box-sizing: content-box; overflow: hidden; }
.card.small .anim { max-width: none; width: calc(100% - 16px); }
.anim img { position: absolute; inset: 0; width: 100%; height: 100%; image-rendering: pixelated; image-rendering: crisp-edges;
  visibility: hidden; }
.anim img.on { visibility: visible; }
.anim img:first-child { visibility: visible; }
.anim.ready img:first-child:not(.on) { visibility: hidden; }
.strip { display: none; }
.controls { display: flex; gap: 8px; align-items: center; margin: 0 0 18px; color: var(--dim); font-size: 13px; }
.empty { color: var(--dim); }
.foot { margin-top: 36px; color: var(--dim); font-size: 13px; }
@media (max-width: 720px) {
  .ideas { grid-template-columns: 1fr; }
  .ideas .card { grid-template-columns: 1fr; }
  .anim { max-width: none; width: calc(100% - 16px); }
  .today { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
</head>
<body>
<main>
<h1>Burn Helper animations</h1>
<p class="lede">The badge shows how many agents are working and whether a session needs you, and it acts out what the
agents are doing: a sword combo when one edits a file, a bomb when it runs a command, and so on. Every frame below is
rendered by the simulator with the badge's own drawing code.</p>

<nav class="top" aria-label="Themes">
  <a href="#activities">Activities</a><a href="#hero">Hero</a><a href="#gameshow">Game show</a>
  <a href="#chocolates">Chocolates</a><a href="#build">What it takes</a>
</nav>

<div class="controls"><button id="play" type="button" aria-pressed="true">Pause animations</button>
<span>Each screen cycles through 4 frames of the animation.</span></div>

<div class="how">
  <div><b>One-shot, then back to running</b>Each animation plays once, for about 1 to 2 seconds, over whatever the
  character is already doing, then the normal walk, run or sprint carries on.</div>
  <div><b>Busy agents don't turn it into a strobe</b>At most one animation every 2 seconds. When several activities
  arrive at once the badge plays the most telling one: a failure, then a finished turn, a subagent, then tool calls.</div>
  <div><b>Counts stay where they are</b>The level, speed lines, hearts and HUD work exactly as today. These only add
  what is happening right now.</div>
</div>

<h2 id="activities">Activities and what each theme does</h2>
<p class="lede">The bridge gets each of these from Claude Code's hooks and passes the latest few on to the badge,
as categories only.</p>
<div class="tablewrap"><table>
<thead><tr><th scope="col">Activity</th>@@THEADS@@</tr></thead>
<tbody>@@ROWS@@</tbody>
</table></div>

@@SECTIONS@@

<section class="theme" id="build">
  <h2>How it works</h2>
  <div class="how" style="margin-top:14px">
    <div><b>Bridge</b>Sorts each hook event into one of the activities above and sends the latest few in
    <code>/status</code> with a running number and their age, for example <code>"ev": [[812, "edit", 1800]]</code>.
    Only the category is sent: no file names, commands or URLs.</div>
    <div><b>Badge</b>Remembers the last number it saw, queues the most telling new one, and plays it when the theme is
    free. Anything older than 6 seconds is skipped. The refill needs nothing from the bridge: the hearts jump back up.</div>
    <div><b>Cost</b>Extra poses and small sprites built once when a theme loads: about 290-650 KB per theme of the
    badge's 8 MB, and a few more seconds on the LOADING screen. Drawing stays at 25 frames a second.</div>
    <div><b>Demos</b>Demo 1 plays every hero animation in turn; the video take uses four of them.</div>
  </div>
</section>

<p class="foot">Rendered with tools/sim/proto_*.py from the badge's theme modules.</p>
</main>
<script>
(function () {
  var playing = !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var btn = document.getElementById("play");
  var anims = Array.prototype.slice.call(document.querySelectorAll(".anim"));
  var k = 0;
  anims.forEach(function (a) { a.classList.add("ready"); a.children[0].classList.add("on"); });
  function show(i) {
    anims.forEach(function (a) {
      var n = a.children.length;
      for (var j = 0; j < n; j++) a.children[j].classList.toggle("on", j === i % n);
    });
  }
  function label() {
    btn.textContent = playing ? "Pause animations" : "Play animations";
    btn.setAttribute("aria-pressed", playing ? "true" : "false");
  }
  label();
  btn.addEventListener("click", function () { playing = !playing; label(); });
  setInterval(function () { if (playing) { k++; show(k); } }, 260);
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
