"""Two-colour badge_stand: classic pixel Zelda heart meter inlaid in front lip.

10 heart containers: 7 full, 1 half, 2 empty (outline only) -> 7.5 / 10.
Hearts are a flush inlay, so the model splits into two parts:
  badge_stand_2colors_body.stl    base colour
  badge_stand_2colors_hearts.stl  heart colour (red)

Run:  python badge_stand_2colors.py
"""
import numpy as np
from manifold3d import Manifold, OpType

import badge_stand as bs

FULL, HALF, EMPTY = 7, 1, 2
PIXEL = 1.05     # mm per sprite pixel (heart = 7 x 6 px)
INLAY = 0.8      # inlay depth into lip face
EPS = 0.05       # pixel overgrow so diagonal-only neighbours fuse (manifold)

# classic NES-style heart, row 0 = top
FILLED = [
    ".XX.XX.",
    "XXXXXXX",
    "XXXXXXX",
    ".XXXXX.",
    "..XXX..",
    "...X...",
]
OUTLINE = [
    ".XX.XX.",
    "X..X..X",
    "X.....X",
    ".X...X.",
    "..X.X..",
    "...X...",
]
# half heart: left half (cols 0-3) filled, right half outline
HALFH = [f[:4] + o[4:] for f, o in zip(FILLED, OUTLINE)]


def heart_pixels(sprite, x_left, z_top):
    """Boxes for one sprite on the lip front face (cradle local frame)."""
    y0 = -bs.LIP_T - 1.0          # start outside face; trimmed by model later
    y1 = -bs.LIP_T + INLAY
    out = []
    for r, row in enumerate(sprite):
        for c, ch in enumerate(row):
            if ch == "X":
                x = x_left + c * PIXEL
                z = z_top - (r + 1) * PIXEL
                out.append(bs.box(x - EPS, y0, z - EPS, x + PIXEL + EPS, y1, z + PIXEL + EPS))
    return out


def build_hearts():
    sprites = [FILLED] * FULL + [HALFH] * HALF + [OUTLINE] * EMPTY
    n = len(sprites)
    hw, hh = 7 * PIXEL, 6 * PIXEL
    x0, x1 = -bs.SIDE_T, bs.W + bs.SIDE_T
    margin = bs.CHAMFER + 1.5
    span = (x1 - x0) - 2 * margin
    gap = (span - n * hw) / (n - 1)
    assert gap > 0.8, f"hearts too wide: gap={gap:.2f}"
    # vertically centred on flat part of lip face (floor top .. under top chamfer)
    z_mid = (0 + bs.LIP_H - bs.CHAMFER) / 2
    z_top = z_mid + hh / 2
    boxes = []
    for i, sp in enumerate(sprites):
        boxes += heart_pixels(sp, x0 + margin + i * (hw + gap), z_top)
    return bs.place(Manifold.batch_boolean(boxes, OpType.Add)), gap


def render(parts, path):
    """Front view (2D projection) + zoom on hearts. Inlay is flush, so draw
    heart part last on top instead of relying on mpl 3D depth sort."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})
    for ax, zoom in zip(axes, [False, True]):
        for v, t, col in parts:
            ax.add_collection(PolyCollection(v[t][:, :, [0, 2]], facecolor=col, edgecolor=col, linewidth=0.2))
        ax.set_aspect("equal"); ax.autoscale_view()
        if zoom:
            vh = parts[-1][0]
            ax.set_xlim(vh[:, 0].min() - 2, vh[:, 0].max() + 2); ax.set_ylim(vh[:, 2].min() - 2, vh[:, 2].max() + 2)
        ax.set_axis_off()
    plt.tight_layout(); plt.savefig(path, dpi=120)


if __name__ == "__main__":
    model = bs.build()
    hearts_raw, gap = build_hearts()
    hearts = hearts_raw ^ model
    body = model - hearts
    vb, tb = bs.write_stl(body, "badge_stand_2colors_body.stl")
    vh, th = bs.write_stl(hearts, "badge_stand_2colors_hearts.stl")
    print(f"gap={gap:.2f}mm body: tris={len(tb)} genus={body.genus()} vol={body.volume():.0f}")
    print(f"hearts: tris={len(th)} vol={hearts.volume():.1f} parts={len(hearts.decompose())}")
    render([(vb, tb, "#e8e2d0"), (vh, th, "#d01818")], "badge_stand_2colors.png")
