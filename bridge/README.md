# Burn Helper bridge

A small server on one computer, a Mac or a Windows PC, that tells the badge how busy your
Claude Code agents are and how much of your usage budget is left. Python 3.9+ standard
library only, plus pyserial on Windows for the USB cable.

## What it reads

- **Live sessions** from `~/.claude/sessions/*.json`, the registry every running
  Claude Code process keeps. Each session reports `busy`, `shell`, `idle` or
  `waiting`. This needs no setup and covers every session on this computer.
- **Hook events** from `cc_hook.py`: tool calls (for calls per minute and calls
  today), subagent starts and stops, and sessions on other machines.
- **Usage limits** from `cc_statusline.py`: the five-hour and seven-day
  percentages Claude Code puts in the status line input. These limits are
  account-wide, so the hearts reflect all usage on the account, including other
  devices and claude.ai.

## Run it

```sh
python3 bridge/burn_helper_bridge.py       # port 8787, phone panel at http://<mac-ip>:8787/
python3 bridge/install.py --dry-run       # preview the settings.json change
python3 bridge/install.py                 # add hooks + status line, start the bridge at login
python3 bridge/install.py --uninstall     # remove exactly what install added
```

`install.py` backs up `~/.claude/settings.json` first, adds one async hook per
event (they never block a session), adds the status line only if you have none,
and installs a LaunchAgent (`com.burnhelper.bridge`, log in
`~/Library/Logs/burn-helper.log`). It replaces the older `com.heartsleft.bridge` and `com.lexco.tufty-bridge` agents if present.

Options: `--port`, `--bind`, `--no-beacon`, `--verbose`. Environment:
`BURN_HELPER_PORT`, `BURN_HELPER_TOKEN`, `BURN_HELPER_STATE_DIR` (state defaults to `~/.claude/burn-helper`). The older `TUFTY_*` names still work.

## Badge discovery

Every 2 seconds the bridge broadcasts `TUFTYBRIDGE 1 <port>` on UDP port 47800 (the wire markers keep their original name so older badges still work).
The badge takes the bridge address from the packet source, so the Mac's IP can
change without reconfiguring anything.

## `GET /status`

```json
{"v":1,"ts":1791575121,"level":4,"busy":6,"waiting":1,"idle":3,"sessions":9,
 "waiting_list":[{"n":"api-server refactor","s":95,"d":"api-server","w":"PERMISSION: BASH","a":7800,"i":"22441a","u":0}],
 "ev":[[41,"edit",1800],[42,"shell",300]],
 "subagents":1,"tpm":2,"tools_today":2,
 "five_hour":{"used":38.0,"resets_at":1791578721},
 "seven_day":{"used":12.0,"resets_at":1791834321},
 "hearts":12,"theme":"hero","theme_seq":3,"last_active":1791575121,"clock":"12:45"}
```

- `hearts` is the remaining five-hour budget in half-heart units, 0 to 20. It is
  `null` until a status line has reported usage. A window whose `resets_at` has
  passed counts as 0% used.
- `level`: 0 asleep, 1 awake (activity in the last 5 minutes or someone waiting),
  2 walking (any busy agent), 3 running (load 2+ or 15+ tool calls a minute),
  4 sprinting (load 4+ or 40+ tool calls a minute). Load is busy sessions plus
  half of each shell session and each subagent. While any agent is working, the badge
  replaces this with its own 15 levels based on `busy` + `subagents` (see docs/how-it-works.md).
- `busy` counts local sessions whose status is busy or shell (a background command), plus busy
  sessions on other machines. A local session that has said busy or shell for 30 minutes with no
  hook event from it is counted as idle instead: its status is stuck, or what is running is a
  server rather than an agent.
- `waiting_list`: the sessions waiting for you, longest first, at most 4: `n` is the
  session's name as Claude Code shows it (set with /rename, or the one Claude Code made up), in
  plain characters, whole up to 40, `s` how many seconds it has
  waited, `d` its folder's name (not the path), `w` what it needs (`PERMISSION: <TOOL>`,
  `A QUESTION`, `YOUR REPLY`, or empty when unknown), `a` how many seconds the session has been running
  (0 when unknown), `i` the first 6 characters of its id and `u` 1 when it has no name of its own:
  then `n` is its folder or its computer's name, numbered when two would look the same. Sessions
  waiting on joined computers are listed by the name their computer's hook sends.
- `ev`: what the agents just did, for the badge's one-shot animations, oldest first: the latest
  6 from the last 10 seconds, each `[number, category, ms ago]`. Categories: `edit`, `read`,
  `shell`, `web` (from the tool of a PostToolUse), `fail` (PostToolUseFailure), `spawn` and
  `back` (SubagentStart/Stop), `done` (Stop), `prompt` (UserPromptSubmit) and `arrive`
  (SessionStart). The number counts up from 1 each time the bridge starts.
- `theme` is set from the phone panel (`POST /theme {"theme": "hero" | "gameshow" | "chocolates" | "auto"}`).
  `theme_seq` increases on every change so the badge can tell a new choice from an old one.
- `pace`: the weekly pace ([how it works](../docs/how-it-works.md#the-weekly-pace)), or `null`
  until the week's usage is known:
  `{"s":0,"p":0,"f":67,"lo":62,"hi":76,"eta":null,"at":"","early":null,"even":74,"left":40,"win":1.5,"learn":1,"cap":"","room":0,"eased":0,"reset":1793044800}`.
  `s` is the step (0 calm, 1 watch, 2 heads-up, 3 out); `p` the chance in percent that the week
  reaches its limit before `reset`; `f` the likely percent used at the reset with no limit, and
  `lo`/`hi` its 80% range; `eta` when the likely use reaches the limit (epoch seconds, or null),
  `at` the same as `SUN 4PM` in the bridge computer's time, and `early` how many seconds before the
  reset that is; `even` the percent an even pace would have used by now; `left` the percent left;
  `win` how many full 5-hour windows that is (null until enough has been seen); `learn` 1 while
  under two weeks are recorded; `cap` the caption up now (`watch`, `warn`, `eased`, `room` or
  empty); `room` 1 while the opt-in room-left note applies; `eased` 1 for 2 hours after the pace
  drops back to calm.

`POST /usage` (the status line's report) answers `{"ok": true, "pace": {...}}` with the same
object.

## Other machines

Install the same hooks and status line on another computer (Windows, Linux or a Mac) and
point them at this Mac:

```sh
python3 bridge/install.py --bridge http://<mac>:8787 [--token <shared secret>]
```

That writes `BURN_HELPER_BRIDGE_URL` (and `BURN_HELPER_TOKEN`) into that computer's
`~/.claude/settings.json` `env`; if you use a token, set the same `BURN_HELPER_TOKEN` for the
bridge. Step by step, including PowerShell: [docs/other-computers.md](../docs/other-computers.md).

Events from another host count as remote sessions: busy for 90 seconds after
their last event. Cloud sessions on claude.ai/code cannot reach a home LAN, so
they only show up through the account-wide usage hearts.

## History (optional)

Off by default. When on, the bridge keeps a SQLite file, `tracking.db` in its state folder
(`~/.claude/burn-helper`, or `%USERPROFILE%\.claude\burn-helper` on Windows), with:

- **`waits`**: one row each time a session waited for you: when it began and ended, how long,
  the session's Claude Code name, which computer, and what it needed (permission for a tool, a
  question, or your reply).
- **`daily`**: one row a day: tool calls, prompts you sent, turns finished, how many waits and
  for how long in all and at most, the 5-hour usage peak, and the week's usage at the last report.

It lives on the bridge computer only. The badge, `/status` and the relay never see it, and it
holds session names, so treat the file as private. The installer asks about it; to change it
later run the bridge install again with `--tracking on` or `--tracking off` (what was recorded
stays in the file). Read it with:

```sh
python3 bridge/stats.py                 # the last 14 days, and the longest waits
python3 bridge/stats.py --days 30 --sessions
python3 bridge/stats.py --csv waits     # or daily: a whole table as CSV
```

Only the four longest-waiting sessions are tracked at any moment, and a wait is measured as the
bridge sees it (a scan every couple of seconds), not to the second.

## Weekly pace

Always on. The bridge keeps `pace.json` in its state folder: the weekly percent at each report for
the last 10 weeks, how many minutes agents worked in each hour of the week, and the 5-hour and
weekly rises it has seen together. It stays on the bridge computer; `/status` carries only the
verdict.

## Privacy

- The hook sends only the session id, event name, tool name, agent id and
  hostname, plus for a notification whether Claude wants permission (and for which
  tool) or your reply. Tool inputs and outputs and the notification's text never
  leave the machine.
- `/status` is mostly counts, plus the categories of recent activity (`ev`). For sessions
  waiting for you it also has their title or folder name, the folder's name and what they
  need (see `waiting_list`); never full paths, prompts or tool inputs. Anyone on your LAN
  can read it and change the theme. Set `BURN_HELPER_TOKEN` to stop other LAN devices from
  posting fake activity.
- `.key` files in `~/.claude/sessions` are never opened.

## Internet relay

`python3 bridge/relay.py on` adds a second listener on `127.0.0.1:8788` and publishes it through
Tailscale Funnel ([setup and details](../docs/relay.md)). It answers only `GET /status`, with
the header `X-Burn-Helper-Key: <key>` (never in the URL, which would end up in logs); anything
else gets 404. It holds at most 8 connections at a time and drops idle ones after 20 seconds. It speaks HTTP/1.1
keep-alive so a badge reuses one TLS connection. The address and key live in
`~/.claude/burn-helper/relay.json` (mode 600) and go to a USB-connected badge as a `relay` field
in the `@TUFTY` line, never over Wi-Fi.
