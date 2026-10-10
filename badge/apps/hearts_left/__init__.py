# Hearts Left: live Claude Code activity and usage on a Pimoroni Tufty 2350.
#
# Polls the bridge on your Mac (bridge/tufty_bridge.py) over Wi-Fi and animates
# one of three themes by activity level, with hearts for the remaining usage.
#
# Buttons
#   A / C      previous / next theme
#   B          info screen -> Wi-Fi debug screen -> close; hold 2 s for phone setup
#              (on the debug screen UP rescans and retries Wi-Fi right away)
#   hold UP    demo mode for 2 s (cycles every level, shows a DEMO tag)
#   DOWN       brightness
#   HOME       switch to the stock app menu (HOME again comes back here)

import gc
import math
import os
import sys
import time

APP_DIR = "/system/apps/hearts_left"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

badge.mode(LORES | VSYNC)

import config  # noqa: E402
import gfx  # noqa: E402
import net  # noqa: E402
import scene as S  # noqa: E402
import usb  # noqa: E402
import debugview  # noqa: E402

THEMES = ("hero", "gameshow", "chocolates")
LABELS = {"hero": "HYRULE", "gameshow": "THE RUNNING MAN", "chocolates": "FORREST"}
BRIGHT = (1.0, 0.7, 0.45, 0.25)
MENU_FLAG = "/state/.hearts_left_menu"

prefs = {"theme": "hero", "bright": 0, "seq": -1, "lights": True}
config.migrate()
State.load("hearts_left", prefs)
# theme ids used before the files were renamed
LEGACY_THEMES = {"zelda": "hero", "runningman": "gameshow", "forrest": "chocolates"}
prefs["theme"] = LEGACY_THEMES.get(prefs.get("theme"), prefs.get("theme"))
if prefs.get("theme") not in THEMES:
    prefs["theme"] = "hero"

st = S.Status()
link = net.Net(config.networks(), config.bridge())
tether = usb.UsbLink()
themes = {}
view = 0        # 0 theme, 1 info overlay, 2 Wi-Fi debug
demo = 0            # 0 off, 1 demo with a DEMO tag, 2 demo with no tag
DEMO_HOLD_MS = 2000      # hold UP alone
HIDDEN_HOLD_MS = 3000    # hold UP + DOWN together
PORTAL_HOLD_MS = 1800    # hold B alone
SHORT_MS = 700           # longer than this is a hold, not a press
down = {}                # button -> ticks when it went down
fired = False            # a hold fired; ignore releases until every button is up
wink_until = 0
portal = None
portal_arm = False       # B is still down from the hold that opened setup; its release must not cancel
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
    State.save("hearts_left", prefs)
    show_toast(LABELS[name])


def save_prefs():
    State.save("hearts_left", prefs)


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
    step = (t // 4500) % 6
    st.level = (S.SLEEP, S.IDLE, S.WALK, S.RUN, S.SPRINT, S.WALK)[step]
    st.busy = (0, 0, 1, 3, 6, 1)[step]
    st.waiting = 1 if step == 5 else 0
    st.tpm = (0, 0, 6, 22, 48, 4)[step]
    st.tools = 1234
    st.online = True
    st.net = ""
    # a 90-second usage window: hearts drain for 75 s while the countdown runs
    # down through minutes, milliseconds and microseconds, then it resets
    into = (t % 90000) * 1000 + time.ticks_us() % 1000
    st.left5 = 75 * 1000000 - into
    st.hearts = 20 if st.left5 <= 0 else max(0, 20 - into // 3750000)
    st.used5 = (20 - st.hearts) * 5
    st.week = 0.6
    st.used7 = 40
    st.left7 = (3 * 86400 + 4 * 3600) * 1000000


def lights(t):
    if time.ticks_diff(wink_until, t) > 0:
        badge.caselights(0.8)
        return
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
    gfx.text("HEARTS LEFT", 4, -1, (217, 119, 87), font.sins)
    rows = []
    if demo:
        rows.append("DATA DEMO%s" % (" (NO TAG)" if demo == 2 else ""))
    else:
        rows.append("DATA %s" % ({"usb": "USB CABLE", "net": "WI-FI"}.get(source, "NONE") if st.online else "OFFLINE"))
    if link.state == "up":
        rows.append("WIFI %s  %s" % (link.ssid[:10], link.ip))
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


def is_up(b, t):
    """True once a button is physically released (they read 0 while pressed)."""
    if badge.released(b):
        return True
    try:
        return b.value() == 1 and time.ticks_diff(t, down[b]) > 100
    except Exception:  # noqa: BLE001
        return False


def short_press(b):
    global view, dimmed
    if b == BUTTON_A:
        switch(-1)
    elif b == BUTTON_C:
        switch(1)
    elif b == BUTTON_B:
        view = (view + 1) % 3
    elif b == BUTTON_UP and view == 2:
        link.rescan()
        show_toast("RESCANNING")
    elif b == BUTTON_DOWN:
        prefs["bright"] = (prefs["bright"] + 1) % len(BRIGHT)
        set_brightness(prefs["bright"])
        save_prefs()
        show_toast("BRIGHTNESS %d%%" % int(BRIGHT[prefs["bright"]] * 100))


def handle_buttons(t):
    """Short presses act on release; holds act once while held."""
    global view, demo, portal, portal_arm, last_input, dimmed, fired, wink_until
    if badge.pressed() or badge.held():
        last_input = t
        if dimmed:
            dimmed = False
            set_brightness(prefs["bright"])
    for b in (BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_UP, BUTTON_DOWN):
        if badge.pressed(b) and b not in down:
            down[b] = t
    if portal is not None:
        if portal_arm:
            # setup stays open after the hold: wait for that press to end, then a new B press cancels
            if BUTTON_B not in down or is_up(BUTTON_B, t):
                portal_arm = False
                down.clear()
        elif portal.phase == "serve" and BUTTON_B in down and is_up(BUTTON_B, t):
            down.clear()
            portal.close()
            portal = None
            link.stop()
        return

    def held(b):
        return time.ticks_diff(t, down[b]) if b in down else -1

    if not fired:
        if held(BUTTON_UP) >= HIDDEN_HOLD_MS and held(BUTTON_DOWN) >= HIDDEN_HOLD_MS:
            # undocumented: demo with no on-screen tag, for videos and talks
            fired = True
            demo = 0 if demo else 2
            wink_until = time.ticks_add(t, 350)
        elif held(BUTTON_UP) >= DEMO_HOLD_MS and BUTTON_DOWN not in down:
            fired = True
            demo = 0 if demo else 1
            show_toast("DEMO ON" if demo else "DEMO OFF")
        elif held(BUTTON_B) >= PORTAL_HOLD_MS and len(down) == 1:
            fired = True
            view = 0
            start_portal()
            portal_arm = portal is not None
            return
    for b in list(down):
        if is_up(b, t):
            dur = time.ticks_diff(t, down.pop(b))
            if not fired and dur <= SHORT_MS:
                short_press(b)
    if not down:
        fired = False


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


def finish_portal():
    """The phone setup tried the new network. Success: back to the main screen on it.
    Failure: back to setup with a note, so the password can be fixed."""
    global portal, portal_arm, link
    ok = portal.outcome == "ok"
    ssid = portal.new_ssid
    portal.close()
    down.clear()
    if ok:
        portal = None
        link = net.Net(config.networks(), config.bridge())
        show_toast("WI-FI " + ssid[:14].upper())
    else:
        link.stop()
        try:
            import portal as P
            portal = P.Portal(link.results(), notice="LAST TRY FAILED: CHECK PW")
            portal_arm = False
        except Exception:  # noqa: BLE001
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
        if portal.phase == "done":
            finish_portal()
            return None
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
    if demo == 1:
        gfx.text("DEMO", 136, 96, (255, 255, 255), font.sins, shadow=(0, 0, 0))
    if view == 1:
        draw_info(t)
    elif view == 2:
        debugview.draw(link, tether, source, t)
    lights(t)
    power_save(t)
    perf[0] = perf[0] * 0.9 + time.ticks_diff(time.ticks_ms(), t_start) * 0.1
    if tether.demo_req is not None:
        globals()["demo"] = tether.demo_req % 3
        tether.demo_req = None
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
