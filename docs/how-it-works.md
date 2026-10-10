# How it works

```
Claude Code sessions ──hooks + status line──▶ bridge (Mac) ──Wi-Fi or USB──▶ badge
  ~/.claude/sessions/*.json ─────────────────▲        ▲
                                                    phone browser (theme picker)
```

- **bridge/hearts_left_bridge.py** runs on the Mac. It reads Claude Code's live session registry
  (`~/.claude/sessions/*.json`, which says which sessions are busy, idle or waiting for you).
  It also takes tool-call events from a hook and usage limits from the status line, and serves
  one small JSON document at `/status`. It announces itself on the LAN with a UDP beacon, and
  when the badge is plugged into the Mac it also pushes the same JSON down the USB cable.
- **The status line** gets the official `rate_limits` numbers from Claude Code: 5-hour and
  7-day usage, account-wide. It prints hearts in your terminal too.
- **The badge app** (`badge/apps/hearts_left`) joins Wi-Fi, finds the bridge by its beacon,
  polls it every 2.5 s without blocking the animation, and draws the theme. All sprites are
  generated on the badge from a tiny posed skeleton (`figure.py`), so the walk, run and sprint
  cycles stay consistent across themes.

## Activity levels

| Level | When | Zelda | Running Man | Forrest |
|---|---|---|---|---|
| 0 asleep | nothing busy for 5 min | Link asleep under the stars | runner asleep on the concrete, OFF AIR | on the bench with his chocolates |
| 1 idle | recently active, or a session waiting | standing guard | limbering up, STANDBY | standing by the bench |
| 2 walk | 1 agent busy | walking the field | jogging into the Zone, LIVE | jogging a country road |
| 3 run | 2–3 agents, or ≥15 tool calls/min | Pegasus-boots dash | a stalker on his heels | bearded, Monument Valley |
| 4 sprint | 4+ agents, or ≥40 tool calls/min | sword dash + spin attacks | explosions, searchlights | a crowd of followers, one per agent |

When any session is waiting for your input, Navi shouts "HEY! LISTEN!", the Running Man
audience votes "YOUR MOVE!", or Forrest yells "JENNY!". The badge's four case LEDs can blink too, but they are off by default (hold DOWN for 2 s to switch them on).

## Usage meters

In the Zelda theme the three counters at the top left are: green gem = tool calls today,
boomerang = agents working right now, ocarina = sessions waiting for you.

Every theme shows the 5-hour limit as ten icons, the weekly limit as a bar, and a countdown
to the next 5-hour reset. Each icon is 10% of the limit left and a half icon is 5%. The icons
flash once less than 20% is left.

| Theme | 5-hour limit | Weekly limit | Countdown |
|---|---|---|---|
| Zelda | Hearts: full, half, empty | Green magic meter under the hearts | Hourglass beside "-LIFE-" |
| Running Man | The runner's explosive collar: green light = charge left, amber = half, dark red = spent; the collar flashes red when low | Cyan charge strip under the collar | The show's game clock |
| Forrest | A box of chocolates: whole, bitten (half), empty paper cup | The road from coast to coast | Clock beside the miles |

![Zelda usage meter](img/meter_hero.png)
![Running Man usage meter](img/meter_gameshow.png)
![Forrest usage meter](img/meter_chocolates.png)

The countdown shows hours and minutes while the reset is far off (`2H13M`). Under an hour it
becomes a ticking clock (`13:42`), under a minute it shows milliseconds (`42.173`), and in the
last ten seconds microseconds (`9.173248`). It turns yellow under 10 minutes and red under one.
After the reset it shows `RESET!` for a minute, then `FULL`. The badge redraws 25 times a
second, so the last digits blur by design. The countdown runs on the badge's own clock,
synced to the bridge, so it ticks smoothly between updates.

**How often the numbers update:** the usage percentages come from Claude Code's status line.
The status line reruns after every Claude response and at least every 60 seconds in each
open session (`refreshInterval` in `~/.claude/settings.json`), and the badge picks the new
value up within 2 to 3 seconds. With no Claude Code session open, the last value stays. The
meters stay grey until a status line has reported usage, which only happens on Claude
subscription accounts. The terminal status line shows `resets in 1h23m`, and the phone panel
runs the same live countdown as the badge.

## Every level of every theme

Simulator renders of each activity level, from asleep to sprinting, for each theme.

![Zelda theme, every level](img/sheet_hero.png)
![Running Man theme, every level](img/sheet_gameshow.png)
![Forrest theme, every level](img/sheet_chocolates.png)
