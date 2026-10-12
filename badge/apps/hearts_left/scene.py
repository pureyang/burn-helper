# Shared scene machinery for the themes: status model, scrolling layers, timing.

import math
import time
import gfx

W = gfx.W
H = gfx.H

# activity levels reported by the bridge
SLEEP, IDLE, WALK, RUN, SPRINT = 0, 1, 2, 3, 4

# hero gait per level and frames-per-second of its cycle
GAIT = {WALK: ("walk", 9), RUN: ("run", 13), SPRINT: ("sprint", 16)}
# background scroll speed in pixels per second
SPEED = {SLEEP: 0, IDLE: 0, WALK: 18, RUN: 46, SPRINT: 78}


class Status:
    """What the themes draw. Filled from the bridge's /status JSON."""

    def __init__(self):
        self.level = SLEEP
        self.hearts = None      # remaining 5-hour budget, half units 0..20
        self.week = None        # remaining 7-day budget, 0..1
        self.busy = 0
        self.waiting = 0
        self.idle = 0
        self.sessions = 0
        self.subagents = 0
        self.tpm = 0
        self.tools = 0
        self.online = False     # fresh data from the bridge
        self.net = "BOOTING"    # short network state for overlays
        self.clock = ""
        self.demo = False
        self.used5 = None       # percent used, as reported
        self.used7 = None
        self.reset5 = None      # epoch seconds when each window resets
        self.reset7 = None
        self.left5 = None       # MICROseconds until each reset; set by tick()
        self.left7 = None
        # Bridge clock anchor. Everything is whole numbers: the badge's floats
        # are 32-bit and cannot hold an epoch time to the second.
        self._now_ms = None     # bridge time (epoch ms) at the anchor
        self._at_ms = 0         # time.ticks_ms() at the anchor
        self._at_us = 0         # time.ticks_us() at the anchor

    def update(self, d):
        self.level = int(d.get("level") or 0)
        self.hearts = d.get("hearts")
        wk = d.get("seven_day")
        self.week = None if not wk else max(0.0, min(1.0, (100.0 - float(wk.get("used", 0))) / 100.0))
        fh = d.get("five_hour") or {}
        self.used5 = fh.get("used")
        self.reset5 = fh.get("resets_at")
        self.used7 = (wk or {}).get("used")
        self.reset7 = (wk or {}).get("resets_at")
        self.busy = int(d.get("busy") or 0)
        self.waiting = int(d.get("waiting") or 0)
        self.idle = int(d.get("idle") or 0)
        self.sessions = int(d.get("sessions") or 0)
        self.subagents = int(d.get("subagents") or 0)
        self.tpm = int(d.get("tpm") or 0)
        self.tools = int(d.get("tools_today") or 0)
        self.waiting_list = []  # [(session name, seconds waiting)], longest first, if the bridge sends it
        self.clock = d.get("clock") or ""
        now_ms = d.get("now_ms")
        if now_ms is None and d.get("ts") is not None:
            now_ms = int(d.get("ts")) * 1000
        if now_ms is not None:
            self.anchor(int(now_ms))

    def anchor(self, now_ms):
        # Keep the running clock unless the bridge disagrees by over a second,
        # so network jitter never makes the countdown jump backwards.
        mine = self.now_ms()
        if mine is None or abs(mine - now_ms) > 1000:
            self._now_ms = now_ms
            self._at_ms = time.ticks_ms()
            self._at_us = time.ticks_us()

    def now_ms(self):
        if self._now_ms is None:
            return None
        return self._now_ms + time.ticks_diff(time.ticks_ms(), self._at_ms)

    def _now_us(self):
        if self._now_ms is None:
            return None
        ms = time.ticks_diff(time.ticks_ms(), self._at_ms)
        # ticks_us wraps after about 9 minutes; use it only while it is valid
        us = time.ticks_diff(time.ticks_us(), self._at_us) if ms < 500000 else ms * 1000
        return self._now_ms * 1000 + us

    def tick(self):
        """Refresh the countdowns; call once per frame."""
        now = self._now_us()
        self.left5 = None if (now is None or not self.reset5) else int(self.reset5) * 1000000 - now
        wl = []
        for w in d.get("waiting_list") or []:
            try:
                wl.append((str(w.get("n") or "session")[:24], int(w.get("s") or 0)))
            except (AttributeError, TypeError, ValueError):
                pass
        self.waiting_list = wl[:4]
        self.left7 = None if (now is None or not self.reset7) else int(self.reset7) * 1000000 - now


class Layer:
    """A horizontally tiling strip (width W) scrolled at a parallax factor."""

    def __init__(self, img, y, factor):
        self.img = img
        self.y = y
        self.factor = factor

    def draw(self, scroll):
        off = int(scroll * self.factor) % self.img.width
        screen.blit(self.img, vec2(-off, self.y))
        if self.img.width - off < W:
            screen.blit(self.img, vec2(self.img.width - off, self.y))


class Theme:
    name = "base"
    label = "BASE"

    def __init__(self):
        self.ready = False
        self.scroll = 0.0
        self.last_t = None
        self.level_since = 0
        self.shown_level = None

    def build(self):
        pass

    def advance(self, st, t):
        if self.last_t is None:
            self.last_t = t
        dt = max(0, min(200, t - self.last_t)) / 1000.0
        self.last_t = t
        boost = 1.0 + min(st.tpm, 60) / 150.0
        self.scroll += SPEED.get(st.level, 0) * boost * dt
        if self.shown_level != st.level:
            self.shown_level = st.level
            self.level_since = t

    def frame(self, frames, t, fps):
        return frames[int(t * fps / 1000) % len(frames)]

    def draw(self, st, t):
        if not self.ready:
            self.build()
            self.ready = True
        self.advance(st, t)
        self.render(st, t)

    def render(self, st, t):
        pass


def blink(t, period=500):
    return (t // period) % 2 == 0


def bob(t, period=900, amp=1.0):
    return math.sin(t * 2 * math.pi / period) * amp
