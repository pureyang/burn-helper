# Install

You need the badge, a USB-C **data** cable, and a Mac with Claude Code and Homebrew installed.
Plug the badge in, then run:

```
curl -fsSL https://raw.githubusercontent.com/pureyang/burn-helper/main/install.sh | bash
```

The installer does everything below and asks before each step that changes something:

1. Downloads the code into `~/hearts-left` (or updates it).
2. Installs the Mac bridge: async hooks and the status line in `~/.claude/settings.json`
   (backed up first) and a login item.
3. Finds the badge. If it runs a conference build or anything other than stock Pimoroni
   firmware, it saves and verifies a full flash backup in `~/hearts-left/backup/`, then
   flashes the stock Tufty 2350 v3.1.1 firmware, downloaded and checked against a pinned
   checksum. It installs `picotool` with Homebrew if needed.
4. Asks for a 2.4 GHz Wi-Fi network. Leave it blank to set it up from your phone later.
5. Copies the Hearts Left app onto the badge and checks that it starts.

Options go after `bash -s --`, for example `... | bash -s -- --yes`:

| Option | Effect |
|---|---|
| `--yes` | accept every step without asking |
| `--no-flash` | never replace the badge's firmware |
| `--no-badge` / `--no-bridge` | set up only the Mac / only the badge |
| `--dry-run` | show what would happen, change nothing |
| `--uninstall` | remove the hooks, status line and login item |

Rerunning the line updates an existing install.

## Manual install

The same steps by hand, from a clone:

### 1. Get the tools and the code

```
brew install picotool
git clone https://github.com/pureyang/burn-helper.git
cd burn-helper
```

Download `tufty-v3.1.1-micropython-with-filesystem.uf2` from the
[Tufty 2350 v3.1.1 release](https://github.com/pimoroni/tufty2350/releases/tag/v3.1.1)
into a `firmware/` folder (`mkdir -p firmware`).

### 2. Back up the badge

Plug the badge into the Mac. The conference build is running and shows up as
`/dev/cu.usbmodem*`. Reboot it into its bootloader, then save and verify all 16 MB of flash:

```
python3 scripts/badge.py bootloader
mkdir -p backup/$(date +%F)
picotool save -a backup/$(date +%F)/flash-full.bin
picotool verify -o 0x10000000 backup/$(date +%F)/flash-full.bin
```

If `bootloader` cannot reach the badge, hold **HOME** while pressing **RESET** instead. The
backup contains the conference Wi-Fi password and keys. `backup/` is git-ignored, so keep it
that way.

### 3. Flash the stock firmware

```
picotool load -v -x firmware/tufty-v3.1.1-micropython-with-filesystem.uf2
```

The badge restarts into Pimoroni's launcher. To go back to the conference firmware later, run
`picotool load -v -x backup/<date>/flash-full.bin` from the bootloader.

### 4. Tell the badge your Wi-Fi (optional now, you can use your phone later)

```
cp badge/secrets.example.py badge/secrets.py   # git-ignored
# edit WIFI_SSID / WIFI_PASSWORD: a 2.4 GHz network the Mac is also on
```

### 5. Install the app on the badge

```
python3 tools/deploy.py --all
```

This copies `badge/` onto the badge's `/system` over USB, which takes about 40 s, then
restarts it. From now on the badge boots straight into the app. Later deploys only send
changed files.

### 6. Install the bridge on the Mac

```
python3 bridge/install.py --dry-run   # shows exactly what will change
python3 bridge/install.py
```

This backs up `~/.claude/settings.json`, then adds the async hooks and the hearts status line,
and starts the bridge as a login item. The log is at `~/Library/Logs/hearts-left.log`. Restart
open Claude Code sessions so they pick up the hooks. To remove everything it added, run
`python3 bridge/install.py --uninstall`.

### 7. Check it

```
curl -s http://127.0.0.1:8787/status    # level, busy, hearts...
```

- With the badge on USB it should show your activity within a few seconds. Press **B** for
  Desktop mode: its first line should read `DATA USB CABLE`.
- Open `http://<your-mac-ip>:8787/` on your phone for the status panel and theme picker.
- Unplug the badge to run on Wi-Fi. Press **B** twice for Paged mode, which opens on the Wi-Fi debug
  page if it doesn't connect.
