#!/usr/bin/env python3
"""Frames of the hero theme's weekly-reset ladder -> tools/sim/out/proto/reset_hero_*.png

The weekly allowance is the green magic meter under the hearts, so the story is MAGIC coming back:
a magic jar in the HUD, Navi's warning, the Triforce assembling for the last minute, and an
item-get under a glowing Triforce at the reset. The drawing is the badge's own
(badge/apps/burn_helper/theme_hero.py); the approved ladder has no 24-hour stage.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator first)
import proto_reset as R  # noqa: E402
import theme_hero as H  # noqa: E402

M = 1000000
BASE_T = 22000                    # a multiple of 2200, so the six-hour HUD swaps on a known beat
Theme = H.Theme

INFO = {
    "six": ("The weekly clock joins the HUD", "5 h 40 m",
            "The top-right clock swaps between the 5-hour countdown and the weekly one, which gets a blue "
            "magic jar and a \"-MAGIC-\" label instead of \"-LIFE-\", and the meter gets a gold outline.",
            "One 6x7 jar sprite (about 170 bytes). The swap is every 1.1 s; only the second frame shows the weekly clock."),
    "hour": ("The caption carries it, the meter pulses", "48 min",
             "The caption line reads \"MAGIC REFILLS IN 47:58\" ticking every second, the top-right clock swaps "
             "faster, and the magic meter pulses gold.",
             "Draws only. The countdown font is the same as today's."),
    "ten": ("Navi's warning", "8:59",
            "Navi flies in with \"HEY! LISTEN! WEEK ENDS 8:59\" in a two-line bubble, and a gold frame pulses "
            "round the scene. It comes at every whole minute for 1.5 s; the caption and the blinking clock carry "
            "the countdown in between.",
            "Reuses the fairy sprite. A waiting session's bar and an activity animation take priority over it."),
    "minute": ("The Triforce builds", "58 s to 41 s",
               "The scene dims, \"THE WEEK'S MAGIC RETURNS IN\" and a big ticking count (seconds and milliseconds) "
               "sit above a Triforce that lights piece by piece (at 60, 55 and 48 s), then glows and sparkles.",
               "Three filled triangles drawn with the same calls as the theme's shapes. Frames here are spread "
               "over the minute (58, 53, 47, 41 s) to show it building."),
    "ten_s": ("Ten, nine, eight...", "6 s",
              "Huge digits, one per second, alternating gold and white, with a white flash on every tick and a "
              "thick pulsing frame. The orange tint says urgency; the words say what for.",
              "20 small digit images (13x24, built once) shown at 2x for the whole-number second. Flash frame is "
              "the second one."),
    "zero": ("Magic restored", "0",
             "A white flash, then the hero lifts a glowing Triforce in the item-get pose with sparkles and a "
             "\"WEEK RESET!\" banner while the magic meter sweeps to full. The caption says \"MAGIC RESTORED!\".",
             "Reuses the item-get pose already on the badge. About 4 s, then back to the scene."),
}


def main():
    items = []
    for key, label, left_us, spread in R.STAGES:
        if key == "day":
            continue                                   # dropped: the ladder starts at six hours
        title, left_text, desc, notes = INFO[key]
        frames = []
        for i in range(R.FRAMES):
            th = Theme()
            if key == "minute":
                left = [58.2, 53.0, 47.4, 41.38][i] * M          # spread over the minute to show the build
            elif key == "ten":
                left = (539.5 - i * 0.35) * M                     # inside the 1.5 s at the whole minute
            else:
                left = left_us - i * spread * 1000
            st = R.status(left)
            t = BASE_T + i * spread
            scr = P.render(th, st, t)
            name = R.out_name("hero", key, i)
            scr.to_png(os.path.join(P.OUT, name), 1)
            frames.append(name)
        items.append({"key": key, "title": title, "desc": desc, "left": left_text, "frames": frames, "notes": notes})
    print(R.write_manifest("hero", items))


if __name__ == "__main__":
    main()
