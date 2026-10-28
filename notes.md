# Tufty 2350 (SELECT 2026 conference badge)

- Board: Pimoroni Tufty 2350, RP2350 rev A4, 16 MB flash, chipid 4f26e2b4783a6d68
- Firmware: MicroPython bw-1.29.0-gc, built 2026-09-22 (stock v3.1.1 is 2026-09-23)
- Secure boot: OFF; image unsigned; debug enabled -> any UF2 can be flashed
- Serial: /dev/cu.usbmodem21101. NOTE: after Ctrl-C the badge main app stops and a watchdog reboots it
  within seconds -> scripts must finish quickly or feed machine.WDT(timeout=8000).
- /system is read-only from the REPL (errno 30); edit secrets.py via disk mode (MSC).
- Custom layer: /system/main.py installs BadgeLink (Supabase realtime/push client in /system/lib).
- Wi-Fi: joining a network via network.WLAN reset the board 4/4 times on the conference build (likely the
  same watchdog as above: the join blocks longer than the WDT timeout). Not seen on stock firmware.

## Backup (2026-10-06)
backup/2026-10-06/flash-full.bin  (picotool save -a, 16 MB, read twice, identical)
sha256 1938cf165eececc6b0a75e61abd3399e4cf0fc70e5b0ffaf850799f076e69621
CONTAINS CREDENTIALS (Wi-Fi password, Supabase keys, device token). Do not sync or commit.
Restore: picotool load -v -x backup/2026-10-06/flash-full.bin   (board in BOOTSEL)

## Stock firmware (flashed 2026-10-09)
Fresh verified backup first: backup/2026-10-09/flash-full.bin
sha256 08a8f3a75ae0f54e7d55211a67cff711ffe8b97341baeb4d4f8078da29dc6d05 (picotool verify: OK)
Flashed firmware/tufty-v3.1.1-micropython-with-filesystem.uf2 -> reports "tufty 3.4.0", MicroPython bw-1.29.0-gc 2026-09-23.
- Flash layout: 0x10000000 firmware, 0x10200000 ROMFS (/rom, fonts only), 0x10300000 FAT (/system,
  4 KB sectors, FAT12), last 1 MB LittleFS (/ with /state, writable). Source of the frozen
  modules: github.com/pimoroni/tufty2350 modules/common.
- /system is FAT mounted readonly=True by _boot_fat. Safe to remount rw from the REPL outside disk
  mode: vfs.umount('/system'); vfs.mount(vfs.VfsFat(rp2.Flash(start=0, len=size-1MB)), '/system').
  tools/deploy.py does this.
- Default display mode LORES 160x120 (pixel-doubled to the 320x240 panel); badge.mode(HIRES) = 320x240.
- App globals (screen, badge, color, image, shape, font, rect, vec2, run, launch...) are injected
  into builtins by the badgeware module, not visible from a bare REPL after Ctrl-C.
- An exception inside run(update) -> fatal_error screen until a button press. HOME = IRQ -> app
  on_exit -> machine.reset(). badge.caselights(v) drives the 4 case LEDs (0..1).
- wifi.connect() (frozen) calls fatal_error on failure -> Burn Helper drives network.WLAN itself.
- CYW43 radio is 2.4 GHz only. AP mode works: ap.config(ssid=..., key=...) -> 192.168.4.1, WPA2.
- No loopback interface while Wi-Fi is down (sockets to 127.0.0.1 -> EHOSTUNREACH).
- picovector facts measured: fresh image is transparent; blit(img, rect) scales nearest-neighbour;
  negative rect width flips; image.qr(text, 0, 0, 1) returns a QR image; pixel fonts (.ppf):
  46-byte header, (u32 codepoint, u16 width) table, 1bpp rows; advance = width + 1, space = (h+2)//4.
- Performance (Burn Helper app, LORES): theme draw 10-14 ms/frame, capped at 25 fps (11 fps asleep).
  Building a theme's sprites takes ~1-2 s the first time it is shown.
- USB: product "Pimoroni Tufty 2350 MicroPython", serial = chip id; port /dev/cu.usbmodem<locationID>01.
- Wi-Fi creds carried over from the conference secrets.py are for a network not in range here; the
  Mac's own network is not visible to the badge on 2.4 GHz (needs a 2.4 GHz SSID or phone hotspot).

## Wi-Fi debugging (2026-10-09)
- Phone portal saved the home network (2.4 GHz ch6, -56 dBm, 2-3 BSSIDs = mesh). Saved password had a
  trailing space (phone keyboard). Joins with the password as saved AND trimmed, pinned to the
  strongest BSSID, security WPA2/WPA3 / WPA3 / WPA-WPA2, country US, pm=PM_NONE, up to 35 s:
  wlan.status() stays 1 (joining) forever, never -3. Conclusion so far: router never completes the
  handshake for this badge (wrong password most likely; else WPA3-only or MAC filter).
  Badge STA MAC: shown on the debug screen (Raspberry Pi OUI 28:cd:c1).
- cyw43 here does not report -3 (wrong password) within 35 s; a stuck status 1 is the only signal.
  Burn Helper calls this verdict STUCK after 20 s.
- Debug: press B twice on the badge, or `python3 tools/netdebug.py` over USB. Log persists in
  /state/burn_helper_net.log on the badge.

## Working conventions
- Commits: small, logical steps, one purpose per commit (a tool, a module, a theme, a fix, docs),
  never one giant commit. Write the subject as an imperative summary and say why in the body.
  Split work before committing; if a big commit slips through on an unpushed branch, split it.
- Keep private data out of tracked files: Wi-Fi names and passwords, the badge MAC, flash dumps,
  badge/secrets.py. Use placeholder names in screenshots and docs.
