# Agents on other computers

The badge counts the Claude Code sessions on the Mac that runs the bridge. If you also run
Claude Code on other computers (Windows, Linux or another Mac), point them at that Mac and
their agents show on the badge too. They count as working agents, their tool calls play the
activity animations, and their status line feeds the usage hearts.

## What you need

- Python 3 on the other computer.
- A way to reach the Mac on port 8787. The easiest is Tailscale: with both computers on your
  tailnet, use the Mac's Tailscale name (`tailscale status` lists it), and it works at home and
  away. On the same home network, the Mac's IP address also works (System Settings → Network),
  but it can change.
- Not the relay's `https://` address from [away from home](relay.md): that one is read-only on
  purpose, for the badge. The Mac's Tailscale name with `http://` and port 8787 is the right one;
  it only answers computers on your tailnet.

This works with the badge at home or [away from home](relay.md): the computers report to the
Mac, and the badge reads from the Mac however it reaches it.

## Windows (PowerShell)

```powershell
py --version                       # no Python? winget install -e --id Python.Python.3.12, then open a new window
git clone https://github.com/pureyang/burn-helper $HOME\burn-helper
py $HOME\burn-helper\bridge\install.py --bridge http://<your-mac>:8787
Invoke-RestMethod http://<your-mac>:8787/health
```

The last line should answer `ok: True`. If `py` isn't found, use `python` instead. Then restart
your Claude Code sessions so they pick up the address.

## macOS or Linux

```sh
git clone https://github.com/pureyang/burn-helper ~/burn-helper
python3 ~/burn-helper/bridge/install.py --bridge http://<your-mac>:8787
curl http://<your-mac>:8787/health
```

## Check it works

Use Claude Code on the other computer for a moment. The badge should show one more agent and
play the animations for its tool calls. On the Mac, `curl -s localhost:8787/status` shows it
in `sessions` and `busy`.

## What it changes

- The other computer's `~/.claude/settings.json` (backed up first) gets the same async hooks and
  hearts status line the Mac uses, plus `BURN_HELPER_BRIDGE_URL` in its `env` section, so every
  Claude Code session there knows where to send. Nothing runs in the background on it.
- What it sends: the session id, event name, tool name and the computer's name, plus the usage
  numbers from the status line. Never prompts, file names, commands or tool output.
- If you already have a status line there, it is left alone, and that computer's usage won't
  feed the hearts. That is also the way to go if it signs into a different Claude account, so
  the hearts don't mix two accounts.
- Anyone who can reach port 8787 could post made-up activity. To stop that, set a shared secret:
  `--token <secret>` here, and the same `BURN_HELPER_TOKEN` for the bridge on the Mac (see the
  [bridge](../bridge/README.md)).

To remove it: run the same `install.py` with `--uninstall`.

## Limits

- Sessions on other computers count as working for 90 seconds after their last event, since the
  Mac can't see their session files. They're counted in the waiting number but not listed by name.
- Claude Code on the web runs in the cloud and can't reach your Mac, so those sessions only show
  up through the usage hearts.
