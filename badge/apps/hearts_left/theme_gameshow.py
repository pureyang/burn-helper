# "Running Man" theme: the 1987 deadly game show, broadcast live from the Zone.
#   sleep  -> runner passed out on the concrete, show is OFF AIR
#   idle   -> runner limbering up while the show is on STANDBY
#   walk   -> jogging into the Zone, LIVE
#   run    -> running flat out with a hockey-masked stalker on his heels
#   sprint -> sprinting through explosions, searchlights sweeping, ratings maxed
# Hearts are the 5-hour budget, the WEEK bar is the 7-day budget.

import math
import figure as F
import gfx
import scene as S

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 214, 0)
PINK = (255, 46, 140)
CYAN = (40, 228, 255)
RED = (230, 30, 40)
NIGHT = (34, 8, 52)

RUNNER = {
    F.OUT: (16, 8, 20), F.SKIN: (236, 176, 128), F.SKIN_D: (190, 130, 90),
    F.HAIR: (60, 36, 24), F.TOP: (255, 212, 0), F.TOP_D: (196, 150, 0),
    F.BOT: (255, 212, 0), F.BOT_D: (196, 150, 0), F.SHOE: (40, 40, 48),
    F.EYE: (16, 8, 20), F.WHITE: (255, 255, 255),
}

STALKER = {
    F.OUT: (10, 10, 20), F.SKIN: (230, 170, 130), F.SKIN_D: (180, 120, 90),
    F.HAIR: (40, 30, 30), F.TOP: (36, 80, 190), F.TOP_D: (24, 52, 130),
    F.BOT: (34, 34, 46), F.BOT_D: (22, 22, 30), F.SHOE: (20, 20, 30),
    F.EYE: (10, 10, 20), F.ACC1: (92, 100, 120), F.ACC2: (255, 40, 40),
    F.ACC3: (150, 100, 56), F.ACC4: (236, 240, 248), F.WHITE: (255, 255, 255),
}


def _stick(g, j, pose):
    hx, hy = j["hand_f"]
    fx, fy = j["fwd"]
    ux, uy = j["up"]
    ex = hx + fx * 4 - ux * 8
    ey = hy + fy * 4 - uy * 8
    g.seg(hx - fx, hy - fy, ex, ey, 1, F.ACC3)
    g.seg(ex, ey, ex + fx * 4, ey + fy * 4, 2, F.ACC3)
    # jersey stripe
    nx, ny = j["neck"]
    hpx, hpy = j["hip"]
    g.seg(nx * 0.5 + hpx * 0.5 - fx * 2, ny * 0.5 + hpy * 0.5 - fy * 2,
          nx * 0.5 + hpx * 0.5 + fx * 2, ny * 0.5 + hpy * 0.5 + fy * 2, 1, F.ACC4)


RUNNER_SPEC = F.Spec(torso_w=5, arm_w=2, leg_w=2, hair="short", forearms=F.TOP, uppers=F.TOP)
STALKER_SPEC = F.Spec(torso_w=6, arm_w=2, leg_w=3, hair="none", hat="helmet",
                      forearms=F.TOP, extra=_stick)


class Theme(S.Theme):
    name = "gameshow"
    label = "RUNNING MAN"

    def build(self):
        rp = gfx.palette(RUNNER)
        sp = gfx.palette(STALKER)

        def run_img(pose):
            return gfx.to_image(F.render(RUNNER_SPEC, pose), rp)

        self.sleep = run_img(F.lying(af=(70, 30), ab=(100, 10)))
        self.flex = [run_img(F.stand(af=(40, 120), ab=(-30, 120))), run_img(F.stand(af=(20, 140), ab=(-20, 140), hip=(0, 1)))]
        self.jog = [gfx.to_image(g, rp) for g in F.cycle(RUNNER_SPEC, "jog", 8)]
        self.run = [gfx.to_image(g, rp) for g in F.cycle(RUNNER_SPEC, "run", 8)]
        self.sprint = [gfx.to_image(g, rp) for g in F.cycle(RUNNER_SPEC, "sprint", 8, mouth=True)]
        self.stalker = [gfx.to_image(g, sp) for g in F.cycle(STALKER_SPEC, "run", 8)]
        self.clock = gfx.clock_icon(YELLOW, BLACK)
        self.far = self._skyline()
        self.mid = self._fence()
        self.ground = self._ground()

    def _skyline(self):
        img = image(160, 44)
        x = -10
        i = 0
        while x < 170:
            w = 14 + (i * 7) % 12
            h = 16 + (i * 13) % 26
            img.pen = gfx.rgb((52, 30, 84) if i % 2 else (44, 24, 72))
            img.rectangle(x, 44 - h, w, h)
            # broken roofline
            img.pen = gfx.rgb(NIGHT)
            img.triangle(x + w - 6, 44 - h, x + w, 44 - h, x + w, 44 - h + 6)
            img.pen = gfx.rgb((255, 190, 60))
            for k in range(3):
                wx = x + 3 + (k * 5 + i * 3) % max(4, w - 4)
                wy = 44 - h + 4 + (k * 7 + i) % max(4, h - 8)
                img.rectangle(wx, wy, 1, 2)
            x += w + 2
            i += 1
        return S.Layer(img, 46, 0.2)

    def _fence(self):
        img = image(160, 22)
        img.pen = color.rgb(150, 160, 180, 90)
        for x in range(-22, 182, 4):
            img.line(x, 2, x + 18, 21)
            img.line(x + 18, 2, x, 21)
        img.pen = gfx.rgb((90, 96, 110))
        for x in range(0, 160, 32):
            img.rectangle(x, 0, 2, 22)
        img.rectangle(0, 1, 160, 1)
        img.pen = gfx.rgb(YELLOW)
        img.rectangle(56, 8, 18, 7)
        img.pen = gfx.rgb(BLACK)
        img.rectangle(58, 10, 14, 1)
        img.rectangle(58, 12, 10, 1)
        return S.Layer(img, 68, 0.6)

    def _ground(self):
        img = image(160, 18)
        img.pen = gfx.rgb((70, 66, 80))
        img.rectangle(0, 0, 160, 18)
        img.pen = gfx.rgb((96, 92, 106))
        img.rectangle(0, 0, 160, 2)
        img.pen = gfx.rgb(YELLOW)
        for x in range(0, 160, 20):
            img.rectangle(x, 11, 10, 2)
        img.pen = gfx.rgb((44, 40, 52))
        for x in range(7, 160, 37):
            img.line(x, 3, x + 4, 7)
            img.line(x + 4, 7, x + 2, 10)
        return S.Layer(img, 90, 1.0)

    # ------------------------------------------------------------ render
    def render(self, st, t):
        lv = st.level
        gfx.box(0, 22, 160, 30, (14, 2, 26))
        gfx.box(0, 52, 160, 38, NIGHT)
        if lv >= S.RUN:
            self.searchlights(t)
        self.far.draw(self.scroll)
        self.mid.draw(self.scroll)
        self.ground.draw(self.scroll)
        self.drums(t)

        if lv == S.SLEEP:
            screen.pen = color.rgb(0, 0, 0, 120)
            screen.rectangle(0, 22, 160, 86)
        self.draw_runner(st, t)
        if lv == S.SPRINT:
            self.explosions(t)
        if st.waiting:
            self.vote(st, t)
        gfx.scanlines(22, 108, 34)
        self.viewfinder(lv, t)
        self.draw_hud(st, t)
        self.draw_caption(st, t)

    def searchlights(self, t):
        for k, base in enumerate((30, 126)):
            a = math.sin(t / 900.0 + k * 2.1) * 0.6
            tipx = base + math.sin(a) * 80
            screen.pen = color.rgb(200, 230, 255, 40)
            screen.triangle(base - 2, 90, base + 2, 90, tipx + 12, 22)
            screen.triangle(base - 2, 90, tipx - 12, 22, tipx + 12, 22)

    def drums(self, t):
        period = 150
        for k in range(2):
            wx = k * period + 40
            x = int((wx - self.scroll) % (period * 2)) - 30
            if -12 < x < 170:
                gfx.box(x, 80, 9, 12, (110, 40, 30))
                gfx.box(x, 83, 9, 1, (60, 20, 16))
                gfx.box(x, 88, 9, 1, (60, 20, 16))
                for i in range(5):
                    p = ((t / 380.0) + i / 5.0) % 1.0
                    fx = x + 4 + math.sin(t / 90.0 + i * 1.7) * 2
                    fy = 79 - p * 12
                    r = 2.6 * (1 - p) + 0.5
                    screen.pen = color.rgb(255, int(220 - 160 * p), 40, int(255 * (1 - p)))
                    screen.shape(shape.circle(fx, fy, r))

    def draw_runner(self, st, t):
        lv = st.level
        foot = 104
        x = 66
        flip = False
        if lv == S.SLEEP:
            img = self.sleep
            x = 52
        elif lv == S.IDLE:
            img = self.flex[(t // 600) % 2]
            flip = (t // 4000) % 2 == 1
        elif lv == S.WALK:
            img = self.frame(self.jog, t, 11)
        elif lv == S.RUN:
            img = self.frame(self.run, t, 14)
        else:
            img = self.frame(self.sprint, t, 17)
            x = 74
        if lv >= S.RUN:
            gap = 34 + math.sin(t / 700.0) * 8 + (10 if lv == S.SPRINT else 0)
            simg = self.frame(self.stalker, t + 120, 13)
            gfx.blit(simg, x - gap - 20, foot - 27 * 2, 2)
        y = foot - 27 * 2
        if lv == S.SLEEP:
            y = foot - 26 * 2 + 4
        gfx.blit(img, x, y, 2, flip)
        if lv == S.SLEEP:
            gfx.zzz(x + 10, y + 26, t, (255, 230, 120), font.sins)

    def explosions(self, t):
        for k in range(2):
            period = 1400 + k * 500
            p = ((t + k * 700) % period) / float(period)
            if p > 0.6:
                continue
            q = p / 0.6
            ex = 18 + k * 34 + (t // period) % 3 * 6
            ey = 86 - k * 8
            r = 3 + q * 12
            screen.pen = color.rgb(255, int(150 - q * 100), 20, int(255 * (1 - q * q)))
            screen.shape(shape.circle(ex, ey, r))
            screen.pen = color.rgb(255, 230, 90, int(255 * (1 - q)))
            screen.shape(shape.circle(ex, ey, r * 0.6))
            screen.pen = color.rgb(255, 255, 230, int(255 * (1 - q)))
            screen.shape(shape.circle(ex, ey, r * 0.25))
            for i in range(6):
                a = i * 1.047 + k
                screen.pen = color.rgb(255, 220, 120, int(255 * (1 - q)))
                screen.rectangle(int(ex + math.cos(a) * r * 1.3), int(ey + math.sin(a) * r * 0.9), 1, 1)

    def vote(self, st, t):
        if (t // 400) % 2 == 0:
            screen.pen = color.rgb(255, 40, 140, 170)
            screen.rectangle(0, 22, 160, 2)
            screen.rectangle(0, 106, 160, 2)
            screen.rectangle(0, 22, 2, 86)
            screen.rectangle(158, 22, 2, 86)
        gfx.bubble(98, 46, "YOUR MOVE!", BLACK, YELLOW, font.sins)

    def viewfinder(self, lv, t):
        c = color.rgb(255, 255, 255, 150)
        screen.pen = c
        for (x, y, dx, dy) in ((4, 26, 1, 1), (155, 26, -1, 1), (4, 103, 1, -1), (155, 103, -1, -1)):
            screen.rectangle(min(x, x + dx * 7), y, 8, 1)
            screen.rectangle(x, min(y, y + dy * 5), 1, 6)

    def draw_hud(self, st, t):
        gfx.box(0, 0, 160, 22, (10, 0, 18))
        gfx.box(0, 21, 160, 1, PINK)
        gfx.text("RUNNING MAN", 2, -2, YELLOW, font.sins, shadow=RED)
        lv = st.level
        if not st.online:
            self.rtext("NO SIGNAL", (150, 150, 160))
        elif lv == S.SLEEP:
            self.rtext("OFF AIR", (150, 150, 160))
        elif lv == S.IDLE:
            self.rtext("STANDBY", CYAN)
        else:
            x = self.rtext("LIVE", WHITE)
            if S.blink(t, 500):
                screen.pen = gfx.rgb(RED)
                screen.shape(shape.circle(x - 5, 5, 3))
        self.draw_collar(st, t, 2, 10)
        # the show's game clock: time until the collar recharges (5-hour reset)
        gfx.box(94, 9, 64, 11, BLACK)
        gfx.box(94, 9, 64, 1, PINK)
        cd = gfx.countdown(st.left5)
        w = gfx.width(cd, font.sins)
        gfx.text(cd, 156 - w, 7, gfx.countdown_color(st.left5, YELLOW, (255, 150, 40), RED), font.sins)
        screen.blit(self.clock, vec2(int(156 - w - 8), 12))

    def draw_collar(self, st, t, x, y):
        """The runner's explosive collar: 10 lights = the 5-hour budget.

        Green = charge left, amber = half a light, dark red = spent. Under two
        lights the rest flash red. The strip under the band is the weekly budget.
        """
        units = st.hearts
        gfx.box(x, y + 1, 84, 7, (58, 62, 74))
        gfx.box(x, y + 1, 84, 1, (110, 116, 132))
        gfx.box(x, y, 4, 9, (120, 126, 142))
        gfx.box(x + 80, y, 4, 9, (120, 126, 142))
        low = units is not None and units <= 4
        flash = low and S.blink(t, 250)
        for i in range(10):
            cx = x + 8 + i * 7
            if units is None:
                c = (40, 40, 48)
            else:
                left = units - i * 2
                if left >= 2:
                    c = (255, 50, 40) if flash else (70, 255, 140)
                elif left == 1:
                    c = (255, 50, 40) if flash else (255, 170, 0)
                else:
                    c = (72, 12, 16)
            gfx.box(cx - 2, y + 2, 5, 5, c)
            if units is not None and units - i * 2 >= 1 and not flash:
                gfx.box(cx - 1, y + 3, 1, 1, (255, 255, 255))
        # weekly budget: a thin charge strip under the collar
        gfx.meter(x + 4, y + 10, 76, 1, st.week, CYAN, (30, 30, 60))

    def rtext(self, s, c):
        x = 158 - gfx.width(s, font.sins)
        gfx.text(s, x, -2, c, font.sins)
        return x

    def draw_caption(self, st, t):
        gfx.box(0, 108, 160, 12, YELLOW)
        gfx.box(0, 108, 4, 12, PINK)
        msg = self.caption(st, t)
        gfx.ctext(gfx.fit(msg, 150, font.sins), 82, 107, BLACK, font.sins)

    def caption(self, st, t):
        if not st.online:
            return st.net or "PLEASE STAND BY..."
        if st.waiting and (t // 2500) % 2 == 0:
            return "AUDIENCE VOTE: YOUR MOVE!"
        if st.hearts is not None and st.hearts <= 4 and (t // 3000) % 2:
            return "COLLAR LOW! RECHARGE " + gfx.countdown(st.left5)
        lv = st.level
        n = max(1, st.busy)
        if lv == S.SLEEP:
            return "OFF AIR - RUNNER ASLEEP"
        if lv == S.IDLE:
            return "STAND BY FOR THE NEXT RUN"
        if lv == S.WALK:
            return "RUNNER IN THE ZONE: %d AGENT%s" % (n, "" if n == 1 else "S")
        if lv == S.RUN:
            return "STALKER RELEASED! %d AGENTS" % n
        return "MAXIMUM RATINGS!" if (t // 3000) % 2 == 0 else "%d AGENTS, %d TOOLS/MIN" % (n, st.tpm)
