#!/usr/bin/env python3
"""More than one Claude account: the status line tags its report with the account (a hash and a
label, read from its config folder), the bridge keeps the main account as before and a row for
each other one, the badge draws those rows, and install.py --add-account sets one up."""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge")
sys.path.insert(0, BRIDGE_DIR)
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import burn_helper_bridge as B  # noqa: E402
import cc_statusline as SL  # noqa: E402
import scene as S  # noqa: E402

for _name, _fn in (("ticks_us", lambda: int(time.time() * 1e6)), ("ticks_ms", lambda: int(time.time() * 1000)),
                   ("ticks_diff", lambda a, b: a - b)):
    if not hasattr(time, _name):
        setattr(time, _name, _fn)

now = int(time.time())

# ---------------------------------------------------------------- the status line's tag
home = tempfile.mkdtemp()
with open(os.path.join(home, ".claude.json"), "w") as f:
    json.dump({"projects": {"x": {"a": {}}}, "oauthAccount": {
        "accountUuid": "uuid-gmail", "ccOnboardingFlags": {"x": 1}, "emailAddress": "me@gmail.com"}}, f)
acme = os.path.join(home, ".claude-acme")
os.makedirs(acme)
with open(os.path.join(acme, ".claude.json"), "w") as f:
    json.dump({"oauthAccount": {"emailAddress": "me@acme.io", "accountUuid": "uuid-acme"}}, f)
os.environ.pop("BURN_HELPER_LABEL", None)
g_tag, g_label, g_default = SL.account(config_dir=None, home=home)
l_tag, l_label, l_default = SL.account(config_dir=acme, home=home)
assert (g_label, g_default, l_label, l_default) == ("GMAIL", True, "ACME", False), (g_label, l_label)
assert g_tag and l_tag and g_tag != l_tag and len(g_tag) == 12, (g_tag, l_tag)
assert "uuid" not in g_tag and "gmail" not in g_tag, "only a hash leaves the computer"
assert SL.account(config_dir=None, home=os.path.join(home, "nope"))[0] is None, "~/.claude signed out: untagged"
other = SL.account(config_dir=os.path.join(home, "nope"), home=home)[0]
assert other and other not in (g_tag, l_tag), "another folder without the file is still its own account, never the main"
os.environ["BURN_HELPER_LABEL"] = "work"
assert SL.account(config_dir=acme, home=home)[1] == "WORK", "the installer's label wins"
del os.environ["BURN_HELPER_LABEL"]
print("PASS status line: tags each config folder's account with a hash and a label, never the email")

# ---------------------------------------------------------------- the bridge
B.STATE_DIR = tempfile.mkdtemp()
B.STATE_FILE = os.path.join(B.STATE_DIR, "state.json")
B.PACE_FILE = os.path.join(B.STATE_DIR, "pace.json")


def rl(u7, u5=None):
    d = {"seven_day": {"used_percentage": u7, "resets_at": now + 3 * 86400}}
    if u5 is not None:
        d["five_hour"] = {"used_percentage": u5, "resets_at": now + 2 * 3600}
    return d


b = B.Bridge()
b.on_usage({"rate_limits": rl(40)})                        # an older, untagged status line: the main account
assert b.status()["hearts"] == 12 and b.status()["accounts"] == []
b.on_usage({"rate_limits": rl(30, 70), "acct": l_tag, "label": "ACME", "default": False})
b.on_usage({"rate_limits": rl(44), "acct": g_tag, "label": "GMAIL", "default": True})
s = b.status()
assert b.main_acct == g_tag and s["label"] == "GMAIL", "the ~/.claude account claims the main hearts"
assert s["hearts"] == 11 and s["mode"] == "week", s                            # GMAIL: weekly only, 56% left
assert len(s["accounts"]) == 1, s["accounts"]
row = s["accounts"][0]
assert row["l"] == "ACME" and row["h"] == 6 and row["w"] == "5h" and row["u"] == "ok", row   # its 5-hour binds
assert row["p"] == 30, "Desktop mode's number: that limit's percent left, exactly (%r)" % row
assert abs(row["r"] - (now + 2 * 3600)) <= 1, row
b.on_usage({"rate_limits": rl(30), "acct": g_tag})       # a lagging session: usage only goes up
assert b.status()["hearts"] == 11 and b.status()["accounts"][0]["h"] == 6, "each report goes to its own account"
b.on_usage({"rate_limits": rl(90, 10), "acct": l_tag, "label": "ACME"})
assert b.status()["accounts"][0]["h"] == 2 and b.status()["accounts"][0]["w"] == "wk", "now its week binds"
assert b.status()["accounts"][0]["p"] == 10, b.status()["accounts"][0]
# Desktop mode's stripes: the exact percent likely left at the weekly reset, only on a weekly limit
assert row["q"] is None, "a 5-hour limit: no forecast (%r)" % row
b.pace_step()
r, pc = b.status()["accounts"][0], b.others[l_tag]["pace"].out
assert pc and r["q"] == max(0, min(r["p"], int(round(100 - pc["f"])))), (r, pc)
ans = b.answer({"acct": l_tag})
assert ans["mode"] == "5h" and b.answer({"acct": g_tag})["mode"] == "week", "each status line hears its own mode"

# the rows survive a restart; the oldest account makes room past ACCOUNTS_MAX
b.persist(force=True)
b2 = B.Bridge()
assert b2.main_acct == g_tag and b2.status()["accounts"][0]["l"] == "ACME", b2.status()["accounts"]
for i in range(B.ACCOUNTS_MAX):
    b2.on_usage({"rate_limits": rl(10), "acct": "%012x" % (i + 1), "label": "X%d" % i})
labels = [r["l"] for r in b2.status()["accounts"]]
assert len(labels) == B.ACCOUNTS_MAX and "ACME" not in labels, labels
b2.others[next(iter(b2.others))]["seen"] = now - B.ACCOUNT_FORGET_S - 1
b2.pace_step()
assert len(b2.status()["accounts"]) == B.ACCOUNTS_MAX - 1, "two weeks without a report: forgotten"
# a session in another account's config folder counts like one in ~/.claude
assert B.session_dirs()[0] == B.SESSIONS_DIR
# a name set on the bridge wins over every reported label, in the case it was typed
import portable  # noqa: E402
b.on_usage({"rate_limits": rl(90, 10), "acct": l_tag, "label": "ACME"})
portable.set_name(B.STATE_DIR, g_tag, "Home")
portable.set_name(B.STATE_DIR, l_tag, "AcmeIO")
s = b.status()
assert s["label"] == "Home" and s["accounts"][0]["l"] == "AcmeIO", (s["label"], s["accounts"])
b.on_usage({"rate_limits": rl(90, 10), "acct": l_tag, "label": "OTHER"})   # another computer's label for it
assert b.status()["accounts"][0]["l"] == "AcmeIO", "the name stays, whichever computer reports"
portable.set_name(B.STATE_DIR, l_tag, None)
assert b.status()["accounts"][0]["l"] == "OTHER", "cleared: the reported label again"
portable.set_name(B.STATE_DIR, g_tag, None)
assert portable.clean_name("AcmeIO") == "AcmeIO" and portable.clean_name("too-long-name") is None
assert portable.clean_name("a b") is None and portable.clean_name("caf\u00e9") is None
b.persist(force=True)


def name_account(*args):
    return subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "install.py"), "--name-account"] + list(args),
                          env=dict(os.environ, BURN_HELPER_STATE_DIR=B.STATE_DIR), capture_output=True, text=True)


r = name_account("other", "AcmeIO")
assert r.returncode == 0 and portable.account_names(B.STATE_DIR) == {l_tag: "AcmeIO"}, r.stdout + r.stderr
r = name_account("main", "Home")
assert r.returncode == 0 and portable.account_names(B.STATE_DIR)[g_tag] == "Home", r.stdout + r.stderr
assert b.status()["label"] == "Home"
r = name_account("acmeio", "")
assert r.returncode == 0 and l_tag not in portable.account_names(B.STATE_DIR), "found by its name, and cleared"
r = name_account("nobody", "X")
assert r.returncode != 0 and "Home (main)" in r.stderr, r.stderr
assert name_account("main", "far too long").returncode != 0, "a name that won't fit is refused"
portable.set_name(B.STATE_DIR, g_tag, None)
print("PASS names: set on the bridge, they win over every reported label, in their own case; "
      "install.py --name-account finds an account by label or name, and clears it")
print("PASS bridge: the main account keeps the hearts, every other one gets a row (its tighter limit), "
      "kept across restarts, at most %d, forgotten after two weeks" % B.ACCOUNTS_MAX)

# ---------------------------------------------------------------- the badge
st = S.Status()
st.update({"hearts": 11, "mode": "week", "now_ms": now * 1000, "label": "GMAIL",
           "accounts": [row, {"l": "WORK", "h": 30, "p": 150, "e": 40, "r": None, "w": "wk", "u": "old"}, "junk"]})
assert st.label == "GMAIL" and len(st.accounts) == 2, st.accounts
assert st.accounts[1]["h"] == 20 and st.accounts[1]["e"] == 20 and st.accounts[1]["p"] == 100, "clamped"
assert st.accounts[0]["p"] == 30
st.update({"hearts": 11, "accounts": [dict(row, p=None)]})
assert st.accounts[0]["p"] is None, "an older bridge sends no percent"
assert S.short_cd(None) == "--" and S.short_cd(65 * 60 * 1000000) == "1H05M" and S.short_cd(-1) == "NOW"
assert S.short_cd((2 * 86400 + 3 * 3600) * 1000000) == "2D03H" and S.short_cd(30 * 1000000) == "1M"
st.update({"hearts": 11})
assert st.accounts == [], "an older bridge: no rows"
print("PASS badge: rows parsed and clamped, short countdowns")

# ---------------------------------------------------------------- Desktop mode names every account
import gfx  # noqa: E402
import views  # noqa: E402
import preview_views as PV  # noqa: E402


def desktop_text(d, online=True, t=0):
    """Every string Desktop mode draws for status d."""
    st = S.Status()
    st.update(d)
    st.online = online
    if not online:
        st.seen_ms = t - 20000
    st.tick()
    drawn, real = [], gfx.text
    gfx.text = lambda s, *a, **k: (drawn.append(s), real(s, *a, **k))[1]
    try:
        harness.new_screen()
        c = views.Ctx(st, PV.link(), PV.FakeTether())
        c.source = "net"
        views.draw(views.DESKTOP, 0, c, t)
    finally:
        gfx.text = real
    return drawn


base = {"hearts": 20, "hearts_end": 17, "mode": "week", "label": "HOME", "now_ms": now * 1000, "busy": 1,
        "seven_day": {"used": 2.0, "resets_at": now + 4 * 86400}, "five_hour": None,
        "usage": {"state": "ok", "age": 1}}
lex = {"l": "LAB", "h": 12, "p": 58, "e": 7, "r": now + 86400, "w": "wk", "u": "ok"}
two = desktop_text(dict(base, accounts=[lex]))
assert "HOME" in two and "98% LEFT" in two, two
assert "LAB" in two and "58% LEFT" in two, "two accounts: a named block each (%r)" % two
assert "WEEK" in two and two.index("HOME") < two.index("LAB"), "the main account first"
turn = desktop_text(dict(base, accounts=[lex]), t=S.PACE_LINE_MS)
assert not any(s.startswith("PACE: ") for s in turn) and "RESETS IN 23H59M" in turn, \
    "the stripes show the pace: the line stays on the reset (%r)" % turn
turn = desktop_text(dict(base, accounts=[dict(lex, q=0)]), t=S.PACE_LINE_MS)
assert "AT THIS PACE IT RUNS OUT" in turn, "a run-out is still said in words (%r)" % turn
old = desktop_text(dict(base, accounts=[dict(lex, p=None)]))
assert "~60% LEFT" in old, "an older bridge: the percent from the hearts, with a ~"
five = [lex, {"l": "ACME", "h": 2, "p": 9, "e": None, "r": now + 3900, "w": "5h", "u": "ok"},
        {"l": "SIDE", "h": 9, "p": 44, "e": 0, "r": now + 44 * 3600, "w": "wk", "u": "ok"},
        {"l": "TEAM", "h": 12, "p": 61, "e": None, "r": now + 3 * 86400, "w": "wk", "u": "old"}]
many = desktop_text(dict(base, accounts=five, waiting=3,
                         waiting_list=[{"n": "a", "s": 9}, {"n": "b", "s": 8}, {"n": "c", "s": 7}]))
for s in ("HOME", "LAB", "ACME", "SIDE", "TEAM", "98%", "58%", "9%", "44%", "61%", "5H", "WK",
          "3 WAITING FOR YOU", "A/C: SESSION DETAILS"):
    assert s in many, "five accounts: %s missing from %r" % (s, many)
lost = desktop_text(dict(base, accounts=five), online=False, t=400000)
assert any(s.startswith("CONNECTION LOST") for s in lost) and "LAB" in lost, lost
one = desktop_text(base)
assert "HOME" not in one and "AT RESET" in one, "one account: Desktop mode as before (%r)" % one
print("PASS Desktop mode: each account by name, main first; two as blocks, five as lines; older bridge, lost")


# the meters: solid up to where the week likely ends, striped for what this pace likely uses
# before the reset, grey for what is used. No tick, and no stripes while the data is lost.
def desktop_meter(d, y, online=True):
    """Each pixel column of the 3-pixel meter at row y in Desktop mode: "solid", "stripes", "grey"."""
    st = S.Status()
    st.update(d)
    st.online = online
    if not online:
        st.seen_ms = 400000 - 20000
    st.tick()
    scr = harness.new_screen()
    c = views.Ctx(st, PV.link(), PV.FakeTether())
    c.source = "net"
    views.draw(views.DESKTOP, 0, c, 0 if online else 400000)
    out = []
    marks = [4 + (152 * q + 50) // 100 for q in (25, 50, 75)]
    for x in range(4, 156):
        px = [(scr.get(x, y + r).r, scr.get(x, y + r).g, scr.get(x, y + r).b) for r in range(-1, 3)]
        if x in marks:
            # a hash mark at each quarter: a gap through the bar and a pixel over it
            assert px[1:] == [views.BG] * 3 and px[0] == views.DIM, "hash mark at x=%d: %r" % (x, px)
            out.append(out[-1])
            continue
        lit = [c != views.MUTED for c in px[1:]]
        out.append("solid" if all(lit) else ("stripes" if any(lit) else "grey"))
    return out


def runs(cols):
    """[(kind, length)] of a meter's columns."""
    out = []
    for k in cols:
        if out and out[-1][0] == k:
            out[-1][1] += 1
        else:
            out.append([k, 1])
    return [tuple(r) for r in out]


paced = dict(base, pace={"s": 0, "f": 16, "even": 21, "p": 2})
m = runs(desktop_meter(dict(paced, accounts=[dict(lex, q=35)]), 10 + 12))
assert m == [("solid", 128), ("stripes", 21), ("grey", 3)], "main: solid to ~84%%, stripes to 98%% (%r)" % (m,)
m = runs(desktop_meter(dict(paced, accounts=[dict(lex, q=35)]), 34 + 12))
assert m == [("solid", 53), ("stripes", 35), ("grey", 64)], "other: solid to ~35%%, stripes to 58%% (%r)" % (m,)
m = runs(desktop_meter(dict(paced, accounts=[lex]), 34 + 12))
assert m == [("solid", 53), ("stripes", 35), ("grey", 64)], "an older bridge: from its half hearts (%r)" % (m,)
m = runs(desktop_meter(dict(paced, accounts=[dict(lex, q=0)]), 34 + 12))
assert m == [("stripes", 88), ("grey", 64)], "on course to run out: all it has left is striped (%r)" % (m,)
m = runs(desktop_meter(dict(paced, accounts=[dict(lex, w="5h", q=None, e=None)]), 34 + 12))
assert m == [("solid", 88), ("grey", 64)], "a 5-hour limit: no forecast (%r)" % (m,)
m = runs(desktop_meter(dict(base, accounts=[lex]), 10 + 12))
assert m == [("solid", 149), ("grey", 3)], "no pace from the bridge: a plain meter, no tick (%r)" % (m,)
m = runs(desktop_meter(dict(paced, accounts=[dict(lex, q=35)]), 34 + 12, online=False))
assert "stripes" not in dict(m), "lost: no stripes (%r)" % (m,)
m = runs(desktop_meter(paced, 10 + 12))
assert m == [("solid", 128), ("stripes", 21), ("grey", 3)], "one account: the WEEK meter too (%r)" % (m,)
lines = [x for k in range(4) for x in desktop_text(dict(paced, accounts=[dict(lex, q=35)]), t=k * S.PACE_LINE_MS)]
assert not any(s.startswith("PACE: ") for s in lines), "calm, striped: no pace line takes turns (%r)" % lines
lines = [x for k in range(4) for x in desktop_text(paced, t=k * S.PACE_LINE_MS)]
assert not any(s.startswith("PACE: ") for s in lines), "one account: the same (%r)" % lines
h5 = dict(paced, mode="5h", hearts=8, five_hour={"used": 60.0, "resets_at": now + 3 * 3600}, accounts=[lex])
lines = [x for k in range(4) for x in desktop_text(h5, t=k * S.PACE_LINE_MS)]
assert "PACE: ~84% LEFT AT RESET" in lines, "a meter showing the 5-hour limit has no stripes: the line says it (%r)" % lines
st = S.Status()
st.update(dict(base, accounts=[dict(lex, q=80), dict(lex, l="ACME", q=-3), dict(lex, l="OLD", p=None, q=20)]))
assert [a["q"] for a in st.accounts] == [58, 0, None], "q is clamped to what is left now (%r)" % st.accounts
print("PASS Desktop meters: the part likely used before the reset striped, hash marks at each quarter; older bridge, 5-hour, lost")

# ---------------------------------------------------------------- each theme's panel
import preview_lost as PL  # noqa: E402


def theme_text(name, d, online=True, t=400100):
    """Every string a theme draws for status d, and the panel's height."""
    st = S.Status()
    st.update(d)
    st.online = online
    if not online:
        st.seen_ms = t - 20000
        S.track_lost(st, t)
    st.tick()
    drawn, real = [], gfx.text
    gfx.text = lambda s, *a, **k: (drawn.append(s), real(s, *a, **k))[1]
    try:
        PL.theme_shot(name, st, t)
    finally:
        gfx.text = real
    return drawn, S.hud_h(st)


acme = {"l": "AcmeIO", "h": 12, "p": 58, "e": 7, "r": now + 86400 + 2 * 3600 + 900, "w": "wk", "u": "ok"}
for name in ("hero", "gameshow", "chocolates"):
    for accts in ([acme], five):
        drawn, h = theme_text(name, dict(base, label="Home", accounts=accts))
        want = ["Home"] + [a["l"] for a in accts]
        assert all(w in drawn for w in want), "%s: every account named (%r)" % (name, drawn)
        assert ("1D02H" if accts == [acme] else "23H59M") in drawn, "%s: each its countdown (%r)" % (name, drawn)
        assert h == S.FX_TOP + S.ACCOUNT_ROW_H * len(accts)
    drawn, _ = theme_text(name, dict(base, label="Home", accounts=[acme]), online=False)
    assert "Home" in drawn and "AcmeIO" in drawn, "%s: still named while the data is lost" % name
    drawn, _ = theme_text(name, dict(base, label="Home", accounts=[]))
    assert "Home" not in drawn, "%s: one account, the theme's own top bar as before" % name
print("PASS themes: one panel for every account in each theme, a row each (name, countdown, icons), "
      "lost and single-account cases")

# ---------------------------------------------------------------- install.py --add-account
ihome = tempfile.mkdtemp()


def install(*args):
    r = subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "install.py")] + list(args),
                       env=dict(os.environ, BURN_HELPER_HOME=ihome, SHELL="/bin/zsh"), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


out = install("--add-account", "acme", "--dry-run")
assert not os.path.exists(os.path.join(ihome, ".claude-acme")), "a dry run changes nothing"
out = install("--add-account", "acme")
with open(os.path.join(ihome, ".claude-acme", "settings.json")) as f:
    s = json.load(f)
assert s["env"] == {"BURN_HELPER_LABEL": "ACME"} and "cc_statusline.py" in s["statusLine"]["command"], s
assert all(e in s["hooks"] for e in ("Stop", "PostToolUse")), s["hooks"].keys()
assert not os.path.exists(os.path.join(ihome, ".claude", "settings.json")), "~/.claude is left alone"
assert "LaunchAgents" not in out and "launchctl" not in out, "no second bridge"
rc = [p for p in (".zshrc", ".bashrc") if os.path.exists(os.path.join(ihome, p))]
if rc:      # a Mac or Linux: the alias went into the shell's start-up file, once
    install("--add-account", "acme")
    with open(os.path.join(ihome, rc[0])) as f:
        text = f.read()
    assert text.count("alias claude-acme=") == 1 and "CLAUDE_CONFIG_DIR=" in text, text
else:       # Windows: the line for the PowerShell profile is printed
    assert "function claude-acme" in out and "$PROFILE" in out, out
import install as I  # noqa: E402
I.WINDOWS, I.MAC, I.HOME = False, True, tempfile.mkdtemp()     # the Mac's way, from any computer
assert "Added the alias claude-acme" in I.add_alias("acme") and "already" in I.add_alias("acme")
with open(os.path.join(I.HOME, ".zshrc")) as f:
    assert f.read().count("""alias claude-acme='CLAUDE_CONFIG_DIR="$HOME/.claude-acme" claude'""") == 1
out = install("--add-account", "acme", "--uninstall")
with open(os.path.join(ihome, ".claude-acme", "settings.json")) as f:
    assert json.load(f) == {}, "uninstall takes ours out of that folder"
key = "00112233445566778899aabbccddeeff"
install("--add-account", "other", "--bridge", "http://my-mac:8787/#k=" + key)
with open(os.path.join(ihome, ".claude-other", "settings.json")) as f:
    senv = json.load(f)["env"]
assert senv == {"BURN_HELPER_BRIDGE_URL": "http://my-mac:8787", "BURN_HELPER_TOKEN": key,
                "BURN_HELPER_LABEL": "OTHER"}, senv     # on a joined computer it needs the key too
r = subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "install.py"), "--add-account", "../x"],
                   env=dict(os.environ, BURN_HELPER_HOME=ihome), capture_output=True, text=True)
assert r.returncode != 0, "a name that isn't a plain word is refused"
print("PASS install --add-account: its own folder, hooks, status line and label, the alias once, "
      "clean uninstall, the key on a joined computer")
