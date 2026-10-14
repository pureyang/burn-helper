#!/usr/bin/env python3
"""The badge's waiting bar, every state, on every theme -> tools/sim/out/waiting_bar.html

    python3 tools/sim/waiting_bar.py

Renders the animation screen of each theme and Desktop mode for none, one, three and four
sessions waiting (with and without an unnamed one), at each step of the 4-second cycle, from
the badge's own code, and builds one self-contained page with them.
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
ALL = [
    {"n": "api-server refactor", "s": 720, "d": "api-server", "w": "PERMISSION: BASH", "a": 7800, "i": "22441a", "u": 0},
    {"n": "docs-site", "s": 360, "d": "docs-site", "w": "YOUR REPLY", "a": 1500, "i": "9b1e04", "u": 0},
    {"n": "web-app", "s": 180, "d": "web-app", "w": "YOUR REPLY", "a": 600, "i": "7f3a2c", "u": 1},
    {"n": "laptop", "s": 60, "d": "laptop", "w": "YOUR REPLY", "a": 0, "i": "c0d5aa", "u": 1},
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
                scr = P.render(th, st, 12 * S.WAIT_CYCLE_MS * 4 + step * S.WAIT_CYCLE_MS + 900)   # a multiple of every list length
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


def build():
    lists, frames = render_all()
    data = {"frames": frames, "lists": {k: [w["i"] for w in v] for k, v in lists.items()},
            "all": ALL, "themes": [[n, label] for n, label, _ in THEMES], "cycle": S.WAIT_CYCLE_MS}
    page = PAGE.replace("@@DATA@@", json.dumps(data, separators=(",", ":")))
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
.pair img{width:100%;height:auto;image-rendering:pixelated;image-rendering:crisp-edges;border-radius:6px;border:8px solid var(--bezel);background:var(--screen)}
.step{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--muted)}
.step b{font-weight:600;color:var(--ink);font-family:var(--mono)}
.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media (max-width:860px){.rules{grid-template-columns:1fr}}
.rule,.how{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:grid;gap:6px;align-content:start}
.rule ul,.how ol{margin:0;padding-left:18px;display:grid;gap:4px;font-size:14px}
.chip{display:inline-block;font-size:12px;font-weight:600;color:var(--wait);background:var(--wait-soft);border-radius:99px;padding:1px 8px}
</style>
</head>
<body>
<div class="wrap">
  <header style="display:grid;gap:10px">
    <div class="eyebrow">Burn Helper badge · animation screen and Desktop mode <span class="chip">on the badge now</span></div>
    <h1>Show which sessions are waiting on you</h1>
    <p class="muted">When a session needs your input, the badge's caption line turns into a waiting bar with its name.
    Several waiting sessions take turns. Sessions you never named get a readable fallback. Every screen below is
    drawn by the badge's own code; pick a state and the screens follow.</p>
  </header>

  <div class="controls" role="group" aria-label="Badge state">
    <div class="ctl"><span>Sessions waiting</span>
      <div class="seg" id="count"><button type="button" data-n="0">None</button><button type="button" data-n="1">One</button><button type="button" data-n="3" aria-pressed="true">Three</button><button type="button" data-n="4">Four</button></div></div>
    <div class="ctl"><span>Names</span>
      <label class="toggle"><input type="checkbox" id="unnamed" checked> Include unnamed sessions</label></div>
    <div class="ctl"><span>Theme</span><div class="seg" id="theme"></div></div>
    <div class="ctl"><span>Cycle</span>
      <div class="seg" id="speed"><button type="button" data-ms="2000">Fast</button><button type="button" data-ms="4000" aria-pressed="true">Normal (the badge)</button><button type="button" data-ms="0">Paused</button></div></div>
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
        <figure id="detailfig"><img id="detail" alt="Desktop mode: one waiting session in detail" width="160" height="120"><figcaption>A/C: one in detail (an unnamed one here)</figcaption></figure>
      </div>
      <p class="small muted">Desktop mode uses the same names, so an unnamed session reads the same in both places.</p>
    </section>
  </div>

  <section class="rules" aria-label="Behaviour">
    <div class="rule"><h3>One session waiting</h3><ul>
      <li>Its name stays in the bar; no cycling.</li>
      <li>Shown as <span class="mono">WAITING name</span>, the label in amber.</li>
      <li>Gone as soon as you answer it.</li></ul></div>
    <div class="rule"><h3>Several waiting</h3><ul>
      <li>Names take turns every 4 s, longest wait first, with a counter (<span class="mono">2/3</span>).</li>
      <li>Up to 4 at a time, the same 4 Desktop mode lists.</li>
      <li>Sessions on your other computers count too.</li></ul></div>
    <div class="rule"><h3>No name given</h3><ul>
      <li>Falls back to the folder plus the start of the session id: <span class="mono">web-app · 7f3a2c</span>, in grey.</li>
      <li>A long folder is shortened, never the id, so two sessions in one folder stay apart.</li>
      <li>A session on another computer shows that computer's name and id.</li></ul></div>
  </section>

  <section class="how" aria-labelledby="how-h">
    <h2 id="how-h">How it works</h2>
    <ol>
      <li>The bridge reads Claude Code's session files and hook events, and sends the waiting sessions in
      <span class="mono">/status</span>: name, how long each has waited, folder, what it needs, the first 6
      characters of its id, and whether it has a name of its own.</li>
      <li>Names come from what you set with <span class="mono">/rename</span>. Without one, the badge shows the
      folder and the id. Sessions on joined computers have no folder there, so they show the computer's name.</li>
      <li>The badge picks which name to show from the clock, so the bar turns every 4 seconds without any extra
      traffic. Nothing changes on screen when no session is waiting.</li>
    </ol>
  </section>
</div>
<script>
(function () {
  var D = @@DATA@@;
  var state = {n: 3, unnamed: true, theme: D.themes[0][0], ms: 4000, i: 0}, timer = null;
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
  function label(w) { return w.u ? w.d + " · " + w.i : w.n; }
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
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
