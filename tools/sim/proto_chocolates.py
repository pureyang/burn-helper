#!/usr/bin/env python3
"""Prototype: one-shot agent-activity animations for the chocolates (Forrest) theme.

    python3 tools/sim/proto_chocolates.py    -> tools/sim/out/proto/chocolates_*.png + chocolates.json

Each activity plays once (1.4-2.2 s) over the run, then the normal animation resumes.
He keeps jogging through most of them; "done" and "arrive" stop him for a moment.
Simulator only for now: nothing here is on the badge yet.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto_common as P  # noqa: E402  (installs the picovector stand-ins)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "badge", "apps", "burn_helper"))
import figure as F  # noqa: E402
import gfx  # noqa: E402
import scene as S  # noqa: E402
import theme_chocolates as C  # noqa: E402

GOLD = (255, 214, 90)
BLUE = (0, 114, 178)           # Okabe-Ito blue: something good happened
VERMILLION = (213, 94, 0)      # Okabe-Ito vermillion: something went wrong
INK = C.INK
WHITE = C.WHITE


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


PRESS = F.Spec(torso_w=4, hair="short", forearms=F.TOP, extra=_press)
JOGGER = F.Spec(torso_w=5, hair="short", hat="cap", shins=F.SKIN, extra=_props)
BEARD = F.Spec(torso_w=5, hair="long", hat="cap", beard=True, shins=F.SKIN, extra=_props)

# arms for each activity pose: (front arm, back arm, prop). Legs keep the jog/run cycle.
ARMS = {
    "paddle_ready": ((40, 30), (-20, 40), "paddle"),
    "paddle_swing": ((88, 48), (-30, 50), "paddle"),
    "box": ((60, 30), (-20, 50), "box"),
    "box_open": ((60, 30), (40, 40), "box_open"),
    "box_eat": ((60, 30), (100, 105), "box_open"),
    "net_up": ((140, 15), (-20, 50), "net"),
    "net_down": ((60, 25), (-20, 50), "net"),
    "wipe": ((100, 105), (-20, 50), None),
    "hold_up": ((150, 20), (-20, 50), None),
    "jolt": ((-35, -15), (160, 20), None),      # front hand on his behind, far arm flung up
    "clutch": ((-35, -15), (30, 70), None),     # running on, still holding it
}

# activity -> (duration ms, caption while it plays)
ACTS = {
    "edit": (1600, "EDITING: PING! PONG! PING!"),
    "read": (2000, "READING: WHAT'S IN THE BOX?"),
    "shell": (1600, "RUNNING A COMMAND: SHRIMP!"),
    "web": (2600, "SEARCHING THE WEB"),
    "spawn": (2000, "A SUBAGENT JOINS THE RUN"),
    "spawn_back": (1400, "THE SUBAGENT IS BACK"),
    "fail": (1800, "OW! A TOOL CALL FAILED"),
    "done": (2800, "END OF THE ROAD: TURN DONE"),
    "prompt": (2200, "NEW ORDERS FROM YOU"),
    "arrive": (2200, "A NEW SESSION SITS DOWN"),
    "refill": (2000, "A NEW BOX! USAGE RESET"),
}

SHRIMP = ("..pp...", ".pPPp..", "pPPPPpa", ".pPPPa.", "..pa.a.")
SHRIMP_KEYS = {"p": (232, 112, 120), "P": (250, 160, 160), "a": (200, 80, 90)}
ENVELOPE = ("WWWWWWWWW", "WkWWWWWkW", "WWkWWWkWW", "WWWkWkWWW", "WWWWkWWWW", "WWWWWWWWW")
ENVELOPE_KEYS = {"W": (255, 255, 250), "k": (150, 140, 130)}
SMILEY = ("YYYYYYY", "YYkYkYY", "YYkYkYY", "YYYYYYY", "YkYYYkY", "YYkkkYY", "YYYYYYY")
SMILEY_KEYS = {"Y": (255, 214, 60), "k": (60, 40, 20)}
THUMB = ("..o...", ".oSo..", ".oSo..", "ooSooo", "oSSSSo", "oSSSSo", ".oooo.")
THUMB_KEYS = {"o": (34, 22, 16), "S": (246, 196, 150)}


class Theme(C.Theme):
    """The chocolates theme plus the proposed one-shot activity animations."""

    def __init__(self):
        super().__init__()
        self.action = None
        self.action_t0 = 0
        self.refill_from = 4

    def start(self, key, t):
        self.action = key
        self.action_t0 = t

    def phase(self, t):
        """0..1 through the current action, or None when nothing is playing."""
        if not self.action:
            return None
        p = (t - self.action_t0) / float(ACTS[self.action][0])
        return p if 0 <= p < 1 else None

    def build(self):
        super().build()
        self.p_run = C.pal()
        self.p_run[F.TOP] = gfx.rgb((236, 106, 40))
        self.p_run[F.TOP_D] = gfx.rgb((184, 76, 26))
        self.p_run[F.BOT] = gfx.rgb((40, 60, 140))
        self.p_run[F.BOT_D] = gfx.rgb((26, 40, 100))
        self.poses = {}
        self.shrimp = gfx.sprite(SHRIMP, SHRIMP_KEYS)
        self.envelope = gfx.sprite(ENVELOPE, ENVELOPE_KEYS)
        self.smiley = gfx.sprite(SMILEY, SMILEY_KEYS)
        self.thumb = gfx.sprite(THUMB, THUMB_KEYS)
        self.big_box = gfx.sprite(("GGGGGGGGGG", "GddddddddG", "GdMdMdMdMG", "GddddddddG", "GdMdMdMdMG",
                                   "GddddddddG", "GGGGGGGGGG"),
                                  {"G": (214, 172, 76), "d": (66, 36, 22), "M": (150, 90, 46)})
        # standing still, and saluting (for "prompt")
        self.still = gfx.to_image(F.render(JOGGER, F.stand()), self.p_run)
        self.salute = gfx.to_image(F.render(JOGGER, F.stand(af=(100, 80))), self.p_run)    # hand at the cap's brim
        # the drill sergeant, half off screen on the left, pointing at him (for "prompt")
        p_sgt = C.pal()
        p_sgt[F.TOP] = gfx.rgb((96, 110, 64))
        p_sgt[F.TOP_D] = gfx.rgb((72, 84, 48))
        p_sgt[F.BOT] = gfx.rgb((96, 110, 64))
        p_sgt[F.BOT_D] = gfx.rgb((72, 84, 48))
        p_sgt[F.HAIR] = gfx.rgb((60, 44, 30))
        self.sergeant = gfx.to_image(F.render(C.SUIT, F.stand(af=(95, 0), mouth=True)), p_sgt)
        # the press: a reporter with a microphone and a cameraman (for "web")
        p_rep, p_cam = C.pal(), C.pal()
        for pp, top, hair in ((p_rep, (84, 92, 120), (40, 30, 24)), (p_cam, (150, 110, 70), (190, 150, 90))):
            pp[F.TOP] = gfx.rgb(top)
            pp[F.TOP_D] = gfx.rgb((top[0] * 3 // 4, top[1] * 3 // 4, top[2] * 3 // 4))
            pp[F.BOT] = gfx.rgb((60, 60, 70))
            pp[F.BOT_D] = gfx.rgb((40, 40, 50))
            pp[F.HAIR] = gfx.rgb(hair)
            pp[F.ACC3] = gfx.rgb((60, 60, 66))
            pp[F.ACC4] = gfx.rgb((255, 255, 255))
        self.reporter = [gfx.to_image(g, p_rep) for g in F.cycle(PRESS, "jog", 8, af=(75, 40), prop="mic")]
        self.cameraman = [gfx.to_image(g, p_cam) for g in F.cycle(PRESS, "jog", 8, af=(150, 60), prop="camera")]

    def cycle(self, lv, arms):
        """The jog (or run) cycle with the arms and prop swapped in; built once on first use."""
        spec, gait = (JOGGER, "jog") if lv == S.WALK else (BEARD, "run" if lv == S.RUN else "sprint")
        key = (gait, arms)
        if key not in self.poses:
            af, ab, prop = ARMS[arms]
            self.poses[key] = [gfx.to_image(g, self.p_run)
                               for g in F.cycle(spec, gait, 8, af=af, ab=ab, prop=prop)]
        return self.poses[key]

    def advance(self, st, t):
        p = self.phase(t)
        if p is not None and self.action in ("done", "arrive", "prompt"):
            self.last_t = t            # he stops: the road stops scrolling
            return
        super().advance(st, t)

    def caption(self, st, t):
        if self.phase(t) is not None and st.online:
            return ACTS[self.action][1]
        return super().caption(st, t)

    def draw_hud(self, st, t):
        p = self.phase(t)
        if p is not None and self.action == "refill":
            keep = st.hearts
            k = min(1.0, max(0.0, (p - 0.3) / 0.6))
            st.hearts = int(self.refill_from + (20 - self.refill_from) * k)
            super().draw_hud(st, t)
            st.hearts = keep
            return
        super().draw_hud(st, t)

    # ------------------------------------------------------------ the figure
    def draw_hero_figure(self, st, t):
        p = self.phase(t)
        if p is None or st.level <= S.IDLE:
            super().draw_hero_figure(st, t)
            return
        getattr(self, "act_" + self.action)(st, t, p)

    def runner(self, st, t, arms=None, x=70, dy=0):
        """Draw him mid-stride (with the followers the level calls for); arms swaps the arm pose."""
        lv = st.level
        foot = 104
        fps = {S.WALK: 11, S.RUN: 13}.get(lv, 15)
        if arms is None:
            frames = self.jog if lv == S.WALK else (self.run if lv == S.RUN else self.sprint)
        else:
            frames = self.cycle(lv, arms)
        followers = 0 if lv == S.WALK else min(max(st.agents - 1, 1 if lv == S.SPRINT else 0), 7)
        for i in range(followers - 1, -1, -1):
            ff = self.crowd[i % len(self.crowd)]
            gfx.blit(ff[int(t * 14 / 1000 + i * 3) % len(ff)], x - 14 - i * 13 - (i % 2) * 4,
                     foot - 27 - 6 - (i % 3) * 3, 1)
        gfx.blit(self.frame(frames, t, fps), x, foot - 27 * 2 - dy, 2)

    def word(self, s, x, y, c, shadow=INK):
        gfx.text(s, x, y, c, font.sins, shadow=shadow)

    # ------------------------------------------------------------ activities
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
        (x0, y0), (x1, y1) = pts[seg], pts[seg + 1]
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

    def act_spawn_back(self, st, t, p):
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
                a = t / 150.0 + i
                gfx.box(8 + (i * 11 + int(p * 60)) % 58, 3 + (i * 5) % 14, 1 + (i % 2), 1 + (i % 2), GOLD)
            self.word("NEW BOX!", 98, 40, GOLD)


# ---------------------------------------------------------------- render the frames
BASE_T = 5200
SHOTS = (
    # key, frame phases, status overrides
    ("edit", (0.22, 0.4, 0.62, 0.76), {}),
    ("read", (0.12, 0.35, 0.65, 0.9), {}),
    ("shell", (0.15, 0.45, 0.6, 0.8), {}),
    ("web", (0.12, 0.35, 0.65, 0.8), {}),
    ("spawn", (0.12, 0.3, 0.6, 0.9), {}),
    ("fail", (0.12, 0.27, 0.38, 0.7), {}),
    ("done", (0.15, 0.45, 0.7, 0.9), {}),
    ("prompt", (0.12, 0.25, 0.4, 0.8), {}),
    ("arrive", (0.05, 0.4, 0.72, 0.9), {}),
    ("refill", (0.1, 0.25, 0.55, 0.9), {"hearts": 20}),
)

TEXT = {
    "edit": ("Ping-pong rally",
             "He pulls out a paddle and rallies off a half-folded practice table, a few hits per edit.",
             "16 extra figure frames (2 arm poses x 8 strides), the table is 8 rectangles. Bridge: send "
             "the tool category of each PostToolUse."),
    "read": ("Box of chocolates",
             "He opens the box while jogging and tries one. You never know what you're gonna get.",
             "24 extra figure frames (3 arm poses); the box is drawn into the figure. Could share 4-stride "
             "cycles to halve that."),
    "shell": ("Shrimp net",
              "A quick swing of a shrimp net, and a shrimp flips out over his head.",
              "16 extra figure frames plus a 7x5 shrimp sprite."),
    "web": ("Reporters",
            "A reporter and a cameraman run alongside. \"WHY ARE YOU RUNNING?\" \"I JUST FELT LIKE RUNNING.\"",
            "16 small press frames (2 figures x 8 strides, 1x like the crowd), mic and camera drawn into "
            "them. Bridge: send the tool category of each PostToolUse (WebFetch, WebSearch)."),
    "spawn": ("A new follower",
              "A new runner jogs in from the left and falls in behind him. When the subagent finishes it "
              "says DONE and peels off (last frame).",
              "Reuses the crowd frames. Bridge: SubagentStart and SubagentStop are already counted; the "
              "badge needs the events themselves (or the change in the subagent count)."),
    "fail": ("Shot in the buttocks",
             "Something zings in from behind and gets him in the buttocks. He jumps, grabs his behind and "
             "runs on holding it: \"SOMETHING BIT ME!\"",
             "16 extra figure frames (2 arm poses x 8 strides); the zing and the hit are lines. OW! is in "
             "vermillion with a white outline, so it reads without colour too. Bridge: PostToolUseFailure "
             "is already hooked."),
    "done": ("Turns around at the ocean",
             "The road runs out at the ocean. He stops, looks at it (\"MIGHT AS WELL TURN AROUND.\") and runs "
             "back the way he came: the end of a turn.",
             "One standing frame; the beach and sea are rectangles, the run back is the jog flipped. The road "
             "stops scrolling while he stands. Bridge: send Stop as an event."),
    "prompt": ("Drill sergeant",
               "A drill sergeant leans in from the left and barks \"GUMP!\". He stops dead and salutes: \"YES, "
               "DRILL SERGEANT!\"",
               "Two standing frames (the salute and the sergeant); the campaign hat is a triangle and two boxes. "
               "Bridge: UserPromptSubmit is already hooked."),
    "arrive": ("Bus-stop bench",
               "A quick cut to the bench: he sits, says hello, stands up and runs off, then back to the road.",
               "Reuses the theme's park scene and sitting and standing frames, so nothing new. Bridge: "
               "SessionStart as an event."),
    "refill": ("New box of chocolates",
               "A full box drops into his hands and the chocolates in the top bar fill back up one by one.",
               "8 extra figure frames (shares the box pose with read). Worked out on the badge when the "
               "5-hour reset time passes, so no bridge change."),
}


def review_sheets(shots, per=3, scale=2):
    """Contact sheets of the rendered frames (3 activities each) for checking by eye."""
    import pvshim
    names = []
    for k in range(0, len(shots), per):
        group = shots[k:k + per]
        tw, th, pad = 160 * scale, 120 * scale, 4
        big = pvshim.image(4 * (tw + pad) + pad, len(group) * (th + pad) + pad)
        big.pen = pvshim.color(40, 40, 48)
        big.clear()
        for r, (key, imgs) in enumerate(group):
            for c, img in enumerate(imgs):
                big.blit(img, pvshim.rect(pad + c * (tw + pad), pad + r * (th + pad), tw, th))
        name = os.path.join(P.OUT, "chocolates_review_%d.png" % (k // per))
        big.to_png(name, 1)
        names.append(name)
    return names


def main():
    import pvshim
    items = []
    shots = []
    for key, phases, over in SHOTS:
        th = Theme()
        kw = dict(level=S.WALK, agents=3, hearts=12)
        kw.update(over)
        level = kw.pop("level")
        st = P.status(**kw)
        if level != st.level:
            st.level = level
        frames = []
        imgs = []
        for i, p in enumerate(phases):
            th.start(key, BASE_T)
            th.last_t = None
            t = BASE_T + int(p * ACTS[key][0])
            # warm-up frames must not start the action early: keep them before it
            if key == "spawn" and i == 3:
                th.start("spawn_back", BASE_T)
                t = BASE_T + int(0.3 * ACTS["spawn_back"][0])
            scr = P.render(th, st, t)
            frames.append(P.save(scr, "chocolates", key, i))
            copy = pvshim.image(160, 120)
            copy.blit(scr, pvshim.vec2(0, 0))
            imgs.append(copy)
        shots.append((key, imgs))
        title, desc, notes = TEXT[key]
        items.append({"key": key, "title": title, "desc": desc, "frames": frames, "notes": notes})
    print(P.write_manifest("chocolates", items))
    if "--review" in sys.argv:
        print(review_sheets(shots))
    for it in items:
        print(it["key"], it["frames"])


if __name__ == "__main__":
    main()
