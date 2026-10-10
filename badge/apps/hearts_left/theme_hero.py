# "Hyrule" theme: a side-view Zelda II style field with a little green-capped hero.
#   sleep  -> curled up asleep under the stars
#   idle   -> standing guard, shield up
#   walk   -> walking the field
#   run    -> Pegasus-boots dash, dust flying
#   sprint -> dashing with sword out, spin attacks
# Hearts are the 5-hour budget, the magic meter is the weekly budget, rupees
# count today's tool calls, boomerangs count busy agents and the ocarina counts
# sessions waiting for you. Navi shows up shouting
# "HEY! LISTEN!" when a session is waiting for you.

import math
import figure as F
import gfx
import scene as S

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (216, 40, 0)
DARK_RED = (90, 20, 20)
GREEN = (60, 176, 40)
DGREEN = (24, 112, 24)
SKY = (108, 156, 252)
SKY_NIGHT = (16, 24, 64)
TAN = (220, 176, 108)
GOLD = (252, 216, 80)

HERO = {
    F.OUT: (24, 20, 16), F.SKIN: (252, 200, 148), F.SKIN_D: (208, 148, 96),
    F.HAIR: (240, 184, 56), F.TOP: (60, 168, 36), F.TOP_D: (28, 112, 24),
    F.BOT: (236, 220, 170), F.BOT_D: (196, 176, 128), F.SHOE: (128, 72, 24),
    F.EYE: (24, 20, 16), F.ACC1: (220, 230, 248), F.ACC2: (140, 156, 200),
    F.ACC3: (44, 80, 200), F.ACC4: (216, 40, 0), F.WHITE: (255, 255, 255),
}


def _props(g, j, pose):
    p = pose.prop or ""
    fx, fy = j["fwd"]
    if "shield" in p:
        hx, hy = j["hand_f"]
        x = int(hx + 0.5)
        y = int(hy - 3.5)
        g.rect(x, y, 3, 6, F.ACC3)
        g.rect(x + 1, y + 1, 1, 4, F.ACC2)
        g.set(x + 1, y + 2, F.ACC4)
    if "sword" in p:
        hx, hy = j["hand_f"] if "fwd" in p else j["hand_b"]
        g.seg(hx - fx, hy - fy, hx + fx * 1, hy + fy * 1, 1, F.SHOE)
        g.set(hx + fy * 1, hy - fx * 1, F.ACC2)
        g.set(hx - fy * 1, hy + fx * 1, F.ACC2)
        g.seg(hx + fx * 2, hy + fy * 2, hx + fx * 8, hy + fy * 8, 1, F.ACC1)


SPEC = F.Spec(w=26, h=26, head_r=4, torso=4, torso_w=6, thigh=3, shin=3, upper=3, fore=3,
              leg_w=2, arm_w=2, hair="short", hat="hood", skirt=True, belt=F.SHOE,
              thighs=F.BOT, shins=F.SHOE, uppers=F.TOP, forearms=F.SKIN, foot=2, extra=_props)

RUPEE = ("..G..", ".GgG.", "GgWgG", "GgggG", "GgggG", "GgggG", ".GgG.", "..G..")
# boomerang = agents out working (thrown, and comes back with the result)
BOOMERANG = ("..OOOO..", ".OLLLOO.", "OLOOOLOO", "OO....OO", "O......O")
# ocarina = a session is waiting for you to play your part
OCARINA = ("..BB....", ".BBBBBB.", "BLBBHBBB", "BBHBBBHB", ".BBBHBB.", "..BBBB..")
FAIRY = ("w...w", "ww.ww", ".wCw.", "ww.ww", "w...w")
HOURGLASS = ("KKKKK", ".KSK.", "..S..", ".KSK.", "KKKKK")


class Theme(S.Theme):
    name = "hero"
    label = "HYRULE"

    def build(self):
        pal = gfx.palette(HERO)

        def img(pose):
            return gfx.to_image(F.render(SPEC, pose), pal)

        self.stand = [img(F.stand(prop="shield")), img(F.stand(prop="shield", eye=False))]
        self.sleep = img(F.lying(lf=(80, 30), lb=(96, 20)))
        self.walk = [gfx.to_image(g, pal) for g in F.cycle(SPEC, "walk", 8, prop="shield")]
        self.run = [gfx.to_image(g, pal) for g in F.cycle(SPEC, "run", 8, prop="shield")]
        self.dash = [gfx.to_image(g, pal) for g in F.cycle(SPEC, "sprint", 8, prop="sword fwd")]
        self.spin = img(F.Pose(lf=(30, 10), lb=(-30, 10), af=(95, 0), ab=(-40, 40), prop="sword fwd"))

        self.hearts = gfx.heart_set(RED, DARK_RED, BLACK)
        self.hearts_grey = gfx.heart_set((120, 120, 120), (60, 60, 60), BLACK)[2]
        self.rupee = gfx.sprite(RUPEE, {"G": (40, 200, 72), "g": (140, 240, 140), "W": WHITE})
        self.boomerang = gfx.sprite(BOOMERANG, {"O": (170, 110, 40), "L": (235, 180, 90)})
        self.ocarina = gfx.sprite(OCARINA, {"B": (60, 100, 220), "L": (160, 195, 255), "H": (20, 30, 90)})
        self.fairy = gfx.sprite(FAIRY, {"w": (200, 230, 255), "C": WHITE})
        self.clock = gfx.sprite(HOURGLASS, {"K": (200, 160, 80), "S": GOLD})

        self.far = self._mountains()
        self.mid = self._trees()
        self.ground = self._ground()
        self.stars = [((i * 53) % 160, 24 + (i * 29) % 40) for i in range(18)]

    # ------------------------------------------------------------ backdrops
    def _mountains(self):
        img = image(160, 40)
        peaks = ((0, 16), (34, 6), (62, 18), (90, 0), (120, 12), (148, 4))
        for k in (-160, 0, 160):
            for i, (px, py) in enumerate(peaks):
                x = px + k
                img.pen = gfx.rgb((150, 112, 80) if i % 2 else (176, 132, 92))
                img.triangle(x - 34, 40, x, py, x + 34, 40)
                img.pen = gfx.rgb((236, 236, 240))
                img.triangle(x - 6, py + 6, x, py, x + 6, py + 6)
        return S.Layer(img, 34, 0.15)

    def _trees(self):
        img = image(160, 30)
        for k in (-160, 0, 160):
            for i in range(6):
                x = k + i * 28 + (i * 7) % 11
                img.pen = gfx.rgb((112, 64, 24))
                img.rectangle(x + 6, 18, 4, 12)
                img.pen = gfx.rgb(DGREEN)
                img.shape(shape.circle(x + 8, 12, 10))
                img.pen = gfx.rgb(GREEN)
                img.shape(shape.circle(x + 6, 10, 7))
                img.pen = gfx.rgb((120, 216, 88))
                img.shape(shape.circle(x + 4, 7, 2))
        return S.Layer(img, 62, 0.45)

    def _ground(self):
        img = image(160, 18)
        img.pen = gfx.rgb(GREEN)
        img.rectangle(0, 0, 160, 6)
        img.pen = gfx.rgb(DGREEN)
        for x in range(0, 160, 6):
            img.rectangle(x, 0, 1, 3)
            img.rectangle(x + 3, 2, 1, 3)
        img.pen = gfx.rgb(TAN)
        img.rectangle(0, 6, 160, 12)
        img.pen = gfx.rgb((184, 136, 80))
        for x in range(0, 160, 20):
            img.rectangle(x + 4, 10, 3, 1)
            img.rectangle(x + 13, 14, 2, 1)
        return S.Layer(img, 90, 1.0)

    # ------------------------------------------------------------ render
    def render(self, st, t):
        night = st.level == S.SLEEP
        gfx.box(0, 22, 160, 68, SKY)
        self.far.draw(self.scroll)
        self.mid.draw(self.scroll)
        self.ground.draw(self.scroll)
        if night:
            screen.pen = color.rgb(8, 12, 48, 170)
            screen.rectangle(0, 22, 160, 86)
            for i, (x, y) in enumerate(self.stars):
                if (t // 400 + i) % 7:
                    gfx.box(x, y - 2, 1, 1, (220, 220, 255))
            screen.pen = gfx.rgb((250, 240, 200))
            screen.shape(shape.circle(132, 32, 6))
            screen.pen = color.rgb(36, 44, 94)
            screen.shape(shape.circle(135, 30, 5))

        self.draw_hero(st, t)
        if st.waiting:
            self.draw_navi(st, t)
        self.draw_hud(st, t)
        self.draw_caption(st, t)

    def draw_hero(self, st, t):
        lv = st.level
        x = 46
        foot = 104
        scale = 2
        flip = False
        if lv == S.SLEEP:
            img = self.sleep
            x = 40
        elif lv == S.IDLE:
            img = self.stand[1] if (t % 3200) < 150 else self.stand[0]
        elif lv == S.WALK:
            img = self.frame(self.walk, t, 9)
        elif lv == S.RUN:
            img = self.frame(self.run, t, 14)
            for i in range(3):
                p = ((t / 300.0) + i / 3.0) % 1.0
                r = 1 + p * 3
                screen.pen = color.rgb(236, 220, 190, int(200 * (1 - p)))
                screen.shape(shape.circle(x + 12 - p * 26, foot - 3 - p * 4, r))
        else:
            cyc = t % 2400
            if cyc < 600:
                img = self.spin
                flip = (cyc // 75) % 2 == 1
                ang = cyc / 600.0 * 2 * math.pi
                cx = x + 26
                cy = foot - 24
                for k in range(10):
                    a = ang - k * 0.25
                    screen.pen = color.rgb(255, 255, 200 - k * 15, 255 - k * 22)
                    screen.shape(shape.circle(cx + math.cos(a) * 30, cy + math.sin(a) * 14, 2.5 - k * 0.2))
            else:
                img = self.frame(self.dash, t, 18)
            for i in range(4):
                p = ((t / 220.0) + i / 4.0) % 1.0
                screen.pen = color.rgb(255, 255, 255, int(220 * (1 - p)))
                screen.shape(shape.circle(x + 6 - p * 36, foot - 3 - p * 6, 1 + p * 3))
        y = foot - img.height * scale + (2 if lv != S.SLEEP else 0) * scale
        if lv == S.SLEEP:
            y = foot - 18 * scale
        gfx.blit(img, x, y, scale, flip)
        if lv == S.SLEEP:
            screen.font = font.sins
            gfx.zzz(x + 10, y + 12, t, (255, 255, 255), font.sins)

    def draw_navi(self, st, t):
        a = t / 380.0
        fx = 70 + math.cos(a) * 22
        fy = 50 + math.sin(a * 1.7) * 8
        screen.pen = color.rgb(120, 200, 255, 70)
        screen.shape(shape.circle(fx + 2, fy + 2, 6))
        gfx.blit(self.fairy, fx, fy, 1, (t // 90) % 2 == 0)
        if (t // 700) % 2 == 0:
            gfx.bubble(int(fx) + 2, int(fy) - 1, "HEY! LISTEN!", (24, 24, 48), WHITE, font.sins)

    def draw_hud(self, st, t):
        gfx.box(0, 0, 160, 22, BLACK)
        screen.blit(self.rupee, vec2(3, 2))
        gfx.text("x%d" % min(st.tools, 9999), 10, -1, WHITE, font.sins)
        screen.blit(self.boomerang, vec2(3, 12))
        gfx.text("x%d" % st.busy, 12, 9, WHITE, font.sins)
        screen.blit(self.ocarina, vec2(30, 12))
        gfx.text("x%d" % st.waiting, 40, 9, WHITE, font.sins)

        gfx.text("-LIFE-", 76, -2, RED, font.sins)
        # time until the hearts refill (the 5-hour window resets)
        cd = gfx.countdown(st.left5)
        w = gfx.width(cd, font.sins)
        gfx.text(cd, 158 - w, -2, gfx.countdown_color(st.left5, WHITE), font.sins)
        screen.blit(self.clock, vec2(int(158 - w - 8), 2))
        low = st.hearts is not None and st.hearts <= 4
        gfx.draw_hearts(self.hearts, st.hearts, 76, 9, blink=low and S.blink(t, 300), unknown=self.hearts_grey)
        # magic meter under the hearts = weekly budget
        gfx.meter(77, 19, 79, 2, st.week, (48, 200, 64), (36, 52, 36))
        if not st.online and S.blink(t, 600):
            gfx.text("?", 62, 4, RED, font.sins)

    def draw_caption(self, st, t):
        gfx.box(0, 108, 160, 12, BLACK)
        msg = self.caption(st, t)
        gfx.ctext(gfx.fit(msg, 156, font.sins), 80, 107, WHITE, font.sins)

    def caption(self, st, t):
        if not st.online:
            return st.net or "SEARCHING FOR BRIDGE..."
        if st.waiting and (t // 2500) % 2 == 0:
            return "%d QUEST%s NEED YOU!" % (st.waiting, "" if st.waiting == 1 else "S")
        if st.hearts is not None and st.hearts <= 4 and (t // 3000) % 2:
            return "LOW HEARTS! REFILL IN " + gfx.countdown(st.left5)
        lv = st.level
        if lv == S.SLEEP:
            return "LINK IS ASLEEP... ZZZ"
        if lv == S.IDLE:
            return "WAITING FOR A QUEST"
        n = max(1, st.busy)
        if lv == S.WALK:
            return "%d AGENT%s ON A QUEST" % (n, "" if n == 1 else "S")
        if lv == S.RUN:
            return "PEGASUS BOOTS! %d AGENTS" % n
        return "IT'S DANGEROUS TO GO ALONE!" if (t // 3000) % 2 == 0 else "%d AGENTS, %d TOOLS/MIN" % (n, st.tpm)
