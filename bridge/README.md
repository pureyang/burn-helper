# Tufty bridge

A small server on your Mac that tells the badge how busy your Claude Code agents
are and how much of your usage budget is left. Python 3.9 standard library only.

## What it reads

- **Live sessions** from `~/.claude/sessions/*.json`, the registry every running
  Claude Code process keeps. Each session reports `busy`, `shell`, `idle` or
  `waiting`. This needs no setup and covers every session on this Mac.
- **Hook events** from `cc_hook.py`: tool calls (for calls per minute and calls
  today), subagent starts and stops, and sessions on other machines.
- **Usage limits** from `cc_statusline.py`: the five-hour and seven-day
  percentages Claude Code puts in the status line input. These limits are
  account-wide, so the hearts reflect all usage on the account, including other
  devices and claude.ai.

## Run it

```sh
python3 bridge/tufty_bridge.py            # port 8787, phone panel at http://<mac-ip>:8787/
python3 bridge/install.py --dry-run       # preview the settings.json change
python3 bridge/install.py                 # add hooks + status line, start the bridge at login
python3 bridge/install.py --uninstall     # remove exactly what install added
```

`install.py` backs up `~/.claude/settings.json` first, adds one async hook per
event (they never block a session), adds the status line only if you have none,
and installs a LaunchAgent (`com.lexco.tufty-bridge`, log in
`~/Library/Logs/tufty-bridge.log`).

Options: `--port`, `--bind`, `--no-beacon`, `--verbose`. Environment:
`TUFTY_PORT`, `TUFTY_TOKEN`, `TUFTY_STATE_DIR`.

## Badge discovery

Every 2 seconds the bridge broadcasts `TUFTYBRIDGE 1 <port>` on UDP port 47800.
The badge takes the bridge address from the packet source, so the Mac's IP can
change without reconfiguring anything.

## `GET /status`

```json
{"v":1,"ts":1791575121,"level":4,"busy":6,"waiting":0,"idle":3,"sessions":9,
 "subagents":1,"tpm":2,"tools_today":2,
 "five_hour":{"used":38.0,"resets_at":1791578721},
 "seven_day":{"used":12.0,"resets_at":1791834321},
 "hearts":12,"theme":"zelda","theme_seq":3,"last_active":1791575121,"clock":"12:45"}
```

- `hearts` is the remaining five-hour budget in half-heart units, 0 to 20. It is
  `null` until a status line has reported usage. A window whose `resets_at` has
  passed counts as 0% used.
- `level`: 0 asleep, 1 awake (activity in the last 5 minutes or someone waiting),
  2 walking (any busy agent), 3 running (load 2+ or 15+ tool calls a minute),
  4 sprinting (load 4+ or 40+ tool calls a minute). Load is busy sessions plus
  half of each shell session and each subagent.
- `theme` is set from the phone panel (`POST /theme {"theme": "zelda" | "runningman" | "forrest" | "auto"}`).
  `theme_seq` increases on every change so the badge can tell a new choice from an old one.

## Other machines

Install the same hooks and status line on another computer and point them at
this Mac:

```sh
export TUFTY_BRIDGE_URL=http://<mac-ip>:8787
export TUFTY_TOKEN=<shared secret>     # optional; set the same value for the bridge
```

Events from another host count as remote sessions: busy for 90 seconds after
their last event. Cloud sessions on claude.ai/code cannot reach a home LAN, so
they only show up through the account-wide usage hearts.

## Privacy

- The hook sends only the session id, event name, tool name, agent id and
  hostname. Tool inputs and outputs never leave the machine.
- `/status` contains counts only: no session names, paths or prompts. Anyone on
  your LAN can read it and change the theme. Set `TUFTY_TOKEN` to stop other LAN
  devices from posting fake activity.
- `.key` files in `~/.claude/sessions` are never opened.
