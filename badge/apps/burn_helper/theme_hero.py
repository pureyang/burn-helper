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
#
# One-shot activity animations (Status.act; only the demos send them for now), each played
# once over the walk or run: edit = sword combo on a slime, read = lens of truth, shell = bomb,
# web = hookshot, spawn = boomerang out and back, fail = knocked back ("OUCH!"), done = item
# get, prompt = a new quest scroll, arrive = out of a cave, refill = a heart container.

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


BODY = dict(head_r=4, torso=4, torso_w=6, thigh=3, shin=3, upper=3, fore=3, leg_w=2, arm_w=2,  # noqa: C408
            hair="short", hat="hood", skirt=True, belt=F.SHOE, thighs=F.BOT, shins=F.SHOE,
            uppers=F.TOP, forearms=F.SKIN, foot=2)
SPEC = F.Spec(w=26, h=26, extra=_props, **BODY)

# ---------------------------------------------------------------- activity animations
ACTIONS = {"edit": 1400, "read": 1600, "shell": 1600, "web": 1400, "spawn": 2000,
           "fail": 1000, "done": 2000, "prompt": 1500, "arrive": 1800, "refill": 2000}
STILL = ("read", "shell", "done", "prompt", "arrive", "refill")      # the hero and the field stop
CAPTIONS = {"spawn": "BOOMERANG OUT: A SUBAGENT", "fail": "OUCH! A TOOL CALL FAILED",
            "done": "QUEST COMPLETE!", "prompt": "A NEW QUEST!", "arrive": "A NEW SESSION BEGINS",
            "refill": "HEARTS REFILLED!"}
SKYBLUE = (86, 180, 233)          # success sparkle (Okabe-Ito sky blue)
VERMILLION = (213, 94, 0)         # failure (Okabe-Ito vermillion), always with a word
ORANGE = (245, 160, 90)
X0, HIP_X, HIP_Y = 46, 13, 25     # activity poses: hip at (13, 25) in a 40x34 grid
SCALE = 2
CAP = {}                          # where the last rendered pose's hands and head are


def _act_props(g, j, pose):
    """Props for the activity poses. Also records where the hands and head ended up."""
    CAP["hand_f"] = j["hand_f"]
    CAP["hand_b"] = j["hand_b"]
    CAP["head"] = j["head"]
    p = pose.prop or ""
    if "shield" in p:
        _props(g, j, F.Pose(prop="shield"))
    hx, hy = j["hand_f"]
    for tok in p.split():
        if tok.startswith("blade"):
            a = float(tok[5:]) * math.pi / 180      # 0 down, 90 forward, 180 up (like the arms)
            dx, dy = math.sin(a), math.cos(a)
            g.seg(hx - dx, hy - dy, hx + dx, hy + dy, 1, F.SHOE)
            g.set(hx + dx + dy, hy + dy - dx, F.ACC2)
            g.set(hx + dx - dy, hy + dy + dx, F.ACC2)
            g.seg(hx + dx * 2, hy + dy * 2, hx + dx * 9, hy + dy * 9, 1, F.ACC1)
        elif tok == "lens":
            g.seg(hx, hy, hx + 1, hy - 2, 1, F.SHOE)
            cx, cy = hx + 2, hy - 5
            g.disc(cx, cy, 2, F.HAIR)
            g.disc(cx, cy, 1, F.ACC1)
            g.set(cx - 1, cy - 1, F.WHITE)
        elif tok == "bomb":
            cx, cy = hx + 1, hy + 1
            g.disc(cx, cy, 2, F.ACC3)
            g.set(cx - 1, cy - 1, F.WHITE)
            g.set(cx + 1, cy - 3, F.SHOE)
            g.set(cx + 2, cy - 4, F.HAIR)
        elif tok == "hook":
            g.rect(hx - 1, hy - 1, 3, 2, F.ACC2)
            g.set(hx + 2, hy - 1, F.ACC1)
        elif tok == "scroll":
            g.rect(hx, hy - 3, 3, 5, F.WHITE)
            g.set(hx + 1, hy - 2, F.BOT_D)
            g.set(hx + 1, hy, F.BOT_D)


ACT_SPEC = F.Spec(w=40, h=34, extra=_act_props, **BODY)
LONG = dict(BODY)
LONG["upper"] = LONG["fore"] = 5
LONG_ARMS = F.Spec(w=40, h=34, extra=_act_props, **LONG)       # for item get, so the chest clears the head

RUPEE = ("..G..", ".GgG.", "GgWgG", "GgggG", "GgggG", "GgggG", ".GgG.", "..G..")
# boomerang = agents out working (thrown, and comes back with the result)
BOOMERANG = ("..OOOO..", ".OLLLOO.", "OLOOOLOO", "OO....OO", "O......O")
# ocarina = a session is waiting for you to play your part
OCARINA = ("..BB....", ".BBBBBB.", "BLBBHBBB", "BBHBBBHB", ".BBBHBB.", "..BBBB..")
FAIRY = ("w...w", "ww.ww", ".wCw.", "ww.ww", "w...w")
HOURGLASS = ("KKKKK", ".KSK.", "..S..", ".KSK.", "KKKKK")
TREASURE = ("..KKKKKK..", ".KGGGGGGK.", "KGYYWYYYGK", "KKKKKKKKKK", "KBBBGGBBBK", "KBBBKKBBBK", "KBBBBBBBBK",
            "KKKKKKKKKK")
SCROLL = ("BWWWWB", "BWKKWB", "BWWWWB", "BWKKWB", "BWWWWB")
PAGE = ("WWWW.", "WKKWW", "WWWWW", "WKKKW", "WWWWW")


def _rot(rows):
    """ASCII sprite rotated 90 degrees clockwise."""
    w = max(len(r) for r in rows)
    rows = [r + "." * (w - len(r)) for r in rows]
    return tuple("".join(rows[len(rows) - 1 - j][i] for j in range(len(rows))) for i in range(w))


class Theme(S.Theme):
    name = "hero"
    label = "HYRULE"
    ACTIONS = ACTIONS

    def __init__(self):
        S.Theme.__init__(self)
        self.refill_from = 0
        self.last_hearts = None

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
        self._build_actions(pal)

    def _build_actions(self, pal):
        """Poses and props for the activity animations, built once."""
        flash = {k: VERMILLION for k in HERO}  # noqa: C420
        flash.update({F.OUT: (90, 30, 0), F.SKIN: ORANGE, F.SKIN_D: ORANGE, F.WHITE: (255, 230, 200),
                      F.ACC1: (255, 230, 200), F.EYE: (90, 30, 0)})
        fpal = gfx.palette(flash)

        def pose(pal_, spec=ACT_SPEC, **kw):
            CAP.clear()
            img = gfx.to_image(F.render(spec, F.Pose(**kw), (HIP_X, HIP_Y)), pal_)
            return img, dict(CAP)

        self.p_thrust = pose(pal, lean=6, hip=(1, 0), lf=(34, 20), lb=(-28, 14), af=(92, 4), ab=(-35, 50), prop="blade90")
        self.p_stab = pose(pal, lean=18, hip=(1, 3), lf=(70, 110), lb=(-20, 85), af=(55, 5), ab=(-30, 40), prop="blade50")
        self.p_slash = pose(pal, lean=-8, hip=(0, -1), lf=(20, 10), lb=(-25, 20), af=(160, 0), ab=(-40, 30),
                            prop="blade165")
        self.p_lens = pose(pal, lf=(4, 2), lb=(-4, 2), af=(125, 10), ab=(-8, 14), prop="lens")
        self.p_crouch = pose(pal, lean=25, hip=(0, 3), lf=(60, 100), lb=(-10, 90), af=(40, 0), ab=(-30, 30), prop="bomb")
        self.p_brace = pose(pal, lean=-4, lf=(10, 4), lb=(-14, 8), af=(70, 30), ab=(-20, 40), prop="shield")
        self.p_aim = pose(pal, lf=(14, 6), lb=(-14, 6), af=(90, 0), ab=(75, 20), prop="hook")
        self.p_throw = pose(pal, lean=6, lf=(25, 10), lb=(-20, 10), af=(135, -10), ab=(-50, 30))
        self.p_catch = pose(pal, lf=(10, 4), lb=(-10, 6), af=(110, 10), ab=(-20, 30))
        self.p_stand = pose(pal, lf=(4, 2), lb=(-4, 2), af=(8, 12), ab=(-8, 12), prop="shield")
        self.p_read = pose(pal, lf=(4, 2), lb=(-4, 2), af=(75, 50), ab=(30, 50), prop="scroll", mouth=True)
        self.p_reach = pose(pal, lf=(4, 2), lb=(-4, 2), af=(150, 10), ab=(-8, 12))
        hurt = dict(lean=-18, hip=(0, -1), lf=(30, 30), lb=(-10, 45), af=(130, 30), ab=(-140, -20), eye=False,  # noqa: C408
                    mouth=True)
        self.p_hurt = pose(pal, **hurt)
        self.p_hurt_flash = pose(fpal, **hurt)
        self.p_itemget = pose(pal, spec=LONG_ARMS, lf=(6, 2), lb=(-6, 2), af=(140, 30), ab=(215, -30), mouth=True)
        self.walk2 = []
        for i in range(8):
            g = F.gait(i / 8.0, *F.GAITS["walk"])
            self.walk2.append(pose(pal, lean=g.lean, hip=g.hip, lf=g.lf, lb=g.lb, af=g.af, ab=g.ab, prop="shield"))

        self.treasure = gfx.sprite(TREASURE, {"K": (60, 30, 10), "G": GOLD, "Y": (255, 240, 150), "W": WHITE,
                                              "B": (150, 90, 40)})
        self.scroll_img = gfx.sprite(SCROLL, {"B": (150, 90, 40), "W": (250, 240, 210), "K": (120, 100, 80)})
        self.page = gfx.sprite(PAGE, {"W": WHITE, "K": (110, 120, 140)})
        keys = {"O": (170, 110, 40), "L": (235, 180, 90)}
        self.boom = [gfx.sprite(BOOMERANG, keys), gfx.sprite(_rot(BOOMERANG), keys)]
        self.big_heart = self.hearts[0]
        self.white_heart = gfx.heart_set(WHITE, WHITE, WHITE, WHITE)[0]
        self.fade = hasattr(screen, "alpha")

    def start_action(self, key, t0, st):
        S.Theme.start_action(self, key, t0, st)
        if key == "refill":
            # the hearts are already full by now: animate them up from what was shown before
            self.refill_from = self.last_hearts if self.last_hearts is not None and self.last_hearts < 20 else 0

    def advance(self, st, t):
        keep = self.scroll
        S.Theme.advance(self, st, t)
        if self.action in STILL and self.acting(t) is not None:
            self.scroll = keep

    def put(self, img_hands, dx=0, dy=0, flip=False):
        """Blit an activity pose with its hip where the normal hero's hip is. Returns its hands
        and head in screen coordinates."""
        img, hands = img_hands
        x, y = X0 + dx, 90 - HIP_Y * SCALE + dy
        gfx.blit(img, x, y, SCALE, flip)
        return {k: (x + v[0] * SCALE, y + v[1] * SCALE) for k, v in hands.items()}

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
        p = self.acting(t)
        if p is not None:
            getattr(self, "act_" + self.action)(st, t, p)
            return
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

    def draw_navi(self, st, t):  # noqa: ARG002
        a = t / 380.0
        fx = 70 + math.cos(a) * 22
        fy = 50 + math.sin(a * 1.7) * 8
        screen.pen = color.rgb(120, 200, 255, 70)
        screen.shape(shape.circle(fx + 2, fy + 2, 6))
        gfx.blit(self.fairy, fx, fy, 1, (t // 90) % 2 == 0)
        if (t // 700) % 2 == 0:
            gfx.bubble(int(fx) + 2, int(fy) - 1, "HEY! LISTEN!", (24, 24, 48), WHITE, font.sins)

    def draw_hud(self, st, t):
        p = self.acting(t)
        if self.action == "refill" and p is not None:
            keep = st.hearts
            st.hearts = self.refill_from if p < 0.45 else min(20, self.refill_from + int((p - 0.45) / 0.4 * 20))
            self.hud(st, t)
            st.hearts = keep
            return
        self.hud(st, t)
        self.last_hearts = st.hearts

    def hud(self, st, t):
        gfx.box(0, 0, 160, 22, BLACK)
        screen.blit(self.rupee, vec2(3, 2))
        gfx.text("x%d" % min(st.tools, 9999), 10, -1, WHITE, font.sins)
        screen.blit(self.boomerang, vec2(3, 12))
        busy = "x%d" % st.agents
        gfx.text(busy, 12, 9, WHITE, font.sins)
        ox = max(30, 12 + gfx.width(busy, font.sins) + 3)    # make room for 3-digit counts
        screen.blit(self.ocarina, vec2(ox, 12))
        gfx.text("x%d" % st.waiting, ox + 10, 9, WHITE, font.sins)

        # time until the hearts refill (the 5-hour window resets)
        cd = gfx.countdown(st.left5)
        w = gfx.width(cd, font.sins)
        if 158 - w - 10 >= 76 + gfx.width("-LIFE-", font.sins):
            gfx.text("-LIFE-", 76, -2, RED, font.sins)     # dropped when the long final-seconds count needs the room
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
        if self.action in CAPTIONS and self.acting(t) is not None:
            return CAPTIONS[self.action]
        if st.waiting and (t // 2500) % 2 == 0:
            return ("1 QUEST NEEDS YOU!" if st.waiting == 1 else "%d QUESTS NEED YOU!" % st.waiting)
        if st.hearts is not None and st.hearts <= 4 and (t // 3000) % 2:
            return "LOW HEARTS! REFILL IN " + gfx.countdown(st.left5)
        tc = S.tier_caption(st, t, "HYPERSPACE JUMP!")
        if tc:
            return tc
        lv = st.level
        if lv == S.SLEEP:
            return "LINK IS ASLEEP... ZZZ"
        if lv == S.IDLE:
            return "WAITING FOR A QUEST"
        n = max(1, st.agents)
        if lv == S.WALK:
            return "%d AGENT%s ON A QUEST" % (n, "" if n == 1 else "S")
        if lv == S.RUN:
            return "PEGASUS BOOTS! %d AGENTS" % n
        return "IT'S DANGEROUS TO GO ALONE!" if (t // 3000) % 2 == 0 else "%d AGENTS, %d TOOLS/MIN" % (n, st.tpm)

    # ------------------------------------------------------------ effects
    def sparkle(self, x, y, size, c, a=255):
        screen.pen = color.rgb(c[0], c[1], c[2], a)
        screen.rectangle(int(x - size), int(y), size * 2 + 1, 1)
        screen.rectangle(int(x), int(y - size), 1, size * 2 + 1)
        screen.rectangle(int(x), int(y), 1, 1)

    def puff(self, x, y, k, c=(230, 230, 230)):
        """A smoke puff, k from 0 (just popped) to 1 (gone)."""
        for i in range(5):
            a = i * 1.257
            r = 3 + k * 10
            screen.pen = color.rgb(c[0], c[1], c[2], int(230 * (1 - k)))
            screen.shape(shape.circle(x + math.cos(a) * r, y + math.sin(a) * r * 0.7, 4 + k * 3))

    def blob(self, x, y, white=False, squash=0.0):
        """A small purple slime for the hero to fight."""
        body = (255, 255, 255) if white else (150, 70, 190)
        top = (255, 255, 255) if white else (200, 140, 230)
        screen.pen = gfx.rgb((40, 16, 50))
        screen.shape(shape.circle(x, y, 7 + squash))
        screen.pen = gfx.rgb(body)
        screen.shape(shape.circle(x, y, 6 + squash))
        screen.pen = gfx.rgb(top)
        screen.shape(shape.circle(x - 2, y - 3, 2))
        gfx.box(x - 3, y - 1, 2, 3, (20, 10, 30))
        gfx.box(x + 1, y - 1, 2, 3, (20, 10, 30))
        gfx.box(x - 7 - squash, y + 4, 15 + squash * 2, 3, body)

    def slash_arc(self, cx, cy, a0, a1, r, k):
        """Fading white arc from angle a0 to a1 (radians), drawn as dots."""
        for i in range(9):
            a = a0 + (a1 - a0) * i / 8.0
            screen.pen = color.rgb(255, 255, 220, int(230 * (1 - k) * (0.4 + 0.6 * i / 8.0)))
            screen.shape(shape.circle(cx + math.cos(a) * r, cy + math.sin(a) * r, 2.2))

    # ------------------------------------------------------------ the activities
    def act_edit(self, st, t, p):  # noqa: ARG002
        """Sword combo: thrust, low stab, rising slash, and the slime pops."""
        ex = 138 - min(1.0, p / 0.25) * 34          # slime slides in to x 104
        ey = 97
        if p < 0.3:
            self.blob(ex, ey)
            h = self.put(self.p_thrust)
            if p > 0.12:
                self.slash_arc(h["hand_f"][0] + 10, h["hand_f"][1], -0.2, 0.2, 8, (p - 0.12) / 0.18)
        elif p < 0.55:
            self.blob(ex + 3, ey, white=(t // 60) % 2 == 0, squash=1)
            h = self.put(self.p_stab)
            x, y = h["hand_f"]
            self.sparkle(x + 14, y + 12, 3, (255, 255, 200))
        elif p < 0.75:
            k = (p - 0.55) / 0.2
            self.blob(ex + 6, ey - 2 * k, white=True)
            h = self.put(self.p_slash)
            sx, sy = h["hand_f"]
            self.slash_arc(sx - 6, sy + 16, 0.7, -1.5, 17, k * 0.6)
        else:
            k = (p - 0.75) / 0.25
            self.puff(ex + 6, ey - 2, k)
            gfx.blit(self.rupee, ex + 4, ey - 4 - 6 * math.sin(k * math.pi), 1)
            self.put(self.p_slash if k < 0.3 else self.p_stand)

    def act_read(self, st, t, p):  # noqa: ARG002
        """Holds up a lens; its light finds a hidden rupee."""
        h = self.put(self.p_lens)
        lx, ly = h["hand_f"]
        lx, ly = lx + 4, ly - 10
        if p > 0.15:
            k = min(1.0, (p - 0.15) / 0.25)
            sweep = 6 * math.sin(t / 180.0)
            screen.pen = color.rgb(255, 244, 170, int(100 * k))
            screen.triangle(int(lx), int(ly), 150, int(70 + sweep), 150, int(104 + sweep))
            screen.pen = color.rgb(255, 250, 210, int(150 * k))
            screen.line(int(lx), int(ly), 150, int(70 + sweep))
            screen.line(int(lx), int(ly), 150, int(104 + sweep))
            screen.pen = color.rgb(255, 250, 210, int(120 * k))
            screen.shape(shape.circle(lx, ly, 4))
        if p > 0.45:
            k = min(1.0, (p - 0.45) / 0.2)
            if self.fade:
                screen.alpha = int(255 * k)
            gfx.blit(self.rupee, 126, 86, 2)
            if self.fade:
                screen.alpha = 255
            if p > 0.6:
                for i in range(3):
                    q = ((t / 260.0) + i / 3.0) % 1.0
                    self.sparkle(124 + i * 8, 84 + i * 5 - q * 4, 2, GOLD, int(255 * (1 - q)))

    def act_shell(self, st, t, p):  # noqa: ARG002
        """Drops a bomb, steps back behind the shield, boom."""
        bx, by = 104, 99
        if p < 0.22:
            self.put(self.p_crouch)
            return
        lit = p < 0.6
        if lit:
            self.put(self.p_brace, dx=-6)
            screen.pen = gfx.rgb((24, 20, 16))
            screen.shape(shape.circle(bx, by, 5))
            screen.pen = gfx.rgb((44, 80, 200))
            screen.shape(shape.circle(bx, by, 4))
            gfx.box(bx - 2, by - 2, 2, 1, (180, 200, 255))
            gfx.box(bx + 2, by - 6, 1, 2, (128, 72, 24))
            if (t // 70) % 2:
                self.sparkle(bx + 3, by - 8, 2, (255, 230, 120))
            else:
                self.sparkle(bx + 3, by - 8, 1, (255, 255, 255))
            return
        k = (p - 0.6) / 0.4
        self.put(self.p_brace, dx=-6)
        if k < 0.35:
            q = k / 0.35
            for r, c in ((16 + 6 * q, (245, 160, 90)), (11 + 5 * q, (252, 216, 80)), (6 + 4 * q, (255, 255, 230))):
                screen.pen = color.rgb(c[0], c[1], c[2], 235)
                screen.shape(shape.circle(bx, by - 4, r))
        else:
            self.puff(bx, by - 6, (k - 0.35) / 0.65, (200, 196, 190))
        for i in range(6):
            a = i * 1.05 + 0.3
            d = 6 + k * 22
            gfx.box(bx + math.cos(a) * d, by - 4 + math.sin(a) * d * 0.6 - k * 6, 2, 2, (110, 80, 50))

    def act_web(self, st, t, p):  # noqa: ARG002
        """Fires the hookshot to the edge of the screen and reels a page back in."""
        h = self.put(self.p_aim)
        hx, hy = h["hand_f"]
        hx += 6
        far = 152
        if p < 0.4:
            tip = hx + (far - hx) * (p / 0.4)
        elif p < 0.55:
            tip = far
        else:
            tip = far - (far - hx) * ((p - 0.55) / 0.45)
        x = hx
        while x < tip - 4:
            gfx.box(x, hy - 1, 2, 1, (200, 210, 230))
            gfx.box(x + 2, hy, 1, 1, (110, 120, 150))
            x += 4
        screen.pen = gfx.rgb((40, 44, 60))
        screen.triangle(int(tip - 1), int(hy - 5), int(tip + 7), int(hy), int(tip - 1), int(hy + 5))
        screen.pen = gfx.rgb((230, 236, 255))
        screen.triangle(int(tip), int(hy - 4), int(tip + 6), int(hy), int(tip), int(hy + 4))
        gfx.box(tip - 3, hy - 1, 4, 2, (200, 210, 230))
        if 0.4 <= p < 0.55:
            self.sparkle(far + 4, hy, 3, (255, 255, 255))
        if p >= 0.55:
            gfx.blit(self.page, tip - 2, hy + 3, 2)

    def act_spawn(self, st, t, p):  # noqa: ARG002
        """Throws a boomerang that arcs away (SubagentStart); it comes back (SubagentStop)."""
        if p < 0.5:
            k = p / 0.5
            self.put(self.p_throw if k < 0.4 else self.p_stand)
            hx, hy = self.p_throw[1]["hand_f"]
            hx, hy = X0 + hx * SCALE, 90 - HIP_Y * SCALE + hy * SCALE
            bx = hx + k * 120
            by = hy - math.sin(k * math.pi * 0.9) * 34 - k * 10
            size = 2 if k < 0.7 else 1
        else:
            k = (p - 0.5) / 0.5
            self.put(self.p_catch if k > 0.55 else self.p_stand)
            hx, hy = self.p_catch[1]["hand_f"]
            hx, hy = X0 + hx * SCALE, 90 - HIP_Y * SCALE + hy * SCALE
            bx = 160 - k * (160 - hx) * 1.0
            by = 34 + (hy - 34) * k + math.sin(k * math.pi) * 8
            size = 1 if k < 0.3 else 2
            if k > 0.85:
                for i in range(4):
                    self.sparkle(hx + math.cos(i * 1.57) * 8, hy + math.sin(i * 1.57) * 6, 2, SKYBLUE)
        spin = self.boom[(t // 80) % 2]
        for j in range(1, 4):                       # a short trail behind it
            screen.pen = color.rgb(235, 180, 90, 90 - j * 25)
            screen.shape(shape.circle(bx - j * 5 * (1 if p < 0.5 else -1) + 4, by + 3, 2))
        gfx.blit(spin, bx, by, size, (t // 160) % 2 == 0)

    def act_fail(self, st, t, p):  # noqa: ARG002
        """Knocked back with a flash; color is never the only signal: it says OUCH!"""
        hop = math.sin(min(1.0, p / 0.6) * math.pi) * 8
        back = -12 * min(1.0, p / 0.6)
        img = self.p_hurt_flash if (t // 70) % 2 == 0 and p < 0.7 else self.p_hurt
        h = self.put(img, dx=back, dy=-hop)
        if p < 0.4:
            k = p / 0.4
            cx, cy = 104, 74
            for i in range(8):
                a = i * 0.785
                r0, r1 = 3 + k * 4, 8 + k * 6
                screen.pen = color.rgb(245, 160, 90, int(255 * (1 - k)))
                for o in (0, 1):
                    screen.line(int(cx + math.cos(a) * r0) + o, int(cy + math.sin(a) * r0),
                                int(cx + math.cos(a) * r1) + o, int(cy + math.sin(a) * r1))
            screen.pen = color.rgb(255, 255, 255, int(255 * (1 - k)))
            screen.shape(shape.circle(cx, cy, 3 - 2 * k))
        hx, hy = h["head"]
        gfx.bubble(int(hx) + 4, int(hy) - 8, "OUCH!", WHITE, VERMILLION, font.sins)

    def act_done(self, st, t, p):  # noqa: ARG002
        """Item get: both hands up, the treasure overhead, sparkles."""
        rise = min(1.0, p / 0.2)
        h = self.put(self.p_itemget if p > 0.12 else self.p_stand)
        hx = (h["hand_f"][0] + h["hand_b"][0]) / 2
        hy = min(h["hand_f"][1], h["hand_b"][1])
        tx = hx - self.treasure.width + 1
        ty = hy - self.treasure.height * 2 + 2 + (1 - rise) * 10
        if p > 0.3:
            k = min(1.0, (p - 0.3) / 0.3)
            cx, cy = tx + self.treasure.width, ty + 8
            for i in range(8):
                a = i * 0.785 + t / 900.0
                screen.pen = color.rgb(252, 216, 80, int(60 * k))
                screen.triangle(int(cx), int(cy), int(cx + math.cos(a - 0.12) * 40), int(cy + math.sin(a - 0.12) * 40),
                                int(cx + math.cos(a + 0.12) * 40), int(cy + math.sin(a + 0.12) * 40))
        if p > 0.12:
            gfx.blit(self.treasure, tx, ty, 2)
        if p > 0.35:
            for i in range(5):
                q = ((t / 500.0) + i / 5.0) % 1.0
                a = i * 1.257
                c = GOLD if i % 2 else SKYBLUE
                self.sparkle(tx + 10 + math.cos(a) * (14 + q * 8), ty + 8 + math.sin(a) * (10 + q * 6), 2, c,
                             int(255 * (1 - q)))

    def act_prompt(self, st, t, p):  # noqa: ARG002
        """A "!" over the hero, and a scroll drops in with the new quest."""
        if p < 0.6:
            h = self.put(self.p_reach if p > 0.3 else self.p_stand)
        else:
            h = self.put(self.p_read)
        hx, hy = h["head"]
        if p < 0.5:
            gfx.bubble(int(hx) + 2, int(hy) - 8 - int(2 * abs(math.sin(t / 120.0))), "!", (24, 24, 48), GOLD, font.sins)
        if p < 0.6:
            k = min(1.0, p / 0.55)
            sx = 64 + math.sin(k * 9) * 6 * (1 - k)
            sy = 24 + k * 30
            gfx.blit(self.scroll_img, sx, sy, 2)

    def act_arrive(self, st, t, p):  # noqa: ARG002
        """Steps out of a cave door into the field."""
        cx, top, bottom = 34, 60, 104
        screen.pen = gfx.rgb((112, 96, 84))
        screen.shape(shape.circle(cx, top + 22, 24))
        gfx.box(cx - 24, top + 22, 48, bottom - top - 22, (112, 96, 84))
        screen.pen = gfx.rgb((150, 132, 116))
        screen.shape(shape.circle(cx - 8, top + 10, 6))
        screen.pen = gfx.rgb((8, 6, 6))
        screen.shape(shape.circle(cx, top + 26, 11))
        gfx.box(cx - 11, top + 26, 22, bottom - top - 26, (8, 6, 6))
        k = min(1.0, p / 0.7)
        dx = int(-26 + 26 * k)
        if p < 0.7:
            self.put(self.walk2[int(t * 9 / 1000) % 8], dx=dx)
        else:
            self.put(self.p_stand)
        # still inside the doorway: in shadow
        screen.pen = color.rgb(8, 6, 6, 170)
        screen.rectangle(cx - 11, top + 18, 22, bottom - top - 18)
        if p > 0.4:
            for i in range(4):
                q = ((t / 400.0) + i / 4.0) % 1.0
                self.sparkle(cx + 14 + i * 6, top + 20 + i * 7 - q * 6, 2, SKYBLUE if i % 2 else GOLD, int(255 * (1 - q)))

    def act_refill(self, st, t, p):  # noqa: ARG002
        """A heart container floats down; the hearts fill back up."""
        self.put(self.p_reach if 0.25 < p < 0.55 else self.p_stand)
        if p < 0.45:
            k = p / 0.45
            hx = 70 + math.sin(k * 8) * 8 * (1 - k)
            hy = 26 + k * 30
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                gfx.blit(self.white_heart, hx + ox, hy + oy, 2)
            gfx.blit(self.big_heart, hx, hy, 2)
        else:
            k = (p - 0.45) / 0.55
            for i in range(6):
                a = i * 1.047 + k * 3
                r = 6 + k * 20
                self.sparkle(80 + math.cos(a) * r, 64 + math.sin(a) * r * 0.6, 2, (255, 160, 170) if i % 2 else GOLD,
                             int(255 * (1 - k)))
