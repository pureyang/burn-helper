# How it works

```
Claude Code sessions ──hooks + status line──▶ bridge (Mac) ──Wi-Fi or USB──▶ badge
  ~/.claude/sessions/*.json ─────────────────▲        ▲
                                                    phone browser (theme picker)
```

- **bridge/burn_helper_bridge.py** runs on the Mac. It reads Claude Code's live session registry
  (`~/.claude/sessions/*.json`, which says which sessions are busy, idle or waiting for you).
  It also takes tool-call events from a hook and usage limits from the status line, and serves
  one small JSON document at `/status`. It announces itself on the LAN with a UDP beacon, and
  when the badge is plugged into the Mac it also pushes the same JSON down the USB cable.
- **The status line** gets the official `rate_limits` numbers from Claude Code: 5-hour and
  7-day usage, account-wide. It prints hearts in your terminal too.
- **The badge app** (`badge/apps/burn_helper`) joins Wi-Fi, finds the bridge by its beacon,
  polls it every 2.5 s without blocking the animation, and draws the theme. All sprites are
  generated on the badge from a tiny posed skeleton (`figure.py`), so the walk, run and sprint
  cycles stay consistent across themes.

## Activity levels

Agents working means busy sessions plus running subagents. With none working, the bridge's
level decides between asleep (nothing for 5 minutes) and idle. With any working, the badge
picks one of 15 levels from the count (`scene.tier_for`):

| Agents | Level | Gait | Added on top (`fx.py`, every theme) |
|---|---|---|---|
| 1 to 3 | 1 to 3 | walk | faster scrolling each level; speed lines from level 2 |
| 4 to 7 | 4 to 7 | run | more speed lines |
| 8 to 10 | 8 to 10 | sprint | more speed lines |
| 11-25 | 11 | sprint | sparks |
| 26-50 | 12 | sprint | more sparks |
| 51-75 | 13 | sprint | heat haze |
| 76-100 | 14 | sprint | a pulsing red edge |
| over 100 | 15, ULTRA | sprint | the scene dims behind hyperspace star streaks |

The tool-call rate still adds speed. Each theme has its own scenes for the gaits:

| Gait | Zelda | Running Man | Forrest |
|---|---|---|---|
| asleep | Link asleep under the stars | runner asleep on the concrete, OFF AIR | on the bench with his chocolates |
| idle | standing guard | limbering up, STANDBY | standing by the bench |
| walk | walking the field | jogging into the Zone, LIVE | jogging a country road |
| run | Pegasus-boots dash | a stalker on his heels | bearded, Monument Valley, with followers |
| sprint | sword dash + spin attacks | explosions, searchlights | a crowd of followers, up to 7 |

![All 15 levels in the Zelda theme](img/tiers_hero.png)

When any session is waiting for your input, Navi shouts "HEY! LISTEN!", the Running Man
audience votes "YOUR MOVE!", or Forrest yells "JENNY!", and the caption line turns into a
waiting bar that names the session, by the name Claude Code shows for it (the one you set with
`/rename`, or the one Claude Code gave it): one stays put, several take turns every 2 seconds
(longest wait first, with a counter). A session with no name at all, which only an older Claude
Code leaves, shows as its folder plus the start of its id, in grey (`web-app · 7f3a2c`). Desktop mode (press **B** once)
lists the waiting sessions by name, and **A**/**C** show each one in detail: whether it needs
permission for a tool (and which) or your reply, its folder, and how long it has waited and
run. The bridge sends each one's title or folder name, cut to 20 plain characters, and the
reason only as a category and tool name, never the notification text. These details are shown
on the badge and in the bridge's `/status` JSON on your network. The badge's four case LEDs can blink too, but they are off by default (hold DOWN for 2 s to switch them on).

## What the agents are doing

The badge also acts out what the agents just did. Each activity plays a short animation once,
on top of the walk or run, then the character carries on:

| Activity | From Claude Code | Zelda | Running Man | Forrest |
|---|---|---|---|---|
| edits a file | Edit, Write, MultiEdit, NotebookEdit | sword combo on a slime | counterattack on a stalker | ping-pong rally |
| reads or searches | Read, Grep, Glob, LS | the lens of truth finds a rupee | searchlights; hides behind a crate | opens the box of chocolates |
| runs a command | Bash | a bomb | barrel blast | shrimp net |
| goes on the web | WebFetch, WebSearch | hookshot | drone cam, "LIVE" | reporters: "WHY ARE YOU RUNNING?" |
| sends out a subagent | SubagentStart | boomerang out and back | a second runner joins | a new follower falls in (and peels off when it is done) |
| a tool call fails | PostToolUseFailure | knocked back, "OUCH!" | zapped, "ZAP!" | shot in the buttocks, "OW!" |
| finishes its turn | Stop | item get, "QUEST COMPLETE!" | the applause sign | turns around at the ocean |
| you send a prompt | UserPromptSubmit | a new quest scroll | the host: "NEXT ROUND!" | drill sergeant: "YES, DRILL SERGEANT!" |
| a session starts | SessionStart | out of a cave | "NEW CONTESTANT" | the bus-stop bench: "HELLO." |
| the usage resets | the hearts jump back up | a heart container | commercial break | a new box of chocolates |

At most one plays every 2 seconds. When several arrive together the badge plays the most
telling: a failure first, then a finished turn, a subagent, your prompt, a new session, and
then tool calls. Anything older than 6 seconds is skipped, so a badge that was away doesn't
replay a backlog. The bridge passes on only the category (`ev` in `/status`), never file names,
commands, URLs or prompts. Both demo modes show them all.

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
