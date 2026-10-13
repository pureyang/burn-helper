#!/usr/bin/env python3
"""Frames of the game show theme's one-shot activity animations.

    python3 tools/sim/proto_gameshow.py     -> tools/sim/out/proto/gameshow_*.png + gameshow.json

While an action plays (about 1.6-2.4 s) it takes over the runner and may draw an overlay card,
then the normal animation resumes. The drawing is the badge's own
(badge/apps/burn_helper/theme_gameshow.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator first)
import scene as S  # noqa: E402
import theme_gameshow as G  # noqa: E402

# The animations now live in the badge's theme_gameshow.py; this renders their frames for the page.
Theme = G.Theme
DUR = G.ACTIONS

# frame times (fraction of the action) worth showing for each one
SHOTS = {
    "edit": (0.14, 0.4, 0.58, 0.86),
    "read": (0.15, 0.4, 0.62, 0.9),
    "shell": (0.1, 0.32, 0.5, 0.75),
    "web": (0.12, 0.38, 0.62, 0.9),
    "spawn": (0.15, 0.38, 0.58, 0.8),
    "fail": (0.1, 0.27, 0.5, 0.82),
    "done": (0.12, 0.38, 0.62, 0.88),
    "prompt": (0.1, 0.35, 0.6, 0.9),
    "arrive": (0.12, 0.45, 0.65, 0.92),
    "refill": (0.08, 0.35, 0.65, 0.95),
}

TITLES = {
    "edit": ("Counterattack",
             "A stalker charges in with his stick. The runner ducks the swing, lands a kick and a punch, "
             "and leaves him seeing stars."),
    "read": ("Searchlight sweep",
             "The searchlights swing over and meet on a crate. The runner crouches behind it and peeks out "
             "until they move on."),
    "shell": ("Barrel blast",
              "A fizzing barrel goes up behind the runner and the blast throws him forward. "
              "Bigger commands could mean bigger booms."),
    "web": ("Drone cam",
            "A camera drone swoops down, frames the runner with a LIVE tag for a second, and flies off."),
    "spawn": ("Tag team",
              "A second runner in a cyan suit catches up, they high-five, and it sprints ahead on its own errand. "
              "When the subagent finishes it would jog back in from the right."),
    "fail": ("Zapped",
             "A bolt hits the runner: he lights up, the scene flashes orange and a bubble says ZAP!, "
             "then he shakes it off in a puff of smoke."),
    "done": ("Applause",
             "The APPLAUSE sign lights up, confetti falls, the runner throws both arms up and a +1 floats away."),
    "prompt": ("The host",
               "The host pops into a picture-in-picture box with his mic and announces the next round."),
    "arrive": ("New contestant",
               "The lights drop, a spotlight finds the runner, and a lower-third card introduces him."),
    "refill": ("Commercial break",
               "Colour bars and a COMMERCIAL BREAK card cover the scene while the collar lights charge back "
               "up, then the show resumes."),
}

NOTES = {
    "edit": "4 new poses (duck, kick, punch) and 3 stalker poses, about 2 KB of images. "
            "Needs a per-tool event from the bridge (an edit counter or event feed).",
    "read": "One new crouch pose; the crate and the locked beams are plain rectangles and triangles. "
            "Needs the Read/Grep/Glob event.",
    "shell": "One leap pose; the barrel and fireball reuse the explosion drawing. Needs the Bash event.",
    "web": "A 11x7 drone sprite. Needs the WebFetch/WebSearch event.",
    "spawn": "A recoloured copy of the run cycle (8 frames, about 4 KB) plus a high-five pose. "
             "The bridge already counts SubagentStart/SubagentStop; it needs to send them as events.",
    "fail": "Two jolt images (normal and lit). Needs PostToolUseFailure forwarded as an event "
            "(the hook already fires for it). Orange flash plus the ZAP! word, never red vs green.",
    "done": "Two cheer poses; confetti is drawn per frame. Needs Stop forwarded as an event.",
    "prompt": "A host figure (2 frames, mouth open and shut). Needs UserPromptSubmit as an event.",
    "arrive": "No new sprites beyond one pose. Needs SessionStart as an event.",
    "refill": "No new sprites. Worked out on the badge when the 5-hour window resets; no bridge change.",
}


def main():
    items = []
    base_t = 5000
    for key in P.KEYS:
        th = Theme()
        th.action = key
        th.action_t0 = base_t
        th.refill_from = 4
        st = P.status(level=S.WALK, agents=3, hearts=4 if key == "refill" else 14)
        frames = []
        for i, f in enumerate(SHOTS[key]):
            t = base_t + int(f * DUR[key])
            th.last_t = None
            th.scroll = 600.0
            scr = P.render(th, st, t)
            frames.append(P.save(scr, "gameshow", key, i))
        title, desc = TITLES[key]
        items.append({"key": key, "title": title, "desc": desc, "frames": frames, "notes": NOTES[key]})
    print(P.write_manifest("gameshow", items))


if __name__ == "__main__":
    main()
