"""Weekly-reset ladder for the chocolates (Forrest) theme -> tools/sim/out/proto/reset_chocolates_*.png

    python3 tools/sim/proto_reset_chocolates.py [--review]

Renders each stage of the ladder from the badge's own theme (badge/apps/burn_helper/theme_chocolates.py):
the week is a box of chocolates; the closer the weekly quota reset gets, the louder it is, from the
top-bar clock changing to Jenny running across the field with the count over her, then a fresh box.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator first)
import proto_reset as R  # noqa: E402
import theme_chocolates as C  # noqa: E402

BASE_T = 40000                     # the HUD's 2 s alternation lines up with the frames from here

TITLES = {
    "six": ("The clock changes", "Every few seconds the top-bar clock shows the weekly countdown instead of the 5-hour one, marked with a gift box and a gold frame round the weekly road."),
    "hour": ("The road pulses", "The caption carries the weekly countdown and the weekly road throbs with a gold edge."),
    "ten": ("The bus comes", "A bus pulls up at the bench with a bubble: \"NEW BOX IN 9:20\", and an orange frame pulses round the scene."),
    "minute": ("Jenny runs", "Slow motion: Jenny runs across the field toward him with the count over her, milliseconds ticking."),
    "ten_s": ("Ten seconds", "Huge flashing numbers on the field, a white flash on every second, Jenny almost there."),
    "zero": ("A new box", "A fresh box drops into his hands, \"LIFE IS LIKE A BOX OF CHOCOLATES\", the chocolates in the top bar and the weekly road refill, sparkles."),
}
NOTES = {
    "six": "No new images: a gift icon drawn from boxes. The clock swaps every 2 s, also in the hour and ten stages.",
    "hour": "No new images. The caption holds; it gives way to an activity caption while one plays, and to the waiting bar.",
    "ten": "No new images: the bus is boxes and two circles. Cuts to the bench for 1.5 s at every whole minute; waits while a session is waiting or an activity plays.",
    "minute": "Jenny's run: 4 frames of 28x30 (about 13 KB with Forrest's open-armed pose), built once. The ghost of her last step needs screen.alpha and is skipped without it.",
    "ten_s": "Two 24x24 scratch images for the big digit (drop shadow, redrawn when the second or flash changes); a full-screen flash every second.",
    "zero": "The new box drop is the 5-hour refill animation. The chocolates and the weekly road fill up for the celebration, then show their true level again.",
}


# ------------------------------------------------------------ render the frames
SPECIAL_LEFTS = {"ten_s": (6.12, 5.94, 5.12, 4.95),       # the build-up, a flash, the build-up, a flash
                 "ten": (9 * 60 + 59.85, 9 * 60 + 59.40, 9 * 60 + 58.90, 9 * 60 + 58.60),   # a bus pulling up
                 "zero": (-0.3, -1.2, -2.2, -3.2)}             # through the 4 seconds


def main():
    import pvshim
    items, sheets = [], []
    for key, label, left_us, spread in R.STAGES:
        if key == "day":
            continue                                           # dropped: the approved ladder starts at 6 hours
        th = C.Theme()
        frames, imgs = [], []
        for i in range(R.FRAMES):
            st = R.status(left_us)
            left = left_us - i * spread * 1000
            if key in SPECIAL_LEFTS:
                left = int(SPECIAL_LEFTS[key][i] * 1000000)
            st.left7 = left
            if key == "zero":
                st.hearts = 9
                st.week = 0.35
            t = BASE_T + i * spread
            if key == "ten_s":
                t = BASE_T + int(1000 * (SPECIAL_LEFTS[key][0] - SPECIAL_LEFTS[key][i]))
            elif key in ("ten", "zero"):
                t = BASE_T + int(1000 * abs(SPECIAL_LEFTS[key][i] - SPECIAL_LEFTS[key][0]))
            th.last_t = None
            scr = P.render(th, st, t)
            name = R.out_name("chocolates", key, i)
            scr.to_png(os.path.join(P.OUT, name), 1)
            frames.append(name)
            copy = pvshim.image(160, 120)
            copy.blit(scr, pvshim.vec2(0, 0))
            imgs.append(copy)
        title, desc = TITLES[key]
        items.append({"key": key, "title": title, "desc": desc, "left": label, "frames": frames,
                      "notes": NOTES[key]})
        sheets.append((key, imgs))
    print(R.write_manifest("chocolates", items))
    if "--review" in sys.argv:
        scale, pad = 2, 4
        for k in range(0, len(sheets), 4):
            group = sheets[k:k + 4]
            big = pvshim.image(4 * (160 * scale + pad) + pad, len(group) * (120 * scale + pad) + pad)
            big.pen = pvshim.color(40, 40, 48)
            big.clear()
            for r, (key, imgs) in enumerate(group):
                for c, img in enumerate(imgs):
                    big.blit(img, pvshim.rect(pad + c * (160 * scale + pad), pad + r * (120 * scale + pad),
                                              160 * scale, 120 * scale))
            path = os.path.join(P.OUT, "reset_chocolates_review_%d.png" % (k // 4))
            big.to_png(path, 1)
            print(path)


if __name__ == "__main__":
    main()
