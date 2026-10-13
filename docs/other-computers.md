# Agents on other computers

There is one bridge: the computer the badge talks to (set up with the one-line installer, a
Mac or a Windows PC). Any other computer you run Claude Code on, Mac, Windows or Linux, can join
it. Its agents then count on the badge, its tool calls play the activity animations, and its
status line feeds the usage hearts.

## Join a computer to the bridge

At the end of the bridge's install, the installer shows the line to run, with the bridge's
address filled in. To see it again, on the bridge run
`python3 ~/burn-helper/bridge/install.py --join-help` (on Windows:
`py $HOME\burn-helper\bridge\install.py --join-help`). The lines look like this.

On a Mac or Linux, in Terminal:

```
curl -fsSL https://raw.githubusercontent.com/pureyang/burn-helper/main/install.sh | bash -s -- --join http://<bridge>:8787
```

On Windows, in PowerShell (Python 3 is needed: `winget install -e --id Python.Python.3.12`):

```
$env:BURN_HELPER_JOIN='http://<bridge>:8787'; irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1 | iex
```

It gets the code into `~/burn-helper`, adds the hooks and the hearts status line, and checks
that the bridge answers. Then restart Claude Code on that computer.

## Which address

- **The bridge's Tailscale name**, with both computers on your tailnet: works at home and away.
  `tailscale status` lists it. This is what the bridge's install suggests when Tailscale runs there.
- **The bridge's IP address**, when both are on the same home network. It can change, though.
- Not the relay's `https://` address from [away from home](relay.md): that one is read-only on
  purpose, for the badge. The Tailscale name with `http://` and port 8787 is the right one; it
  only answers computers on your tailnet.

This works with the badge at home or away from home: the computers report to the bridge, and
the badge reads from the bridge however it reaches it.

## Check it works

Use Claude Code on the joined computer for a moment. The badge should show one more agent and
play the animations for its tool calls. On the bridge, `/status` shows it in `sessions` and
`busy`: `curl -s localhost:8787/status` on a Mac, `Invoke-RestMethod localhost:8787/status` on
Windows.

If the installer says it can't reach the bridge, check that the bridge is on, that the computer
can reach it (same network, or both on your tailnet) and, for a Windows bridge, that Windows
Firewall lets port 8787 in on that network. The installer's rule covers Private networks; if
your tailnet shows up as Public on the bridge, allow it there too.

## What it changes

- The joined computer's `~/.claude/settings.json` (backed up first) gets the same async hooks
  and hearts status line the bridge uses, plus `BURN_HELPER_BRIDGE_URL` in its `env` section, so
  every Claude Code session there knows where to send. Nothing runs in the background on it.
- What it sends: the session id, event name, tool name and the computer's name, plus the usage
  numbers from the status line. Never prompts, file names, commands or tool output.
- If you already have a status line there, it is left alone, and that computer's usage won't
  feed the hearts. That is also the way to go if it signs into a different Claude account, so
  the hearts don't mix two accounts.
- Anyone who can reach port 8787 could post made-up activity. To stop that, set a shared secret:
  run `bridge/install.py --bridge <url> --token <secret>` on the joined computer, and set the same
  `BURN_HELPER_TOKEN` for the bridge (see the [bridge](../bridge/README.md)).

To leave the bridge, run the same line with `--uninstall` instead of `--join ...` (on Windows,
`$env:BURN_HELPER_UNINSTALL=1` before the line instead of `BURN_HELPER_JOIN`).

## Limits

- Sessions on joined computers count as working for 90 seconds after their last event, since the
  bridge can't see their session files. They're counted in the waiting number but not listed by
  name.
- Claude Code on the web runs in the cloud and can't reach the bridge, so those sessions only
  show up through the usage hearts.
