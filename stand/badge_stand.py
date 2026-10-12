"""Desk stand for Pimoroni Tufty 2350 badge (85 W x 76 H x 20 D mm).

Holds badge upright (landscape), leaned back. Equal-height side walls, kept
low so a USB-C plug (port centre 30 mm above badge bottom, left edge) clears.
All convex edges chamfered.

Run:  python badge_stand.py   -> writes badge_stand.stl + badge_stand.png
"""
import struct
import numpy as np
from manifold3d import Manifold

# ---- badge ----
BADGE_W = 85.0   # width (x)
BADGE_H = 76.0   # height
BADGE_D = 20.0   # depth / thickness
TOL = 0.8        # clearance added to slot (per axis total)

# ---- stand ----
TILT = 15.0          # lean-back angle, degrees
RISE = 8.0           # slot floor height above table at front edge
FLOOR_T = 4.0        # slot floor thickness
LIP_H = 9.0          # front lip height (covers buttons 4 mm up; unused when seated)
LIP_T = 3.0          # front lip thickness
BACK_H = 48.0        # back wall height
BACK_T = 4.0         # back wall thickness
USB_Z = 30.0         # USB-C port centre above badge bottom (left edge)
PLUG_HALF = 6.5      # half height of USB-C plug overmold
SIDE_H = USB_Z - PLUG_HALF - 4.0  # both side walls, 4 mm under plug -> 19.5
SIDE_T = 3.0
BASE_T = 3.0         # foot plate thickness
BASE_BACK = 30.0     # foot extension behind back wall (anti-tip)
BASE_FRONT = 6.0     # foot extension in front of lip
WINDOW = True        # cutout in back wall so rear LEDs show
CHAMFER = 1.0        # 45 deg chamfer on all convex edges

W = BADGE_W + TOL
D = BADGE_D + TOL


def box(x0, y0, z0, x1, y1, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def place(m):
    """Cradle local frame -> world: lean back about front-bottom edge, lift to RISE."""
    m = m.translate([0, LIP_T, FLOOR_T]).rotate([-TILT, 0, 0])
    return m.translate([0, 0, RISE - FLOOR_T])


def build():
    # Cradle in local frame: slot floor at z=0, badge in x[0,W], y[0,D].
    x0, x1 = -SIDE_T, W + SIDE_T
    floor = box(x0, -LIP_T, -FLOOR_T, x1, D + BACK_T, 0)
    lip = box(x0, -LIP_T, 0, x1, 0, LIP_H)
    back = box(x0, D, 0, x1, D + BACK_T, BACK_H)
    if WINDOW:
        back = back - box(14, D - 1, 16, W - 14, D + BACK_T + 1, BACK_H - 8)
    side = box(W, -LIP_T, 0, x1, D + BACK_T, SIDE_H)
    left = box(x0, -LIP_T, 0, 0, D + BACK_T, SIDE_H)
    cradle = floor + lip + back + side + left

    cradle = place(cradle)
    floor_t = place(floor)

    # solid pedestal: hull of tilted floor with its footprint on table
    lo, hi = floor_t.bounding_box()[:3], floor_t.bounding_box()[3:]
    footprint = box(lo[0], lo[1], 0, hi[0], hi[1], 0.01)
    pedestal = Manifold.batch_hull([floor_t, footprint])

    # foot plate
    blo, bhi = cradle.bounding_box()[:3], cradle.bounding_box()[3:]
    foot = box(blo[0], -BASE_FRONT, 0, bhi[0], bhi[1] + BASE_BACK, BASE_T)

    model = cradle + pedestal + foot
    # trim anything below table
    model = model ^ box(-500, -500, 0, 500, 500, 500)
    return chamfer(model, CHAMFER)


def chamfer(m, c):
    """Morphological opening with octahedron: bevels convex edges, keeps size."""
    if c <= 0:
        return m
    pts = [[c, 0, 0], [-c, 0, 0], [0, c, 0], [0, -c, 0], [0, 0, c], [0, 0, -c]]
    octa = Manifold.hull_points(pts)
    return m.minkowski_difference(octa).minkowski_sum(octa)


def write_stl(m, path):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    t = np.asarray(mesh.tri_verts)
    with open(path, "wb") as f:
        f.write(b"badge stand".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(t)))
        for a, b, c in t:
            p0, p1, p2 = v[a], v[b], v[c]
            n = np.cross(p1 - p0, p2 - p0)
            ln = np.linalg.norm(n)
            n = n / ln if ln else n
            f.write(struct.pack("<12fH", *n, *p0, *p1, *p2, 0))
    return v, t


def render(v, t, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(12, 6))
    for i, (el, az) in enumerate([(20, -60), (10, -150)]):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(v[t], facecolor="#f08a24", edgecolor="#5a3000", linewidth=0.1))
        lo, hi = v.min(0), v.max(0)
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(0, 2 * r)
        ax.view_init(el, az); ax.set_xlabel("x (USB-C side = low x)")
        ax.set_ylabel("y (back)")
    plt.tight_layout(); plt.savefig(path, dpi=110)


if __name__ == "__main__":
    m = build()
    v, t = write_stl(m, "badge_stand.stl")
    lo, hi = v.min(0), v.max(0)
    print(f"tris={len(t)} size={hi - lo} volume={m.volume():.0f} mm3 genus={m.genus()}")
    render(v, t, "badge_stand.png")
