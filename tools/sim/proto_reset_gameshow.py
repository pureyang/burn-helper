#!/usr/bin/env python3
"""The weekly-reset ladder for the game show theme -> tools/sim/out/proto/reset_gameshow_*.png

The week is the SEASON: when the weekly quota resets, a new season of the game starts. The nearer
the reset, the louder the show gets about it. The drawing is the badge's own
(badge/apps/burn_helper/theme_gameshow.py, S.week_stage); this renders its frames for the page.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_reset as R  # noqa: E402  (installs the simulator)
import proto_common as P  # noqa: E402
import scene as S  # noqa: E402
import theme_gameshow as G  # noqa: E402

BASE_T = 44000                    # a multiple of 2200 ms, so the "six" stage starts on the 5-hour clock

TITLES = {
    "six": ("Second clock", "5 h 40 min"),
    "hour": ("The caption takes over", "48 min"),
    "ten": ("The host cuts in", "9 min, at each whole minute"),
    "minute": ("Studio countdown board", "41 s"),
    "ten_s": ("Flashing numbers", "6 s"),
    "zero": ("New season", "0"),
}
DESC = {
    "six": "The game clock in the corner takes turns between the 5-hour recharge and a pink RESET clock "
           "counting to the weekly reset.",
    "hour": "The caption is the countdown now, the weekly strip pulses, the logo gives way to SEASON FINALE "
            "every other turn, and the searchlights sweep even when the runner is only jogging.",
    "ten": "At every whole minute of the last ten, the host slides in for a second and a half with the time "
           "left, and a pink frame pulses round the scene. The pink RESET clock stays up in the corner.",
    "minute": "A studio board fills the screen: ON AIR IN, big digits ticking in milliseconds, and the "
              "audience sign flashing.",
    "ten_s": "The digits flash yellow and white and the whole screen takes a white flash on every second.",
    "zero": "A NEW SEASON title card, confetti, and the collar lights and weekly strip fill back up. "
            "It lasts 4 seconds.",
}
NOTES = {
    "six": "No new sprites. Takes over the clock box for 2.2 s in every 4.4 s.",
    "hour": "No new sprites. The searchlights are drawn at every level in this stage, so a walking runner "
            "gets them too. The pulsing strip is one meter drawn thicker.",
    "ten": "Reuses the host sprites from the prompt animation, so no new images. The frames show the "
           "interstitial; in between it is just the HUD and the caption.",
    "minute": "No sprites: boxes, text and the badge's biggest font. A few filled boxes a frame. Waits while "
              "a session is waiting for you or an activity plays.",
    "ten_s": "Full-screen white flash is one translucent rectangle. Waits like the board does.",
    "zero": "About 36 confetti boxes per frame, like the applause animation.",
}
# the 'ten' interstitial shows in the 1.5 s before each whole minute of what is left
TEN_LEFT = 8 * 60 * R.M + 59 * R.M + 900000


def main():
    items = []
    for key, label, left, spread in R.STAGES:
        if key == "day":
            continue                      # dropped: no quiet 24-hour notice
        th = G.Theme()
        frames = []
        for i in range(R.FRAMES):
            if key == "ten":
                us = TEN_LEFT - i * 350 * 1000         # inside the interstitial's 1.5 s window
            elif key == "zero":
                us = -(250 + i * 900) * 1000           # through the 4-second celebration
            else:
                us = left - i * spread * 1000
            st = R.status(us)
            st.hearts = 9
            th.last_t = None
            th.last_hearts = 9
            scr = P.render(th, st, BASE_T + 150 + i * spread)
            name = R.out_name("gameshow", key, i)
            scr.to_png(os.path.join(P.OUT, name), 1)
            frames.append(name)
        title, lft = TITLES[key]
        items.append({"key": key, "title": title, "desc": DESC[key], "left": lft, "frames": frames,
                      "notes": NOTES[key]})
    print(R.write_manifest("gameshow", items))


if __name__ == "__main__":
    os.makedirs(P.OUT, exist_ok=True)
    main()
