#!/usr/bin/env python3
"""The connection lost: never connected vs lost, the stage boundaries, what is forgotten and kept,
the back-online moment, and the words the screens use."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402
harness.install()
import net  # noqa: E402
import scene as S  # noqa: E402
import views  # noqa: E402
import preview_views as PV  # noqa: E402

T = 1000000

# no data since boot: never "lost", whatever the time
st = S.Status()
assert st.seen_ms is None and S.lost_stage(st, T) is None and S.lost_ms(st, T) is None, "never connected is not lost"

st.update({"level": 3, "busy": 3, "subagents": 1, "waiting": 1, "waiting_list": [{"n": "api", "s": 9}], "tpm": 12,
           "hearts": 19, "clock": "12:41", "five_hour": {"used": 5.0, "resets_at": 99}, "seven_day": {"used": 58.0}})
assert st.seen_ms is not None and st.seen_clock == "12:41", "data notes when it came and the bridge's clock"
st.seen_ms = T
st.online = True
assert S.lost_stage(st, T + 30000) is None, "fresh data is never lost"

# stage boundaries, from the last data
st.online = False
for gone, want in ((0, "blip"), (12000, "blip"), (S.LOST_PAGE_MS - 1, "blip"), (S.LOST_PAGE_MS, "lost"), (86400000, "lost")):
    assert S.lost_stage(st, T + gone) == want, (gone, S.lost_stage(st, T + gone), want)

# while lost nothing is shown working or waiting; the usage stays, as of the last data
S.track_lost(st, T + 20000)
assert (st.level, st.agents, st.tier, st.busy, st.waiting, st.waiting_list, st.tpm) == (S.IDLE, 0, 0, 0, 0, [], 0), \
    (st.level, st.agents, st.waiting)
assert st.hearts == 19 and st.used5 == 5.0 and st.used7 == 58.0 and st.reset5 == 99, "the usage is kept"
assert not st.was_lost, "a blip is not the lost page"
st.online = True
S.track_lost(st, T + 21000)
assert st.back_ms is None, "back from a blip: no back-online caption"

st.online = False
S.track_lost(st, T + 90000)
assert st.was_lost
st.online = True
S.track_lost(st, T + 95000)
assert not st.was_lost and st.back_ms == T + 95000, "back from the lost page: noted"
assert S.back_online(st, T + 95000 + S.BACK_MS - 1) and not S.back_online(st, T + 95000 + S.BACK_MS)
st.online = False
assert not S.back_online(st, T + 95001), "only while the data is fresh"

# the words
for ms, want in ((23000, "0:23"), (252000, "4:12"), (3725000, "1H02M"), ((2 * 86400 + 3 * 3600) * 1000, "2D03H")):
    assert S.lost_for(ms) == want, (ms, S.lost_for(ms), want)
st.seen_ms, st.net, st.trouble = T, "BRIDGE NOT ANSWERING", "bridge"
assert S.lost_caption(st, T + 23000 - (T + 23000) % (2 * S.LOST_CAPTION_MS)).startswith("CONNECTION LOST ")
assert S.lost_caption(st, T + 23000 - (T + 23000) % (2 * S.LOST_CAPTION_MS) + S.LOST_CAPTION_MS) == "BRIDGE NOT ANSWERING"
st.net = ""
assert S.lost_reason(st) == "NO DATA FROM THE BRIDGE", "a reason even without a network label"
for trouble, want in (("wifi", "B x2: THE WI-FI PAGE"), ("relay", "IS THE BRIDGE ONLINE?"), ("bridge", "IS THE BRIDGE AWAKE?"),
                      ("", "IS THE BRIDGE AWAKE?")):
    st.trouble = trouble
    assert S.lost_advice(st) == want, (trouble, S.lost_advice(st))
assert S.last_usage(st) == "AS OF 12:41: 5H 95% WK 42%", S.last_usage(st)
st.est5 = True
assert S.last_usage(st) == "AS OF 12:41: 5H ~95% WK 42%", S.last_usage(st)
st.est5, st.seen_clock = False, ""
assert S.last_usage(st) == "LAST: 5H 95% WK 42%" and S.as_of(st) == "", "an older bridge sends no clock"

# the network says what kind of trouble it is
n = net.Net([("home-wifi", "pw", "phone")])
n.state = "joining"
assert n.trouble() == "wifi"
n.state, n.up_t = "up", None
assert n.trouble() == "bridge"

# Debug mode's DATA row
c = views.Ctx(st, PV.link(), PV.FakeTether())
assert views.data_row(c, T + 252000) == "LOST 4M12S AGO", views.data_row(c, T + 252000)
never = S.Status()
assert views.data_row(views.Ctx(never, PV.link(), PV.FakeTether()), T) == "OFFLINE"

print("PASS lost: none since boot is not lost; under %d s a blip, then the lost page; nothing working or waiting "
      "while lost, the usage kept as of the last data; back-online only after the lost page" % (S.LOST_PAGE_MS // 1000))
