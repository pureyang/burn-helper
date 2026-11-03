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
lexco = os.path.join(home, ".claude-lexco")
os.makedirs(lexco)
with open(os.path.join(lexco, ".claude.json"), "w") as f:
    json.dump({"oauthAccount": {"emailAddress": "me@lexco.io", "accountUuid": "uuid-lexco"}}, f)
os.environ.pop("BURN_HELPER_LABEL", None)
g_tag, g_label, g_default = SL.account(config_dir=None, home=home)
l_tag, l_label, l_default = SL.account(config_dir=lexco, home=home)
assert (g_label, g_default, l_label, l_default) == ("GMAIL", True, "LEXCO", False), (g_label, l_label)
assert g_tag and l_tag and g_tag != l_tag and len(g_tag) == 12, (g_tag, l_tag)
assert "uuid" not in g_tag and "gmail" not in g_tag, "only a hash leaves the computer"
assert SL.account(config_dir=None, home=os.path.join(home, "nope"))[0] is None, "~/.claude signed out: untagged"
other = SL.account(config_dir=os.path.join(home, "nope"), home=home)[0]
assert other and other not in (g_tag, l_tag), "another folder without the file is still its own account, never the main"
os.environ["BURN_HELPER_LABEL"] = "work"
assert SL.account(config_dir=lexco, home=home)[1] == "WORK", "the installer's label wins"
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
b.on_usage({"rate_limits": rl(30, 70), "acct": l_tag, "label": "LEXCO", "default": False})
b.on_usage({"rate_limits": rl(44), "acct": g_tag, "label": "GMAIL", "default": True})
s = b.status()
assert b.main_acct == g_tag and s["label"] == "GMAIL", "the ~/.claude account claims the main hearts"
assert s["hearts"] == 11 and s["mode"] == "week", s                            # GMAIL: weekly only, 56% left
assert len(s["accounts"]) == 1, s["accounts"]
row = s["accounts"][0]
assert row["l"] == "LEXCO" and row["h"] == 6 and row["w"] == "5h" and row["u"] == "ok", row   # its 5-hour binds
assert abs(row["r"] - (now + 2 * 3600)) <= 1, row
b.on_usage({"rate_limits": rl(30), "acct": g_tag})       # a lagging session: usage only goes up
assert b.status()["hearts"] == 11 and b.status()["accounts"][0]["h"] == 6, "each report goes to its own account"
b.on_usage({"rate_limits": rl(90, 10), "acct": l_tag, "label": "LEXCO"})
assert b.status()["accounts"][0]["h"] == 2 and b.status()["accounts"][0]["w"] == "wk", "now its week binds"
ans = b.answer({"acct": l_tag})
assert ans["mode"] == "5h" and b.answer({"acct": g_tag})["mode"] == "week", "each status line hears its own mode"

# the rows survive a restart; the oldest account makes room past ACCOUNTS_MAX
b.persist(force=True)
b2 = B.Bridge()
assert b2.main_acct == g_tag and b2.status()["accounts"][0]["l"] == "LEXCO", b2.status()["accounts"]
for i in range(B.ACCOUNTS_MAX):
    b2.on_usage({"rate_limits": rl(10), "acct": "%012x" % (i + 1), "label": "X%d" % i})
labels = [r["l"] for r in b2.status()["accounts"]]
assert len(labels) == B.ACCOUNTS_MAX and "LEXCO" not in labels, labels
b2.others[next(iter(b2.others))]["seen"] = now - B.ACCOUNT_FORGET_S - 1
b2.pace_step()
assert len(b2.status()["accounts"]) == B.ACCOUNTS_MAX - 1, "two weeks without a report: forgotten"
# a session in another account's config folder counts like one in ~/.claude
assert B.session_dirs()[0] == B.SESSIONS_DIR
print("PASS bridge: the main account keeps the hearts, every other one gets a row (its tighter limit), "
      "kept across restarts, at most %d, forgotten after two weeks" % B.ACCOUNTS_MAX)

# ---------------------------------------------------------------- the badge
st = S.Status()
st.update({"hearts": 11, "mode": "week", "now_ms": now * 1000, "label": "GMAIL",
           "accounts": [row, {"l": "WORK", "h": 30, "e": 40, "r": None, "w": "wk", "u": "old"}, "junk"]})
assert st.label == "GMAIL" and len(st.accounts) == 2, st.accounts
assert st.accounts[1]["h"] == 20 and st.accounts[1]["e"] == 20, "clamped"
assert S.short_cd(None) == "--" and S.short_cd(65 * 60 * 1000000) == "1H05M" and S.short_cd(-1) == "NOW"
assert S.short_cd((2 * 86400 + 3 * 3600) * 1000000) == "2D03H" and S.short_cd(30 * 1000000) == "1M"
st.update({"hearts": 11})
assert st.accounts == [], "an older bridge: no rows"
print("PASS badge: rows parsed and clamped, short countdowns")

# ---------------------------------------------------------------- install.py --add-account
ihome = tempfile.mkdtemp()


def install(*args):
    r = subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "install.py")] + list(args),
                       env=dict(os.environ, BURN_HELPER_HOME=ihome, SHELL="/bin/zsh"), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


out = install("--add-account", "lexco", "--dry-run")
assert not os.path.exists(os.path.join(ihome, ".claude-lexco")), "a dry run changes nothing"
out = install("--add-account", "lexco")
with open(os.path.join(ihome, ".claude-lexco", "settings.json")) as f:
    s = json.load(f)
assert s["env"] == {"BURN_HELPER_LABEL": "LEXCO"} and "cc_statusline.py" in s["statusLine"]["command"], s
assert all(e in s["hooks"] for e in ("Stop", "PostToolUse")), s["hooks"].keys()
assert not os.path.exists(os.path.join(ihome, ".claude", "settings.json")), "~/.claude is left alone"
assert "LaunchAgents" not in out and "launchctl" not in out, "no second bridge"
rc = [p for p in (".zshrc", ".bashrc") if os.path.exists(os.path.join(ihome, p))]
if rc:      # a Mac or Linux: the alias went into the shell's start-up file, once
    install("--add-account", "lexco")
    with open(os.path.join(ihome, rc[0])) as f:
        text = f.read()
    assert text.count("alias claude-lexco=") == 1 and "CLAUDE_CONFIG_DIR=" in text, text
else:       # Windows: the line for the PowerShell profile is printed
    assert "function claude-lexco" in out and "$PROFILE" in out, out
import install as I  # noqa: E402
I.WINDOWS, I.MAC, I.HOME = False, True, tempfile.mkdtemp()     # the Mac's way, from any computer
assert "Added the alias claude-lexco" in I.add_alias("lexco") and "already" in I.add_alias("lexco")
with open(os.path.join(I.HOME, ".zshrc")) as f:
    assert f.read().count("""alias claude-lexco='CLAUDE_CONFIG_DIR="$HOME/.claude-lexco" claude'""") == 1
out = install("--add-account", "lexco", "--uninstall")
with open(os.path.join(ihome, ".claude-lexco", "settings.json")) as f:
    assert json.load(f) == {}, "uninstall takes ours out of that folder"
r = subprocess.run([sys.executable, os.path.join(BRIDGE_DIR, "install.py"), "--add-account", "../x"],
                   env=dict(os.environ, BURN_HELPER_HOME=ihome), capture_output=True, text=True)
assert r.returncode != 0, "a name that isn't a plain word is refused"
print("PASS install --add-account: its own folder, hooks, status line and label, the alias once, "
      "clean uninstall")
