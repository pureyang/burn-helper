# Claude Buddy: live Claude Code activity on a Pimoroni Tufty 2350.
#
# Polls the bridge on your Mac (bridge/tufty_bridge.py) over Wi-Fi and animates
# one of three themes by activity level, with hearts for the remaining usage.
#
# Buttons
#   A / C      previous / next theme
#   B          info screen -> Wi-Fi debug screen -> close; hold 2 s for phone setup
#              (on the debug screen UP rescans and retries Wi-Fi right away)
#   UP         demo mode (cycles every level, for showing it off)
#   DOWN       brightness
#   HOME       switch to the stock app menu (HOME again comes back here)

import gc
import math
import os
import sys
import time

APP_DIR = "/system/apps/claude_buddy"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

badge.mode(LORES | VSYNC)

import config  # noqa: E402
import gfx  # noqa: E402
import net  # noqa: E402
import scene as S  # noqa: E402
import usb  # noqa: E402
import debugview  # noqa: E402

THEMES = ("zelda", "runningman", "forrest")
LABELS = {"zelda": "HYRULE", "runningman": "THE RUNNING MAN", "forrest": "FORREST"}
BRIGHT = (1.0, 0.7, 0.45, 0.25)
MENU_FLAG = "/state/.buddy_menu"

prefs = {"theme": "zelda", "bright": 0, "seq": -1, "lights": True}
State.load("claude_buddy", prefs)
if prefs.get("theme") not in THEMES:
    prefs["theme"] = "zelda"

st = S.Status()
link = net.Net(config.networks(), config.bridge())
tether = usb.UsbLink()
themes = {}
view = 0        # 0 theme, 1 info overlay, 2 Wi-Fi debug
demo = False
portal = None
b_down_t = None
seen = {"usb": 0, "net": 0}
source = None   # "usb" or "net": where the current numbers came from
last_input = time.ticks_ms()
dimmed = False
frame_t = time.ticks_ms()
toast = None
toast_t = 0
perf = [0.0, 0.0]   # moving averages: draw ms, frame-to-frame ms


def set_brightness(i):
    try:
        display.backlight(BRIGHT[i % len(BRIGHT)])
    except Exception:  # noqa: BLE001
        pass


set_brightness(prefs["bright"])


def show_toast(msg):
    global toast, toast_t
    toast = msg
    toast_t = time.ticks_ms()


def theme_obj(name):
    th = themes.get(name)
    if th is None:
        # building sprites takes a moment, so say so
        screen.pen = color.rgb(0, 0, 0)
        screen.clear()
        gfx.ctext("LOADING", 80, 44, (255, 255, 255), font.sins)
        gfx.ctext(LABELS[name], 80, 58, (217, 119, 87), font.sins)
        display.update()
        mod = __import__("theme_" + name)
        th = mod.Theme()
        th.build()
        th.ready = True
        themes[name] = th
        gc.collect()
    return th


def switch(delta=0, name=None):
    if name is None:
        i = THEMES.index(prefs["theme"])
        name = THEMES[(i + delta) % len(THEMES)]
    prefs["theme"] = name
    State.save("claude_buddy", prefs)
    show_toast(LABELS[name])


def save_prefs():
    State.save("claude_buddy", prefs)


def apply_bridge():
    """Copy the freshest bridge data (USB tether or Wi-Fi) into the status model."""
    global source
    d = None
    for name, src in (("net", link), ("usb", tether)):
        if src.seq != seen[name] and src.data is not None:
            seen[name] = src.seq
            # prefer USB while it is fresh; Wi-Fi fills in when unplugged
            if name == "usb" or not tether.fresh():
                d = src.data
                source = name
    if d is None:
        return
    st.update(d)
    tseq = d.get("theme_seq")
    if isinstance(tseq, int) and tseq != prefs.get("seq"):
        prefs["seq"] = tseq
        if d.get("theme") in THEMES and d.get("theme") != prefs["theme"]:
            switch(name=d.get("theme"))
        else:
            save_prefs()


def demo_status(t):
    lv = (t // 4500) % 6
    lv = (S.SLEEP, S.IDLE, S.WALK, S.RUN, S.SPRINT, S.WALK)[lv]
    st.level = lv
    st.busy = (0, 0, 1, 3, 6, 1)[(t // 4500) % 6]
    st.waiting = 1 if (t // 4500) % 6 == 5 else 0
    st.hearts = 20 - ((t // 900) % 21)
    st.week = 0.6
    st.tpm = (0, 0, 6, 22, 48, 4)[(t // 4500) % 6]
    st.tools = 1234
    st.online = True
    st.net = ""


def lights(t):
    if not prefs.get("lights", True):
        return
    lv = st.level if st.online else S.SLEEP
    if st.waiting and st.online:
        v = 0.6 if (t // 300) % 2 == 0 else 0.0
        badge.caselights(v)
        return
    if lv == S.SLEEP:
        badge.caselights(0)
    elif lv == S.IDLE:
        badge.caselights(0.04)
    elif lv == S.WALK:
        badge.caselights(0.08 + 0.08 * (1 + math.sin(t / 600.0)))
    elif lv == S.RUN:
        badge.caselights(0.15 + 0.15 * (1 + math.sin(t / 250.0)))
    else:
        k = (t // 120) % 4
        badge.caselights(*[0.5 if i == k else 0.05 for i in range(4)])


def draw_info(t):
    screen.pen = color.rgb(0, 0, 0, 215)
    screen.rectangle(0, 0, 160, 120)
    gfx.text("CLAUDE BUDDY", 4, -1, (217, 119, 87), font.sins)
    rows = []
    rows.append("DATA %s" % ({"usb": "USB CABLE", "net": "WI-FI"}.get(source, "NONE") if st.online else "OFFLINE"))
    if link.state == "up":
        rows.append("WIFI %s" % link.ssid[:12])
        rows.append("IP   %s" % link.ip)
    else:
        rows.append("WIFI " + (link.label() or link.state)[:22])
    b = link.bridge
    age = "" if link.ok_t is None else " %ds" % (net.since(link.ok_t) // 1000)
    rows.append("BRDG %s%s" % ("%s:%d" % b if b else "searching", age))
    rows.append("BUSY %d  WAIT %d  IDLE %d" % (st.busy, st.waiting, st.idle))
    rows.append("TOOLS/MIN %d  TODAY %d" % (st.tpm, st.tools))
    for label, used, left in (("5H", st.used5, st.left5), ("7D", st.used7, st.left7)):
        pct = "--" if used is None else "%d%%" % int(used)
        when = gfx.countdown(left)
        rows.append("%s %s USED%s" % (label, pct, "" if left is None else
                                      (", RESET IN " + when if left > 0 else ", " + when)))
    try:
        bat = "USB" if badge.usb_connected() else "%d%%" % badge.battery_level()
    except Exception:  # noqa: BLE001
        bat = "?"
    rows.append("BATT %s  LVL %d  %s" % (bat, st.level, st.clock))
    if link.err:
        rows.append("ERR " + link.err[:22])
    y = 9
    for r in rows[:9]:
        gfx.text(r, 4, y, (230, 230, 230), font.sins)
        y += 10
    gfx.text("HOLD B: PHONE SETUP", 4, 107, (120, 120, 130), font.sins)


def handle_buttons(t):
    global view, demo, portal, b_down_t, last_input, dimmed
    any_btn = badge.pressed() or badge.held()
    if any_btn:
        last_input = t
        if dimmed:
            dimmed = False
            set_brightness(prefs["bright"])
    if portal is not None:
        if badge.pressed(BUTTON_B):
            portal.close()
            portal = None
            link.stop()
        return
    if badge.pressed(BUTTON_A):
        switch(-1)
    if badge.pressed(BUTTON_C):
        switch(1)
    if badge.pressed(BUTTON_UP) and view == 2:
        link.rescan()
        show_toast("RESCANNING")
    elif badge.pressed(BUTTON_UP):
        demo = not demo
        show_toast("DEMO ON" if demo else "DEMO OFF")
    if badge.pressed(BUTTON_DOWN):
        prefs["bright"] = (prefs["bright"] + 1) % len(BRIGHT)
        set_brightness(prefs["bright"])
        save_prefs()
        show_toast("BRIGHTNESS %d%%" % int(BRIGHT[prefs["bright"]] * 100))
    if badge.pressed(BUTTON_B):
        b_down_t = t
    if b_down_t is not None and badge.held(BUTTON_B) and time.ticks_diff(t, b_down_t) > 1800:
        b_down_t = None
        view = 0
        start_portal()
    if badge.released(BUTTON_B):
        if b_down_t is not None:
            view = (view + 1) % 3
        b_down_t = None


def start_portal():
    global portal
    link.stop()
    try:
        import portal as P
        portal = P.Portal(link.results())
    except Exception as e:  # noqa: BLE001
        show_toast("SETUP FAILED")
        link.err = repr(e)[:40]
        portal = None


def power_save(t):
    global dimmed
    if not dimmed and st.level == S.SLEEP and time.ticks_diff(t, last_input) > 10 * 60 * 1000:
        dimmed = True
        try:
            display.backlight(0.12)
        except Exception:  # noqa: BLE001
            pass
    if dimmed and st.level != S.SLEEP:
        dimmed = False
        set_brightness(prefs["bright"])


def pace(t):
    """Cap the frame rate: smooth when busy, frugal when asleep."""
    global frame_t
    target = 90 if (st.level == S.SLEEP and not st.waiting) else 40
    spent = time.ticks_diff(time.ticks_ms(), frame_t)
    try:
        if spent < target:
            time.sleep_ms(target - spent)
    except KeyboardInterrupt:
        # Ctrl-C over USB (tools/deploy.py --shot): keep the finished frame
        try:
            import screenshot
            screenshot.save("/shot.png")
        except Exception:  # noqa: BLE001
            pass
        raise
    now = time.ticks_ms()
    perf[1] = perf[1] * 0.9 + time.ticks_diff(now, frame_t) * 0.1
    frame_t = now


def update():
    t = time.ticks_ms()
    t_start = t
    handle_buttons(t)
    if portal is not None:
        portal.tick()
        portal.draw(t)
        return None
    link.tick()
    tether.tick()
    apply_bridge()
    st.online = link.fresh() or tether.fresh()
    st.net = "" if tether.fresh() else link.label()
    if demo:
        demo_status(t)
    else:
        st.tick()
    th = theme_obj(prefs["theme"])
    th.draw(st, t)
    if toast is not None and time.ticks_diff(t, toast_t) < 1500:
        w = gfx.width(toast, font.sins) + 8
        gfx.box(80 - w // 2, 48, w, 13, (0, 0, 0))
        gfx.box(80 - w // 2, 48, w, 1, (217, 119, 87))
        gfx.ctext(toast, 80, 48, (255, 255, 255), font.sins)
    if demo:
        gfx.text("DEMO", 136, 96, (255, 255, 255), font.sins, shadow=(0, 0, 0))
    if view == 1:
        draw_info(t)
    elif view == 2:
        debugview.draw(link, tether, source, t)
    lights(t)
    power_save(t)
    perf[0] = perf[0] * 0.9 + time.ticks_diff(time.ticks_ms(), t_start) * 0.1
    if tether.view_req is not None:
        globals()["view"] = tether.view_req % 3
        tether.view_req = None
    if tether.netlog_req:
        tether.netlog_req = False
        try:
            usb.send_lines("NETLOG", link.dump() + ["-- log --"] + link.log)
        except Exception as e:  # noqa: BLE001
            print("@NETLOG-ERR", e)
    if tether.shot_req:
        tether.shot_req = False
        try:
            usb.send_screenshot("draw_ms=%.1f frame_ms=%.1f theme=%s level=%d src=%s" % (
                perf[0], perf[1], prefs["theme"], st.level, source))
        except Exception as e:  # noqa: BLE001
            print("@SHOTERR", e)
    pace(t)
    return None


def on_exit():
    # HOME was pressed: next boot shows the stock menu instead of this app.
    try:
        badge.caselights(0)
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(MENU_FLAG, "w") as f:
            f.write("1")
    except Exception:  # noqa: BLE001
        pass


run(update)
