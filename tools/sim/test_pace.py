#!/usr/bin/env python3
"""The weekly pace: the bridge's forecast and message ladder (bridge/pace.py), first piece by piece,
then over hundreds of simulated weeks of seven kinds of user, as in the study that tuned it.

The simulated weeks: each kind of user has its working hours and how hard it works then; every
week and every day differs from the last (the day's swing carries partly into the next), each
5-hour window caps at 100% of itself, one full window costs K of the week, and the week stops at
its limit. The bridge learns only whole percents, and only while someone works. Each kind's
history (8 earlier weeks) teaches the forecast; then every week is replayed hour by hour through
the real Ladder, counting how early a run-out was flagged and how often a week that ended with
room to spare was flagged anyway.

python3 tools/sim/test_pace.py [weeks per kind, default 400]
"""
import json
import math
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
import pace as P  # noqa: E402

H = P.H
HOUR = P.HOUR

# ---------------------------------------------------------------- piece by piece
tmp = tempfile.mkdtemp()
assert not P.room_enabled(tmp)
assert P.set_room(tmp, True) and P.room_enabled(tmp) and not P.set_room(tmp, True)
assert P.set_room(tmp, False) and not P.room_enabled(tmp)

# a week's curve from its reports: straight between them, flat after the last
c = P.curve([[10 * HOUR, 10], [20 * HOUR, 30]], 0)
assert len(c) == H + 1 and c[0] == 0 and abs(c[5] - 5) < 1e-9 and abs(c[15] - 20) < 1e-9 and c[H] == 30

# a model learnt from identical weeks forecasts them back: half the week done by its middle
flat = [min(100.0, 80.0 * h / H) for h in range(H + 1)]
m = P.learn([(flat, False)] * 4)
assert abs(m["P"] - 80) < 1e-6 and abs(m["S"][84] - 0.5) < 1e-6
fc = P.forecast(m, 40, 84)
assert abs(fc["final"] - 80) < 6 and fc["lo"] <= fc["final"] <= fc["hi"] and fc["p"] < 0.2 and fc["eta"] is None, fc
fc = P.forecast(m, 70, 84)                       # far ahead of the usual: out before the reset
assert fc["final"] > 100 and fc["p"] > 0.8 and 84 < fc["eta"] < H, fc
assert P.forecast(m, 100, 84)["p"] == 1.0

# the ladder: quiet on the first day, louder at once, quieter only after DWELL_S, then "eased"
hot = {"p": 0.95, "eta": 40.0, "final": 130}
cool = {"p": 0.1, "eta": None, "final": 70}
L = P.Ladder(1000)
assert L.step(0, 10, 50, hot) == 0, "the first day says nothing"
assert L.step(0, 30, 50, hot) == 2
assert L.step(1, 31, 50, cool) == 2 and L.step(1 + P.DWELL_S - 1, 32, 50, cool) == 2, "holds through the dwell"
assert L.step(1 + P.DWELL_S, 33, 50, cool) == 0 and L.eased is not None
assert L.step(2 + P.DWELL_S, 34, 92, cool) == 2, "90% used is a heads-up whatever the forecast"
assert L.step(3 + P.DWELL_S, 35, 100, cool) == 3
watch = {"p": 0.7, "eta": 30 + 60.0, "final": 104}
L = P.Ladder(1000)
assert L.step(0, 30, 60, watch) == 1
assert L.step(0, 30, 60, dict(watch, eta=30 + 80.0)) == 1, "a run-out beyond 72 h does not step up..."
assert P.Ladder(1000).step(0, 30, 60, dict(watch, eta=30 + 80.0)) == 0, "...or start a watch"

# captions: only while agents work, at most every 4 h (watch) or 2 h (heads-up), CAPTION_S each
L = P.Ladder(1000)
L.step(0, 30, 60, watch)
assert L.caption(0, False, False) == "", "nobody working: nothing said"
assert L.caption(100, True, False) == "watch" and L.caption(100 + P.CAPTION_S - 1, True, False) == "watch"
assert L.caption(100 + P.CAPTION_S, True, False) == ""
assert L.caption(100 + P.WATCH_EVERY_S - 1, True, False) == ""
assert L.caption(100 + P.WATCH_EVERY_S, True, False) == "watch"
L.step(200, 31, 60, hot)
assert L.caption(100 + P.WATCH_EVERY_S + P.WARN_EVERY_S, True, False) == "warn"
# eased once, room-left once, and room only when calm
L = P.Ladder(1000)
L.step(0, 30, 60, hot)
L.step(10, 31, 60, cool)
L.step(10 + P.DWELL_S, 33, 60, cool)
assert L.s == 0 and L.caption(20 + P.DWELL_S, True, False) == "eased"
assert L.caption(20 + P.DWELL_S + P.CAPTION_S + P.WATCH_EVERY_S, True, False) == ""
assert L.caption(30 + P.DWELL_S + P.CAPTION_S, True, True) == "room"
assert L.caption(40 + P.DWELL_S + 2 * P.CAPTION_S, True, True) == "", "room is said once a week"

# Pace: reports, activity, the exchange rate, the verdict, and a round trip through pace.json
path = os.path.join(tmp, "pace.json")
monday = time.mktime((2026, 10, 19, 13, 0, 0, 0, 0, -1))          # a window that opens Monday 13:00
reset = int(monday + P.WEEK_S)
pc = P.Pace(path)
now = monday + 2 * 86400                                           # Wednesday 13:00
for i in range(12):                                                # 1% of the week per 3.7% of a window
    t = now + i * 600
    pc.report(t, {"used": 10 + i * 37 / 4.0, "resets_at": int(now + 4 * HOUR)}, {"used": 20 + i * 2.5, "resets_at": reset})
assert len(pc.weeks) == 1 and len(pc.weeks[0]["pts"]) >= 10
assert pc.rate() is not None and abs(pc.rate() - 0.27) < 0.02, pc.rate()
out = pc.step(now + 7200, {"used": 47.5, "resets_at": reset}, True)
assert out["s"] == 0 and out["learn"] == 1 and out["even"] == 30 and out["left"] == 52, out
assert out["win"] is not None and abs(out["win"] - 0.52 / 0.27) < 0.15, out
assert pc.busy[50] == 1 and pc.seen[50] == 1, "Wednesday 15:00 is hour 50 of the week"
pc.save(force=True)
pc2 = P.Pace(path)
assert pc2.weeks == pc.weeks and abs(pc2.rate() - pc.rate()) < 1e-6 and pc2.ladder.reset == reset
# a week that has rolled over with no report yet: a new week, nothing used, the ladder starts again
out = pc2.step(reset + 3600, {"used": 47.5, "resets_at": reset}, False)
assert out["reset"] == reset + P.WEEK_S and out["left"] == 100 and out["s"] == 0 and pc2.ladder.reset == reset + P.WEEK_S
# the room-left note: opted in, the last 12 hours, 20% or more left
pc3 = P.Pace(os.path.join(tmp, "room.json"))
assert pc3.step(reset - 6 * HOUR, {"used": 65, "resets_at": reset}, True, room_on=False)["room"] == 0
out = pc3.step(reset - 6 * HOUR + 60, {"used": 65, "resets_at": reset}, True, room_on=True)
assert out["room"] == 1 and out["cap"] == "room", out
assert pc3.step(reset - 6 * HOUR + 120, {"used": 85, "resets_at": reset}, True, room_on=True)["room"] == 0
assert P.Pace(os.path.join(tmp, "x.json")).step(now, {"used": None, "resets_at": reset}, True) is None

# the bridge: a report feeds the pace, a scan steps it, /status carries it
state = tempfile.mkdtemp()
os.environ["BURN_HELPER_STATE_DIR"] = state
import burn_helper_bridge as B  # noqa: E402
assert B.PACE_FILE == os.path.join(state, "pace.json")
b = B.Bridge()
t0 = time.time()
b.on_usage({"rate_limits": {"five_hour": {"used_percentage": 20, "resets_at": t0 + 3 * HOUR},
                            "seven_day": {"used_percentage": 40, "resets_at": t0 + 3 * 86400}}})
assert b.status()["pace"] is None, "nothing until the first scan"
b.pace_step()
pc = b.status()["pace"]
assert pc["s"] == 0 and pc["left"] == 60 and pc["reset"] == int(t0 + 3 * 86400) and pc["cap"] == "", pc
assert len(b.pace.weeks) == 1 and b.pace.weeks[-1]["pts"][-1][1] == 40
P.set_room(state, True)
b.pace_step()
assert b.status()["pace"]["room"] == 0, "room-left only in the week's last 12 hours"
P.set_room(state, False)
b.persist(force=True)
assert P.Pace(B.PACE_FILE).weeks == b.pace.weeks
print("PASS pace: curves, learning, forecast, ladder, captions, room-left, pace.json")

# ---------------------------------------------------------------- hundreds of weeks
K = 0.27                  # one full 5-hour window costs 27% of the week (as measured on one bridge)
START_HOUR = 13           # the window opens Monday 13:00
DAY_SD = 0.38             # how much one day differs from the next (log scale)


def clock(h):
    t = START_HOUR + int(h)
    return t // 24 % 7, t % 24, t // 24        # weekday, hour, day of the window


def desk(h):
    wd, hr, _ = clock(h)
    if wd < 5 and 9 <= hr < 18:
        return 0.8
    if wd < 5 and 18 <= hr < 22:
        return 0.15
    if wd >= 5 and 10 <= hr < 18:
        return 0.06
    return 0.01


def owl(h):
    wd, hr, _ = clock(h)
    if hr >= 20 or hr < 2:
        return 0.7
    return 0.55 if wd >= 5 and 11 <= hr < 18 else 0.02


KINDS = [
    {"key": "steady", "T": 62, "sw": 0.15, "act": lambda h, ev: desk(h), "mult": lambda h, ev: 1.0},
    {"key": "crunch", "T": 74, "sw": 0.18, "events": lambda r: {"crunch": r.random() < 0.6},
     "act": lambda h, ev: 0.9 if ev.get("crunch") and clock(h)[0] in (2, 3) and clock(h)[1] >= 9 else desk(h),
     "mult": lambda h, ev: 2.6 if ev.get("crunch") and clock(h)[0] in (2, 3) else 0.8},
    {"key": "late", "T": 88, "sw": 0.2,
     "act": lambda h, ev: (0.85 if 9 <= clock(h)[1] else 0.08) if h >= 92 else desk(h),
     "mult": lambda h, ev: 2.1 if h >= 92 else 0.45},
    {"key": "front", "T": 72, "sw": 0.18,
     "act": lambda h, ev: 0.9 if h < 35 and clock(h)[1] >= 8 else desk(h),
     "mult": lambda h, ev: 2.3 if h < 35 else 0.5},
    {"key": "fleet", "T": 104, "sw": 0.12, "bg": 0.45, "act": lambda h, ev: desk(h), "mult": lambda h, ev: 1.0},
    {"key": "owl", "T": 74, "sw": 0.22, "act": lambda h, ev: owl(h), "mult": lambda h, ev: 1.0},
    {"key": "light", "T": 32, "sw": 0.2, "act": lambda h, ev: desk(h) * 0.7, "mult": lambda h, ev: 1.0},
]


def week(kind, seed, cap=True):
    """One week: the true weekly percent at the end of each hour, what the bridge was told (whole
    percents, only in hours someone worked), which hours had work, and when it hit the limit."""
    r = random.Random(seed)
    ev = kind["events"](r) if "events" in kind else {}
    week_i = math.exp(kind["sw"] * r.gauss(0, 1))
    day_i, x = [], 0.0
    for _ in range(9):
        x = 0.4 * x + math.sqrt(1 - 0.16) * r.gauss(0, 1)
        day_i.append(math.exp(DAY_SD * x - DAY_SD * DAY_SD / 2))
    rate = kind.get("rate", 1.0)
    truth, rep, active = [0.0] * (H + 1), [0.0] * (H + 1), [0] * H
    wk, win, used5, hit = 0.0, -1, 0.0, None
    for h in range(H):
        units = 0.0
        on = r.random() < min(0.98, kind["act"](h, ev))
        noise = math.exp(0.55 * r.gauss(0, 1) - 0.55 * 0.55 / 2)
        if on:
            units += rate * kind["mult"](h, ev) * week_i * day_i[clock(h)[2]] * noise
        if kind.get("bg"):                                  # agents left running, every hour
            units += rate * week_i * (0.6 + 0.8 * r.random()) * kind["act_sum"] / H * kind["bg"] / (1 - kind["bg"])
        if units > 0:
            if win < 0 or h >= win + 5:
                win, used5 = h, 0.0
            units = min(units, 100 - used5)
            used5 += units
        if not cap:
            wk += K * units
        elif hit is None:
            before = wk
            wk += K * units
            if wk >= 100:
                hit, wk = h + (100 - before) / (K * units), 100.0
        truth[h + 1] = wk
        active[h] = 1 if units > 0 and (hit is None or hit > h) else 0
        rep[h + 1] = math.floor(wk + 1e-9) if active[h] else rep[h]
    return {"truth": truth, "rep": rep, "active": active, "hit": hit, "final": truth[H]}


def calibrate(kind):
    """The work rate that puts the kind's median week (no weekly limit) at its target T."""
    kind["act_sum"] = sum(min(0.98, kind["act"](h, {})) for h in range(H))
    kind["rate"] = 1.0
    for _ in range(4):
        tot = sorted(week(kind, 9000 + i, cap=False)["final"] for i in range(161))
        kind["rate"] *= max(0.2, min(5.0, kind["T"] / max(1.0, tot[80])))


def replay(w, model):
    """The week hour by hour through the bridge's ladder: when it first said watch and heads-up,
    and how many captions it showed."""
    lad = P.Ladder(1)
    first_watch = first_warn = None
    caps, last_cap = 0, None
    for h in range(1, H):
        u = w["rep"][h]
        if u >= 100 or (w["hit"] is not None and h >= w["hit"]):
            break
        now = h * HOUR
        s = lad.step(now, h, u, P.forecast(model, u, h))
        if s >= 1 and first_watch is None:
            first_watch = h
        if s >= 2 and first_warn is None:
            first_warn = h
        lad.caption(now, w["active"][h], False)
        if lad.cap_t == now and lad.cap_kind in ("watch", "warn") and lad.cap_t != last_cap:
            caps, last_cap = caps + 1, now
    return first_watch, first_warn, caps


def study(weeks, history=8):
    rows = {}
    for ki, kind in enumerate(KINDS):
        calibrate(kind)
        past = [week(kind, 100000 + ki * 1000 + 7919 * (i + 1)) for i in range(history)]
        model = P.learn([(w["rep"], w["hit"] is not None) for w in past])
        st = {"weeks": weeks, "hits": 0, "caught12": 0, "missed": 0, "calm": 0, "false": 0, "close": 0, "caps": 0}
        for i in range(weeks):
            w = week(kind, 500000 + ki * 100000 + i * 31)
            fw, _, caps = replay(w, model)
            st["caps"] += caps
            if w["hit"] is not None:
                st["hits"] += 1
                lead = None if fw is None or fw > w["hit"] else w["hit"] - fw
                if lead is None or lead < 2:
                    st["missed"] += 1
                elif lead >= 12:
                    st["caught12"] += 1
            elif w["final"] >= 90:
                st["close"] += 1                  # ended close to the limit: a watch there is fair
            else:
                st["calm"] += 1
                if fw is not None:
                    st["false"] += 1
        rows[kind["key"]] = st
    return rows


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    t0 = time.time()
    rows = study(n)
    tot = {k: sum(r[k] for r in rows.values()) for k in ("weeks", "hits", "caught12", "missed", "calm", "false", "caps")}
    print("%-7s %5s %5s %8s %7s %6s %6s %8s" % ("kind", "weeks", "hits", "caught12", "missed", "calm", "false", "caps/wk"))
    for k, r in rows.items():
        print("%-7s %5d %5d %8s %7s %6d %6s %8.1f" % (
            k, r["weeks"], r["hits"], "%d%%" % (100 * r["caught12"] / r["hits"]) if r["hits"] else "-",
            "%d%%" % (100 * r["missed"] / r["hits"]) if r["hits"] else "-", r["calm"],
            "%d%%" % (100 * r["false"] / r["calm"]) if r["calm"] else "-", r["caps"] / r["weeks"]))
    caught = tot["caught12"] / max(1, tot["hits"])
    missed = tot["missed"] / max(1, tot["hits"])
    false = tot["false"] / max(1, tot["calm"])
    print("all     caught >= 12 h ahead %.0f%%, missed %.1f%%, false alarms %.1f%%, %.1f captions a week (%.0f s)" % (
        100 * caught, 100 * missed, 100 * false, tot["caps"] / tot["weeks"], time.time() - t0))
    # the study's bar: under 5% false alarms and under 3% missed run-outs, across every kind
    assert false < 0.05, "false alarms %.1f%%" % (100 * false)
    assert missed < 0.03, "missed run-outs %.1f%%" % (100 * missed)
    assert caught > 0.75, "caught 12 h ahead only %.0f%%" % (100 * caught)
    assert rows["light"]["false"] == 0 and rows["light"]["caps"] == 0, "a light user hears nothing"
    print("PASS pace study: %d simulated weeks of %d kinds of user" % (tot["weeks"], len(KINDS)))
    if "--json" in sys.argv:
        print(json.dumps(rows))
