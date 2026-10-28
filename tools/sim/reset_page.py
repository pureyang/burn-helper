#!/usr/bin/env python3
"""The weekly-reset proposal, with approve / change / drop on every stage -> tools/sim/out/weekly_reset.html

    python3 tools/sim/reset_page.py

Builds from tools/sim/out/proto/reset_<theme>.json (written by tools/sim/proto_reset_<theme>.py).
One self-contained page: every stage of the ladder on every theme, animated at the badge's pace,
with buttons to approve, ask for a change or drop each one, a note box, and a button that copies
your answers as plain text to paste back.
"""
import base64
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402
import proto_reset as R  # noqa: E402

THEMES = (("hero", "Hero", "Zelda: the weekly quota is the magic meter"),
          ("gameshow", "Game show", "The Running Man: the week is the season"),
          ("chocolates", "Chocolates", "Forrest: the week is a fresh box of chocolates"))
OUT = os.path.join(HERE, "out", "weekly_reset.html")

LADDER = (
    ("day", "Under 24 h", "A caption once an hour"),
    ("six", "Under 6 h", "The top-right clock alternates 5-hour / weekly"),
    ("hour", "Under 1 h", "The caption carries it; the meter pulses"),
    ("ten", "Under 10 min", "An interstitial every minute; the case LEDs start to breathe"),
    ("minute", "Under 1 min", "A full-screen countdown, milliseconds ticking"),
    ("ten_s", "Under 10 s", "Flashing numbers, a flash on every second"),
    ("zero", "At the reset", "A 4-second celebration, the meter refills"),
)
QUESTIONS = (
    ("loud", "How loud?", ("Escalate every week", "Quieter when the week is barely used, loudest when it is nearly spent",
                           "Only the last 10 minutes")),
    ("leds", "Case LEDs in the last 10 minutes?", ("Yes, a different rhythm from the waiting alert", "No, keep them for waiting sessions")),
    ("demo", "A speeded-up weekly countdown in the demo modes?", ("Yes", "No")),
    ("both", "The 5-hour reset", ("Stays as it is", "Gets a small version too")),
)


def uri(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def load():
    data = {}
    for key, _, _ in THEMES:
        path = os.path.join(P.OUT, "reset_%s.json" % key)
        items = json.load(open(path)) if os.path.exists(path) else []
        for it in items:
            it["frames"] = [uri(os.path.join(P.OUT, f)) for f in it["frames"]]
        data[key] = items
    return data


def build():
    data = load()
    page = PAGE.replace("@@DATA@@", json.dumps({
        "themes": [[k, l, d] for k, l, d in THEMES], "ladder": LADDER, "questions": QUESTIONS, "items": data},
        separators=(",", ":")))
    with open(OUT, "w") as f:
        f.write(page)
    print(OUT, len(page) // 1024, "KB;", {k: len(v) for k, v in data.items()}, "stages")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weekly Reset Proposal</title>
<style>
:root{
  --bg:#F4F2EE; --panel:#FFFFFF; --ink:#1D1B19; --dim:#6B6660; --line:#D9D3CB; --chip:#EFE9E1;
  --yes:#0072B2; --yes-soft:#DCEBF5; --maybe:#8A6D00; --maybe-soft:#F8EFB8; --no:#D55E00; --no-soft:#FBE3D3;
  --bezel:#2B2B30; --screen:#0C0E14; --sel:#1D1B19; --sel-ink:#F4F2EE;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#15161A; --panel:#1E2026; --ink:#ECEBE8; --dim:#9A9690; --line:#34363E; --chip:#2A2C33;
    --yes:#56B4E9; --yes-soft:#1D3342; --maybe:#EFE27A; --maybe-soft:#3B3716; --no:#F5A05A; --no-soft:#41281A;
    --bezel:#3A3A42; --sel:#ECEBE8; --sel-ink:#15161A;
  }
}
:root[data-theme="dark"]{
  --bg:#15161A; --panel:#1E2026; --ink:#ECEBE8; --dim:#9A9690; --line:#34363E; --chip:#2A2C33;
  --yes:#56B4E9; --yes-soft:#1D3342; --maybe:#EFE27A; --maybe-soft:#3B3716; --no:#F5A05A; --no-soft:#41281A;
  --bezel:#3A3A42; --sel:#ECEBE8; --sel-ink:#15161A;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;padding:28px 16px 90px}
main{max-width:1180px;margin:0 auto;display:grid;gap:26px}
h1{font-size:28px;margin:0 0 6px;letter-spacing:-.01em} h2{font-size:21px;margin:0} h3{font-size:15px;margin:0}
p{margin:0}.lede{color:var(--dim);max-width:60em}.small{font-size:13px}.muted{color:var(--dim)}
button{font:inherit;color:var(--ink);cursor:pointer}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.pill{font-size:13px;font-weight:600;padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:var(--panel)}
.pill:hover,.pill:focus-visible{border-color:var(--ink);outline:none}
.ladder{display:grid;grid-template-columns:repeat(7,1fr);gap:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.ladder div{padding:12px 12px;border-right:1px solid var(--line);display:grid;gap:3px;align-content:start}
.ladder div:last-child{border-right:0}
.ladder b{font-size:13px}.ladder span{font-size:12.5px;color:var(--dim)}
.ladder .bars{display:flex;gap:2px;align-items:flex-end;height:22px;margin-bottom:4px}
.ladder .bars i{width:6px;background:var(--ink);border-radius:1px;opacity:.85}
@media (max-width:900px){.ladder{grid-template-columns:1fr 1fr}.ladder div{border-bottom:1px solid var(--line)}}
.theme{display:grid;gap:14px;border-top:2px solid var(--line);padding-top:10px}
.stages{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;display:grid;gap:10px;align-content:start}
.card[data-v="yes"]{border-color:var(--yes)} .card[data-v="change"]{border-color:var(--maybe)} .card[data-v="drop"]{border-color:var(--no)}
.anim{position:relative;width:100%;aspect-ratio:4/3;background:var(--screen);border:8px solid var(--bezel);border-radius:6px;box-sizing:border-box;overflow:hidden}
.anim img{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated;image-rendering:crisp-edges;visibility:hidden}
.anim img.on{visibility:visible}
.head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.left{font:600 12px ui-monospace,Menlo,monospace;background:var(--chip);border-radius:6px;padding:1px 7px;white-space:nowrap}
.desc{font-size:13.5px;color:var(--dim)}
.notes{font-size:12.5px;border-left:2px solid var(--line);padding-left:8px;color:var(--dim)}
.votes{display:flex;gap:6px;flex-wrap:wrap}
.votes button{font-size:13px;font-weight:600;padding:5px 11px;border:1px solid var(--line);border-radius:8px;background:transparent}
.votes button[aria-pressed="true"]{background:var(--sel);color:var(--sel-ink);border-color:var(--sel)}
.votes button[data-v="yes"][aria-pressed="true"]{background:var(--yes);border-color:var(--yes);color:#fff}
.votes button[data-v="change"][aria-pressed="true"]{background:var(--maybe-soft);border-color:var(--maybe);color:var(--ink)}
.votes button[data-v="drop"][aria-pressed="true"]{background:var(--no);border-color:var(--no);color:#fff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .votes button[data-v="yes"][aria-pressed="true"],:root:not([data-theme="light"]) .votes button[data-v="drop"][aria-pressed="true"]{color:#15161A}}
textarea{width:100%;font:inherit;font-size:13.5px;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:7px 9px;min-height:2.6em;resize:vertical}
textarea:focus-visible,.votes button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.qs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.q{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;display:grid;gap:8px;align-content:start}
.q label{display:flex;gap:8px;align-items:flex-start;font-size:14px;cursor:pointer}
.q input{margin-top:4px;accent-color:var(--ink)}
.sum{position:fixed;left:0;right:0;bottom:0;background:var(--panel);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap}
.sum .count{font-size:13.5px}
.sum button{font-weight:600;font-size:14px;padding:8px 16px;border-radius:8px;border:1px solid var(--ink);background:var(--ink);color:var(--bg)}
dialog{max-width:640px;width:calc(100% - 32px);border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--ink);padding:16px}
dialog::backdrop{background:rgba(0,0,0,.45)}
dialog pre{white-space:pre-wrap;font:12.5px/1.5 ui-monospace,Menlo,monospace;background:var(--bg);padding:10px;border-radius:8px;max-height:46vh;overflow:auto;margin:10px 0}
</style>
</head>
<body>
<main>
<header>
  <h1>Weekly quota reset: a bigger deal</h1>
  <p class="lede">The weekly reset gets louder as it nears: a quiet caption a day out, then a clock that takes over the screen, then a celebration. The 5-hour reset stays as it is. Every screen below is drawn by the simulator with the badge's own drawing code, at the badge's pace. For each stage on each theme, approve it, ask for a change (and say what), or drop it.</p>
</header>

<div class="bar">
  <button class="pill" id="play" type="button" aria-pressed="true">Pause animations</button>
  <button class="pill" id="allyes" type="button">Approve everything left undecided</button>
  <span class="small muted" id="saved">Your answers are kept in this browser.</span>
</div>

<section aria-label="The ladder"><h2 style="margin-bottom:10px">The ladder, louder at every step</h2><div class="ladder" id="ladder"></div></section>

<div id="themes"></div>

<section aria-label="Decisions"><h2 style="margin-bottom:10px">A few decisions</h2><div class="qs" id="qs"></div></section>
</main>

<div class="sum"><span class="count" id="count"></span><button type="button" id="copy">Copy my answers</button></div>
<dialog id="dlg"><h3>Your answers</h3><p class="small muted">Copy this and paste it back into the chat.</p><pre id="out"></pre>
<div class="bar"><button class="pill" id="copy2" type="button">Copy</button><button class="pill" id="close" type="button">Close</button></div></dialog>

<script>
(function () {
  var D = @@DATA@@;
  var KEY = "weekly-reset-answers-v1";
  var A = {};
  try { A = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { A = {}; }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(A)); } catch (e) {} count(); }
  var ICON = {yes: "✓", change: "✎", drop: "✗"}, WORD = {yes: "Approve", change: "Change", drop: "Drop"};

  var ladder = document.getElementById("ladder");
  D.ladder.forEach(function (s, i) {
    var d = document.createElement("div"), b = document.createElement("span"); b.className = "bars";
    for (var k = 0; k <= i; k++) { var bar = document.createElement("i"); bar.style.height = (5 + k * 3) + "px"; b.appendChild(bar); }
    var t = document.createElement("b"); t.textContent = s[1]; var x = document.createElement("span"); x.textContent = s[2];
    d.appendChild(b); d.appendChild(t); d.appendChild(x); ladder.appendChild(d);
  });

  var anims = [];
  var themes = document.getElementById("themes");
  D.themes.forEach(function (th) {
    var sec = document.createElement("section"); sec.className = "theme"; sec.id = th[0];
    var h = document.createElement("div"); var h2 = document.createElement("h2"); h2.textContent = th[1];
    var p = document.createElement("p"); p.className = "small muted"; p.textContent = th[2]; h.appendChild(h2); h.appendChild(p); sec.appendChild(h);
    var grid = document.createElement("div"); grid.className = "stages";
    var items = D.items[th[0]] || [];
    if (!items.length) { var e = document.createElement("p"); e.className = "muted"; e.textContent = "Not rendered yet."; grid.appendChild(e); }
    items.forEach(function (it) {
      var id = th[0] + "/" + it.key;
      var card = document.createElement("article"); card.className = "card";
      var a = document.createElement("div"); a.className = "anim";
      it.frames.forEach(function (src, i) { var im = document.createElement("img"); im.src = src; im.width = 160; im.height = 120;
        im.alt = i === 0 ? th[1] + ", " + it.title : ""; if (i) im.setAttribute("aria-hidden", "true"); if (i === 0) im.className = "on"; a.appendChild(im); });
      anims.push({el: a, interval: it.ms || 700, k: 0});
      var head = document.createElement("div"); head.className = "head";
      var t = document.createElement("h3"); t.textContent = it.title; var l = document.createElement("span"); l.className = "left"; l.textContent = it.left;
      head.appendChild(t); head.appendChild(l);
      var desc = document.createElement("p"); desc.className = "desc"; desc.textContent = it.desc;
      card.appendChild(a); card.appendChild(head); card.appendChild(desc);
      if (it.notes) { var n = document.createElement("p"); n.className = "notes"; n.textContent = it.notes; card.appendChild(n); }
      var votes = document.createElement("div"); votes.className = "votes"; votes.setAttribute("role", "group"); votes.setAttribute("aria-label", "Your verdict on " + th[1] + ", " + it.title);
      var note = document.createElement("textarea"); note.placeholder = "What should change?"; note.setAttribute("aria-label", "What should change on " + th[1] + ", " + it.title); note.hidden = true;
      function paint() {
        var v = (A[id] || {}).v; card.dataset.v = v || "";
        votes.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.v === v ? "true" : "false"); });
        note.hidden = !(v === "change" || (A[id] || {}).note);
        if (document.activeElement !== note) note.value = (A[id] || {}).note || "";
      }
      ["yes", "change", "drop"].forEach(function (v) {
        var b = document.createElement("button"); b.type = "button"; b.dataset.v = v; b.textContent = ICON[v] + " " + WORD[v];
        b.addEventListener("click", function () { var cur = A[id] || {}; cur.v = cur.v === v ? "" : v; A[id] = cur; paint(); save(); if (v === "change") note.focus(); });
        votes.appendChild(b);
      });
      note.addEventListener("input", function () { var cur = A[id] || {}; cur.note = note.value; A[id] = cur; save(); });
      card.appendChild(votes); card.appendChild(note);
      card._id = id; card._paint = paint; paint();
      grid.appendChild(card);
    });
    sec.appendChild(grid); themes.appendChild(sec);
  });

  var qs = document.getElementById("qs");
  D.questions.forEach(function (q) {
    var box = document.createElement("div"); box.className = "q"; var h = document.createElement("h3"); h.textContent = q[1]; box.appendChild(h);
    q[2].forEach(function (opt, i) {
      var lab = document.createElement("label"), r = document.createElement("input"); r.type = "radio"; r.name = "q-" + q[0]; r.value = String(i);
      r.checked = (A["q:" + q[0]] || {}).v === String(i);
      r.addEventListener("change", function () { A["q:" + q[0]] = {v: String(i)}; save(); });
      lab.appendChild(r); lab.appendChild(document.createTextNode(opt)); box.appendChild(lab);
    });
    qs.appendChild(box);
  });

  function cards() { return Array.prototype.slice.call(document.querySelectorAll(".card")).filter(function (c) { return c._id; }); }
  function count() {
    var n = {yes: 0, change: 0, drop: 0, none: 0};
    cards().forEach(function (c) { var v = (A[c._id] || {}).v; n[v || "none"]++; });
    document.getElementById("count").textContent = "✓ " + n.yes + " approved   ✎ " + n.change + " to change   ✗ " + n.drop + " dropped   " + n.none + " undecided";
  }
  document.getElementById("allyes").addEventListener("click", function () {
    cards().forEach(function (c) { if (!(A[c._id] || {}).v) { var cur = A[c._id] || {}; cur.v = "yes"; A[c._id] = cur; c._paint(); } });
    save();
  });

  function summary() {
    var lines = ["Weekly reset: my answers", ""];
    D.themes.forEach(function (th) {
      lines.push(th[1].toUpperCase());
      (D.items[th[0]] || []).forEach(function (it) {
        var a = A[th[0] + "/" + it.key] || {};
        lines.push("  " + (ICON[a.v] || "?") + " " + it.title + " (" + it.left + "): " + (WORD[a.v] || "undecided") + (a.note ? " - " + a.note : ""));
      });
      lines.push("");
    });
    D.questions.forEach(function (q) { var a = A["q:" + q[0]]; lines.push(q[1] + " " + (a ? q[2][+a.v] : "(no answer)")); });
    return lines.join("\n");
  }
  var dlg = document.getElementById("dlg"), out = document.getElementById("out");
  function copyText(btn) {
    var t = summary();
    (navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = btn.dataset.l; }, 1500); }, function () { btn.textContent = "Select and copy"; });
  }
  ["copy", "copy2"].forEach(function (id) { var b = document.getElementById(id); b.dataset.l = b.textContent; });
  document.getElementById("copy").addEventListener("click", function () { out.textContent = summary(); if (dlg.showModal) dlg.showModal(); copyText(this); });
  document.getElementById("copy2").addEventListener("click", function () { copyText(this); });
  document.getElementById("close").addEventListener("click", function () { dlg.close(); });

  var playing = !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var btn = document.getElementById("play");
  function lab() { btn.textContent = playing ? "Pause animations" : "Play animations"; btn.setAttribute("aria-pressed", playing ? "true" : "false"); }
  lab();
  btn.addEventListener("click", function () { playing = !playing; lab(); });
  setInterval(function () {
    if (!playing) return;
    anims.forEach(function (a) {
      var im = a.el.children; a.k = (a.k + 1) % im.length;
      for (var j = 0; j < im.length; j++) im[j].classList.toggle("on", j === a.k);
    });
  }, 450);
  count();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
