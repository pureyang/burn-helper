#!/usr/bin/env python3
"""Frames of the chocolates (Forrest) theme's one-shot activity animations.

    python3 tools/sim/proto_chocolates.py    -> tools/sim/out/proto/chocolates_*.png + chocolates.json

Each activity plays once (1.4-2.8 s) over the run, then the normal animation resumes.
He keeps jogging through most of them; "done", "prompt" and "arrive" stop him for a moment.
The drawing is the badge's own (badge/apps/burn_helper/theme_chocolates.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the picovector stand-ins)
import scene as S  # noqa: E402
import theme_chocolates as C  # noqa: E402

Theme = C.Theme
DUR = C.ACTIONS


# ---------------------------------------------------------------- render the frames
BASE_T = 5200
SHOTS = (
    # key, frame phases, status overrides
    ("edit", (0.22, 0.4, 0.62, 0.76), {}),
    ("read", (0.12, 0.35, 0.65, 0.9), {}),
    ("shell", (0.15, 0.45, 0.6, 0.8), {}),
    ("web", (0.12, 0.35, 0.65, 0.8), {}),
    ("spawn", (0.12, 0.3, 0.6, 0.9), {}),
    ("fail", (0.12, 0.27, 0.38, 0.7), {}),
    ("done", (0.15, 0.45, 0.7, 0.9), {}),
    ("prompt", (0.12, 0.25, 0.4, 0.8), {}),
    ("arrive", (0.05, 0.4, 0.72, 0.9), {}),
    ("refill", (0.1, 0.25, 0.55, 0.9), {"hearts": 20}),
)

TEXT = {
    "edit": ("Ping-pong rally",
             "He pulls out a paddle and rallies off a half-folded practice table, a few hits per edit.",
             "8 extra figure frames (2 arm poses x 4 strides) per gait, the table is 8 rectangles. "
             "Bridge: send the tool category of each PostToolUse."),
    "read": ("Box of chocolates",
             "He opens the box while jogging and tries one. You never know what you're gonna get.",
             "12 extra figure frames (3 arm poses x 4 strides) per gait; the box is drawn into the figure."),
    "shell": ("Shrimp net",
              "A quick swing of a shrimp net, and a shrimp flips out over his head.",
              "8 extra figure frames per gait plus a 7x5 shrimp sprite."),
    "web": ("Reporters",
            "A reporter and a cameraman run alongside. \"WHY ARE YOU RUNNING?\" \"I JUST FELT LIKE RUNNING.\"",
            "8 small press frames (2 figures x 4 strides, 1x like the crowd), mic and camera drawn into "
            "them. Bridge: send the tool category of each PostToolUse (WebFetch, WebSearch)."),
    "spawn": ("A new follower",
              "A new runner jogs in from the left and falls in behind him. When the subagent finishes it "
              "says DONE and peels off (last frame).",
              "Reuses the crowd frames. Bridge: SubagentStart and SubagentStop are already counted; the "
              "badge needs the events themselves (or the change in the subagent count)."),
    "fail": ("Shot in the buttocks",
             "Something zings in from behind and gets him in the buttocks. He jumps, grabs his behind and "
             "runs on holding it: \"SOMETHING BIT ME!\"",
             "8 extra figure frames (2 arm poses x 4 strides) per gait; the zing and the hit are lines. OW! is in "
             "vermillion with a white outline, so it reads without colour too. Bridge: PostToolUseFailure "
             "is already hooked."),
    "done": ("Turns around at the ocean",
             "The road runs out at the ocean. He stops, looks at it (\"MIGHT AS WELL TURN AROUND.\") and runs "
             "back the way he came: the end of a turn.",
             "One standing frame; the beach and sea are rectangles, the run back is the jog flipped. The road "
             "stops scrolling while he stands. Bridge: send Stop as an event."),
    "prompt": ("Drill sergeant",
               "A drill sergeant leans in from the left and barks \"GUMP!\". He stops dead and salutes: \"YES, "
               "DRILL SERGEANT!\"",
               "Two standing frames (the salute and the sergeant); the campaign hat is a triangle and two boxes. "
               "Bridge: UserPromptSubmit is already hooked."),
    "arrive": ("Bus-stop bench",
               "A quick cut to the bench: he sits, says hello, stands up and runs off, then back to the road.",
               "Reuses the theme's park scene and sitting and standing frames, so nothing new. Bridge: "
               "SessionStart as an event."),
    "refill": ("New box of chocolates",
               "A full box drops into his hands and the chocolates in the top bar fill back up one by one.",
               "Shares the box pose with read. Worked out on the badge when the "
               "5-hour reset time passes, so no bridge change."),
}


def review_sheets(shots, per=3, scale=2):
    """Contact sheets of the rendered frames (3 activities each) for checking by eye."""
    import pvshim
    names = []
    for k in range(0, len(shots), per):
        group = shots[k:k + per]
        tw, th, pad = 160 * scale, 120 * scale, 4
        big = pvshim.image(4 * (tw + pad) + pad, len(group) * (th + pad) + pad)
        big.pen = pvshim.color(40, 40, 48)
        big.clear()
        for r, (key, imgs) in enumerate(group):
            for c, img in enumerate(imgs):
                big.blit(img, pvshim.rect(pad + c * (tw + pad), pad + r * (th + pad), tw, th))
        name = os.path.join(P.OUT, "chocolates_review_%d.png" % (k // per))
        big.to_png(name, 1)
        names.append(name)
    return names


def main():
    import pvshim
    items = []
    shots = []
    for key, phases, over in SHOTS:
        th = Theme()
        kw = dict(level=S.WALK, agents=3, hearts=12)
        kw.update(over)
        level = kw.pop("level")
        st = P.status(**kw)
        if level != st.level:
            st.level = level
        frames = []
        imgs = []
        for i, p in enumerate(phases):
            act = key
            t = BASE_T + int(p * DUR[key])
            if key == "spawn" and i == 3:          # the last frame shows it coming back
                act = "back"
                t = BASE_T + int(0.3 * DUR["back"])
            th.action = act
            th.action_t0 = BASE_T
            th.refill_from = 4
            th.last_t = None
            scr = P.render(th, st, t)              # warm-up frames come before BASE_T: the action waits
            frames.append(P.save(scr, "chocolates", key, i))
            copy = pvshim.image(160, 120)
            copy.blit(scr, pvshim.vec2(0, 0))
            imgs.append(copy)
        shots.append((key, imgs))
        title, desc, notes = TEXT[key]
        items.append({"key": key, "title": title, "desc": desc, "frames": frames, "notes": notes})
    print(P.write_manifest("chocolates", items))
    if "--review" in sys.argv:
        print(review_sheets(shots))
    for it in items:
        print(it["key"], it["frames"])


if __name__ == "__main__":
    main()
