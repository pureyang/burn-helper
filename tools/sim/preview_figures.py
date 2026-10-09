import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
harness.install()
import figure as F, gfx
from pvshim import image, color, rect, vec2

pal = gfx.palette({F.OUT:(20,16,24), F.SKIN:(248,190,140), F.SKIN_D:(200,140,100), F.HAIR:(80,50,30),
    F.TOP:(240,210,40), F.TOP_D:(190,160,20), F.BOT:(240,210,40), F.BOT_D:(190,160,20), F.SHOE:(60,60,70),
    F.EYE:(20,16,24), F.ACC1:(200,30,40), F.ACC2:(140,20,30), F.WHITE:(255,255,255)})
spec = F.Spec(torso=7, torso_w=5)
frames = []
frames.append(F.render(spec, F.stand()))
frames.append(F.render(spec, F.lying()))
frames.append(F.render(spec, F.sitting()))
for g in ("walk", "jog", "run", "sprint"):
    frames += F.cycle(spec, g, 8)
sheet = image(8 * 30, 5 * 32)
sheet.pen = color.rgb(90, 120, 160); sheet.clear()
for i, gr in enumerate(frames):
    img = gfx.to_image(gr, pal)
    sheet.blit(img, vec2((i % 8) * 30 + 1, (i // 8) * 32 + 1))
sheet.to_png(os.path.join(os.path.dirname(__file__), 'out', 'figures.png'), 4)
print('ok', len(frames))
