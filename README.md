# Hearts Left

Your Claude Code agents as a pixel game on a Pimoroni Tufty 2350 conference badge.

A pixel-art character on the badge sleeps, idles, walks, runs or sprints depending on
how many Claude Code agents are working across your sessions. Ten hearts (or chocolates, or
collar lights, depending on the theme) show how much of your 5-hour usage limit is left,
with a countdown to the next reset; a second meter shows the weekly limit. There are three
themes: a Zelda-style field, *The Running Man* game show, and Forrest Gump's run across
America.

Real screenshots from the badge (Zelda, Running Man and Forrest themes):

![Zelda on the badge](docs/img/device_hero.png) ![Running Man on the badge](docs/img/device_gameshow.png) ![Forrest on the badge](docs/img/device_chocolates.png)

Press **B** to step from the animation through Desktop mode, Paged mode and Waiting focus
(shown in demo mode, with example network details):

![Desktop mode on the badge](docs/img/device_desktop.png) ![Paged mode, usage left](docs/img/device_paged.png) ![Waiting focus](docs/img/device_waiting.png)

## Quick install

You need a Mac, the badge, a USB-C **data** cable, and Claude Code already set up (run it once).
Plug the badge in, then paste this into Terminal:

```
curl -fsSL https://raw.githubusercontent.com/pureyang/hearts-left/main/install.sh | bash
```

The installer asks before each change. It:

1. Installs the Mac bridge (async Claude Code hooks, a hearts status line, a login item;
   `~/.claude/settings.json` is backed up first).
2. If the badge isn't on stock firmware, backs up its whole flash and then flashes Pimoroni's.
3. Asks for your Wi-Fi name and password and **tests the join from the badge itself**, so a
   typo is caught now. A combined 2.4/5 GHz network is fine: use its normal name, because the
   badge joins the 2.4 GHz side. Skip it and set Wi-Fi from your phone later (hold **B**).
4. Copies the app onto the badge and checks that it starts.

If the badge stops answering, the installer asks you to press its **RESET** button and carries
on once it responds.

Handy options (after `| bash -s --`): `--yes` (no questions), `--no-flash`, `--dry-run`,
`--uninstall`. Wi-Fi not connecting? See [Wi-Fi troubleshooting](docs/wifi.md#wi-fi-troubleshooting).

## What the badge shows

The character speeds up with the number of agents working (busy sessions plus running
subagents), over 15 levels:

| Agents working | Level | The character |
|---|---|---|
| none | asleep or idle | asleep (nothing for 5 minutes) or standing by |
| 1 to 3 | 1 to 3 | walking |
| 4 to 7 | 4 to 7 | running |
| 8 to 10 | 8 to 10 | sprinting |
| 11-25, 26-50, 51-75, 76-100 | 11 to 14 | sprinting, with sparks, then heat haze, then a pulsing edge |
| over 100 | 15, ULTRA | flying through hyperspace |

Every level adds speed and speed lines, so all 15 look different. When a session is waiting
for your input the character calls for you, and the optional case LEDs flash. Ten icons show the 5-hour usage limit left, a bar shows the weekly limit, and a
countdown runs to the next reset. See [how it works](docs/how-it-works.md) for the meters and
every theme and level, and [all 15 levels](docs/img/tiers_hero.png) side by side.

## Screens

**B** steps through four screens. None of them turns the screen off, and the three status
screens pause the animation to save battery. Usage is always shown as what is **left**.

- **Animation**: the theme.
- **Desktop mode**: everything on one screen, from the data source and Wi-Fi to the levels and
  usage left.
- **Paged mode**: one topic per page, with A/C to turn pages: status, usage left, connection
  and Wi-Fi debug. When Wi-Fi is not working it opens on the Wi-Fi page.
- **Waiting focus**: how many sessions need you, the longest wait, and which sessions they
  are (names need the updated bridge).

## Buttons

Short presses act when you let go, so holding a button never also triggers its press.

![Demo mode on the badge](docs/img/device_demo.png)

| Button | Action |
|---|---|
| A / C | previous / next theme. In Paged mode: previous / next page |
| B | next screen: animation, Desktop mode, Paged mode, Waiting focus, then the animation again. Hold 2 s for phone setup |
| Hold UP 2 s | demo, hero theme only: a 30-second ramp from asleep through all 15 levels to hyperspace, with sessions waiting now and then, and a DEMO tag. Hold again to stop |
| UP | on the Wi-Fi page of Paged mode: rescan |
| DOWN | brightness: 10 levels, then 0% (screen off, the badge keeps running; a note shows for 3 s first), then full again |
| Hold DOWN 2 s | case LEDs on or off (off by default). When on, they pulse with activity and flash when a session is waiting for you |
| HOME | stock app menu; HOME again comes back |

## Wi-Fi in short

The badge's radio is 2.4 GHz only. A combined 2.4/5 GHz network works under its normal name,
and the badge must be on the same network as the Mac. Hold **B** for 2 seconds to set Wi-Fi up
from your phone: setup stays open, joins the network on the badge and shows the result. A wrong
password never reports an error on this radio, the badge just stays in "joining". Details,
troubleshooting and shipping badges with an event network are in [docs/wifi.md](docs/wifi.md).

## Documentation

| Page | What is in it |
|---|---|
| [Hardware and compatibility](docs/hardware.md) | The tested setup, supported and unsupported devices, networks and Macs |
| [Install](docs/manual-install.md) | What the installer does, its options, and the manual steps |
| [Wi-Fi](docs/wifi.md) | Setup from the phone, event networks, troubleshooting |
| [How it works](docs/how-it-works.md) | Bridge, badge app, activity levels, usage meters, every theme |
| [Making themes](docs/themes.md) | The theme contract, memory and build-time budgets, how to add one |
| [Development](docs/development.md) | Simulator, tools, tests, repo layout |
| [Demo video](docs/video.md) | Recording the 20-second demo take the badge plays on its own |
| [Bridge](bridge/README.md) | The Mac-side server and its API |
| [Desk stand](stand/README.md) | A 3D-printable stand that keeps the badge upright with the USB-C cable plugged in, with an optional two-colour heart meter |

## License

[MIT](LICENSE) for the code. The license does not cover the names and characters the homage
themes refer to (Zelda, *The Running Man*, Forrest Gump); those belong to their owners.

## Private data

Flash backups (`backup/`), firmware images, raw dumps and `badge/secrets.py` are git-ignored
because they can hold Wi-Fi passwords and keys. Never commit them.
