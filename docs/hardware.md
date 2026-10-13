# Hardware and compatibility

## The combination that works today

This is the exact setup this repo was built and tested on:

| Part | Tested with |
|---|---|
| Badge | Pimoroni **Tufty 2350**, the edition handed out at **Supabase Select 2026**. It has an RP2350 (rev A4) with 16 MB of flash and a 320×240 colour screen, which the app drives at 160×120 pixel-doubled. Its radio is a Raspberry Pi CYW43439 module (2.4 GHz only), with four case LEDs and a USB-C port |
| Badge firmware | Stock Pimoroni Tufty 2350 MicroPython **v3.1.1** "with filesystem", from [pimoroni/tufty2350 releases](https://github.com/pimoroni/tufty2350/releases). It reports `tufty 3.4.0`, MicroPython bw-1.29.0-gc. This replaces the conference firmware |
| Computer | **Mac mini (Mac18,5, Apple silicon), macOS 27.0** (build 26A428) |
| Mac software | The Apple-supplied `/usr/bin/python3` 3.9.6 (no extra packages), `picotool` 2.3.1 from Homebrew, and **Claude Code 2.1.295 / 2.1.296** (native install) |
| Link | **USB-C data cable from the badge to the Mac**: confirmed working end to end |

**Wi-Fi status:** confirmed end to end on a combined 2.4/5 GHz home network (WPA2/WPA3
mixed): the badge joins the 2.4 GHz side, finds the bridge by its beacon and polls it. A wrong
password is the usual cause of a join that never completes (this radio reports no error, it just
stays in "joining"). See [Wi-Fi](wifi.md#wi-fi-troubleshooting).

## Compatibility

| Device or setup | Status |
|---|---|
| Tufty 2350, Supabase Select 2026 edition | **Tested** (after reflashing to stock firmware, below) |
| Tufty 2350, retail Pimoroni unit | Should work: same board and same stock firmware. Not tested |
| Pimoroni firmware v4.0.0-ide.1 or later | Not tested. Stay on v3.1.1 unless you want to try |
| Badger 2350 (e-ink), Blinky 2350 (LED matrix) | Not supported. They run the same framework, but the themes are drawn for the Tufty's colour screen |
| Tufty 2040 (older badge) | Not supported: no Wi-Fi and a different firmware/API |
| Other Macs on recent macOS with `/usr/bin/python3` 3.9+ | Should work. Only the Mac above is tested |
| Windows 10/11 as the bridge | Supported, newer and less tested than the Mac: `install.ps1`, Python 3 and pyserial (the installer adds it), a login item under your user, and a Windows Firewall rule for port 8787 |
| Linux as the bridge | Not supported. A Linux computer can join a bridge ([other computers](other-computers.md)) |
| Any computer joining the bridge | Mac, Windows or Linux with Python 3 ([other computers](other-computers.md)) |
| Claude Code versions | Needs a version that writes `~/.claude/sessions/*.json` and puts `rate_limits` in the status-line JSON. 2.1.295+ does |
| Wi-Fi: 2.4 GHz, WPA2 (or WPA2/WPA3 mixed) with a password | Supported |
| Wi-Fi: 5 GHz only, WPA3 only, enterprise (802.1X, eduroam) or captive-portal hotel/conference networks | Not supported by the badge |
| Phone hotspot | Supported. On iPhone turn on *Maximize Compatibility* so it runs at 2.4 GHz. The bridge joins the same hotspot, or stays home with the [internet relay](relay.md) |
