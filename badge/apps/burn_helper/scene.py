# Shared scene machinery for the themes: status model, scrolling layers, timing.

import math
import time
import gfx
import fx

W = gfx.W
H = gfx.H

# activity levels reported by the bridge
SLEEP, IDLE, WALK, RUN, SPRINT = 0, 1, 2, 3, 4

# What an agent just did (the bridge's "ev" feed), most telling first: when several arrive
# together, the badge plays the first of them.
ACT_ORDER = ("fail", "done", "spawn", "back", "prompt", "arrive", "refill", "shell", "web", "edit", "read")
ACT_RANK = {k: i for i, k in enumerate(ACT_ORDER)}
ACT_FRESH_MS = 6000     # older than this when it arrives (or while it waits its turn): skip it

# hero gait per level and frames-per-second of its cycle
GAIT = {WALK: ("walk", 9), RUN: ("run", 13), SPRINT: ("sprint", 16)}
# background scroll speed in pixels per second
SPEED = {SLEEP: 0, IDLE: 0, WALK: 18, RUN: 46, SPRINT: 78}

# Activity tiers by how many agents are working (busy sessions + running subagents):
# 1 to 10 one agent at a time, then 11-25, 26-50, 51-75, 76-100, and ULTRA above 100.
MAX_TIER = ULTRA = 15
BANDS = ((25, 11), (50, 12), (75, 13), (100, 14))
TIER_TEXT = {11: "11-25", 12: "26-50", 13: "51-75", 14: "76-100", 15: "100+"}


def tier_for(agents):
    if agents <= 0:
        return 0
    if agents <= 10:
        return agents
    for top, tier in BANDS:
        if agents <= top:
            return tier
    return ULTRA


def gait_for(tier):
    """The level whose gait a tier uses: walk for 1-3, run for 4-7, sprint from 8."""
    return WALK if tier <= 3 else (RUN if tier <= 7 else SPRINT)


def tier_caption(st, t, ultra_line):
    """A caption for the top tiers, or None to let the theme use its own."""
    if st.tier >= ULTRA:
        return ultra_line if (t // 2500) % 2 == 0 else "%d AGENTS: ULTRA" % st.agents
    if st.tier > 10 and (t // 3000) % 2:
        return "%d AGENTS AT WORK" % st.agents
    return None


# the scene area between the themes' top bar and caption, where tier effects are drawn
FX_TOP, FX_BOTTOM = 22, 108


class Status:
    """What the themes draw. Filled from the bridge's /status JSON."""

    def __init__(self):
        self.level = SLEEP
        self.hearts = None      # remaining 5-hour budget, half units 0..20
        self.week = None        # remaining 7-day budget, 0..1
        self.busy = 0
        self.agents = 0         # busy sessions + running subagents
        self.tier = 0           # 0 none working, 1..MAX_TIER (see tier_for)
        self.waiting = 0
        self.waiting_list = []  # [{n: name, s: seconds waiting, d: folder, w: why, a: session age}], longest first
        self.idle = 0
        self.sessions = 0
        self.subagents = 0
        self.tpm = 0
        self.tools = 0
        self.online = False     # fresh data from the bridge
        self.net = "BOOTING"    # short network state for overlays
        self.clock = ""
        self.demo = False
        # One thing an agent just did, for the theme to animate once (see Theme.ACTIONS). The
        # app moves `pending` into `act` when the theme is free; the demos set `act` directly.
        self.act = None         # "edit", "read", "shell", "web", "spawn", "back", "fail", "done", "prompt", "arrive", "refill"
        self.act_t = 0          # ticks_ms when it started
        self.act_seq = 0        # a new number for every new activity
        self.pending = None     # the most telling activity not played yet
        self.pending_t = 0
        self.ev_seen = None     # the bridge's number for the newest activity already handled
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
        old = self.hearts
        self.hearts = d.get("hearts")
        if old is not None and self.hearts is not None and self.hearts >= old + 6:
            self.queue("refill")            # the 5-hour window reset: the hearts jumped back up
        self.take_events(d.get("ev"))
        wk = d.get("seven_day")
        self.week = None if not wk else max(0.0, min(1.0, (100.0 - float(wk.get("used", 0))) / 100.0))
        fh = d.get("five_hour") or {}
        self.used5 = fh.get("used")
        self.reset5 = fh.get("resets_at")
        self.used7 = (wk or {}).get("used")
        self.reset7 = (wk or {}).get("resets_at")
        self.busy = int(d.get("busy") or 0)
        self.waiting = int(d.get("waiting") or 0)
        wl = []
        for w in d.get("waiting_list") or []:
            try:
                wl.append({"n": str(w.get("n") or "session")[:24], "s": int(w.get("s") or 0),
                           "d": str(w.get("d") or "")[:24], "w": str(w.get("w") or "")[:24],
                           "a": int(w.get("a") or 0)})
            except (AttributeError, TypeError, ValueError):
                pass
        self.waiting_list = wl[:4]
        self.idle = int(d.get("idle") or 0)
        self.sessions = int(d.get("sessions") or 0)
        self.subagents = int(d.get("subagents") or 0)
        self.tpm = int(d.get("tpm") or 0)
        self.tools = int(d.get("tools_today") or 0)
        self.set_agents(self.busy + self.subagents)
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

    def take_events(self, ev):
        """Queue the most telling new activity from the bridge's feed: [[number, kind, ms ago]]."""
        if ev is None:
            return                          # an older bridge without the feed
        if not ev:
            if self.ev_seen is None:
                self.ev_seen = 0            # nothing recent: whatever comes next is new
            return
        top = None
        best = None
        for e in ev:
            try:
                n, kind, age = int(e[0]), str(e[1]), int(e[2])
            except (TypeError, ValueError, IndexError):
                continue
            if top is None or n > top:
                top = n
            if self.ev_seen is not None and n > self.ev_seen and age < ACT_FRESH_MS and kind in ACT_RANK:
                if best is None or ACT_RANK[kind] < ACT_RANK[best]:
                    best = kind
        if top is None:
            return
        if self.ev_seen is None or top < self.ev_seen:
            # first contact, or the bridge restarted and counts from 1 again: catch up quietly
            self.ev_seen = top
            return
        self.ev_seen = top
        if best is not None:
            self.queue(best)

    def queue(self, kind):
        now = time.ticks_ms()
        if (self.pending is None or time.ticks_diff(now, self.pending_t) > ACT_FRESH_MS
                or ACT_RANK[kind] <= ACT_RANK[self.pending]):
            self.pending = kind
            self.pending_t = now

    def next_act(self, t, free):
        """Start the pending activity at t if the theme is free (nothing playing, 2 s since the
        last one). Returns True when one started."""
        if self.pending is None:
            return False
        if time.ticks_diff(t, self.pending_t) > ACT_FRESH_MS:
            self.pending = None
            return False
        if not free:
            return False
        self.act, self.act_t, self.act_seq = self.pending, t, t
        self.pending = None
        return True

    def set_agents(self, n):
        """Set the working-agent count; while any work, the tier picks the gait."""
        self.agents = max(0, int(n))
        self.tier = tier_for(self.agents)
        if self.tier:
            self.level = gait_for(self.tier)

    def tick(self):
        """Refresh the countdowns; call once per frame."""
        now = self._now_us()
        self.left5 = None if (now is None or not self.reset5) else int(self.reset5) * 1000000 - now
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
    ACTIONS = {}        # activity (Status.act) -> how long its one-shot animation plays, in ms

    def __init__(self):
        self.ready = False
        self.scroll = 0.0
        self.last_t = None
        self.level_since = 0
        self.shown_level = None
        self.action = None      # the activity animation playing, if any
        self.action_t0 = 0
        self.act_seen = 0

    def start_action(self, key, t0, st):  # noqa: ARG002
        self.action = key
        self.action_t0 = t0

    def acting(self, t):
        """How far (0..1) the activity animation is, or None when none is playing."""
        if self.action is None:
            return None
        p = (t - self.action_t0) / self.ACTIONS[self.action]
        if p >= 1:
            self.action = None
            return None
        return p if p >= 0 else None

    def build(self):
        pass

    def advance(self, st, t):
        if self.last_t is None:
            self.last_t = t
        dt = max(0, min(200, t - self.last_t)) / 1000.0
        self.last_t = t
        boost = (1.0 + min(st.tpm, 60) / 150.0) * (1.0 + 0.06 * max(0, st.tier - 1))
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
        if st.act_seq != self.act_seen:
            self.act_seen = st.act_seq
            if st.act in self.ACTIONS:
                self.start_action(st.act, st.act_t, st)
        self.advance(st, t)
        self.render(st, t)
        if st.tier:
            fx.draw(st.tier, t, FX_TOP, FX_BOTTOM)

    def render(self, st, t):
        pass


def blink(t, period=500):
    return (t // period) % 2 == 0


def bob(t, period=900, amp=1.0):
    return math.sin(t * 2 * math.pi / period) * amp
