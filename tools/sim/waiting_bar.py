#!/usr/bin/env python3
"""The badge's waiting bar, every state, on every theme -> tools/sim/out/waiting_bar.html

    python3 tools/sim/waiting_bar.py

Renders the animation screen of each theme and Desktop mode for none, one, three and four
sessions waiting (with and without an unnamed one), at each session's turn, plus the waiting
bar frame by frame at the badge's 25 frames a second for three speed settings, from the badge's
own code, and builds one self-contained page with them.
"""
import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator)
import harness  # noqa: E402
import scene as S  # noqa: E402
import theme_chocolates  # noqa: E402
import theme_gameshow  # noqa: E402
import theme_hero  # noqa: E402
import views  # noqa: E402

THEMES = (("hero", "Hero", theme_hero), ("gameshow", "Game show", theme_gameshow),
          ("chocolates", "Chocolates", theme_chocolates))
# the sessions waiting in the examples, longest wait first, as the bridge sends them
# (names: one set with /rename, one Claude Code made up, one from another computer's hook, and one
# with no name at all, which only an older Claude Code leaves)
ALL = [
    {"n": "api-server refactor", "s": 720, "d": "api-server", "w": "PERMISSION: BASH", "a": 7800, "i": "22441a", "u": 0},
    {"n": "docs-site-amber-42", "s": 360, "d": "docs-site", "w": "YOUR REPLY", "a": 1500, "i": "9b1e04", "u": 0},
    {"n": "math homework helper", "s": 180, "d": "math", "w": "YOUR REPLY", "a": 0, "i": "c0d5aa", "u": 0},
    {"n": "web-app", "s": 60, "d": "web-app", "w": "YOUR REPLY", "a": 600, "i": "7f3a2c", "u": 1},
]
COUNTS = (0, 1, 3, 4)
OUT = os.path.join(P.OUT, "wbar")


def waiting(n, unnamed):
    """The same pick as the page's controls: the first n, leaving out unnamed ones when asked."""
    pool = [w for w in ALL if unnamed or not w["u"]]
    return pool[:n]


def key(lst):
    return "-".join(w["i"] for w in lst) or "none"


def uri(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


class Tether:
    def fresh(self):
        return True


def render_all():
    os.makedirs(OUT, exist_ok=True)
    lists = {}
    for n in COUNTS:
        for unnamed in (True, False):
            lst = waiting(n, unnamed)
            lists[key(lst)] = lst
    frames = {}      # "<theme>|<list key>|<step>" -> data uri
    for name, _, mod in THEMES:
        th = mod.Theme()
        for k, lst in lists.items():
            for step in range(max(1, len(lst))):
                st = P.status(agents=2, waiting=len(lst))
                st.waiting_list = [dict(w) for w in lst]
                th.last_t = None
                T = 50000
                # session `step`'s turn, just begun: its name at its start
                S._turn.update(key=tuple(w.get("i") or w.get("n") for w in lst), i=step, t0=T - 300)
                scr = P.render(th, st, T)
                path = os.path.join(OUT, "%s_%s_%d.png" % (name, k, step))
                scr.to_png(path, 1)
                frames["%s|%s|%d" % (name, k, step)] = uri(path)
    # Desktop mode (the same for every theme), and one waiting session in detail
    for k, lst in lists.items():
        for sel in [None] + ([2] if len(lst) > 2 else []):
            scr = harness.new_screen()
            st = P.status(agents=2, waiting=len(lst))
            st.waiting_list = [dict(w) for w in lst]
            c = views.Ctx(st, None, Tether())
            c.source = "net"
            c.wait_sel = sel
            views.draw(views.DESKTOP, 0, c, 0)
            path = os.path.join(OUT, "desk_%s_%s.png" % (k, "list" if sel is None else sel))
            scr.to_png(path, 1)
            frames["desk|%s|%s" % (k, "list" if sel is None else sel)] = uri(path)
    return lists, frames


# ---------------------------------------------------------------- the speed player
# (label, cycle ms for a name that fits, hold ms at a long name's start, scroll px/s, rest ms at its end)
PRESETS = (("calm", "Calm", 3000, 1400, 16, 1000),
           ("badge", "Recommended (the badge)", S.WAIT_CYCLE_MS, S.WAIT_HOLD_MS, S.WAIT_SCROLL_PX_S, S.WAIT_END_MS),
           ("brisk", "Brisk", 1500, 600, 40, 500))
EXAMPLES = (("four", "Four waiting, two long names", [
    {"n": "api-server refactor", "s": 720, "d": "api-server", "w": "", "a": 0, "i": "22441a", "u": 0},
    {"n": "notes", "s": 400, "d": "notes", "w": "", "a": 0, "i": "5d0e11", "u": 0},
    {"n": "fix the flaky checkout tests on ci", "s": 300, "d": "shop", "w": "", "a": 0, "i": "a7c3f0", "u": 0},
    {"n": "docs-site-amber-42", "s": 60, "d": "docs-site", "w": "", "a": 0, "i": "9b1e04", "u": 0}]),
    ("one", "One waiting, a long name", [
    {"n": "fix the flaky checkout tests on ci", "s": 300, "d": "shop", "w": "", "a": 0, "i": "a7c3f0", "u": 0}]))
FRAME_MS = 40                 # the badge draws 25 frames a second


def render_player():
    """The bar alone, every frame of one full round, for each speed setting and example."""
    keep = (S.WAIT_CYCLE_MS, S.WAIT_HOLD_MS, S.WAIT_SCROLL_PX_S, S.WAIT_END_MS)
    out = {"presets": [[p[0], p[1], p[2], p[3], p[4], p[5]] for p in PRESETS],
           "examples": [[e[0], e[1]] for e in EXAMPLES], "frame_ms": FRAME_MS, "bg": {}, "strips": {}}
    th = theme_hero.Theme()
    for ex, _, lst in EXAMPLES:
        st = P.status(agents=2, waiting=len(lst))
        st.waiting_list = [dict(w) for w in lst]
        th.last_t = None
        S._turn.update(key=None)
        path = os.path.join(OUT, "player_bg_%s.png" % ex)
        P.render(th, st, 50000).to_png(path, 1)
        out["bg"][ex] = uri(path)
        for pid, _, cycle, hold, speed, end in PRESETS:
            S.WAIT_CYCLE_MS, S.WAIT_HOLD_MS, S.WAIT_SCROLL_PX_S, S.WAIT_END_MS = cycle, hold, speed, end
            S._turn.update(key=None, i=0, t0=0)
            frames, t, rounds = [], 0, 0
            last_i = 0
            while True:
                scr = harness.new_screen(160, 12)
                S.draw_waiting_bar(st, t, y=0)
                if S._turn["i"] == 0 and last_i != 0 or (len(lst) == 1 and t > 0 and S._turn["t0"] == t):
                    break                  # back to the first session: one full round
                last_i = S._turn["i"]
                path = os.path.join(OUT, "strip.png")
                scr.to_png(path, 1)
                frames.append(uri(path))
                t += FRAME_MS
                if t > 60000:
                    break
            out["strips"]["%s|%s" % (pid, ex)] = frames
    S.WAIT_CYCLE_MS, S.WAIT_HOLD_MS, S.WAIT_SCROLL_PX_S, S.WAIT_END_MS = keep
    return out


# screenshots from the badge itself, if they were taken (tools/deploy.py --shot-only), and what they show
DEVICE = (("device_dev_wait1.png", "One waiting: its name stays"),
          ("device_dev_wait2a.png", "Two waiting: they take turns, with a counter"),
          ("device_dev_detail_unnamed.png", "Desktop mode, the same session in detail"))


def device_strip():
    have = [(f, c) for f, c in DEVICE if os.path.exists(os.path.join(OUT, f))]
    if not have:
        return ""
    figs = "".join('<figure><img src="%s" alt="%s" width="160" height="120"><figcaption>%s</figcaption></figure>'
                   % (uri(os.path.join(OUT, f)), c, c) for f, c in have)
    return ('<section class="view" aria-labelledby="dev-h"><h2 id="dev-h">On the badge itself</h2>'
            '<div class="pair three">%s</div><p class="small muted">Screenshots taken from the badge running its '
            'demo, which has two sessions waiting.</p></section>' % figs)


def build():
    lists, frames = render_all()
    data = {"frames": frames, "lists": {k: [w["i"] for w in v] for k, v in lists.items()},
            "all": ALL, "themes": [[n, label] for n, label, _ in THEMES], "cycle": S.WAIT_CYCLE_MS,
            "player": render_player()}
    page = PAGE.replace("@@DATA@@", json.dumps(data, separators=(",", ":"))).replace("@@DEVICE@@", device_strip())
    out = os.path.join(HERE, "out", "waiting_bar.html")
    with open(out, "w") as f:
        f.write(page)
    print(out, len(page) // 1024, "KB,", len(frames), "frames")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Waiting Sessions Bar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Instrument+Sans:wght@400;500;600;700&display=swap">
<style>
:root{
  --bg:#F2F1EE; --surface:#FFFFFF; --ink:#1B1A18; --muted:#6B6862; --line:#DCD9D3;
  --wait:#B45309; --wait-soft:#FDF0D8; --bezel:#2B2B30; --screen:#0C0E14;
  --sans:"Instrument Sans",-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){color-scheme:dark;
    --bg:#121212; --surface:#1C1C1C; --ink:#ECEAE6; --muted:#9C988F; --line:#2E2D2A;
    --wait:#FBBF24; --wait-soft:#3A2E12; --bezel:#3A3A42;}
}
:root[data-theme="dark"]{color-scheme:dark;
  --bg:#121212; --surface:#1C1C1C; --ink:#ECEAE6; --muted:#9C988F; --line:#2E2D2A;
  --wait:#FBBF24; --wait-soft:#3A2E12; --bezel:#3A3A42;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans);padding:28px 16px 64px}
.wrap{max-width:1120px;margin:0 auto;display:grid;gap:28px}
h1,h2,h3{margin:0;line-height:1.15} h1{font-size:30px;letter-spacing:-.01em} h2{font-size:20px} h3{font-size:15px;font-weight:600}
p{margin:0;max-width:72ch}
.muted{color:var(--muted)} .small{font-size:13px}
.eyebrow{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.mono{font-family:var(--mono);font-size:.88em}
.controls{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.ctl{display:grid;gap:6px}
.ctl > span{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden;flex-wrap:wrap}
.seg button{font:inherit;font-size:13.5px;background:transparent;color:var(--ink);border:0;padding:6px 12px;cursor:pointer}
.seg button+button{border-left:1px solid var(--line)}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--bg)}
.seg button:focus-visible,.toggle input:focus-visible{outline:2px solid var(--wait);outline-offset:2px}
.toggle{display:inline-flex;gap:8px;align-items:center;font-size:14px;cursor:pointer}
.toggle input{accent-color:var(--wait);width:16px;height:16px;margin:0}
.views{display:grid;grid-template-columns:1.25fr 1fr;gap:20px;align-items:start}
@media (max-width:860px){.views{grid-template-columns:1fr}}
.view{display:grid;gap:10px;min-width:0}
.badge{background:var(--bezel);border-radius:14px;padding:14px;display:grid;gap:10px}
.badge img{display:block;width:100%;height:auto;image-rendering:pixelated;image-rendering:crisp-edges;border-radius:4px;background:var(--screen)}
.badge .btns{display:flex;justify-content:space-between;padding:0 6px}
.badge .btns i{width:22px;height:8px;border-radius:4px;background:#55555E;display:block}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pair figure{margin:0;display:grid;gap:6px}
.pair figcaption{font-size:13px;color:var(--muted)}
.pair.three{grid-template-columns:repeat(3,1fr)}
@media (max-width:560px){.pair.three{grid-template-columns:1fr 1fr}}
.pair img{width:100%;height:auto;image-rendering:pixelated;image-rendering:crisp-edges;border-radius:6px;border:8px solid var(--bezel);background:var(--screen)}
.step{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--muted)}
.step b{font-weight:600;color:var(--ink);font-family:var(--mono)}
.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media (max-width:860px){.rules{grid-template-columns:1fr}}
.rule,.how{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:grid;gap:6px;align-content:start}
.rule ul,.how ol{margin:0;padding-left:18px;display:grid;gap:4px;font-size:14px}
#player{display:block;width:100%;height:auto;aspect-ratio:4/3;image-rendering:pixelated;image-rendering:crisp-edges;border-radius:4px;background:var(--screen)}
.timing dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:14px}
.timing dt{color:var(--muted)} .timing dd{margin:0;font-weight:600}
.chip{display:inline-block;font-size:12px;font-weight:600;color:var(--wait);background:var(--wait-soft);border-radius:99px;padding:1px 8px}
</style>
</head>
<body>
<div class="wrap">
  <header style="display:grid;gap:10px">
    <div class="eyebrow">Burn Helper badge · animation screen and Desktop mode <span class="chip">on the badge now</span></div>
    <h1>Show which sessions are waiting on you</h1>
    <p class="muted">When a session needs your input, the badge's caption line turns into a waiting bar with the
    session's name, the same name Claude Code shows. Several waiting sessions take turns; a name too long for the bar
    scrolls through once. Every screen below is drawn by the badge's own code.</p>
  </header>

  <section class="view" aria-labelledby="sp-h">
    <h2 id="sp-h">Speed: watch it at the badge's pace</h2>
    <p class="small muted">Played frame by frame at the badge's 25 frames a second. Compare the settings; the badge
    uses the recommended one: a name that fits never moves, and a long one shows its start first, glides once, rests,
    and hands over.</p>
    <div class="controls" role="group" aria-label="Speed">
      <div class="ctl"><span>Setting</span><div class="seg" id="preset"></div></div>
      <div class="ctl"><span>Example</span><div class="seg" id="example"></div></div>
      <div class="ctl"><span>Playback</span><div class="seg"><button type="button" id="playbtn" aria-pressed="true">Pause</button></div></div>
    </div>
    <div class="views">
      <div class="badge"><canvas id="player" width="160" height="120" aria-label="The badge's animation screen with the waiting bar playing"></canvas><div class="btns"><i></i><i></i><i></i></div></div>
      <div class="how timing" aria-live="polite"><h3 id="tm-h">This setting</h3><dl id="timing"></dl></div>
    </div>
  </section>

  <div class="controls" role="group" aria-label="Badge state">
    <div class="ctl"><span>Sessions waiting</span>
      <div class="seg" id="count"><button type="button" data-n="0">None</button><button type="button" data-n="1">One</button><button type="button" data-n="3" aria-pressed="true">Three</button><button type="button" data-n="4">Four</button></div></div>
    <div class="ctl"><span>Names</span>
      <label class="toggle"><input type="checkbox" id="unnamed" checked> Include one with no name</label></div>
    <div class="ctl"><span>Theme</span><div class="seg" id="theme"></div></div>
    <div class="ctl"><span>Cycle</span>
      <div class="seg" id="speed"><button type="button" data-ms="2000" aria-pressed="true">Fast (the badge)</button><button type="button" data-ms="4000">Slow</button><button type="button" data-ms="0">Paused</button></div></div>
  </div>

  <div class="views">
    <section class="view" aria-labelledby="a-h">
      <h2 id="a-h">Animation screen: the waiting bar</h2>
      <div class="badge"><img id="anim" alt="The badge's animation screen" width="160" height="120"><div class="btns"><i></i><i></i><i></i></div></div>
      <div class="step" id="step" aria-live="polite"></div>
      <p class="small muted">The theme still calls for you in the scene (Navi's "HEY! LISTEN!", the audience vote,
      "JENNY!"); the caption line says who.</p>
    </section>
    <section class="view" aria-labelledby="d-h">
      <h2 id="d-h">Desktop mode (press B)</h2>
      <div class="pair">
        <figure><img id="desk" alt="Desktop mode: usage left and the sessions waiting" width="160" height="120"><figcaption>The list, longest wait first</figcaption></figure>
        <figure id="detailfig"><img id="detail" alt="Desktop mode: one waiting session in detail" width="160" height="120"><figcaption>A/C: one in detail (the one from another computer here)</figcaption></figure>
      </div>
      <p class="small muted">Desktop mode uses the same names, so a session reads the same in both places.</p>
    </section>
  </div>

  @@DEVICE@@

  <section class="rules" aria-label="Behaviour">
    <div class="rule"><h3>One session waiting</h3><ul>
      <li>Its name stays in the bar. A name too long for it scrolls through once, rests, and starts again.</li>
      <li>Shown as <span class="mono">WAITING name</span>, the label in amber.</li>
      <li>Gone as soon as you answer it.</li></ul></div>
    <div class="rule"><h3>Several waiting</h3><ul>
      <li>A name that fits shows 2 s. A long one stays at its start 1 s, glides left at 24 pixels a second
      (one pixel a frame), rests 0.8 s, then the next one comes, longest wait first, with a counter (<span class="mono">2/3</span>).</li>
      <li>Up to 4 at a time, the same 4 Desktop mode lists.</li>
      <li>Sessions on your other computers count too, under their own names.</li></ul></div>
    <div class="rule"><h3>Which name</h3><ul>
      <li>The session's Claude Code name: the one you set with <span class="mono">/rename</span>, or the one Claude Code gave it (<span class="mono">docs-site-amber-42</span>).</li>
      <li>Sent whole, up to 40 characters; the bar scrolls whatever doesn't fit.</li>
      <li>Without a name (an older Claude Code, or a computer not yet sending names) it goes by its folder or its
      computer's name, in grey, numbered only when two look alike: <span class="mono">web-app</span>,
      <span class="mono">OTHER-PC 2</span>. Never a hex id.</li></ul></div>
  </section>

  <section class="how" aria-labelledby="how-h">
    <h2 id="how-h">How it works</h2>
    <ol>
      <li>The bridge reads Claude Code's session files and hook events, and sends the waiting sessions in
      <span class="mono">/status</span>: name, how long each has waited, folder, what it needs, the first 6
      characters of its id, and whether it has a name of its own.</li>
      <li>The name is the one in Claude Code's session file. On a joined computer, its hook looks the name up in
      that computer's session files and sends it with the "waiting" event; nothing else about the session goes along.</li>
      <li>The badge times each turn itself, so the names turn and scroll without any extra traffic. Nothing moves
      when every name fits, and nothing changes on screen when no session is waiting.</li>
    </ol>
  </section>
</div>
<script>
(function () {
  var D = @@DATA@@;
  var state = {n: 3, unnamed: true, theme: D.themes[0][0], ms: D.cycle, i: 0}, timer = null;
  var themeSeg = document.getElementById("theme");
  D.themes.forEach(function (t, k) {
    var b = document.createElement("button"); b.type = "button"; b.dataset.t = t[0]; b.textContent = t[1];
    b.setAttribute("aria-pressed", k === 0 ? "true" : "false"); themeSeg.appendChild(b);
  });
  function pick() {
    var pool = D.all.filter(function (w) { return state.unnamed || !w.u; });
    return pool.slice(0, state.n);
  }
  function key(list) { return list.map(function (w) { return w.i; }).join("-") || "none"; }
  function label(w) { return w.n; }
  function render() {
    var list = pick(), k = key(list), n = Math.max(1, list.length);
    if (state.i >= n) state.i = 0;
    document.getElementById("anim").src = D.frames[state.theme + "|" + k + "|" + state.i];
    document.getElementById("desk").src = D.frames["desk|" + k + "|list"];
    var det = D.frames["desk|" + k + "|2"], fig = document.getElementById("detailfig");
    fig.hidden = !det; if (det) document.getElementById("detail").src = det;
    var step = document.getElementById("step");
    step.textContent = "";
    if (!list.length) { step.textContent = "Nothing waiting: the theme's usual caption."; return; }
    var w = list[state.i], s = document.createElement("b");
    s.textContent = label(w);
    step.appendChild(document.createTextNode(list.length > 1 ? "Showing " + (state.i + 1) + " of " + list.length + ": " : "Showing: "));
    step.appendChild(s);
    step.appendChild(document.createTextNode(" (waiting " + Math.round(w.s / 60) + " min" + (w.w ? ", " + w.w.toLowerCase() : "") + ")"));
  }
  function tick() { var n = pick().length; if (n > 1) { state.i = (state.i + 1) % n; render(); } }
  function restart() { clearInterval(timer); timer = null; if (state.ms) timer = setInterval(tick, state.ms); }
  function seg(id, attr, key, num) {
    var el = document.getElementById(id);
    el.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      el.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      state[key] = num ? Number(b.dataset[attr]) : b.dataset[attr];
      if (key !== "theme") state.i = 0;
      render(); restart();
    });
  }
  seg("count", "n", "n", true); seg("speed", "ms", "ms", true); seg("theme", "t", "theme", false);
  document.getElementById("unnamed").addEventListener("change", function (e) { state.unnamed = e.target.checked; state.i = 0; render(); });
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    state.ms = 0;
    document.querySelectorAll("#speed button").forEach(function (x) { x.setAttribute("aria-pressed", x.dataset.ms === "0" ? "true" : "false"); });
  }
  render(); restart();

  // ------------------------------------------------ the speed player
  var PL = D.player, pl = {preset: "badge", example: PL.examples[0][0], playing: true, k: 0, imgs: [], bg: null};
  var canvas = document.getElementById("player"), ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  function segFill(id, items, cur, key) {
    var el = document.getElementById(id);
    items.forEach(function (it) {
      var b = document.createElement("button"); b.type = "button"; b.dataset.v = it[0]; b.textContent = it[1];
      b.setAttribute("aria-pressed", it[0] === cur ? "true" : "false"); el.appendChild(b);
    });
    el.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      el.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      pl[key] = b.dataset.v; load();
    });
  }
  segFill("preset", PL.presets, pl.preset, "preset");
  segFill("example", PL.examples, pl.example, "example");
  function load() {
    var srcs = PL.strips[pl.preset + "|" + pl.example] || [];
    pl.imgs = srcs.map(function (s) { var im = new Image(); im.src = s; return im; });
    pl.bg = new Image(); pl.bg.src = PL.bg[pl.example];
    pl.k = 0;
    var p = PL.presets.filter(function (x) { return x[0] === pl.preset; })[0];
    var dl = document.getElementById("timing"); dl.textContent = "";
    [["A name that fits", (p[2] / 1000) + " s"], ["A long name, still at its start", (p[3] / 1000) + " s"],
     ["Then scrolls at", p[4] + " pixels a second (about " + Math.round(p[4] / 5) + " letters)"],
     ["Rests at its end", (p[5] / 1000) + " s"],
     ["One full round of this example", (srcs.length * PL.frame_ms / 1000).toFixed(1) + " s"]].forEach(function (r) {
      var dt = document.createElement("dt"), dd = document.createElement("dd"); dt.textContent = r[0]; dd.textContent = r[1];
      dl.appendChild(dt); dl.appendChild(dd);
    });
  }
  function draw() {
    if (pl.bg && pl.bg.complete) ctx.drawImage(pl.bg, 0, 0);
    var im = pl.imgs[pl.k];
    if (im && im.complete) ctx.drawImage(im, 0, 108);
  }
  var last = null, acc = 0;
  function frame(ts) {
    if (last === null) last = ts;
    var dt = ts - last; last = ts;
    if (pl.playing && pl.imgs.length) {
      acc += dt;
      while (acc >= PL.frame_ms) { acc -= PL.frame_ms; pl.k = (pl.k + 1) % pl.imgs.length; }
    }
    draw();
    requestAnimationFrame(frame);
  }
  var btn = document.getElementById("playbtn");
  btn.addEventListener("click", function () {
    pl.playing = !pl.playing; btn.textContent = pl.playing ? "Pause" : "Play";
    btn.setAttribute("aria-pressed", pl.playing ? "true" : "false");
  });
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    pl.playing = false; btn.textContent = "Play"; btn.setAttribute("aria-pressed", "false");
  }
  load(); requestAnimationFrame(frame);
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
