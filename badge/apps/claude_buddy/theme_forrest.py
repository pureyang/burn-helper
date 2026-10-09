# "Forrest" theme (the surprise): Forrest Gump's run across America.
#   sleep  -> on the Savannah bus-stop bench with a box of chocolates, feather drifting
#   idle   -> standing by the bench, ready to go
#   walk   -> "I just felt like running." jogging down a country road
#   run    -> long hair and beard, Monument Valley highway
#   sprint -> the whole crowd of followers running behind him (one per busy agent)
# Hearts are the 5-hour budget; the road bar is the weekly budget; MILES counts
# today's tool calls. When a session waits for you he shouts "JENNY!".

import math
import figure as F
import gfx
import scene as S

INK = (60, 36, 20)
CREAM = (250, 240, 214)
RED = (206, 32, 40)
WHITE = (255, 255, 255)

BASE = {
    F.OUT: (34, 22, 16), F.SKIN: (246, 196, 150), F.SKIN_D: (204, 150, 108),
    F.HAIR: (122, 78, 40), F.EYE: (34, 22, 16), F.SHOE: (246, 246, 246),
    F.ACC1: (206, 32, 40), F.ACC2: (150, 20, 28), F.ACC3: (110, 64, 30), F.ACC4: (230, 190, 70),
    F.WHITE: (255, 255, 255),
}


def pal(**cols):
    d = dict(BASE)
    d.update(cols)
    return gfx.palette(d)


def _box(g, j, pose):
    if pose.prop == "box":
        hx, hy = j["hand_f"]
        g.rect(int(hx) - 2, int(hy) - 2, 6, 3, F.ACC3)
        g.rect(int(hx) - 2, int(hy) - 3, 6, 1, F.ACC4)


SUIT = F.Spec(torso_w=5, hair="short", forearms=F.TOP, extra=_box)
JOGGER = F.Spec(torso_w=5, hair="short", hat="cap", shins=F.SKIN)
BEARD = F.Spec(torso_w=5, hair="long", hat="cap", beard=True, shins=F.SKIN)
CROWD = F.Spec(torso_w=4, hair="short", shins=F.SKIN)


class Theme(S.Theme):
    name = "forrest"
    label = "FORREST"

    def build(self):
        p_suit = pal()
        p_suit[F.TOP] = gfx.rgb((236, 230, 212))
        p_suit[F.TOP_D] = gfx.rgb((196, 188, 166))
        p_suit[F.BOT] = gfx.rgb((236, 230, 212))
        p_suit[F.BOT_D] = gfx.rgb((196, 188, 166))
        p_suit[F.HAIR] = gfx.rgb((150, 104, 60))
        p_run = pal()
        p_run[F.TOP] = gfx.rgb((236, 106, 40))
        p_run[F.TOP_D] = gfx.rgb((184, 76, 26))
        p_run[F.BOT] = gfx.rgb((40, 60, 140))
        p_run[F.BOT_D] = gfx.rgb((26, 40, 100))

        self.sit = gfx.to_image(F.render(SUIT, F.sitting(prop="box")), p_suit)
        self.sit_blink = gfx.to_image(F.render(SUIT, F.sitting(prop="box", eye=False)), p_suit)
        self.stand = gfx.to_image(F.render(SUIT, F.stand()), p_suit)
        self.wave = gfx.to_image(F.render(SUIT, F.stand(af=(150, 30))), p_suit)
        self.jog = [gfx.to_image(g, p_run) for g in F.cycle(JOGGER, "jog", 8)]
        self.run = [gfx.to_image(g, p_run) for g in F.cycle(BEARD, "run", 8)]
        self.sprint = [gfx.to_image(g, p_run) for g in F.cycle(BEARD, "sprint", 8)]
        self.crowd = []
        shirts = ((70, 150, 220), (240, 200, 60), (120, 190, 90), (220, 120, 160))
        hairs = ((60, 40, 30), (200, 160, 90), (30, 24, 20), (140, 70, 40))
        for i, c in enumerate(shirts):
            p = pal()
            p[F.TOP] = gfx.rgb(c)
            p[F.TOP_D] = gfx.rgb((c[0] * 3 // 4, c[1] * 3 // 4, c[2] * 3 // 4))
            p[F.BOT] = gfx.rgb((60, 60, 70))
            p[F.BOT_D] = gfx.rgb((40, 40, 50))
            p[F.HAIR] = gfx.rgb(hairs[i])
            self.crowd.append([gfx.to_image(g, p) for g in F.cycle(CROWD, "run", 8)])

        self.hearts = gfx.heart_set(RED, (234, 200, 190), INK)
        self.hearts_grey = gfx.heart_set((170, 160, 150), (226, 218, 204), INK)[2]
        self.feather = gfx.sprite(("....GWW", "..GWWW.", ".WWWG..", "WWG....", "G......"),
                                  {"W": (255, 255, 255), "G": (200, 200, 210)})

        self.park_trees = self._park()
        self.hills = self._hills()
        self.fence = self._fence()
        self.mesas = self._mesas()
        self.road = self._road((96, 92, 92), (255, 224, 90))
        self.desert_road = self._road((84, 76, 76), (255, 230, 120))

    # ------------------------------------------------------------ backdrops
    def _park(self):
        img = image(160, 60)
        for x, r in ((14, 20), (70, 16), (136, 22)):
            img.pen = gfx.rgb((90, 64, 40))
            img.rectangle(x - 3, 30, 7, 30)
            img.pen = gfx.rgb((52, 104, 52))
            img.shape(shape.circle(x, 24, r))
            img.pen = gfx.rgb((76, 136, 64))
            img.shape(shape.circle(x - r // 3, 20, r * 2 // 3))
            img.pen = gfx.rgb((150, 160, 140))
            for k in range(4):
                img.rectangle(x - r // 2 + k * r // 3, 30 + (k % 2) * 3, 1, 6)
        return img

    def _hills(self):
        img = image(160, 30)
        for k in (-160, 0, 160):
            img.pen = gfx.rgb((120, 176, 96))
            img.shape(shape.circle(k + 30, 40, 34))
            img.shape(shape.circle(k + 120, 44, 40))
            img.pen = gfx.rgb((100, 156, 80))
            img.shape(shape.circle(k + 80, 46, 30))
        return S.Layer(img, 56, 0.2)

    def _fence(self):
        img = image(160, 16)
        img.pen = gfx.rgb((126, 90, 56))
        for x in range(0, 160, 20):
            img.rectangle(x, 2, 2, 14)
        img.rectangle(0, 5, 160, 1)
        img.rectangle(0, 10, 160, 1)
        img.pen = gfx.rgb((80, 60, 40))
        img.rectangle(70, 0, 2, 16)
        img.rectangle(56, 0, 30, 1)
        return S.Layer(img, 72, 0.6)

    def _mesas(self):
        img = image(160, 44)
        for k in (-160, 0, 160):
            for x, w, h in ((8, 26, 30), (56, 14, 40), (76, 10, 36), (112, 34, 26)):
                img.pen = gfx.rgb((186, 82, 44))
                img.rectangle(k + x, 44 - h, w, h)
                img.pen = gfx.rgb((150, 60, 34))
                img.rectangle(k + x + w - 4, 44 - h, 4, h)
                img.pen = gfx.rgb((206, 110, 60))
                img.triangle(k + x - 8, 44, k + x, 44 - h // 2, k + x, 44)
                img.triangle(k + x + w, 44, k + x + w, 44 - h // 2, k + x + w + 8, 44)
        return S.Layer(img, 44, 0.15)

    def _road(self, asphalt, stripe):
        img = image(160, 20)
        img.pen = gfx.rgb(asphalt)
        img.rectangle(0, 2, 160, 18)
        img.pen = gfx.rgb((140, 130, 120))
        img.rectangle(0, 2, 160, 1)
        img.pen = gfx.rgb(stripe)
        for x in range(0, 160, 16):
            img.rectangle(x, 12, 8, 2)
        return S.Layer(img, 88, 1.0)

    # ------------------------------------------------------------ render
    def render(self, st, t):
        lv = st.level
        if lv <= S.IDLE:
            self.draw_park(st, t)
        elif lv == S.WALK:
            gfx.box(0, 22, 160, 66, (150, 200, 240))
            self.hills.draw(self.scroll)
            gfx.box(0, 82, 160, 8, (110, 160, 80))
            self.fence.draw(self.scroll)
            self.road.draw(self.scroll)
            gfx.box(0, 108 - 2, 160, 2, (110, 160, 80))
        else:
            gfx.box(0, 22, 160, 22, (252, 214, 160))
            gfx.box(0, 44, 160, 44, (250, 196, 140))
            screen.pen = gfx.rgb((255, 236, 180))
            screen.shape(shape.circle(128, 40, 9))
            self.mesas.draw(self.scroll)
            gfx.box(0, 84, 160, 6, (226, 168, 110))
            self.desert_road.draw(self.scroll)
        self.draw_forrest(st, t)
        self.draw_hud(st, t)
        self.draw_caption(st, t)

    def draw_park(self, st, t):
        gfx.box(0, 22, 160, 70, (160, 208, 236))
        screen.blit(self.park_trees, vec2(0, 30))
        gfx.box(0, 88, 160, 4, (100, 150, 70))
        gfx.box(0, 92, 160, 16, (176, 172, 164))
        gfx.box(0, 92, 160, 1, (210, 206, 198))
        for x in range(0, 160, 24):
            gfx.box(x, 92, 1, 16, (150, 146, 140))
        # bus stop bench
        gfx.box(36, 74, 52, 3, (150, 96, 50))
        gfx.box(36, 79, 52, 3, (150, 96, 50))
        gfx.box(34, 86, 56, 3, (126, 78, 40))
        for x in (38, 84):
            gfx.box(x, 86, 3, 18, (60, 60, 64))
        gfx.box(38, 74, 2, 14, (60, 60, 64))
        gfx.box(84, 74, 2, 14, (60, 60, 64))
        # suitcase
        gfx.box(96, 92, 14, 11, (120, 74, 40))
        gfx.box(96, 96, 14, 1, (90, 54, 28))
        gfx.box(101, 90, 4, 2, (60, 40, 20))
        # the feather
        p = (t % 9000) / 9000.0
        fx = 120 - p * 70 + math.sin(t / 700.0) * 10
        fy = 22 + p * 66
        gfx.blit(self.feather, fx, fy, 2, math.sin(t / 700.0) > 0)

    def draw_forrest(self, st, t):
        lv = st.level
        foot = 104
        if lv == S.SLEEP:
            img = self.sit_blink if (t % 4000) < 160 else self.sit
            gfx.blit(img, 34, 44, 2)
            return
        if lv == S.IDLE:
            img = self.wave if (t % 5000) < 900 else self.stand
            gfx.blit(img, 92, foot - 27 * 2 - 2, 2)
            return
        x = 70
        if lv == S.WALK:
            img = self.frame(self.jog, t, 11)
        elif lv == S.RUN:
            img = self.frame(self.run, t, 13)
        else:
            img = self.frame(self.sprint, t, 15)
            x = 84
        followers = 0 if lv == S.WALK else min(max(st.busy - 1, 1 if lv == S.SPRINT else 0), 7)
        for i in range(followers - 1, -1, -1):
            frames = self.crowd[i % len(self.crowd)]
            fimg = frames[int(t * 14 / 1000 + i * 3) % len(frames)]
            fx = x - 14 - i * 13 - (i % 2) * 4
            fy = foot - 27 - 6 - (i % 3) * 3
            gfx.blit(fimg, fx, fy, 1)
        gfx.blit(img, x, foot - 27 * 2, 2)
        if st.waiting:
            gfx.bubble(x + 30, foot - 54, "JENNY!", INK, WHITE, font.sins)

    def draw_hud(self, st, t):
        gfx.box(0, 0, 160, 22, CREAM)
        gfx.box(0, 21, 160, 1, (200, 180, 150))
        low = st.hearts is not None and st.hearts <= 4
        gfx.draw_hearts(self.hearts, st.hearts, 2, 2, blink=low and S.blink(t, 300), unknown=self.hearts_grey)
        miles = str(min(st.tools, 99999))
        w = gfx.width(miles, font.sins)
        gfx.text(miles, 158 - w, -2, INK, font.sins)
        gfx.text("MILES", 158 - w - 4 - gfx.width("MILES", font.sins), -2, (150, 110, 70), font.sins)
        # the weekly budget as a road from coast to coast
        gfx.box(2, 13, 156, 6, (96, 92, 92))
        if st.week is not None:
            fw = int(156 * st.week)
            gfx.box(2, 13, fw, 6, (76, 72, 72))
            for x in range(4, 2 + fw - 4, 10):
                gfx.box(x, 15, 5, 2, (255, 224, 90))
            gfx.box(2 + fw - 2, 12, 3, 8, RED)
        if not st.online and S.blink(t, 600):
            gfx.text("?", 92, -2, RED, font.sins)

    def draw_caption(self, st, t):
        gfx.box(0, 108, 160, 12, (30, 24, 20))
        msg = self.caption(st, t)
        gfx.ctext(gfx.fit(msg, 156, font.sins), 80, 107, CREAM, font.sins)

    def caption(self, st, t):
        if not st.online:
            return st.net or "WAITING AT THE BUS STOP..."
        if st.waiting and (t // 2500) % 2 == 0:
            return "%d SESSION%s NEED YOU" % (st.waiting, "" if st.waiting == 1 else "S")
        if st.hearts is not None and st.hearts <= 4 and (t // 3000) % 2:
            return "I'M PRETTY TIRED..."
        lv = st.level
        alt = (t // 3500) % 2
        if lv == S.SLEEP:
            return "LIFE IS LIKE A BOX OF" if alt == 0 else "CHOCOLATES..."
        if lv == S.IDLE:
            return "MAMA ALWAYS SAID..." if alt == 0 else "STUPID IS AS STUPID DOES"
        if lv == S.WALK:
            return "I JUST FELT LIKE RUNNING"
        n = max(1, st.busy)
        if lv == S.RUN:
            return "RUN, FORREST, RUN!" if alt == 0 else "%d AGENTS RUNNING" % n
        return "RUN, FORREST, RUN!!" if alt == 0 else "%d FOLLOWERS, %d TOOLS/MIN" % (n, st.tpm)
