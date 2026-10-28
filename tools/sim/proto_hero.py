#!/usr/bin/env python3
"""Frames of the hero theme's one-shot activity animations -> tools/sim/out/proto/hero_*.png

Each activity plays once (1-2 s) over whatever the hero is doing, then the normal animation
resumes. Tool calls are fights and items; the rest are story beats. The drawing is the badge's
own (badge/apps/burn_helper/theme_hero.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator first)
import scene as S  # noqa: E402
import theme_hero as H  # noqa: E402

# The animations now live in the badge's theme_hero.py; this renders their frames for the page.
Theme = H.Theme
DUR = H.ACTIONS


ITEMS = [
    ("edit", "Sword combo",
     "A slime slides in and the hero takes it apart: a thrust, a low stab, a rising slash, then it pops into "
     "smoke and drops a rupee.",
     "4 new poses (about 1.5 KB of sprites); the slime, slash arc and smoke are drawn shapes. The bridge must "
     "say which tool ran (edit vs read vs shell vs web), e.g. a small recent-events list in /status."),
    ("read", "Lens of truth",
     "The hero stops and holds up a lens. Its light sweeps the path and a hidden rupee fades in.",
     "1 pose; the light cone is one translucent triangle. Needs image alpha for the fade-in, or just pop it in."),
    ("shell", "Bomb",
     "Crouches to set down a blue bomb, steps back behind the shield while the fuse fizzes, then boom.",
     "2 poses; the bomb, blast rings, smoke and debris are shapes. A short shake of the scene would sell it."),
    ("web", "Hookshot",
     "Fires a chain to the edge of the screen and reels back a page from the web.",
     "1 pose plus a tiny page sprite; the chain is a row of 2-pixel boxes."),
    ("spawn", "Boomerang out and back",
     "Throws the boomerang (the HUD's agent icon) and it arcs off screen when a subagent starts. It flies back "
     "into the hero's hand when the subagent finishes.",
     "Reuses the HUD boomerang plus one rotated copy, 2 poses. Two halves: SubagentStart and SubagentStop, which "
     "the bridge already counts but would need to pass on as events."),
    ("fail", "Knocked back",
     "Something hits the hero: it hops back, flashing vermillion, and says OUCH! The hearts don't change, since "
     "a failed tool call costs nothing.",
     "1 pose in 2 palettes (normal and flash). Needs PostToolUseFailure passed on as an event. The word, not just "
     "the color, carries the meaning."),
    ("done", "Item get",
     "When a turn finishes the hero lifts a treasure chest overhead with both hands, with light rays and gold "
     "and blue sparkles. Caption: QUEST COMPLETE!",
     "1 pose and a 10x8 chest sprite. Stop happens once per turn, so this is rare enough to be a treat."),
    ("prompt", "New quest",
     "When you send a prompt a \"!\" pops over the hero's head and a scroll drops in. The hero catches it and "
     "reads it.",
     "2 poses and a small scroll sprite. UserPromptSubmit is already a hook event; it just needs passing on."),
    ("arrive", "Out of the cave",
     "A new session starts: a cave door appears on the left and the hero walks out of the dark into the field.",
     "The cave is a few circles and boxes; the walk reuses the gait. Plays at most once per new session."),
    ("refill", "Heart container",
     "When the 5-hour limit resets, a big heart floats down to the hero and the hearts fill back up one by one. "
     "Caption: HEARTS REFILLED!",
     "No bridge change: the badge already knows the reset time. Reuses the heart sprites."),
]

PHASES = (0.1, 0.35, 0.6, 0.85)
CUSTOM = {"edit": (0.15, 0.42, 0.66, 0.84), "shell": (0.12, 0.45, 0.68, 0.86),
          "spawn": (0.08, 0.22, 0.7, 0.93), "fail": (0.12, 0.3, 0.5, 0.8), "done": (0.08, 0.3, 0.55, 0.85),
          "arrive": (0.05, 0.3, 0.55, 0.85)}
BASE_T = 5000


def main():
    items = []
    for key, title, desc, notes in ITEMS:
        frames = []
        for i, ph in enumerate(CUSTOM.get(key, PHASES)):
            theme = Theme()
            if key == "refill":
                st = P.status(level=S.WALK, agents=3, hearts=3)
                theme.refill_from = 3
            elif key in ("arrive",):
                st = P.status(level=S.WALK, agents=1)
            else:
                st = P.status(level=S.WALK, agents=3)
            theme.action = key
            theme.action_t0 = BASE_T
            t = BASE_T + int(ph * DUR[key])
            scr = P.render(theme, st, t)
            frames.append(P.save(scr, "hero", key, i))
        items.append({"key": key, "title": title, "desc": desc, "frames": frames, "notes": notes})
    print(P.write_manifest("hero", items))


if __name__ == "__main__":
    main()
