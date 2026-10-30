#!/usr/bin/env python3
"""Every theme, state and animation of the badge on one shareable page -> tools/sim/out/showcase.html

    python3 tools/sim/showcase.py

Needs firmware/tufty-v3.1.1-micropython.uf2 (the simulator takes its pixel fonts from it).
Renders the badge's own theme code frame by frame, builds the weekly-reset ladder and the
waiting bar with the sibling scripts, and writes one self-contained file: frames embedded, no
network, no server. Open it in any browser, or send it as is.
"""
import base64
import hashlib
import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator first)
import harness  # noqa: E402
import proto_page  # noqa: E402
import preview_lost as PL  # noqa: E402
import preview_pace as PP  # noqa: E402
import power  # noqa: E402
import preview_views as PV  # noqa: E402
import scene as S  # noqa: E402
import views  # noqa: E402
import waiting_bar as WB  # noqa: E402

OUT = os.path.join(HERE, "out", "showcase.html")
TMP = os.path.join(HERE, "out", "showcase_tmp.png")
M = 1000000
THEMES = (("hero", "Hero", "A Zelda II style field: the hero walks, runs and sprints with your agents."),
          ("gameshow", "Game show", "The Running Man: the runner dodges as more agents join the show."),
          ("chocolates", "Chocolates", "Forrest Gump's run across America, a box of chocolates for the week."))
LABEL = {k: v for k, v, _ in THEMES}
STEP = 80                        # ms per frame on the page (the badge draws every 40)

IMGS = []                        # unique frames, as base64 PNGs
_seen = {}


def add_png(path):
    with open(path, "rb") as f:
        raw = f.read()
    h = hashlib.sha1(raw).hexdigest()
    if h not in _seen:
        _seen[h] = len(IMGS)
        IMGS.append(base64.b64encode(raw).decode())
    return _seen[h]


def add_scr(scr):
    scr.to_png(TMP, 1)
    return add_png(TMP)


def add_uri(uri):
    """A frame already encoded as a data URI (the waiting bar's)."""
    b = uri.split(",", 1)[1]
    h = hashlib.sha1(b.encode()).hexdigest()
    if h not in _seen:
        _seen[h] = len(IMGS)
        IMGS.append(b)
    return _seen[h]


def item(title, desc, frames, theme="", ms=STEP, tag="", note=""):
    return dict(title=title, desc=desc, frames=frames, theme=theme, ms=ms, tag=tag, note=note)


def load(name):
    return __import__("theme_" + name).Theme()


# ------------------------------------------------------------------ live states

STATES = (
    ("asleep", "Asleep", "No activity for a while: the screen dims and the character sleeps.",
     dict(level=S.SLEEP, agents=0, tpm=0), 4000),
    ("idle", "Idle", "Recent activity, nothing working right now.", dict(level=S.IDLE, agents=0, tpm=0), 4000),
    ("walk", "1 agent: walking", "Each extra agent up to 10 adds speed and speed lines.", dict(agents=1, tpm=6), 4000),
    ("run", "5 agents: running", "Four to seven agents run.", dict(agents=5, tpm=20), 4000),
    ("sprint", "9 agents: sprinting", "Eight or more agents sprint.", dict(agents=9, tpm=40), 4100),
    ("waiting", "A session needs you", "The character calls for you; the waiting bar names the session.",
     dict(agents=2, waiting=1), 6000),
    ("low", "Usage running low", "Few hearts left: they blink and the caption counts down to the refill.",
     dict(agents=3, hearts=3, week=0.2), 9000),
    ("offline", "Looking for the bridge", "Before any data arrives it says what it is searching for.", None, 6600),
)


def live_state(theme, key, st_kw, t0):
    th = load(theme)
    if st_kw is None:
        st = S.Status()
        st.online = False
        st.net = "SEARCHING FOR BRIDGE..."
    else:
        st = P.status(**{k: v for k, v in st_kw.items() if k != "level"})
        if "level" in st_kw:
            st.level = st_kw["level"]
    th.last_t = None
    return [add_scr(P.render(th, st, t0 + i * STEP, warm=(i == 0))) for i in range(12)]


def sec_states():
    groups = []
    for theme, label, what in THEMES:
        items = []
        for key, title, desc, kw, t0 in STATES:
            items.append(item(title, desc, live_state(theme, key, kw, t0), theme))
        groups.append(dict(title="%s: %s" % (label, what), items=items))
    return groups


# ------------------------------------------------------------------ activity tiers

TIER_AGENTS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 40, 63, 88, 128)


def tier_label(agents):
    st = S.Status()
    st.set_agents(agents)
    tier = st.tier
    if tier <= 10:
        return "%d agent%s" % (agents, "" if agents == 1 else "s"), tier
    return ("ULTRA: 100+ agents" if tier >= 15 else "%s agents" % S.TIER_TEXT[tier]), tier


def sec_tiers():
    groups = []
    for theme, label, _ in THEMES:
        items = []
        th = load(theme)
        for agents in TIER_AGENTS:
            st = P.status(level=S.WALK, agents=agents, hearts=12, tpm=min(60, 8 + agents))
            title, tier = tier_label(agents)
            th.last_t = None
            frames = [add_scr(P.render(th, st, 5200 + i * STEP, warm=(i == 0))) for i in range(10)]
            items.append(item(title, "Activity tier %d of 15." % tier, frames, theme))
        groups.append(dict(title="%s: from one agent to ULTRA" % label, items=items))
    return groups


# ------------------------------------------------------------------ one-shot activities

ACT_TEXT = {k: (label, trig) for k, label, trig in P.ACTIVITIES}


def play_action(theme, key):
    """Every frame of one activity animation, from its first to its last, at STEP ms."""
    mod = __import__("theme_" + theme)
    dur = mod.ACTIONS[key]
    th = mod.Theme()
    hearts = 4 if key == "refill" else 12
    st = P.status(level=S.WALK, agents=1 if key == "arrive" else 3, hearts=hearts)
    base = 5000
    th.action = key
    th.action_t0 = base
    th.refill_from = 4 if theme != "hero" else 3
    th.last_t = None
    if theme == "gameshow":
        th.scroll = 600.0
    frames = []
    n = dur // STEP + 2
    for i in range(n):
        act_key = key
        t = base + i * STEP
        if theme == "chocolates" and key == "spawn" and i * STEP > dur * 0.72:
            th.action, th.action_t0 = "back", base + int(dur * 0.72)
        frames.append(add_scr(P.render(th, st, t, warm=(i == 0))))
    return frames


def sec_actions():
    groups = []
    for theme, label, _ in THEMES:
        manifest = {x["key"]: x for x in json.load(open(os.path.join(P.OUT, theme + ".json")))}
        items = []
        for key, act, trig in P.ACTIVITIES:
            m = manifest.get(key, {})
            items.append(item("%s: %s" % (act, m.get("title", key)), m.get("desc", ""), play_action(theme, key), theme,
                              tag=trig))
        groups.append(dict(title="%s: what the agents are doing, acted out" % label, items=items))
    return groups


# ------------------------------------------------------------------ weekly reset

def sec_reset():
    groups = []
    for theme, label, _ in THEMES:
        path = os.path.join(P.OUT, "reset_%s.json" % theme)
        items = []
        for x in json.load(open(path)):
            frames = [add_png(os.path.join(P.OUT, f)) for f in x["frames"]]
            items.append(item(x["title"], x["desc"], frames, theme, ms=x.get("ms", 450),
                              tag=x.get("left", "")))
        groups.append(dict(title="%s: the countdown to the weekly reset" % label, items=items))
    return groups


# ------------------------------------------------------------------ waiting bar

def sec_waiting():
    lists, frames = WB.render_all()
    names = {"none": "Nobody waiting"}
    groups = []
    order = sorted(lists.items(), key=lambda kv: (len(kv[1]), any(w["u"] for w in kv[1])))
    for theme, label, _ in THEMES:
        items = []
        for k, lst in order:
            idx = [add_uri(frames["%s|%s|%d" % (theme, k, s)]) for s in range(max(1, len(lst)))]
            n = len(lst)
            title = "Nobody waiting" if not n else "%d waiting" % n + (", one unnamed" if any(w["u"] for w in lst) else "")
            desc = ("The bar names each session in turn, every 2 seconds." if n > 1 else
                    "The bar shows the session's name and how long it has waited." if n == 1 else
                    "No bar: the scene has the whole screen.")
            items.append(item(title, desc, idx, theme, ms=2000))
        groups.append(dict(title="%s: the waiting bar" % label, items=items))
    desk = []
    for k, lst in order:
        for sel in ([None] + ([2] if len(lst) > 2 else [])):
            uri = frames.get("desk|%s|%s" % (k, "list" if sel is None else sel))
            if uri:
                n = len(lst)
                t = "Desktop mode: " + ("nobody waiting" if not n else "%d waiting" % n) + (
                    "" if sel is None else ", one session in detail") + (", one unnamed" if any(w["u"] for w in lst) else "")
                desk.append(item(t, "", [add_uri(uri)], ""))
    groups.append(dict(title="Desktop mode: who is waiting", items=desk))
    return groups


# ------------------------------------------------------------------ lost connection, pace, views

def stills(shots, strip):
    items = []
    for fname, label, img in shots:
        items.append(item(label.replace(":", ": ", 1) if ": " not in label else label, "", [add_scr(img)],
                          next((t for t, _, _ in THEMES if fname.startswith(t)), "")))
    return items


def sec_lost():
    return [dict(title="When the connection drops, and when it comes back", items=stills(PL.shots(), ""))]


def sec_pace():
    return [dict(title="The weekly pace: will the week last?", items=stills(PP.shots(), ""))]


def sec_modes():
    groups = []
    desk = []
    for name, view, page, waiting, sel, title in (
            ("desktop_clear", views.DESKTOP, 0, 0, None, "Desktop mode: nothing waiting"),
            ("desktop", views.DESKTOP, 0, 2, None, "Desktop mode: two waiting"),
            ("desktop_many", views.DESKTOP, 0, 4, None, "Desktop mode: four waiting")):
        scr = harness.new_screen()
        c = views.Ctx(PV.status(waiting), PV.link(), PV.FakeTether())
        c.source = "net"
        c.wait_sel = sel
        views.draw(view, page, c, 0)
        desk.append(item(title, "", [add_scr(scr)]))
    for i in range(3):
        scr = harness.new_screen()
        c = views.Ctx(PV.status(3), PV.link(), PV.FakeTether())
        c.source = "net"
        c.wait_sel = i
        views.draw(views.DESKTOP, 0, c, 0)
        desk.append(item("Desktop mode: session %d in detail" % (i + 1), "", [add_scr(scr)]))
    groups.append(dict(title="Desktop mode (press B on the badge)", items=desk))
    dbg = []
    for p, name in enumerate(("Overview", "Connection", "Wi-Fi")):
        scr = harness.new_screen()
        c = views.Ctx(PV.status(1), PV.link(), PV.FakeTether())
        c.source = "net"
        views.draw(views.DEBUG, p, c, 0)
        dbg.append(item("Debug mode: %s" % name, "", [add_scr(scr)]))
    groups.append(dict(title="Debug mode", items=dbg))
    return groups


def sec_battery():
    """The low-battery banner (unplugged, 20% and 10%) over each theme and over Desktop mode."""
    cases = (("Low, 18%", "Unplugged at 20% or less: an orange banner with the charge and the time left, 6 s of every 45 s.",
              18, (100, True)),
             ("Critical, 7%", "At 10% or less the banner stays until the badge is plugged in.", 7, (30, True)))
    groups = []
    for theme, label, _ in THEMES:
        items = []
        th = load(theme)
        for title, desc, pct, left in cases:
            w = power.warning((False, False, 3.3, pct), left)
            st = P.status(level=S.WALK, agents=3, hearts=12)
            th.last_t = None
            frames = []
            for i in range(10):
                scr = P.render(th, st, 5200 + i * STEP, warm=(i == 0))
                views.draw_battery_warning(w)
                frames.append(add_scr(scr))
            items.append(item(title, desc, frames, theme))
        groups.append(dict(title="%s: battery warning" % label, items=items))
    desk = []
    for title, pct, left in (("Desktop mode: low, 18%", 18, (100, True)), ("Desktop mode: critical, 7%", 7, (30, True)),
                             ("Debug mode: critical, 7%", 7, None)):
        w = power.warning((False, False, 3.3, pct), left)
        scr = harness.new_screen()
        c = views.Ctx(PV.status(1), PV.link(), PV.FakeTether())
        c.source = "net"
        views.draw(views.DEBUG if title.startswith("Debug") else views.DESKTOP, 0, c, 0)
        views.draw_battery_warning(w)
        desk.append(item(title, "", [add_scr(scr)]))
    groups.append(dict(title="On the status screens", items=desk))
    return groups


# ------------------------------------------------------------------ the page

SECTIONS = (
    ("states", "Live states", "What the badge shows right now, in every theme: from asleep to a sprint, a session that "
     "needs you, usage running low and no bridge yet.", sec_states),
    ("tiers", "From 1 agent to ULTRA", "Fifteen activity tiers. More agents means more speed, then sparks, heat haze, a "
     "pulsing edge and, past 100 agents, hyperspace.", sec_tiers),
    ("actions", "What the agents are doing", "Ten one-shot animations, played once over the running character, one for "
     "each kind of thing Claude Code does. Only the category is sent to the badge, never file names or commands.",
     sec_actions),
    ("waiting", "Sessions waiting for you", "A bar names every session that needs you, turning every 2 seconds. Desktop "
     "mode lists them with how long each has waited.", sec_waiting),
    ("reset", "The weekly reset", "The last day of the week builds up to the reset: a clock in the HUD, a caption, a "
     "warning, a full-screen countdown and a celebration when the allowance comes back.", sec_reset),
    ("pace", "Weekly pace", "A tick on the weekly meter shows where an even pace would be, and a caption says when the "
     "week is on course to run out early.", sec_pace),
    ("battery", "Low battery", "Unplugged at 20% or less, an orange banner shows the charge and the time left; at 10% it "
     "stays until the badge is plugged in. It never shows on USB or while charging.", sec_battery),
    ("lost", "Connection lost", "The badge says that the connection is lost, for how long and why, and when it is back.",
     sec_lost),
    ("modes", "Desktop and Debug modes", "Two plain views for when you want numbers instead of a game.", sec_modes),
)


def card(it):
    th = it["theme"]
    return ('<figure class="card" data-theme="%s"><canvas class="screen" width="160" height="120" data-f="%s" data-ms="%d" '
            'role="img" aria-label="%s"></canvas><figcaption><b>%s</b>%s%s</figcaption></figure>' % (
                th, ",".join(map(str, it["frames"])), it["ms"], html.escape(it["title"]), html.escape(it["title"]),
                '<span class="tag">%s</span>' % html.escape(it["tag"]) if it["tag"] else "",
                "<span>%s</span>" % html.escape(it["desc"]) if it["desc"] else ""))


def build():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # the scripts that write frames to disk first
    for s in ("proto_hero", "proto_gameshow", "proto_chocolates",
              "proto_reset_hero", "proto_reset_gameshow", "proto_reset_chocolates"):
        subprocess.run([sys.executable, os.path.join(HERE, s + ".py")], check=True, stdout=subprocess.DEVNULL)
    body, nav, total = [], [], 0
    for sid, title, intro, fn in SECTIONS:
        print("rendering", sid, flush=True)
        groups = fn()
        n = sum(len(g["items"]) for g in groups)
        total += n
        nav.append('<a href="#%s">%s <small>%d</small></a>' % (sid, html.escape(title), n))
        gh = "".join('<h3>%s</h3><div class="grid">%s</div>' % (html.escape(g["title"]), "".join(card(i) for i in g["items"]))
                     for g in groups)
        body.append('<section id="%s"><h2>%s</h2><p class="lede">%s</p>%s</section>' % (sid, html.escape(title), html.escape(intro), gh))
    page = (TEMPLATE.replace("@@NAV@@", "".join(nav)).replace("@@BODY@@", "".join(body))
            .replace("@@COUNT@@", str(total)).replace("@@IMGS@@", json.dumps(IMGS)))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    if os.path.exists(TMP):
        os.remove(TMP)
    print(OUT, "%d screens, %d unique frames, %.1f MB" % (total, len(IMGS), len(page) / 1048576.0))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Burn Helper Showcase</title>
<style>
:root { --bg:#f6f4f1; --panel:#fff; --ink:#1d1b19; --dim:#6b6660; --line:#d9d3cb; --accent:#c2653f; --chip:#efe9e1;
  --screen:#0c0e14; --bezel:#2b2b30; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#15161a; --panel:#1e2026; --ink:#ecebe8;
  --dim:#9a9690; --line:#34363e; --accent:#e08a6c; --chip:#2a2c33; --bezel:#3a3a42; } }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 118px; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }
header { max-width:1240px; margin:0 auto; padding:28px 16px 8px; }
h1 { font-size:30px; margin:0 0 4px; letter-spacing:-.01em; }
h2 { font-size:24px; margin:0 0 4px; }
h3 { font-size:13px; margin:26px 0 10px; color:var(--dim); text-transform:uppercase; letter-spacing:.06em; }
.lede { color:var(--dim); max-width:52em; margin:0 0 6px; }
.bar { position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line); }
.bar > div { max-width:1240px; margin:0 auto; padding:10px 16px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.bar a, .bar button { font:600 13px/1 inherit; font-family:inherit; color:var(--ink); text-decoration:none; padding:7px 12px;
  border:1px solid var(--line); border-radius:999px; background:var(--panel); cursor:pointer; }
.bar a small { color:var(--dim); font-weight:400; }
.bar a:hover, .bar button:hover { border-color:var(--accent); }
.bar button[aria-pressed="true"] { background:var(--accent); border-color:var(--accent); color:#fff; }
.bar .sep { flex:1; }
.bar label { font-size:13px; color:var(--dim); }
main { max-width:1240px; margin:0 auto; padding:8px 16px 64px; }
section { margin-top:44px; padding-top:10px; border-top:2px solid var(--line); }
.grid { display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); }
.card { margin:0; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px; }
canvas.screen { display:block; width:100%; aspect-ratio:4/3; background:var(--screen); border:6px solid var(--bezel);
  border-radius:6px; box-sizing:border-box; image-rendering:pixelated; cursor:pointer; }
figcaption { margin-top:8px; font-size:13px; color:var(--dim); }
figcaption b { display:block; font-size:14px; color:var(--ink); margin-bottom:2px; }
figcaption span { display:block; }
figcaption .tag { font:12px ui-monospace,Menlo,monospace; margin-bottom:3px; }
.hidden { display:none !important; }
.foot { margin-top:48px; color:var(--dim); font-size:13px; }
noscript { display:block; padding:16px; background:var(--chip); border-radius:8px; margin:12px 0; }
</style>
</head>
<body>
<header>
<h1>Burn Helper: everything the badge shows</h1>
<p class="lede">Burn Helper turns a Tufty 2350 conference badge into a desk toy that shows how much Claude Code usage is left
as hearts, how many agents are working as a character that walks, runs and sprints, and which sessions need you. These are
@@COUNT@@ screens, every one drawn frame by frame by the badge's own code and played here at the badge's pace.</p>
</header>
<div class="bar"><div>
@@NAV@@
<span class="sep"></span>
<label>Theme</label>
<button type="button" data-t="" aria-pressed="true">All</button>
<button type="button" data-t="hero" aria-pressed="false">Hero</button>
<button type="button" data-t="gameshow" aria-pressed="false">Game show</button>
<button type="button" data-t="chocolates" aria-pressed="false">Chocolates</button>
<button type="button" id="play" aria-pressed="true">Pause</button>
</div></div>
<main>
<noscript>This page plays the animations with a little JavaScript. Turn it on to see them move.</noscript>
@@BODY@@
<p class="foot">Rendered by tools/sim/showcase.py with the badge's theme modules. Click a screen to step its animation by one frame.</p>
</main>
<script>
(function () {
  var DATA = @@IMGS@@;
  var imgs = DATA.map(function (b) { var i = new Image(); i.src = "data:image/png;base64," + b; return i; });
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var playing = !reduce, t0 = performance.now(), stepped = 0;
  var cards = Array.prototype.slice.call(document.querySelectorAll("canvas.screen")).map(function (c) {
    var f = c.dataset.f.split(",").map(Number);
    return { c: c, f: f, ms: +c.dataset.ms, g: c.getContext("2d"), vis: false, last: -1, off: 0 };
  });
  cards.forEach(function (k) { k.g.imageSmoothingEnabled = false; });
  function draw(k, n) {
    var im = imgs[k.f[n]];
    if (!im || !im.complete) return;
    k.g.drawImage(im, 0, 0);
    k.last = n;
  }
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { cards.forEach(function (k) { if (k.c === e.target) k.vis = e.isIntersecting; }); });
  }, { rootMargin: "120px" }) : null;
  cards.forEach(function (k) { if (io) io.observe(k.c); else k.vis = true; });
  cards.forEach(function (k) { k.c.addEventListener("click", function () { if (!playing) { k.off++; draw(k, k.off % k.f.length); } }); });
  function tick(now) {
    cards.forEach(function (k) {
      if (!k.vis || k.f.length < 2 && k.last === 0) return;
      var n = playing ? Math.floor((now - t0) / k.ms) % k.f.length : (k.off % k.f.length);
      if (n !== k.last) draw(k, n);
    });
    requestAnimationFrame(tick);
  }
  window.addEventListener("load", function () { cards.forEach(function (k) { k.last = -1; }); });
  requestAnimationFrame(tick);
  var btn = document.getElementById("play");
  function label() { btn.textContent = playing ? "Pause" : "Play"; btn.setAttribute("aria-pressed", playing ? "true" : "false"); }
  label();
  btn.addEventListener("click", function () {
    playing = !playing;
    if (playing) t0 = performance.now(); else cards.forEach(function (k) { k.off = Math.max(0, k.last); });
    label();
  });
  var tbtns = Array.prototype.slice.call(document.querySelectorAll("button[data-t]"));
  tbtns.forEach(function (b) {
    b.addEventListener("click", function () {
      tbtns.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      var t = b.dataset.t;
      document.querySelectorAll(".card").forEach(function (c) {
        c.classList.toggle("hidden", !!t && !!c.dataset.theme && c.dataset.theme !== t);
      });
      document.querySelectorAll("section h3").forEach(function (h) {
        var g = h.nextElementSibling;
        h.classList.toggle("hidden", !g.querySelector(".card:not(.hidden)"));
        g.classList.toggle("hidden", !g.querySelector(".card:not(.hidden)"));
      });
    });
  });
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
