#!/usr/bin/env python3
"""Generate badge/apps/hearts_left/icon.png (24x24, transparent) for the stock launcher."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sim"))
import harness
harness.install()
import pvshim, figure as F, gfx, theme_hero as Z
g = F.render(Z.SPEC, F.stand(prop="shield"))
img = gfx.to_image(g, gfx.palette(Z.HERO))
icon = pvshim.image(24, 24)
# crop the figure's bounding box into the icon, centred
xs = [x for y in range(g.h) for x in range(g.w) if g.get(x, y)]
ys = [y for y in range(g.h) for x in range(g.w) if g.get(x, y)]
x0, y0 = min(xs), min(ys)
w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
icon.blit(img, pvshim.rect(x0, y0, w, h), pvshim.rect((24 - w) // 2, (24 - h) // 2, w, h))
out = os.path.join(harness.APP, "icon.png")
icon.to_png(out, 1, alpha=True)
print(out, w, h)
