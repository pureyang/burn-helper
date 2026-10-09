# tufty-badge

An interactive way to show your agent usage on any conference badge.

This repo holds the working notes, probe scripts and tooling from getting a
Pimoroni Tufty 2350 (the SELECT 2026 conference badge) to act as a live display
for AI agent usage: reverse-engineering the stock firmware, its Supabase-backed
realtime/push layer, and how to safely back up and restore the board.

## Contents

- `notes.md` - board facts, firmware findings, gotchas (watchdog, read-only `/system`, Wi-Fi resets)
- `scripts/probe_board.py` - probe RP2350 flash, `/system` writability, mounts over serial
- `scripts/serial_template.py` - raw-REPL template for running code on the badge from macOS

## Not included

Flash backups (`backup/`), firmware images (`*.uf2`) and raw dumps (`*.bin`) are
git-ignored. Flash dumps contain Wi-Fi passwords, Supabase keys and device tokens:
never commit them.

## Restore a board

Put the board in BOOTSEL, then `picotool load -v -x <your-backup>.bin`.
