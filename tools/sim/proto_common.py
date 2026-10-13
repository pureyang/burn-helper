"""Shared pieces for prototyping the proposed agent-activity animations in the simulator.

Each theme has a tools/sim/proto_<theme>.py that subclasses the real theme, adds the
proposed one-shot animations, renders a few frames of each to tools/sim/out/proto/, and
writes a manifest (tools/sim/out/proto/<theme>.json) that the proposal page is built from.
Nothing here runs on the badge yet; the drawing uses the same picovector calls and
figure.py, so whatever is picked can move into the theme modules as is.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402

harness.install()
import pvshim  # noqa: E402
import scene  # noqa: E402

OUT = os.path.join(HERE, "out", "proto")
M = 1000000

# The activities the bridge can tell apart from Claude Code's hooks. `trigger` is what fires it.
# Each plays once (about 1-2 s) over whatever the character is already doing, then the
# normal animation resumes.
ACTIVITIES = (
    ("edit", "Edits a file", "PostToolUse: Edit, Write, MultiEdit, NotebookEdit"),
    ("read", "Reads or searches", "PostToolUse: Read, Grep, Glob, LS"),
    ("shell", "Runs a command", "PostToolUse: Bash"),
    ("web", "Goes on the web", "PostToolUse: WebFetch, WebSearch"),
    ("spawn", "Sends out a subagent", "SubagentStart (and SubagentStop when it comes back)"),
    ("fail", "A tool call fails", "PostToolUseFailure"),
    ("done", "Finishes its turn", "Stop"),
    ("prompt", "You send a prompt", "UserPromptSubmit"),
    ("arrive", "A session starts", "SessionStart"),
    ("refill", "Usage limit resets", "the 5-hour window resets (worked out on the badge, no bridge change)"),
)
KEYS = [a[0] for a in ACTIVITIES]


def status(level=scene.WALK, agents=3, hearts=14, week=0.6, waiting=0, tools=402, tpm=18):
    st = scene.Status()
    st.online = True
    st.net = ""
    st.level = level
    st.busy = agents
    st.subagents = 0
    st.set_agents(agents)
    st.hearts = hearts
    st.week = week
    st.waiting = waiting
    st.tools = tools
    st.tpm = tpm
    st.sessions = agents + waiting + 1
    st.left5 = (65 * 60) * M
    st.left7 = (3 * 86400) * M
    return st


def render(theme, st, t, warm=True):
    """One frame at time t (ms), as the badge would draw it. Returns the screen image."""
    if warm:
        for k in range(6, 0, -1):
            harness.new_screen()
            theme.draw(st, t - k * 50)
    scr = harness.new_screen()
    scr.pen = pvshim.color(0, 0, 0)
    scr.clear()
    theme.draw(st, t)
    return scr


def save(scr, theme_name, key, i):
    os.makedirs(OUT, exist_ok=True)
    name = "%s_%s_%d.png" % (theme_name, key, i)
    scr.to_png(os.path.join(OUT, name), 1)
    return name


def write_manifest(theme_name, items):
    """items: [{key, title, desc, frames: [file names], notes}] in ACTIVITIES order."""
    os.makedirs(OUT, exist_ok=True)
    trig = {k: (label, trigger) for k, label, trigger in ACTIVITIES}
    for it in items:
        it.setdefault("activity", trig[it["key"]][0])
        it.setdefault("trigger", trig[it["key"]][1])
    path = os.path.join(OUT, theme_name + ".json")
    with open(path, "w") as f:
        json.dump(items, f, indent=1)
    return path
