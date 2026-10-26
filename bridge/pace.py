"""Weekly pace: is this week's usage on course to reach the weekly limit before it resets?

The bridge learns from what it sees and keeps it in pace.json in its state folder, on this
computer only (the badge and the status line get the verdict, never the history):
  * the weekly percent at each report, for this week and the last few
  * when agents work, by hour of the week: the shape of a week, before whole weeks are known
  * how much of the week one full 5-hour window costs: both meters' rises between the same reports

From these it forecasts the week's use at the reset, with odds, and steps a message ladder:
  calm      nothing said; the weekly meters show where an even pace would be (the pace tick)
  watch     a run-out is likely (60%) and within 3 days: Desktop mode and the status line say when,
            and the themes' caption says it now and then while agents work (every 4 hours at most)
  heads-up  likely (85%) and within a day and a half, or 90% of the week used: the same, every 2 hours
  out       the weekly limit is reached
A louder step comes at once; a quieter one only after the forecast has stayed lower for 2 hours,
and then one "pace eased" caption. The week's first day says nothing.

Opt-in (`install.py --room-left on`): in the last 12 hours of a week with 20% or more left, one
caption says how much is left, and Desktop mode and the status line say it for those hours. It
reports what is left; it never urges anyone to use it.

The forecast reads the use so far against the usual shape of a week: by hour h a week has usually
done S(h) of its use, and usually ends at P percent. Its band comes from how wrong that reading was
on past weeks (a week that hit the limit only shows how far it got, so the fit treats it as
censored). With under two past weeks it is learning: the shape comes from when agents work (or a
weekday desk week), the total is a guess, and the band is wider. The method and every threshold
come from a study of thousands of simulated weeks, which tools/sim/test_pace.py replays against
this code.
"""
import json
import math
import os
import time
from statistics import NormalDist

H = 168                     # hours in the weekly window
HOUR = 3600
WEEK_S = H * HOUR
WEEKS_KEPT = 10             # weeks of reports kept (the forecast learns from the last LEARN_WEEKS)
LEARN_WEEKS = 8
POINT_GAP_S = 60            # at most one report kept a minute

C_PRIOR = 0.25              # how much the usual total counts against this week's own evidence
PRIOR_POINTS = 12           # how many backtest points the default band counts for
COLD_TOTAL = 60.0           # the usual total, as a percent of the week, before any week is known
ACT_MIN = 30                # minutes seen in an hour of the week before its activity counts

# the message ladder, as tuned in the study
QUIET_H = 24                # nothing said in the week's first day (unless NEAR_OUT)
WATCH_ON, WATCH_OFF = 0.60, 0.40
WARN_ON, WARN_OFF = 0.85, 0.65
WATCH_WITHIN_H = 72         # only speak of a run-out this close
WARN_WITHIN_H = 36
NEAR_OUT = 90               # this much of the week used is a heads-up whatever the forecast
DWELL_S = 2 * HOUR          # a quieter step waits until the forecast has stayed lower this long
WATCH_EVERY_S = 4 * HOUR    # captions at most this often, and only while agents work
WARN_EVERY_S = 2 * HOUR
CAPTION_S = 30              # how long one caption stays up
EASED_KEEP_S = 12 * HOUR    # the "pace eased" caption waits this long for agents to work
EASED_SHOW_S = 2 * HOUR     # Desktop mode and the status line say "pace eased" this long
ROOM_H = 12                 # the opt-in room-left note: the week's last 12 hours,
ROOM_MIN_LEFT = 20          # with at least this much left
RATE_MIN = 100              # 5-hour percent seen before the windows-left figure is trusted

DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_N = NormalDist()


def room_file(state_dir):
    return os.path.join(state_dir, "pace_room.enabled")


def room_enabled(state_dir):
    return os.path.exists(room_file(state_dir))


def set_room(state_dir, on):
    """Turn the room-left note on or off (the bridge checks it as it goes). True if it changed."""
    path = room_file(state_dir)
    if on and not os.path.exists(path):
        os.makedirs(state_dir, exist_ok=True)
        with open(path, "w") as f:
            f.write("on\n")
        return True
    if not on and os.path.exists(path):
        os.remove(path)
        return True
    return False


# ---------------------------------------------------------------- the forecast
def phi(x):
    return _N.cdf(x)


def default_spread(h):
    return 0.18 + 0.55 * math.sqrt(max(0.0, 1.0 - h / H))


def _i(h):
    return min(H, max(0, int(round(h))))


def desk(t):
    """The chance of working at local time t in a nine-to-six weekday week: the guess before
    anything is known."""
    lt = time.localtime(t)
    if lt.tm_wday < 5 and 9 <= lt.tm_hour < 18:
        return 0.8
    if lt.tm_wday < 5 and 18 <= lt.tm_hour < 22:
        return 0.15
    if lt.tm_wday >= 5 and 10 <= lt.tm_hour < 18:
        return 0.06
    return 0.01


def shape(weights):
    """The share of a week's use done by each hour (169 values, 0 to 1) from how much work each
    hour usually holds."""
    tot = sum(weights) or 1.0
    s, run = [], 0.0
    for w in weights:
        s.append(run / tot)
        run += w
    s.append(1.0)
    return s


def cold_model(weights):
    return {"S": shape(weights), "P": COLD_TOTAL, "mu": [0.0] * (H + 1),
            "sd": [default_spread(h) + 0.1 for h in range(H + 1)], "n": 0}


def curve(pts, start):
    """The weekly percent used at each hour of a week (169 values) from its reports [[t, used]]:
    straight between reports, from 0 at the start, flat after the last."""
    xs, ys = [0.0], [0.0]
    for t, u in pts:
        x = (t - start) / HOUR
        if 0 <= x <= H and x >= xs[-1]:
            xs.append(x)
            ys.append(float(u))
    out, j = [], 0
    for h in range(H + 1):
        while j + 1 < len(xs) and xs[j + 1] <= h:
            j += 1
        if j + 1 < len(xs) and xs[j + 1] > xs[j]:
            out.append(ys[j] + (ys[j + 1] - ys[j]) * (h - xs[j]) / (xs[j + 1] - xs[j]))
        else:
            out.append(ys[j])
    return out


def shape_remaining(m, u, h):
    """The use still to come this week, before the limit, by the usual shape."""
    s = min(0.995, m["S"][_i(h)])
    total = (u + C_PRIOR * m["P"]) / (s + C_PRIOR)
    return max(0.0, (1 - s) * total)


def censored_normal(pool, sd0):
    """Mean and spread of [(x, censored)], where a censored x is only a lower bound (EM)."""
    mu, sd = 0.0, sd0
    for _ in range(25):
        s1 = s2 = 0.0
        for x, cens in pool:
            if not cens:
                s1 += x
                s2 += x * x
                continue
            a = (x - mu) / sd
            tail = max(1e-9, 1 - phi(a))
            lam = math.exp(-a * a / 2) / math.sqrt(2 * math.pi) / tail
            s1 += mu + sd * lam
            s2 += mu * mu + sd * sd + sd * (x + mu) * lam
        mu = s1 / len(pool)
        sd = math.sqrt(max(0.01, s2 / len(pool) - mu * mu))
    return mu, sd


def learn(weeks):
    """A model from past weeks [(curve, hit the limit)]: the usual shape and total, and the band.

    The band is a backtest on the same weeks: the log ratio of the use that came after each hour to
    the use forecast then. A week that hit the limit stopped at 100, which hides how far it would
    have gone, so its ratios are lower bounds."""
    n = len(weeks)
    S = [0.0] * (H + 1)
    P = 0.0
    for rep, _ in weeks:
        f = max(1.0, rep[H])
        for h in range(H + 1):
            S[h] += min(1.0, rep[h] / f)
        P += rep[H]
    m = {"S": [s / n for s in S], "P": P / n, "mu": [0.0] * (H + 1), "sd": [0.0] * (H + 1), "n": n}
    bins = [[] for _ in range(H + 1)]
    for rep, hit in weeks:
        for h in range(6, H, 3):
            u = rep[h]
            if u >= 100:
                continue
            r = shape_remaining(m, u, h)
            bins[h].append((math.log((rep[H] - u + 2) / (r + 2)), 1 if hit else 0))
    for h in range(H + 1):
        d = default_spread(h)
        pool = [p for j in range(max(0, h - 9), min(H, h + 9) + 1) for p in bins[j]]
        if len(pool) < 4:
            m["sd"][h] = d
            continue
        mu, sd = censored_normal(pool, d)
        w = len(pool) / (len(pool) + PRIOR_POINTS)    # a few weeks are not much to go on
        m["mu"][h] = w * mu
        m["sd"][h] = max(0.12, w * sd + (1 - w) * d)
    return m


def eta_shape(m, u, h, rest):
    """The hour the use reaches 100, walking the usual shape forward with `rest` still to come."""
    s0 = m["S"][_i(h)]
    left = 1 - s0
    if left <= 0:
        return None
    for j in range(max(1, int(math.ceil(h))), H + 1):
        v = u + rest * (m["S"][j] - s0) / left
        if v >= 100:
            vp = u + rest * (m["S"][j - 1] - s0) / left
            return j - 1 + (100 - vp) / max(1e-6, v - vp)
    return None


def forecast(m, u, h):
    """{final, lo, hi, p, eta}: the likely use at the reset (and its 80% range), the chance it
    reaches the limit, and the hour of the week it would (None if the likely use stays under)."""
    i = _i(h)
    r = shape_remaining(m, u, h)
    need = 100 - u

    def at(q):
        return u + max(0.0, (r + 2) * math.exp(m["mu"][i] + m["sd"][i] * _N.inv_cdf(1 - q)) - 2)

    p = 1.0 if need <= 0 else 1 - phi((math.log((need + 2) / (r + 2)) - m["mu"][i]) / m["sd"][i])
    f = at(0.5)
    return {"final": f, "lo": at(0.9), "hi": at(0.1), "p": p,
            "eta": eta_shape(m, u, h, f - u) if f >= 100 else None}


# ---------------------------------------------------------------- the ladder
def wanted(h, u, fc):
    """The step the forecast calls for now: 0 calm, 1 watch, 2 heads-up."""
    if u >= NEAR_OUT:
        return 2
    if h < QUIET_H or fc["eta"] is None:
        return 0
    ahead = fc["eta"] - h
    if fc["p"] >= WARN_ON and ahead <= WARN_WITHIN_H:
        return 2
    if fc["p"] >= WATCH_ON and ahead <= WATCH_WITHIN_H:
        return 1
    return 0


class Ladder:
    """The message step for one week: louder at once, quieter only once the forecast has stayed
    lower for DWELL_S. 0 calm, 1 watch, 2 heads-up, 3 out."""

    def __init__(self, reset=0, d=None):
        d = d or {}
        self.reset = int(d.get("reset", reset))
        self.s = int(d.get("s", 0))
        self.below = d.get("below")         # since when the forecast has been lower
        self.eased = d.get("eased")         # when it last stepped down to calm
        self.eased_said = bool(d.get("eased_said"))
        self.cap_t = d.get("cap_t")         # when the last caption went up (None: none yet this week)
        self.cap_kind = str(d.get("cap_kind", ""))
        self.room_said = bool(d.get("room_said"))

    def to_dict(self):
        return {"reset": self.reset, "s": self.s, "below": self.below, "eased": self.eased,
                "eased_said": self.eased_said, "cap_t": self.cap_t, "cap_kind": self.cap_kind,
                "room_said": self.room_said}

    def step(self, now, h, u, fc):
        if u >= 100:
            self.s, self.below = 3, None
            return self.s
        w = wanted(h, u, fc)
        if w > self.s:
            self.s, self.below = w, None
        elif w < self.s:
            ahead = None if fc["eta"] is None else fc["eta"] - h
            if self.s == 2:
                off = (fc["p"] < WARN_OFF or ahead is None or ahead > WARN_WITHIN_H) and u < NEAR_OUT
            else:
                off = fc["p"] < WATCH_OFF or ahead is None or ahead > WATCH_WITHIN_H
            if not off:
                self.below = None
            else:
                if self.below is None:
                    self.below = now
                if now - self.below >= DWELL_S:
                    self.s = (1 if fc["p"] >= WATCH_ON else 0) if self.s == 2 else 0
                    self.below = None
                    if self.s == 0:
                        self.eased, self.eased_said = now, False
        else:
            self.below = None
        return self.s

    def caption(self, now, working, room):
        """Start a caption if one is due ("watch", "warn", "eased" or "room"); returns the one up
        now, or "". Only while agents work: someone is looking then."""
        if working:
            if self.s in (1, 2):
                if self.cap_t is None or now - self.cap_t >= (WARN_EVERY_S if self.s == 2 else WATCH_EVERY_S):
                    self.cap_t, self.cap_kind = now, ("warn" if self.s == 2 else "watch")
            elif self.s == 0 and self.eased is not None and not self.eased_said and now - self.eased < EASED_KEEP_S:
                self.cap_t, self.cap_kind, self.eased_said = now, "eased", True
            elif self.s == 0 and room and not self.room_said:
                self.cap_t, self.cap_kind, self.room_said = now, "room", True
        return self.cap_kind if self.cap_t is not None and 0 <= now - self.cap_t < CAPTION_S else ""


def day_hour(t):
    """"SUN 4PM": local time to the nearest hour."""
    lt = time.localtime(t + 1800)
    return "%s %d%s" % (DAYS[lt.tm_wday], lt.tm_hour % 12 or 12, "AM" if lt.tm_hour < 12 else "PM")


# ---------------------------------------------------------------- what the bridge keeps
class Pace:
    def __init__(self, path):
        self.path = path
        self.weeks = []             # [{"reset": epoch s, "pts": [[t, used], ...]}], oldest first
        self.anchor = None          # the reset's time of the week the activity is binned against
        self.seen = [0.0] * H       # minutes seen in each hour of the week (from its start)
        self.busy = [0.0] * H       # of those, minutes with agents working
        self.last_min = 0
        self.d5 = self.d7 = 0.0     # 5-hour and weekly percent risen between the same reports
        self.last = None            # [used5, reset5, used7, reset7] at the last report
        self.ladder = Ladder()
        self.out = None             # the latest verdict, for /status
        self._model = None
        self._model_key = None
        self._dirty = False
        self._saved = 0.0
        self.load()

    # ------------------------------------------------------------ persistence
    def load(self):
        try:
            with open(self.path) as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(d, dict):
            return
        try:
            self.weeks = [{"reset": int(w["reset"]), "pts": [[float(t), float(u)] for t, u in w["pts"]]}
                          for w in d.get("weeks", [])][-WEEKS_KEPT:]
            a = d.get("act") or {}
            if len(a.get("seen", ())) == H and len(a.get("busy", ())) == H:
                self.anchor = a.get("anchor")
                self.seen = [float(x) for x in a["seen"]]
                self.busy = [float(x) for x in a["busy"]]
            r = d.get("rate") or {}
            self.d5, self.d7 = float(r.get("d5", 0)), float(r.get("d7", 0))
            self.last = r.get("last")
            self.ladder = Ladder(d=d.get("ladder"))
        except (KeyError, TypeError, ValueError):
            pass

    def save(self, force=False):
        now = time.time()
        if not (self._dirty or force) or (not force and now - self._saved < 60):
            return
        d = {"v": 1, "weeks": self.weeks,
             "act": {"anchor": self.anchor, "seen": [round(x, 2) for x in self.seen],
                     "busy": [round(x, 2) for x in self.busy]},
             "rate": {"d5": round(self.d5, 2), "d7": round(self.d7, 2), "last": self.last},
             "ladder": self.ladder.to_dict()}
        self._dirty, self._saved = False, now
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(d, f, separators=(",", ":"))
            os.replace(tmp, self.path)
        except OSError:
            pass

    # ------------------------------------------------------------ what comes in
    def _week(self, reset):
        for w in self.weeks:
            if abs(w["reset"] - reset) <= HOUR:
                return w
        w = {"reset": reset, "pts": []}
        self.weeks = sorted(self.weeks + [w], key=lambda x: x["reset"])[-WEEKS_KEPT:]
        return w

    def report(self, now, five, seven):
        """A status line's report, as the bridge holds it after taking it in: the 5-hour and
        weekly windows {"used", "resets_at"}."""
        if not seven or seven.get("used") is None or not seven.get("resets_at"):
            return
        u7, r7 = float(seven["used"]), int(seven["resets_at"])
        if now >= r7 or now < r7 - WEEK_S:
            return
        pts = self._week(r7)["pts"]
        if not pts or u7 > pts[-1][1]:
            if len(pts) > 1 and now - pts[-1][0] < POINT_GAP_S:
                pts[-1] = [round(now, 1), u7]
            else:
                pts.append([round(now, 1), u7])
            self._dirty = True
        if five and five.get("used") is not None and five.get("resets_at"):
            u5, r5 = float(five["used"]), int(five["resets_at"])
            if self.last:
                lu5, lr5, lu7, lr7 = self.last
                # rises inside one 5-hour window and one week only: across a new window, use
                # nobody reported could have been spent in the old one
                if abs(r5 - lr5) <= 60 and abs(r7 - lr7) <= HOUR and u5 >= lu5 and u7 >= lu7:
                    if u5 > lu5 or u7 > lu7:
                        self.d5 += u5 - lu5
                        self.d7 += u7 - lu7
                        self._dirty = True
            self.last = [u5, r5, u7, r7]

    def _sample(self, now, reset, working):
        """When agents work, by hour of the week: one sample a minute."""
        minute = int(now // 60)
        if minute == self.last_min:
            return
        self.last_min = minute
        anchor = reset % WEEK_S
        if self.anchor is None or min(abs(anchor - self.anchor), WEEK_S - abs(anchor - self.anchor)) > 2 * HOUR:
            # a new reset time: the old hours no longer line up
            self.anchor, self.seen, self.busy = anchor, [0.0] * H, [0.0] * H
        b = int((now - (reset - WEEK_S)) // HOUR) % H
        self.seen[b] += 1
        if working:
            self.busy[b] += 1
        self._dirty = True

    def _new_week(self, reset):
        """A new week: start its ladder and, when the last one rolled over, let older evidence
        count for less."""
        if self.ladder.reset and reset > self.ladder.reset:
            self.d5, self.d7 = self.d5 * 0.5, self.d7 * 0.5
            self.seen = [x * 0.75 for x in self.seen]
            self.busy = [x * 0.75 for x in self.busy]
        self.ladder = Ladder(reset)
        self._dirty = True

    # ------------------------------------------------------------ the verdict
    def past_weeks(self, start):
        """The finished weeks worth learning from: recorded from near their start, the last LEARN_WEEKS."""
        out = []
        for w in self.weeks:
            if w["reset"] <= start + HOUR and len(w["pts"]) >= 3 and w["pts"][0][1] <= 15:
                out.append(w)
        return out[-LEARN_WEEKS:]

    def weights(self, start):
        """How much work each hour of the week holds: what this bridge has seen, else a desk week."""
        return [(self.busy[b] / self.seen[b] + 0.01) if self.seen[b] >= ACT_MIN else desk(start + b * HOUR) + 0.03
                for b in range(H)]

    def model(self, start):
        past = self.past_weeks(start)
        key = tuple(w["reset"] for w in past) or ("cold", int(time.time() // HOUR))
        if key != self._model_key:
            if past:
                weeks = []
                for w in past:
                    rep = curve(w["pts"], w["reset"] - WEEK_S)
                    weeks.append((rep, max(rep) >= 99.5))
                self._model = learn(weeks)
            else:
                self._model = cold_model(self.weights(start))
            self._model_key = key
        return self._model

    def rate(self):
        """Weekly percent per 5-hour percent, once enough has been seen."""
        return self.d7 / self.d5 if self.d5 >= RATE_MIN else None

    def step(self, now, seven, working, room_on=False):
        """Once a scan: take in whether agents work, step the ladder, and return the verdict for
        /status (None while the week's usage is unknown)."""
        if not seven or seven.get("used") is None or not seven.get("resets_at"):
            self.out = None
            return None
        reset, u = int(seven["resets_at"]), float(seven["used"])
        if now >= reset:
            # the week rolled over and no report says so yet: a new week, nothing used
            reset += (int((now - reset) // WEEK_S) + 1) * WEEK_S
            u = 0.0
        start = reset - WEEK_S
        if abs(self.ladder.reset - reset) > HOUR:
            self._new_week(reset)
        self._sample(now, reset, working)
        h = max(0.0, min(H - 0.01, (now - start) / HOUR))
        m = self.model(start)
        fc = forecast(m, u, h)
        lad = self.ladder
        before = lad.to_dict()
        s = lad.step(now, h, u, fc)
        room = bool(room_on) and s == 0 and reset - now <= ROOM_H * HOUR and 100 - u >= ROOM_MIN_LEFT
        cap = lad.caption(now, working, room)
        if lad.to_dict() != before:
            self._dirty = True
        eta = None if fc["eta"] is None or s == 3 else int(start + fc["eta"] * HOUR)
        k = self.rate()
        self.out = {
            "s": s,                                          # 0 calm, 1 watch, 2 heads-up, 3 out
            "p": int(round(fc["p"] * 100)),                  # chance of reaching the limit before the reset
            "f": int(round(min(999, fc["final"]))),          # likely percent used at the reset (no limit)
            "lo": int(round(min(999, fc["lo"]))),            # and its 80% range
            "hi": int(round(min(999, fc["hi"]))),
            "eta": eta,                                      # when the likely use reaches the limit
            "at": day_hour(eta) if eta else "",              # the same, as "SUN 4PM" on this computer
            "early": (reset - eta) if eta else None,         # seconds before the reset that would be
            "even": int(round(100 * h / H)),                 # percent an even pace would have used by now
            "left": max(0, int(round(100 - u))),
            "win": round((100 - u) / (100 * k), 1) if k else None,   # full 5-hour windows that is
            "learn": 1 if m["n"] < 2 else 0,                 # under two weeks to learn from
            "cap": cap,                                      # the caption up now: watch, warn, eased, room or ""
            "room": 1 if room else 0,                        # the opt-in room-left note applies
            "eased": 1 if (s == 0 and lad.eased is not None and now - lad.eased < EASED_SHOW_S) else 0,
            "reset": reset,
        }
        return self.out
