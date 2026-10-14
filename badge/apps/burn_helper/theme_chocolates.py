# "Forrest" theme (the surprise): Forrest Gump's run across America.
#   sleep  -> on the Savannah bus-stop bench with a box of chocolates, feather drifting
#   idle   -> standing by the bench, ready to go
#   walk   -> "I just felt like running." jogging down a country road
#   run    -> long hair and beard, Monument Valley highway
#   sprint -> the whole crowd of followers running behind him (one per busy agent)
# Hearts are the 5-hour budget; the road bar is the weekly budget; MILES counts
# today's tool calls. When a session waits for you he shouts "JENNY!".
#
# One-shot activity animations (Status.act), each played once over the jog or run: edit =
# a ping-pong rally, read = opens the box of chocolates, shell = a shrimp net, web = reporters
# run alongside ("WHY ARE YOU RUNNING?"), spawn / back = a follower joins / peels off, fail =
# shot in the buttocks ("OW!"), done = turns around at the ocean, prompt = a drill sergeant
# barks and he salutes, arrive = a cut to the bus-stop bench, refill = a new box of chocolates.

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


# ---------------------------------------------------------------- activity animations
GOLD = (255, 214, 90)
BLUE = (0, 114, 178)            # something good happened (Okabe-Ito blue), always with a word
VERMILLION = (213, 94, 0)       # something went wrong (Okabe-Ito vermillion), always with a word

# activity -> how long it plays (ms), and the caption while it does
ACTIONS = {"edit": 1600, "read": 2000, "shell": 1600, "web": 2600, "spawn": 2000, "back": 1400,
           "fail": 1800, "done": 2800, "prompt": 2200, "arrive": 2200, "refill": 2000}
CAPTIONS = {"edit": "EDITING: PING! PONG! PING!", "read": "READING: WHAT'S IN THE BOX?",
            "shell": "RUNNING A COMMAND: SHRIMP!", "web": "SEARCHING THE WEB",
            "spawn": "A SUBAGENT JOINS THE RUN", "back": "THE SUBAGENT IS BACK",
            "fail": "OW! A TOOL CALL FAILED", "done": "END OF THE ROAD: TURN DONE",
            "prompt": "NEW ORDERS FROM YOU", "arrive": "A NEW SESSION SITS DOWN",
            "refill": "A NEW BOX! USAGE RESET"}
STILL = ("done", "arrive", "prompt")       # he stops, and so does the road


def _props(g, j, pose):
    """Hand props for the activity poses: paddle, box (closed or open), net."""
    p = pose.prop or ""
    hx, hy = j["hand_f"]
    ex, ey = j["elbow_f"]
    dx, dy = hx - ex, hy - ey
    n = math.sqrt(dx * dx + dy * dy) or 1.0
    dx, dy = dx / n, dy / n
    if p == "paddle":
        g.seg(hx, hy, hx + dx * 1.5, hy + dy * 1.5, 1, F.ACC3)
        g.disc(hx + dx * 3.2, hy + dy * 3.2, 1.6, F.ACC1)
    elif p.startswith("box"):
        x, y = int(hx) - 1, int(hy) - 2
        g.rect(x, y, 7, 3, F.ACC3)
        if p == "box_open":
            g.rect(x, y, 7, 1, F.ACC2)               # chocolates showing
            g.rect(x + 1, y, 1, 1, F.ACC4)
            g.rect(x + 4, y, 1, 1, F.ACC4)
            g.rect(x - 1, y - 4, 1, 4, F.ACC4)       # lid flipped up behind
        else:
            g.rect(x, y - 1, 7, 1, F.ACC4)
    elif p == "net":
        cx, cy = hx + dx * 4, hy + dy * 4
        g.seg(hx, hy, cx - dx * 1.5, cy - dy * 1.5, 1, F.ACC3)
        g.disc(cx, cy, 2.2, F.WHITE)
        g.disc(cx, cy, 1.0, F.T)


def _press(g, j, pose):
    """The reporter's microphone and the cameraman's shoulder camera."""
    p = pose.prop or ""
    hx, hy = j["hand_f"]
    fx, fy = j["fwd"]
    if p == "mic":
        g.seg(hx, hy, hx + fx * 2, hy + fy * 2 - 1, 1, F.ACC3)
        g.disc(hx + fx * 3, hy + fy * 3 - 2, 1, F.OUT)
    elif p == "camera":
        cx, cy = j["head"]
        g.rect(cx - 3, cy - 1, 7, 4, F.ACC3)            # body on the shoulder, beside the head
        g.rect(cx + 4, cy, 2, 2, F.OUT)                 # lens
        g.set(cx - 2, cy - 2, F.ACC4)


ACT_JOGGER = F.Spec(torso_w=5, hair="short", hat="cap", shins=F.SKIN, extra=_props)
PRESS = F.Spec(torso_w=4, hair="short", forearms=F.TOP, extra=_press)

# arm poses for the activities: (front arm, back arm, prop), on the jog at every level (so he
# has no beard while one plays, and there are half as many frames to build).
ARMS = {
    "paddle_ready": ((40, 30), (-20, 40), "paddle"),
    "paddle_swing": ((88, 48), (-30, 50), "paddle"),
    "box": ((60, 30), (-20, 50), "box"),
    "box_open": ((60, 30), (40, 40), "box_open"),
    "box_eat": ((60, 30), (100, 105), "box_open"),
    "net_up": ((140, 15), (-20, 50), "net"),
    "net_down": ((60, 25), (-20, 50), "net"),
    "jolt": ((-35, -15), (160, 20), None),      # front hand on his behind, far arm flung up
    "clutch": ((-35, -15), (30, 70), None),     # running on, still holding it
}
STRIDES = 4     # frames per activity cycle: half the normal 8, shown twice as long, to save memory

SHRIMP = ("..pp...", ".pPPp..", "pPPPPpa", ".pPPPa.", "..pa.a.")
SHRIMP_KEYS = {"p": (232, 112, 120), "P": (250, 160, 160), "a": (200, 80, 90)}
BIG_BOX = ("GGGGGGGGGG", "GddddddddG", "GdMdMdMdMG", "GddddddddG", "GdMdMdMdMG", "GddddddddG", "GGGGGGGGGG")
BIG_BOX_KEYS = {"G": (214, 172, 76), "d": (66, 36, 22), "M": (150, 90, 46)}


# A box of chocolates is Forrest's life meter: 10 chocolates = the full
# 5-hour budget, a bitten one = half, an empty paper cup = used up.
CHOC_FULL = ("...dddd...", ".dMMMMMMd.", "dMHHMMMMMd", "dMMMMMMMMd", "CdMMMMMMdC", "CCddddddCC", ".CCCCCCCC.")
CHOC_HALF = ("...ddd....", ".dMMMMd...", "dMHHMMMd..", "dMMMMMMFF.", "CdMMMMMMdC", "CCddddddCC", ".CCCCCCCC.")
CHOC_GONE = ("..........", "..........", "..........", ".c......c.", "CccccccccC", "CCccccccCC", ".CCCCCCCC.")
CHOC_KEYS = {"d": (52, 26, 12), "M": (124, 68, 34), "H": (214, 156, 104), "C": (200, 154, 64),
             "c": (110, 82, 38), "F": (246, 176, 188)}
SHOE = ("...WW..", "..WWWW.", "WWRRWWW", "WWWWRRW", "KKKKKKK")


class Theme(S.Theme):
    name = "chocolates"
    label = "FORREST"
    ACTIONS = ACTIONS

    def __init__(self):
        S.Theme.__init__(self)
        self.refill_from = 0
        self.last_hearts = None

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

        self.chocs = (gfx.sprite(CHOC_FULL, CHOC_KEYS), gfx.sprite(CHOC_HALF, CHOC_KEYS),
                      gfx.sprite(CHOC_GONE, CHOC_KEYS))
        self.shoe = gfx.sprite(SHOE, {"W": (250, 250, 250), "R": RED, "K": (90, 80, 76)})
        self.clock = gfx.clock_icon(INK, CREAM)
        self.feather = gfx.sprite(("....GWW", "..GWWW.", ".WWWG..", "WWG....", "G......"),
                                  {"W": (255, 255, 255), "G": (200, 200, 210)})

        self.park_trees = self._park()
        self.hills = self._hills()
        self.fence = self._fence()
        self.mesas = self._mesas()
        self.road = self._road((96, 92, 92), (255, 224, 90))
        self.desert_road = self._road((84, 76, 76), (255, 230, 120))
        self._build_actions(p_run)

    def _build_actions(self, p_run):
        """Poses and props for the activity animations, built once (so nothing hitches the
        first time one plays): every arm pose on the jog."""
        self.arms = {}
        for name in ARMS:
            af, ab, prop = ARMS[name]
            self.arms[name] = [gfx.to_image(g, p_run)
                               for g in F.cycle(ACT_JOGGER, "jog", STRIDES, af=af, ab=ab, prop=prop)]
        self.shrimp = gfx.sprite(SHRIMP, SHRIMP_KEYS)
        self.big_box = gfx.sprite(BIG_BOX, BIG_BOX_KEYS)
        # standing still, and saluting with his hand at the cap's brim
        self.still = gfx.to_image(F.render(JOGGER, F.stand()), p_run)
        self.salute = gfx.to_image(F.render(JOGGER, F.stand(af=(100, 80))), p_run)
        # the drill sergeant, half off screen on the left, pointing at him
        p_sgt = pal()
        p_sgt[F.TOP] = gfx.rgb((96, 110, 64))
        p_sgt[F.TOP_D] = gfx.rgb((72, 84, 48))
        p_sgt[F.BOT] = gfx.rgb((96, 110, 64))
        p_sgt[F.BOT_D] = gfx.rgb((72, 84, 48))
        p_sgt[F.HAIR] = gfx.rgb((60, 44, 30))
        self.sergeant = gfx.to_image(F.render(SUIT, F.stand(af=(95, 0), mouth=True)), p_sgt)
        # the press: a reporter with a microphone and a cameraman
        p_rep = pal()
        p_cam = pal()
        for pp, top, hair in ((p_rep, (84, 92, 120), (40, 30, 24)), (p_cam, (150, 110, 70), (190, 150, 90))):
            pp[F.TOP] = gfx.rgb(top)
            pp[F.TOP_D] = gfx.rgb((top[0] * 3 // 4, top[1] * 3 // 4, top[2] * 3 // 4))
            pp[F.BOT] = gfx.rgb((60, 60, 70))
            pp[F.BOT_D] = gfx.rgb((40, 40, 50))
            pp[F.HAIR] = gfx.rgb(hair)
            pp[F.ACC3] = gfx.rgb((60, 60, 66))
            pp[F.ACC4] = gfx.rgb((255, 255, 255))
        self.reporter = [gfx.to_image(g, p_rep) for g in F.cycle(PRESS, "jog", STRIDES, af=(75, 40), prop="mic")]
        self.cameraman = [gfx.to_image(g, p_cam)
                          for g in F.cycle(PRESS, "jog", STRIDES, af=(150, 60), prop="camera")]

    def start_action(self, key, t0, st):
        S.Theme.start_action(self, key, t0, st)
        if key == "refill":
            # the box is already full by now: animate it up from what was shown before
            self.refill_from = self.last_hearts if self.last_hearts is not None and self.last_hearts < 20 else 0

    def playing(self, st, t):
        """Like acting(), but the activities only show on the road (not asleep or idle on the bench)."""
        if st.level <= S.IDLE:
            return None
        return self.acting(t)

    def advance(self, st, t):
        if self.action in STILL and self.playing(st, t) is not None:
            self.last_t = t            # he stops: the road stops scrolling
            return
        S.Theme.advance(self, st, t)

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
        self.draw_hero_figure(st, t)
        self.draw_hud(st, t)
        self.draw_caption(st, t)

    def draw_park(self, st, t):  # noqa: ARG002
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

    def draw_hero_figure(self, st, t):
        p = self.playing(st, t)
        if p is not None:
            getattr(self, "act_" + self.action)(st, t, p)
            return
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
        followers = 0 if lv == S.WALK else min(max(st.agents - 1, 1 if lv == S.SPRINT else 0), 7)
        for i in range(followers - 1, -1, -1):
            frames = self.crowd[i % len(self.crowd)]
            fimg = frames[int(t * 14 / 1000 + i * 3) % len(frames)]
            fx = x - 14 - i * 13 - (i % 2) * 4
            fy = foot - 27 - 6 - (i % 3) * 3
            gfx.blit(fimg, fx, fy, 1)
        gfx.blit(img, x, foot - 27 * 2, 2)
        if st.waiting:
            gfx.bubble(x + 30, foot - 54, "JENNY!", INK, WHITE, font.sins)

    def draw_chocolates(self, units, x, y, blink):
        # the box: gold trim, dark tray, 2 rows of 5
        gfx.box(x, y, 65, 19, (214, 172, 76))
        gfx.box(x + 1, y + 1, 63, 17, (66, 36, 22))
        full, half, gone = self.chocs
        for i in range(10):
            if units is None:
                img = gone
            else:
                left = units - i * 2
                img = full if left >= 2 else (half if left == 1 else gone)
                if blink and img is not gone:
                    img = gone
            screen.blit(img, vec2(x + 3 + (i % 5) * 12, y + 2 + (i // 5) * 8))

    def draw_hud(self, st, t):
        p = self.playing(st, t)
        if p is not None and self.action == "refill":
            keep = st.hearts
            k = min(1.0, max(0.0, (p - 0.3) / 0.6))
            st.hearts = int(self.refill_from + (20 - self.refill_from) * k)
            self.hud(st, t)
            st.hearts = keep
            return
        self.hud(st, t)
        self.last_hearts = st.hearts

    def hud(self, st, t):
        gfx.box(0, 0, 160, 22, CREAM)
        gfx.box(0, 21, 160, 1, (200, 180, 150))
        low = st.hearts is not None and st.hearts <= 4
        self.draw_chocolates(st.hearts, 1, 1, low and S.blink(t, 300))
        # time until the box refills (the 5-hour window resets)
        screen.blit(self.clock, vec2(69, 2))
        gfx.text(gfx.countdown(st.left5), 76, -2, gfx.countdown_color(st.left5, INK, (190, 120, 20), RED), font.sins)
        miles = str(min(st.tools, 99999))
        w = gfx.width(miles, font.sins)
        gfx.text(miles, 158 - w, -2, INK, font.sins)
        screen.blit(self.shoe, vec2(int(158 - w - 9), 2))
        # the weekly budget as a road from coast to coast
        gfx.box(69, 13, 88, 6, (96, 92, 92))
        if st.week is not None:
            fw = int(88 * st.week)
            gfx.box(69, 13, fw, 6, (76, 72, 72))
            for x in range(71, 69 + fw - 4, 10):
                gfx.box(x, 15, 5, 2, (255, 224, 90))
            gfx.box(69 + fw - 2, 12, 3, 8, RED)
        if not st.online and S.blink(t, 600):
            gfx.text("?", 62, -2, RED, font.sins)

    def draw_caption(self, st, t):
        gfx.box(0, 108, 160, 12, (30, 24, 20))
        msg = self.caption(st, t)
        gfx.ctext(gfx.fit(msg, 156, font.sins), 80, 107, CREAM, font.sins)

    def caption(self, st, t):
        if not st.online:
            return st.net or "WAITING AT THE BUS STOP..."
        if self.playing(st, t) is not None:
            return CAPTIONS[self.action]
        if st.waiting and (t // 2500) % 2 == 0:
            return "%d SESSION%s NEED YOU" % (st.waiting, "" if st.waiting == 1 else "S")
        if st.hearts is not None and st.hearts <= 4 and (t // 3000) % 2:
            return "I'M PRETTY TIRED... %d CHOCOLATE%s LEFT" % ((st.hearts + 1) // 2, "" if (st.hearts + 1) // 2 == 1 else "S")
        tc = S.tier_caption(st, t, "RUNNING INTO HYPERSPACE!")
        if tc:
            return tc
        lv = st.level
        alt = (t // 3500) % 2
        if lv == S.SLEEP:
            return "LIFE IS LIKE A BOX OF" if alt == 0 else "CHOCOLATES..."
        if lv == S.IDLE:
            return "MAMA ALWAYS SAID..." if alt == 0 else "STUPID IS AS STUPID DOES"
        if lv == S.WALK:
            return "I JUST FELT LIKE RUNNING"
        n = max(1, st.agents)
        if lv == S.RUN:
            return "RUN, FORREST, RUN!" if alt == 0 else "%d AGENTS RUNNING" % n
        return "RUN, FORREST, RUN!!" if alt == 0 else "%d FOLLOWERS, %d TOOLS/MIN" % (n, st.tpm)

    # ------------------------------------------------------------ the activities
    def runner(self, st, t, arms=None, x=70, dy=0):
        """Draw him mid-stride (with the followers the level calls for); arms swaps the arm pose."""
        lv = st.level
        foot = 104
        fps = 11 if lv == S.WALK else (13 if lv == S.RUN else 15)
        if arms is None:
            frames = self.jog if lv == S.WALK else (self.run if lv == S.RUN else self.sprint)
        else:
            frames = self.arms[arms]
            fps = fps * STRIDES / 8.0          # half the frames, each shown twice as long
        followers = 0 if lv == S.WALK else min(max(st.agents - 1, 1 if lv == S.SPRINT else 0), 7)
        for i in range(followers - 1, -1, -1):
            ff = self.crowd[i % len(self.crowd)]
            gfx.blit(ff[int(t * 14 / 1000 + i * 3) % len(ff)], x - 14 - i * 13 - (i % 2) * 4,
                     foot - 27 - 6 - (i % 3) * 3, 1)
        gfx.blit(self.frame(frames, t, fps), x, foot - 27 * 2 - dy, 2)

    def word(self, s, x, y, c, shadow=INK):
        gfx.text(s, x, y, c, font.sins, shadow=shadow)

    def act_edit(self, st, t, p):
        """A ping-pong rally against the half-folded practice table."""
        shift = 16 * min(1.0, p / 0.08, (1.0 - p) / 0.08)     # he drifts left to make room
        x = 70 - shift
        # table: playing half flat, far half folded up as a backboard
        top, wall = (24, 64, 132), WHITE
        gfx.box(114, 84, 28, 4, top)
        gfx.box(114, 84, 28, 1, wall)
        gfx.box(141, 56, 4, 32, top)
        gfx.box(141, 56, 1, 32, wall)
        gfx.box(140, 79, 1, 5, WHITE)                  # net at the fold
        for lx in (116, 138):
            gfx.box(lx, 88, 2, 16, (70, 70, 76))
        # ball: paddle -> bounce on the table -> backboard -> bounce -> paddle, 4 rallies
        hits = 4
        k = (p * hits) % 1.0
        px = x + 48
        pts = ((px, 64), (124, 83), (140, 66), (122, 83), (px, 64))
        seg = min(3, int(k * 4))
        f = k * 4 - seg
        x0, y0 = pts[seg]
        x1, y1 = pts[seg + 1]
        bx = x0 + (x1 - x0) * f
        by = y0 + (y1 - y0) * f - math.sin(f * math.pi) * 5
        swing = k > 0.85 or k < 0.15
        self.runner(st, t, "paddle_swing" if swing else "paddle_ready", x=x)
        gfx.box(bx - 1, by - 1, 5, 5, INK)
        gfx.box(bx, by, 3, 3, WHITE)
        if swing:
            self.word("PING!", x + 30, 40, WHITE)
        elif 0.35 < k < 0.65:
            self.word("PONG!", 118, 40, WHITE)

    def act_read(self, st, t, p):
        """Opens the box of chocolates and tries one: you never know what you're gonna get."""
        if p < 0.25:
            arms = "box"
        elif p < 0.5:
            arms = "box_open"
        else:
            arms = "box_eat"
        self.runner(st, t, arms)
        if 0.25 <= p < 0.5:
            gfx.bubble(104, 50, "WHAT'LL I GET?", INK, WHITE, font.sins)
        elif p >= 0.6:
            gfx.bubble(104, 50, "MMM. NOUGAT.", INK, WHITE, font.sins)

    def act_shell(self, st, t, p):
        """Swings a shrimp net and a shrimp flips out over his head."""
        arms = "net_up" if p < 0.3 else "net_down"
        self.runner(st, t, arms)
        if p >= 0.35:
            q = (p - 0.35) / 0.65
            sx = 122 - q * 70
            sy = 76 - math.sin(q * math.pi) * 46
            gfx.blit(self.shrimp, sx, sy, 2, (int(q * 6) % 2) == 1)
            if q > 0.2:
                self.word("SHRIMP!", 116, 52, (250, 160, 160))

    def act_web(self, st, t, p):
        """Reporters run alongside and ask him why he's running."""
        foot = 104
        q = min(1.0, p / 0.22) if p < 0.88 else 1.0 - (p - 0.88) / 0.12
        rx = -34 + q * 72                                      # the reporter ends at 38, just behind him
        cx = rx - 30
        ry, cy = foot - 27 - 5, foot - 27 - 7
        gfx.blit(self.frame(self.cameraman, t + 300, 12), cx, cy, 1)
        gfx.box(cx + 9, cy + 4, 9, 5, (50, 50, 56))            # shoulder camera
        gfx.box(cx + 18, cy + 5, 2, 3, (20, 20, 24))
        gfx.box(cx + 10, cy + 5, 1, 1, (255, 255, 255))
        gfx.blit(self.frame(self.reporter, t, 12), rx, ry, 1)
        gfx.box(rx + 18, ry + 11, 6, 1, (70, 70, 76))          # microphone held out to him
        gfx.box(rx + 23, ry + 9, 3, 3, (20, 20, 24))
        self.runner(st, t)
        if 0.22 <= p < 0.55:
            gfx.bubble(int(rx) + 14, foot - 32, "WHY ARE YOU RUNNING?", INK, WHITE, font.sins)
        elif 0.55 <= p < 0.88:
            gfx.bubble(102, 50, "I JUST FELT LIKE RUNNING.", INK, WHITE, font.sins)

    def act_spawn(self, st, t, p):
        """A new follower jogs in from the left and falls in behind him."""
        foot = 104
        q = min(1.0, p / 0.45)
        fx = -30 + q * 86                              # ends at 56, just behind him
        ff = self.crowd[1]
        gfx.blit(ff[int(t * 16 / 1000) % len(ff)], fx, foot - 27 - 6, 1)
        self.runner(st, t)
        if p > 0.45:
            self.word("+1", fx + 10, foot - 52, BLUE, shadow=WHITE)

    def act_back(self, st, t, p):
        """The subagent finishes: the follower waves and peels off to the left."""
        foot = 104
        fx = 56 - p * 90
        ff = self.crowd[1]
        gfx.blit(ff[int(t * 12 / 1000) % len(ff)], fx, foot - 27 - 6 + p * 4, 1, True)
        self.runner(st, t)
        if p < 0.6:
            self.word("DONE!", fx + 4, foot - 52, BLUE, shadow=WHITE)

    def act_fail(self, st, t, p):
        """Shot in the buttocks: something zings in from behind, he jumps, grabs his behind and
        runs on holding it. "OW!" carries the meaning, not the colour."""
        rear_x, rear_y = 94, 84                                # the seat of his shorts at x 70
        if p < 0.2:
            self.runner(st, t)
            k = p / 0.2                                        # a zing from off screen, left
            zx = -10 + (rear_x + 10) * k
            screen.pen = color.rgb(255, 255, 255, 220)
            screen.rectangle(int(zx) - 14, rear_y, 14, 1)
            screen.pen = color.rgb(255, 255, 255, 110)
            screen.rectangle(int(zx) - 26, rear_y, 12, 1)
            return
        if p < 0.45:
            k = (p - 0.2) / 0.25
            hop = int(math.sin(k * math.pi) * 10)
            self.runner(st, t, "jolt", dy=hop)
            hx, hy = rear_x - 6, rear_y - hop                  # the hit, just behind him
            r0, r1 = 3 + k * 3, 8 + k * 7
            for i in range(8):
                a = i * 0.785
                for o, c in ((1, (213, 94, 0)), (0, (245, 160, 90))):
                    screen.pen = color.rgb(c[0], c[1], c[2], int(255 * (1 - k * 0.5)))
                    screen.line(int(hx + math.cos(a) * r0) + o, int(hy + math.sin(a) * r0),
                                int(hx + math.cos(a) * r1) + o, int(hy + math.sin(a) * r1))
            if k < 0.5:
                screen.pen = color.rgb(255, 255, 255, 230)
                screen.shape(shape.circle(hx, hy, 3 - 4 * k))
            self.word("OW!", rear_x - 30, rear_y - hop - 24, VERMILLION, shadow=WHITE)
            return
        self.runner(st, t, "clutch")
        if p < 0.9:
            gfx.bubble(78, 40, "SOMETHING BIT ME!", INK, WHITE, font.sins)

    def act_done(self, st, t, p):
        """The road runs out at the ocean: he stops, looks at it, turns around and runs back."""
        foot = 104
        x = 70 - 22 * min(1.0, p / 0.3)                       # he eases left as the shore arrives
        edge = 160 - 52 * min(1.0, p / 0.3)                   # the waterline slides in to x 108
        gfx.box(edge - 18, 84, 178 - edge, 24, (234, 216, 170))            # sand over the road
        gfx.box(edge - 18, 84, 178 - edge, 1, (250, 236, 200))
        gfx.box(edge, 60, 160 - edge, 38, (40, 112, 190))                  # the ocean, out to the horizon
        gfx.box(edge, 60, 160 - edge, 2, (110, 170, 225))
        for i in range(6):                                                 # waves
            wx = edge + 3 + (i * 17 + t // 80) % max(1, int(160 - edge - 6))
            gfx.box(wx, 66 + i * 5, 5, 1, (200, 226, 248))
        sw = int(2 * math.sin(t / 220.0))
        gfx.box(edge - 6 + sw, 97, 166 - edge, 2, (250, 250, 255))         # surf on the sand
        if p < 0.3:
            self.runner(st, t, x=int(x))
        elif p < 0.62:
            gfx.blit(self.still, x, foot - 27 * 2 - 2, 2)
            if p > 0.36:
                gfx.bubble(88, 50, "MIGHT AS WELL TURN AROUND.", INK, WHITE, font.sins)
        else:
            k = (p - 0.62) / 0.38
            gfx.blit(self.frame(self.jog, t, 11), x - k * 52, foot - 27 * 2, 2, True)   # running back

    def act_prompt(self, st, t, p):
        """A drill sergeant leans in from the left and barks; he stops and salutes."""
        foot = 104
        sx = -40 + 20 * min(1.0, p / 0.15)                    # half of him, at the left edge
        gfx.blit(self.sergeant, sx, foot - 27 * 2 - 2, 2)
        hx, hy = sx + 28, foot - 56 + 4                        # his head (the figure's head at 2x)
        screen.pen = gfx.rgb((120, 88, 44))
        screen.triangle(int(hx - 6), int(hy + 1), int(hx), int(hy - 8), int(hx + 6), int(hy + 1))
        gfx.box(hx - 1, hy - 7, 2, 4, (88, 62, 28))           # the pinch on the crown
        gfx.box(hx - 11, hy + 1, 22, 2, (120, 88, 44))        # the wide brim of the campaign hat
        if p < 0.3:
            self.runner(st, t)
            gfx.bubble(int(hx) + 4, int(hy) - 6, "GUMP!", INK, WHITE, font.sins)
        else:
            gfx.blit(self.salute, 70, foot - 27 * 2 - 2, 2)
            if p < 0.45:                                       # the snap of the salute
                for dx, dy, w in ((126, 54, 5), (127, 59, 4), (126, 64, 5)):
                    gfx.box(dx, dy, w, 1, (255, 255, 255))
            if p > 0.38:
                gfx.bubble(104, 50, "YES, DRILL SERGEANT!", INK, WHITE, font.sins)

    def act_arrive(self, st, t, p):
        """A cut to the bus-stop bench: he sits, says hello, stands up and runs off."""
        foot = 104
        self.draw_park(st, t)
        if p < 0.65:
            gfx.blit(self.sit, 34, 44, 2)
            if p > 0.1:
                gfx.bubble(62, 46, "HELLO.", INK, WHITE, font.sins)
        elif p < 0.82:
            gfx.blit(self.stand, 92, foot - 27 * 2 - 2, 2)
        else:
            gfx.blit(self.frame(self.jog, t, 11), 92 + (p - 0.82) * 300, foot - 27 * 2, 2)

    def act_refill(self, st, t, p):
        """A fresh box drops in and the chocolates in the top bar fill back up."""
        self.runner(st, t, "box" if p > 0.3 else None)
        if p < 0.3:
            q = p / 0.3
            gfx.blit(self.big_box, 104, 22 + q * 40, 2)
        if p > 0.3:
            for i in range(6):                         # gold sparkle on the top bar as it fills
                gfx.box(8 + (i * 11 + int(p * 60)) % 58, 3 + (i * 5) % 14, 1 + (i % 2), 1 + (i % 2), GOLD)
            self.word("NEW BOX!", 98, 40, GOLD)
