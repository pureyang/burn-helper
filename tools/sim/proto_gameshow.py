#!/usr/bin/env python3
"""Prototype: one-shot agent-activity animations for the game show theme.

    python3 tools/sim/proto_gameshow.py     -> tools/sim/out/proto/gameshow_*.png + gameshow.json

Subclasses the real theme and adds `action` / `action_t0`: while an action is playing
(about 1.6-2 s) it takes over the runner and may draw an overlay card, then the normal
animation resumes. Uses the theme's own figure specs, palettes and picovector calls, so a
chosen action can move into badge/apps/burn_helper/theme_gameshow.py as is.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the simulator first)
import figure as F  # noqa: E402
import gfx  # noqa: E402
import scene as S  # noqa: E402
import theme_gameshow as G  # noqa: E402

GOLD = (255, 200, 40)
SKYBLUE = (86, 180, 233)        # Okabe-Ito sky blue: success accents
VERMILLION = (213, 94, 0)       # Okabe-Ito vermillion: failure accents
VERMILLION_L = (245, 160, 90)
BROWN = (130, 82, 40)
BROWN_D = (86, 52, 24)

# a subagent runner: same build, cyan suit so it reads as a second player
BUDDY = dict(G.RUNNER)
BUDDY.update({F.TOP: (40, 200, 230), F.TOP_D: (20, 140, 170), F.BOT: (40, 200, 230), F.BOT_D: (20, 140, 170),
              F.HAIR: (200, 120, 40)})
# the runner lit up by a zap: suit and skin flash pale
ZAPPED = dict(G.RUNNER)
ZAPPED.update({F.TOP: (255, 250, 210), F.TOP_D: (230, 220, 160), F.BOT: (255, 250, 210), F.BOT_D: (230, 220, 160),
               F.SKIN: (255, 255, 255), F.SKIN_D: (220, 220, 230), F.HAIR: (255, 255, 255), F.OUT: (120, 40, 0)})
HOST = {
    F.OUT: (16, 8, 20), F.SKIN: (236, 180, 140), F.SKIN_D: (190, 136, 100),
    F.HAIR: (70, 44, 28), F.TOP: (200, 30, 120), F.TOP_D: (140, 20, 84),
    F.BOT: (40, 30, 60), F.BOT_D: (26, 20, 40), F.SHOE: (20, 20, 24),
    F.EYE: (16, 8, 20), F.ACC1: (200, 200, 210), F.ACC2: (60, 60, 70), F.WHITE: (255, 255, 255),
}


def _mic(g, j, pose):
    if pose.prop != "mic":
        return
    hx, hy = j["hand_f"]
    ux, uy = j["up"]
    g.seg(hx, hy, hx + ux * 3, hy + uy * 3, 1, F.ACC2)
    g.disc(hx + ux * 4, hy + uy * 4, 1, F.ACC1)
    # bow tie
    nx, ny = j["neck"]
    g.set(nx, ny + 1, F.WHITE)


HOST_SPEC = F.Spec(torso_w=6, arm_w=2, leg_w=2, hair="short", forearms=F.TOP, uppers=F.TOP,
                   shins=F.BOT, extra=_mic)

DRONE = ("RR.......RR",
         "KKKK...KKKK",
         ".K.......K.",
         ".KKKKKKKKK.",
         "..KGGGGGK..",
         "...KLLLK...",
         "....KKK....")

# frame times (fraction of the action) worth showing for each one
SHOTS = {
    "edit": (0.14, 0.4, 0.58, 0.86),
    "read": (0.15, 0.4, 0.62, 0.9),
    "shell": (0.1, 0.32, 0.5, 0.75),
    "web": (0.12, 0.38, 0.62, 0.9),
    "spawn": (0.15, 0.38, 0.58, 0.8),
    "fail": (0.1, 0.27, 0.5, 0.82),
    "done": (0.12, 0.38, 0.62, 0.88),
    "prompt": (0.1, 0.35, 0.6, 0.9),
    "arrive": (0.12, 0.45, 0.65, 0.92),
    "refill": (0.08, 0.35, 0.65, 0.95),
}
DUR = {"edit": 1800, "read": 1800, "shell": 1600, "web": 1800, "spawn": 2000, "fail": 1400,
       "done": 1800, "prompt": 1800, "arrive": 2200, "refill": 2400}

CAPTIONS = {
    "edit": ("STALKER ATTACKS!", "COUNTERATTACK!"),
    "read": ("SEARCHLIGHTS ON!", "HIDING IN THE ZONE..."),
    "shell": ("PYRO IN THE ZONE!", "KA-BOOM!"),
    "web": ("DRONE CAM: LIVE FEED", "DRONE CAM: LIVE FEED"),
    "spawn": ("A NEW RUNNER ENTERS!", "SUBAGENT ON THE RUN"),
    "fail": ("ZAP! A TOOL FAILED", "ZAP! A TOOL FAILED"),
    "done": ("APPLAUSE! TURN DONE", "APPLAUSE! TURN DONE"),
    "prompt": ("THE HOST HAS A NEW RULE", "NEXT ROUND!"),
    "arrive": ("PLEASE WELCOME...", "A NEW CONTESTANT!"),
    "refill": ("WE'LL BE RIGHT BACK", "COLLAR RECHARGED!"),
}


def ease(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def seg(p, a, b):
    """0..1 progress of p within [a, b]."""
    return max(0.0, min(1.0, (p - a) / (b - a)))


class Theme(G.Theme):
    """The game show theme with the proposed one-shot actions."""

    def __init__(self):
        super().__init__()
        self.action = None
        self.action_t0 = 0

    def build(self):
        super().build()
        rp = gfx.palette(G.RUNNER)
        sp = gfx.palette(G.STALKER)

        def r(pose, pal=rp, spec=G.RUNNER_SPEC):
            return gfx.to_image(F.render(spec, pose), pal)

        self.duck = r(F.Pose(lean=38, hip=(0, 4), lf=(84, 96), lb=(20, 130), af=(120, 120), ab=(60, 120)))
        self.kick = r(F.Pose(lean=-28, hip=(0, -1), lf=(100, 4), lb=(-12, 6), af=(40, 70), ab=(-60, 80), mouth=True))
        self.punch = r(F.Pose(lean=12, lf=(36, 30), lb=(-34, 12), af=(92, 0), ab=(-20, 110), mouth=True))
        self.crouch = r(F.Pose(lean=10, hip=(0, 5), lf=(82, 84), lb=(70, 120), af=(70, 70), ab=(40, 90)))
        self.leap = r(F.Pose(lean=18, lf=(84, 100), lb=(-40, 70), af=(130, 30), ab=(-70, 40), mouth=True))
        self.cheer = [r(F.Pose(lf=(8, 2), lb=(-8, 2), af=(140, 0), ab=(-140, 0), mouth=True)),
                      r(F.Pose(hip=(0, -2), lf=(14, 10), lb=(-14, 10), af=(125, 15), ab=(-125, -15), mouth=True))]
        self.pose_in = r(F.Pose(lf=(10, 2), lb=(-10, 2), af=(160, 20), ab=(-40, 120)))     # one fist up
        zp = gfx.palette(ZAPPED)
        jolt = F.Pose(hip=(0, -2), lf=(34, 0), lb=(-34, 0), af=(140, -30), ab=(-140, 30), eye=False, mouth=True)
        self.jolt = [r(jolt), r(jolt, zp)]
        bp = gfx.palette(BUDDY)
        self.buddy = [gfx.to_image(g, bp) for g in F.cycle(G.RUNNER_SPEC, "run", 8)]
        self.five = r(F.Pose(lean=4, lf=(30, 30), lb=(-30, 20), af=(150, 10), ab=(-30, 60)))
        self.buddy_five = r(F.Pose(lean=4, lf=(30, 30), lb=(-30, 20), af=(150, 10), ab=(-30, 60)), bp)
        # stalker: closing in, the swing, knocked flat
        self.s_swing = r(F.Pose(lean=30, lf=(30, 20), lb=(-30, 10), af=(150, 20), ab=(-20, 60)), sp, G.STALKER_SPEC)
        self.s_follow = r(F.Pose(lean=50, lf=(40, 30), lb=(-40, 10), af=(60, 0), ab=(-40, 50)), sp, G.STALKER_SPEC)
        self.s_down = r(F.lying(af=(60, 30), ab=(120, 10)), sp, G.STALKER_SPEC)
        hp = gfx.palette(HOST)
        self.host = [gfx.to_image(F.render(HOST_SPEC, F.Pose(lf=(6, 2), lb=(-6, 2), af=(40, 120), ab=(-20, 30),
                                                             prop="mic", mouth=m)), hp) for m in (False, True)]
        self.drone = gfx.sprite(DRONE, {"R": (200, 200, 220), "K": (60, 64, 80), "G": (150, 156, 176),
                                        "L": (40, 228, 255)})

    # ------------------------------------------------------------ plumbing
    def progress(self, t):
        if self.action is None:
            return None
        p = (t - self.action_t0) / float(DUR[self.action])
        return p if 0.0 <= p < 1.0 else None

    def render(self, st, t):
        # the base theme's render, with the action hooked in before the scanlines and HUD
        lv = st.level
        p = self.progress(t)
        gfx.box(0, 22, 160, 30, (14, 2, 26))
        gfx.box(0, 52, 160, 38, G.NIGHT)
        if p is not None and self.action == "read":
            self.lock_on(t, p)
        elif lv >= S.RUN:
            self.searchlights(t)
        self.far.draw(self.scroll)
        self.mid.draw(self.scroll)
        self.ground.draw(self.scroll)
        self.drums(t)
        if lv == S.SLEEP:
            screen.pen = color.rgb(0, 0, 0, 120)
            screen.rectangle(0, 22, 160, 86)
        if p is None:
            self.draw_runner(st, t)
        else:
            getattr(self, "act_" + self.action)(st, t, p)
        if lv == S.SPRINT:
            self.explosions(t)
        if st.waiting:
            self.vote(st, t)
        gfx.scanlines(22, 108, 34)
        self.viewfinder(lv, t)
        if p is not None:
            over = getattr(self, "over_" + self.action, None)
            if over:
                over(st, t, p)
        saved = st.hearts
        if p is not None and self.action == "refill":
            st.hearts = min(20, 4 + int(seg(p, 0.15, 0.8) * 17))    # the collar lights fill back up
        self.draw_hud(st, t)
        st.hearts = saved
        self.draw_caption(st, t)

    def caption(self, st, t):
        p = self.progress(t)
        if p is not None:
            a, b = CAPTIONS[self.action]
            return a if p < 0.45 else b
        return super().caption(st, t)

    def gait_img(self, st, t):
        lv = st.level
        if lv == S.RUN:
            return self.frame(self.run, t, 14)
        if lv == S.SPRINT:
            return self.frame(self.sprint, t, 17)
        return self.frame(self.jog, t, 11)

    def put(self, img, x, foot=104, flip=False, h=27, lift=0):
        gfx.blit(img, x, foot - h * 2 - lift, 2, flip)

    # ------------------------------------------------------------ edit: a fight
    def act_edit(self, st, t, p):
        x = 66
        if p < 0.3:                        # stalker charges in from the left, stick raised
            q = ease(seg(p, 0.0, 0.3))
            sx = -50 + q * 76
            self.put(self.frame(self.stalker, t, 16), sx)
            self.put(self.gait_img(st, t), x, flip=p > 0.18)       # the runner hears him and turns
        elif p < 0.5:                      # the swing: runner ducks under it
            self.put(self.s_swing if p < 0.4 else self.s_follow, 12)
            self.put(self.duck, x, flip=True, lift=-6)
            self.whoosh(86, 58, t)
        elif p < 0.75:                     # counter: a high kick, then a punch
            self.put(self.s_follow, 22 - (p - 0.5) * 30)
            self.put(self.kick if p < 0.63 else self.punch, x - 10, flip=True)
            self.pow(54, 52 if p < 0.63 else 60, "POW!" if p < 0.63 else "WHAM!")
        else:                              # stalker flat on the concrete, runner turns and goes
            self.put(self.s_down, 2 - (p - 0.75) * 60, h=24, lift=-6)
            self.put(self.gait_img(st, t), x, flip=p < 0.85)
            for i in range(3):             # dazed stars
                a = t / 160.0 + i * 2.1
                gfx.box(18 + math.cos(a) * 7 - (p - 0.75) * 60, 80 + math.sin(a) * 2, 1, 1, GOLD)

    def whoosh(self, x, y, t):
        # the stick's swing, an arc passing just over his head
        screen.pen = color.rgb(255, 255, 255, 190)
        for i in range(9):
            a = 3.6 + i * 0.22
            screen.rectangle(int(x + math.cos(a) * 22), int(y + math.sin(a) * 10), 2, 1)

    def pow(self, x, y, word):
        # a starburst with a word: theme yellow, not a good/bad colour
        screen.pen = gfx.rgb(G.YELLOW)
        for i in range(8):
            a = i * 0.785
            screen.line(int(x), int(y), int(x + math.cos(a) * 9), int(y + math.sin(a) * 7))
        w = int(gfx.width(word, font.sins))
        gfx.box(x - w // 2 - 2, y - 13, w + 4, 10, G.YELLOW)
        gfx.text(word, x - w // 2, y - 15, G.BLACK, font.sins)

    # ------------------------------------------------------------ read: searchlights find him
    def lock_on(self, t, p):
        target = 94
        for k, base in enumerate((30, 126)):
            free = base + math.sin(math.sin(t / 900.0 + k * 2.1) * 0.6) * 80
            q = ease(seg(p, 0.1, 0.45)) * (1 - ease(seg(p, 0.82, 1.0)))
            tipx = free + (target - free) * q
            screen.pen = color.rgb(220, 240, 255, 40 + int(40 * q))
            screen.triangle(base - 2, 90, base + 2, 90, tipx + 12, 22)
            screen.triangle(base - 2, 90, tipx - 12, 22, tipx + 12, 22)

    def act_read(self, st, t, p):
        x = 66
        cx = 160 - ease(seg(p, 0.0, 0.3)) * 66          # a crate scrolls in, then he stops behind it
        if p >= 0.82:
            cx = 94 - ease(seg(p, 0.82, 1.0)) * 90
        hiding = 0.28 <= p < 0.82
        if hiding:
            self.put(self.crouch, x - 4, lift=-2)
            if 0.5 <= p < 0.8 and (t // 250) % 2 == 0:
                # peeking over the top
                gfx.text("?", 104, 52, G.WHITE, font.sins)
            self.crate(int(cx), 104)       # in front of him while he hides
        else:
            self.crate(int(cx), 104)       # behind him while he runs
            self.put(self.gait_img(st, t), x)
        if 0.45 <= p < 0.82:               # the beams meet on the crate
            screen.pen = color.rgb(255, 255, 230, 70)
            screen.shape(shape.circle(cx + 11, 86, 16))

    def crate(self, x, foot):
        y = foot - 22
        gfx.box(x, y, 24, 22, BROWN)
        gfx.box(x, y, 24, 2, BROWN_D)
        gfx.box(x, y + 10, 24, 2, BROWN_D)
        gfx.box(x, y + 20, 24, 2, BROWN_D)
        gfx.box(x, y, 2, 22, BROWN_D)
        gfx.box(x + 22, y, 2, 22, BROWN_D)
        screen.pen = gfx.rgb(BROWN_D)
        screen.line(x + 2, y + 2, x + 22, y + 10)
        screen.line(x + 2, y + 12, x + 22, y + 20)

    # ------------------------------------------------------------ shell: a barrel goes up
    def act_shell(self, st, t, p):
        x = 66
        bx = 36
        lift = 0
        img = self.gait_img(st, t)
        if 0.3 <= p < 0.75:                # blown into the air
            q = seg(p, 0.3, 0.75)
            lift = int(math.sin(q * math.pi) * 18)
            img = self.leap
        self.put(img, x + (8 * seg(p, 0.3, 0.75) if p < 0.75 else 8 - 8 * seg(p, 0.75, 1.0)), lift=lift)
        if p < 0.3:                        # a fizzing barrel next to him
            gfx.box(bx, 90, 12, 14, (180, 40, 30))
            gfx.box(bx, 93, 12, 1, (110, 20, 16))
            gfx.box(bx, 99, 12, 1, (110, 20, 16))
            gfx.box(bx + 2, 94, 8, 4, G.YELLOW)
            gfx.box(bx + 6, 86, 1, 4, (200, 200, 200))
            if (t // 80) % 2:
                gfx.box(bx + 5 + (t // 40) % 3, 84, 2, 2, (255, 230, 120))
            for i in range(5):
                a = t / 70.0 + i * 1.3
                gfx.box(bx + 6 + math.cos(a) * 4, 84 + math.sin(a) * 3, 1, 1, (255, 200, 80))
        else:                              # the fireball
            q = seg(p, 0.3, 1.0)
            ex, ey = bx + 6, 94
            r = 5 + q * 26
            screen.pen = color.rgb(255, int(150 - q * 110), 20, int(255 * (1 - q * q)))
            screen.shape(shape.circle(ex, ey, r))
            screen.pen = color.rgb(255, 230, 90, int(255 * (1 - q)))
            screen.shape(shape.circle(ex, ey, r * 0.6))
            screen.pen = color.rgb(255, 255, 230, int(255 * (1 - q)))
            screen.shape(shape.circle(ex, ey, r * 0.25))
            for i in range(10):
                a = i * 0.628
                d = r * (1.1 + 0.3 * (i % 2))
                screen.pen = color.rgb(255, 220, 120, int(255 * (1 - q)))
                screen.rectangle(int(ex + math.cos(a) * d), int(ey + math.sin(a) * d * 0.7), 2, 1)
            if q < 0.6:
                w = int(gfx.width("BOOM!", font.sins))
                gfx.text("BOOM!", ex - w // 2, 54 - int(q * 6), G.YELLOW, font.sins, shadow=(120, 30, 0))

    # ------------------------------------------------------------ web: the drone cam
    def act_web(self, st, t, p):
        self.put(self.gait_img(st, t), 66)
        if p < 0.3:
            q = ease(seg(p, 0.0, 0.3))
            dx, dy = 150 - q * 32, 24 + q * 16
        elif p < 0.75:
            dx, dy = 118 + math.sin(t / 200.0) * 3, 40 + math.sin(t / 130.0) * 2
        else:
            q = ease(seg(p, 0.75, 1.0))
            dx, dy = 118 + q * 34, 40 - q * 16
        dx, dy = int(dx), int(dy)
        # spinning rotors: alternate long and short blur
        long_ = (t // 60) % 2 == 0
        gfx.box(dx - (3 if long_ else 1), dy, 8 if long_ else 4, 1, (220, 220, 235))
        gfx.box(dx + 14 - (1 if long_ else 0), dy, 8 if long_ else 4, 1, (220, 220, 235))
        gfx.blit(self.drone, dx, dy + 1, 2)
        if (t // 250) % 2 == 0:
            gfx.box(dx + 10, dy + 12, 2, 2, (255, 40, 40))
        if 0.3 <= p < 0.75:
            # the camera's view: a framing box on the runner and a LIVE tag
            screen.pen = color.rgb(255, 255, 255, 200)
            for (x, y, sx, sy) in ((76, 46, 1, 1), (112, 46, -1, 1), (76, 104, 1, -1), (112, 104, -1, -1)):
                screen.rectangle(min(x, x + sx * 5), y, 6, 1)
                screen.rectangle(x, min(y, y + sy * 4), 1, 5)
            gfx.box(dx - 4, dy + 18, 26, 9, G.BLACK)
            if (t // 250) % 2 == 0:
                screen.pen = gfx.rgb((255, 40, 40))
                screen.shape(shape.circle(dx, dy + 22, 2))
            gfx.text("LIVE", dx + 3, dy + 16, G.WHITE, font.sins)

    # ------------------------------------------------------------ spawn: a second runner
    def act_spawn(self, st, t, p):
        x = 66
        if p < 0.4:                        # catches up from the left
            q = ease(seg(p, 0.0, 0.4))
            self.put(self.frame(self.buddy, t + 200, 15), -60 + q * 98)
            self.put(self.gait_img(st, t), x)
        elif p < 0.65:                     # high five
            self.put(self.buddy_five, 40)
            self.put(self.five, x, flip=True)
            if p > 0.5:
                gfx.text("*", 74, 32, G.YELLOW, font.sins)
                screen.pen = gfx.rgb(G.YELLOW)
                for i in range(6):
                    a = i * 1.047
                    screen.rectangle(int(76 + math.cos(a) * 6), int(42 + math.sin(a) * 5), 1, 1)
        else:                              # and sprints off ahead on its own errand
            q = ease(seg(p, 0.65, 1.0))
            self.put(self.gait_img(st, t), x)
            self.put(self.frame(self.buddy, t + 200, 17), 40 + q * 130)
            if q < 0.6:
                gfx.text("GO!", 52 + int(q * 120), 30, (150, 240, 255), font.sins)

    # ------------------------------------------------------------ fail: zapped
    def act_fail(self, st, t, p):
        x = 66
        if p < 0.12:
            self.put(self.gait_img(st, t), x)
        elif p < 0.62:
            jit = (t // 40) % 2
            self.put(self.jolt[(t // 70) % 2], x + jit - 1, lift=2)
            # the bolt from the top of the scene
            if (t // 60) % 3 != 2:
                pts = ((98, 22), (90, 32), (100, 38), (92, 48), (98, 54))
                screen.pen = gfx.rgb(VERMILLION_L)
                for i in range(len(pts) - 1):
                    screen.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                    screen.line(pts[i][0] + 1, pts[i][1], pts[i + 1][0] + 1, pts[i + 1][1])
            for i in range(8):
                a = t / 50.0 + i * 0.8
                d = 14 + (i * 5) % 9
                gfx.box(94 + math.cos(a) * d, 78 + math.sin(a) * d * 0.9, 1, 1, VERMILLION_L)
            screen.pen = color.rgb(213, 94, 0, 46)
            screen.rectangle(0, 22, 160, 86)
            gfx.bubble(120, 44, "ZAP!", G.BLACK, VERMILLION_L, font.sins)
        else:                              # shakes it off, a little smoke, back to running
            self.put(self.gait_img(st, t), x)
            q = seg(p, 0.62, 1.0)
            for i in range(3):
                screen.pen = color.rgb(160, 160, 170, int(160 * (1 - q)))
                screen.shape(shape.circle(92 + i * 5 - q * 20, 48 - q * 14 - i * 3, 2 + q * 3))

    # ------------------------------------------------------------ done: applause
    def act_done(self, st, t, p):
        x = 66
        if 0.15 <= p < 0.85:
            self.put(self.cheer[(t // 180) % 2], x)
        else:
            self.put(self.gait_img(st, t), x)
        # confetti from the top
        cols = ((255, 46, 140), (255, 214, 0), (40, 228, 255), (255, 255, 255), (86, 180, 233))
        for i in range(36):
            seed = (i * 7919) % 997
            fx = (seed * 13) % 160 + math.sin(t / 200.0 + i) * 3
            fy = 22 + ((seed % 60) + p * 120) % 86
            if p < 0.12 and fy > 22 + p * 600:
                continue
            gfx.box(fx, fy, 2 if i % 3 == 0 else 1, 1, cols[i % len(cols)])
        if 0.2 <= p < 0.9:
            k = seg(p, 0.2, 0.9)
            gfx.text("+1", 100, 44 - int(k * 14), GOLD, font.sins, shadow=G.BLACK)

    def over_done(self, st, t, p):
        on = (t // 200) % 2 == 0
        w = int(gfx.width("APPLAUSE", font.sins)) + 10
        x = 80 - w // 2
        gfx.box(x - 1, 25, w + 2, 13, SKYBLUE)
        gfx.box(x, 26, w, 11, G.BLACK)
        gfx.text("APPLAUSE", x + 5, 24, GOLD if on else (120, 96, 30), font.sins)
        for i in range(0, w, 4):
            if ((i // 4) + (t // 120)) % 2:
                gfx.box(x + i, 26, 1, 1, GOLD)
                gfx.box(x + i, 36, 1, 1, GOLD)

    # ------------------------------------------------------------ prompt: the host
    def act_prompt(self, st, t, p):
        self.put(self.gait_img(st, t), 50)

    def over_prompt(self, st, t, p):
        # the host slides into a picture-in-picture box, says his line, slides out
        q = ease(seg(p, 0.0, 0.2)) * (1 - ease(seg(p, 0.85, 1.0)))
        bx = int(160 - q * 52)
        top = 44
        gfx.box(bx - 2, top - 2, 52, 62, G.PINK)
        gfx.box(bx, top, 48, 58, (30, 10, 50))
        for i in range(6):                 # studio lights behind him
            gfx.box(bx + 3 + i * 8, top + 2, 3, 2, G.YELLOW if (i + t // 150) % 2 else (120, 90, 20))
        talking = 0.25 <= p < 0.8 and (t // 140) % 2 == 0
        gfx.blit(self.host[1 if talking else 0], bx - 4, top - 6, 2)
        if 0.22 <= p < 0.85:
            gfx.bubble(bx + 22, top - 1, "NEXT ROUND!", G.BLACK, G.WHITE, font.sins)

    # ------------------------------------------------------------ arrive: spotlight and a card
    def act_arrive(self, st, t, p):
        x = 66
        dim = ease(seg(p, 0.0, 0.2)) * (1 - ease(seg(p, 0.85, 1.0)))
        screen.pen = color.rgb(0, 0, 0, int(170 * dim))
        screen.rectangle(0, 22, 160, 86)
        if dim > 0.05:
            screen.pen = color.rgb(255, 250, 200, int(70 * dim))
            screen.triangle(90, 22, 70, 104, 118, 104)
            screen.pen = color.rgb(255, 250, 200, int(60 * dim))
            screen.shape(shape.circle(94, 104, 14))
        if 0.15 <= p < 0.85:
            self.put(self.pose_in if (t // 500) % 2 == 0 else self.flex[0], x)
        else:
            self.put(self.gait_img(st, t), x)

    def over_arrive(self, st, t, p):
        # a lower-third card slides in from the left
        q = ease(seg(p, 0.2, 0.4)) * (1 - ease(seg(p, 0.8, 0.95)))
        x = int(-90 + q * 92)
        gfx.box(x, 82, 86, 12, G.PINK)
        gfx.box(x, 94, 70, 9, G.BLACK)
        gfx.text("NEW CONTESTANT", x + 3, 80, G.YELLOW, font.sins)
        gfx.text("SESSION #4", x + 3, 92, G.WHITE, font.sins)

    # ------------------------------------------------------------ refill: commercial break
    def act_refill(self, st, t, p):
        self.put(self.gait_img(st, t), 66)

    def over_refill(self, st, t, p):
        q = ease(seg(p, 0.0, 0.12)) * (1 - ease(seg(p, 0.85, 1.0)))
        if q <= 0:
            return
        top = 22 + int((1 - q) * 86)
        h = 108 - top
        bars = ((200, 200, 200), (200, 200, 0), (0, 200, 200), (0, 200, 0), (200, 0, 200), (200, 0, 0), (0, 0, 200))
        bw = 160 // len(bars) + 1
        for i, c in enumerate(bars):
            gfx.box(i * bw, top, bw, min(h, 40), c)
        if h > 40:
            gfx.box(0, top + 40, 160, h - 40, (16, 8, 28))
            gfx.ctext("COMMERCIAL BREAK", 80, top + 42, G.YELLOW, font.sins)
            gfx.ctext("COLLAR RECHARGING", 80, top + 54, G.WHITE, font.sins)
            # a little charge bar matching the collar
            k = seg(p, 0.15, 0.8)
            gfx.meter(40, top + 66, 80, 4, k, SKYBLUE, (40, 40, 60))


TITLES = {
    "edit": ("Counterattack",
             "A stalker charges in with his stick. The runner ducks the swing, lands a kick and a punch, "
             "and leaves him seeing stars."),
    "read": ("Searchlight sweep",
             "The searchlights swing over and meet on a crate. The runner crouches behind it and peeks out "
             "until they move on."),
    "shell": ("Barrel blast",
              "A fizzing barrel goes up behind the runner and the blast throws him forward. "
              "Bigger commands could mean bigger booms."),
    "web": ("Drone cam",
            "A camera drone swoops down, frames the runner with a LIVE tag for a second, and flies off."),
    "spawn": ("Tag team",
              "A second runner in a cyan suit catches up, they high-five, and it sprints ahead on its own errand. "
              "When the subagent finishes it would jog back in from the right."),
    "fail": ("Zapped",
             "A bolt hits the runner: he lights up, the scene flashes orange and a bubble says ZAP!, "
             "then he shakes it off in a puff of smoke."),
    "done": ("Applause",
             "The APPLAUSE sign lights up, confetti falls, the runner throws both arms up and a +1 floats away."),
    "prompt": ("The host",
               "The host pops into a picture-in-picture box with his mic and announces the next round."),
    "arrive": ("New contestant",
               "The lights drop, a spotlight finds the runner, and a lower-third card introduces him."),
    "refill": ("Commercial break",
               "Colour bars and a COMMERCIAL BREAK card cover the scene while the collar lights charge back "
               "up, then the show resumes."),
}

NOTES = {
    "edit": "4 new poses (duck, kick, punch) and 3 stalker poses, about 2 KB of images. "
            "Needs a per-tool event from the bridge (an edit counter or event feed).",
    "read": "One new crouch pose; the crate and the locked beams are plain rectangles and triangles. "
            "Needs the Read/Grep/Glob event.",
    "shell": "One leap pose; the barrel and fireball reuse the explosion drawing. Needs the Bash event.",
    "web": "A 11x7 drone sprite. Needs the WebFetch/WebSearch event.",
    "spawn": "A recoloured copy of the run cycle (8 frames, about 4 KB) plus a high-five pose. "
             "The bridge already counts SubagentStart/SubagentStop; it needs to send them as events.",
    "fail": "Two jolt images (normal and lit). Needs PostToolUseFailure forwarded as an event "
            "(the hook already fires for it). Orange flash plus the ZAP! word, never red vs green.",
    "done": "Two cheer poses; confetti is drawn per frame. Needs Stop forwarded as an event.",
    "prompt": "A host figure (2 frames, mouth open and shut). Needs UserPromptSubmit as an event.",
    "arrive": "No new sprites beyond one pose. Needs SessionStart as an event.",
    "refill": "No new sprites. Worked out on the badge when the 5-hour window resets; no bridge change.",
}


def main():
    items = []
    base_t = 5000
    for key in P.KEYS:
        th = Theme()
        th.action = key
        th.action_t0 = base_t
        st = P.status(level=S.WALK, agents=3, hearts=4 if key == "refill" else 14)
        frames = []
        for i, f in enumerate(SHOTS[key]):
            t = base_t + int(f * DUR[key])
            th.last_t = None
            th.scroll = 600.0
            scr = P.render(th, st, t)
            frames.append(P.save(scr, "gameshow", key, i))
        title, desc = TITLES[key]
        items.append({"key": key, "title": title, "desc": desc, "frames": frames, "notes": NOTES[key]})
    print(P.write_manifest("gameshow", items))


if __name__ == "__main__":
    main()
