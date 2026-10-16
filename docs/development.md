# Development

```
python3 tools/simulate.py                       # render every theme/level to tools/sim/out/*.png
python3 tools/simulate.py --tiers hero          # all 15 activity levels on one sheet
python3 tools/sim/preview_views.py              # render Desktop mode and the Debug mode pages
python3 tools/sim/video_storyboard.py           # one frame per beat of the 20-second video demo
python3 tools/sim/preview_debug.py              # render the Wi-Fi debug screen states
python3 tools/deploy.py                         # copy changed files to the badge and restart
python3 tools/deploy.py --shot-only x.png [--view 1-2] [--page 0-2] [--demo 1]   # screenshot the badge
python3 tools/netdebug.py                       # badge Wi-Fi diagnosis over USB
python3 tools/batterylog.py                     # copy the badge's battery log and sum up each run on battery
python3 tools/sim/test_net.py                   # badge networking code against a live local bridge
python3 tools/sim/test_portal.py                # phone setup portal form handling
python3 tools/sim/test_tiers.py                 # the 15 activity levels and the waiting list
python3 tools/sim/test_waiting.py               # what the bridge says about sessions waiting for you
python3 tools/sim/test_activity.py              # the activity feed: bridge categories, badge picking one
python3 tools/sim/proto_page.py                 # every theme's animations on one page -> tools/sim/out/animations.html
python3 tools/sim/demo_script.py                # both demos beat by beat -> tools/sim/out/demo_script.html
python3 tools/sim/test_relay.py                 # the internet relay listener: key, 404s, connection cap
python3 scripts/badge.py exec "print(1)"        # raw REPL one-liner
```

While the app runs it also takes test commands on the USB serial port: `@VIEW n` (0 animation,
1 Desktop, 2 Debug), `@PAGE n` (Debug mode's page, 0-2), `@DEMO n`, `@KEY A|B|C|UP|DOWN` (a short
press), `@RELAY 1|0` (use the internet relay even at home, or stop), `@SHOT` (a screenshot) and `@NETLOG` (the Wi-Fi report).

The simulator (`tools/sim/pvshim.py`) re-implements the badge's `picovector` drawing calls
with the pixel rules measured on the device. These are nearest-neighbour blits and flips, and
the ROM pixel fonts with the firmware's spacing. So the PNGs match the real screen.
`tools/deploy.py` remounts the badge's read-only `/system` volume read-write over serial, so
deploying doesn't need USB disk mode. The badge tools take a lock file so the bridge's USB
tether pauses while they use the port.

## Contents

- `badge/` - everything that goes onto the badge's `/system` (app, `main.py`, secrets template)
- `bridge/` - Mac-side bridge, hook, status line, installer ([details](../bridge/README.md))
- `install.sh` - the one-line installer
- `tools/` - badge setup, deploy, Wi-Fi debug, simulator, tests, icon generator
- `scripts/badge.py` - stdlib serial/raw-REPL helper (also `bootloader`, `disk`, `reset`)
- `scripts/probe_board.py`, `scripts/serial_template.py` - original probe scripts
- `notes.md` - board facts, firmware findings, gotchas

## Not included

Flash backups (`backup/`), firmware images (`*.uf2`), raw dumps (`*.bin`) and
`badge/secrets.py` are git-ignored. They contain Wi-Fi passwords, Supabase keys and device
tokens, so never commit them.
