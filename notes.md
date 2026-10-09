# Tufty 2350 (SELECT 2026 conference badge)

- Board: Pimoroni Tufty 2350, RP2350 rev A4, 16 MB flash, chipid 4f26e2b4783a6d68
- Firmware: MicroPython bw-1.29.0-gc, built 2026-09-22 (stock v3.1.1 is 2026-09-23)
- Secure boot: OFF; image unsigned; debug enabled -> any UF2 can be flashed
- Serial: /dev/cu.usbmodem21101. NOTE: after Ctrl-C the badge main app stops and a watchdog reboots it
  within seconds -> scripts must finish quickly or feed machine.WDT(timeout=8000).
- /system is read-only from the REPL (errno 30); edit secrets.py via disk mode (MSC).
- Custom layer: /system/main.py installs BadgeLink (Supabase realtime/push client in /system/lib).
- Wi-Fi: joining a network via network.WLAN reset the board 4/4 times (BadgeLink radio mgmt suspected, unproven).

## Backup (2026-10-06)
backup/2026-10-06/flash-full.bin  (picotool save -a, 16 MB, read twice, identical)
sha256 1938cf165eececc6b0a75e61abd3399e4cf0fc70e5b0ffaf850799f076e69621
CONTAINS CREDENTIALS (Wi-Fi password, Supabase keys, device token). Do not sync or commit.
Restore: picotool load -v -x backup/2026-10-06/flash-full.bin   (board in BOOTSEL)
