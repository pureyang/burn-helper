# Agents on other computers

There is one bridge: the computer the badge talks to (set up with the one-line installer, a
Mac or a Windows PC). Any other computer you run Claude Code on, Mac, Windows or Linux, can join
it. Its agents then count on the badge, its tool calls play the activity animations, and its
status line feeds the usage hearts.

## Join a computer to the bridge

Run the **join line** on each of these computers, not the bridge's one-liner: there is only
one bridge. (If you do run the bridge's one-liner on a computer on the same network, it hears the
bridge and offers to join it instead. And the join line stops and removes a bridge it finds on
the computer it runs on.) At the end of the bridge's install, the installer shows the join line with the
bridge's address filled in. To see it again, on the bridge run
`python3 ~/burn-helper/bridge/install.py --join-help` (on Windows:
`py $HOME\burn-helper\bridge\install.py --join-help`). The lines look like this.

On a Mac or Linux, in Terminal:

```
curl -fsSL https://raw.githubusercontent.com/pureyang/burn-helper/main/install.sh | bash -s -- --join 'http://<bridge>:8787/#k=<key>'
```

On Windows, in PowerShell (Python 3 is needed: `winget install -e --id Python.Python.3.12`):

```
$env:BURN_HELPER_JOIN='http://<bridge>:8787/#k=<key>'; irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1 | iex
```

The part after `#k=` is the bridge's key: without it the bridge turns the computer away. Keep
these lines to yourself. It gets the code into `~/burn-helper`, adds the hooks and the hearts status line, and checks
that the bridge answers. Then restart Claude Code on that computer.

## Tailscale on each computer

Tailscale lets your computers reach the bridge from any network. It belongs to the computer, and a
Tailscale account has nothing to do with a Claude account: put every computer on the same tailnet
(the private network your Tailscale account makes), whichever Claude accounts they use. The free
plan works. The badge isn't on Tailscale for this, so there is nothing to do on the badge.

Do the bridge first, then each other computer, before you run its join line:

1. Install Tailscale from [tailscale.com/download](https://tailscale.com/download). On Linux:
   `curl -fsSL https://tailscale.com/install.sh | sh`, then `sudo tailscale up`.
2. Open it and sign in with the **same Tailscale account** on every computer.
3. On the joining computer, check that it can see the bridge. `tailscale status` should list the
   bridge computer. With the Mac app the command is
   `/Applications/Tailscale.app/Contents/MacOS/Tailscale status`, and on Windows
   `& "C:\Program Files\Tailscale\tailscale.exe" status`. Then check the port itself:
   `nc -vz <bridge> 8787` on a Mac or Linux, `Test-NetConnection <bridge> -Port 8787` on Windows.

On the bridge, run `install.py --join-help` once Tailscale is on, so the join lines carry its
Tailscale address.

| Your setup | Tailscale | Burn Helper |
|---|---|---|
| Several computers, one Claude account | The same Tailscale account on all of them | The join line on each |
| Several computers, on different Claude accounts | The same Tailscale account on all of them | The join line on each. Each other Claude account gets its own row on the badge |
| The same Claude account on several computers | The same Tailscale account on all of them | The join line on each. That account counts once, however many computers report it |
| Two Claude accounts on one computer | Nothing more: the computer is already on | [`--add-account`](#a-second-claude-account) |
| Several user accounts on one computer | Sign in while logged in as the user who runs Claude Code | The join line as that user |
| A computer on another Tailscale account, such as a work one | See below | The join line as usual |

Tailscale's Mac and Windows apps run in your login session, which is why the user matters. If
`tailscale status` doesn't list the bridge for that user, Tailscale is off or on another account
there.

### A computer on another Tailscale account

A computer signed in to another tailnet can't see the bridge's `100.x` address, so the installer
says it can't reach the bridge. There are two ways to fix that.

- **Sign in to your account as well.** Tailscale can stay signed in to both: `tailscale login` adds
  an account and `tailscale switch <account>` changes to it. Only one is active at a time, though,
  so nothing reaches the bridge while the other one is.
- **Share the bridge computer with that tailnet.** This leaves that computer on its own tailnet. In
  the [admin console](https://login.tailscale.com/admin/machines) of the bridge's tailnet, open
  **Share** on the bridge's row, and accept the invite from the other tailnet. Whoever accepts has to be an Owner, Admin or IT
  admin there. Connections go only from that tailnet to the bridge, which is all a joined computer
  needs: it sends to the bridge, and the bridge never calls it back. The bridge usually keeps its
  `100.x` address there. If that address is taken it gets another, so use the one `tailscale status`
  shows on that computer.

Either way the join line still carries the key, and the bridge turns away anything without it.

### Keep the bridge reachable

Tailscale's sign-ins expire, after 180 days by default. When the bridge's does, every joined
computer loses it at once. For a computer that is always on, turn that off: in the
[admin console](https://login.tailscale.com/admin/machines), open the menu on the bridge's row, then
**Disable Key Expiry**.

## Which address

- **The bridge's Tailscale address** (`100.x.y.z`; `tailscale ip -4` on the bridge shows it), with
  both computers on [your tailnet](#tailscale-on-each-computer): works at home and away. This is
  what the bridge's install suggests when Tailscale runs there.
- **The bridge's IP address**, when both are on the same home network. It can change, though.
- Not the bridge's Tailscale name (`<name>.<tailnet>.ts.net`). With the relay from
  [away from home](relay.md) on, public DNS answers that name with the relay's address, which is
  read-only and has no port 8787, so a computer that isn't using Tailscale's DNS can't connect
  ("Unable to connect to the remote server").

This works with the badge at home or away from home: the computers report to the bridge, and
the badge reads from the bridge however it reaches it.

## Check it works

Use Claude Code on the joined computer for a moment. The badge should show one more agent and
play the animations for its tool calls. On the bridge, `/status` shows it in `sessions` and
`busy`: `curl -s localhost:8787/status` on a Mac, `Invoke-RestMethod localhost:8787/status` on
Windows.

If the installer says it can't reach the bridge at a `100.x` address, start with Tailscale on that
computer: it has to be installed, running and on [the bridge's tailnet](#tailscale-on-each-computer),
so `tailscale status` lists the bridge. Otherwise, check that the bridge is on, that the computer
can reach it (same network, or both on your tailnet) and, for a Windows bridge, that Windows
Firewall lets port 8787 in on that network. The installer's rule covers Private networks; if
your tailnet shows up as Public on the bridge, allow it there too.

Another VPN on the joining computer, such as a work or privacy VPN, can take over the `100.x`
addresses Tailscale uses. Then `tailscale status` looks fine and `tailscale ping` gets an answer,
but nothing reaches the bridge ("Unable to connect to the remote server"). Turn the other VPN
off, or set it to leave Tailscale's traffic alone (often called split tunnelling), and try again.
`Test-NetConnection <bridge> -Port 8787` on Windows, or `nc -vz <bridge> 8787` on a Mac or
Linux, shows when the connection gets through.

## What it changes

- The joined computer's `~/.claude/settings.json` (backed up first) gets the same async hooks
  and hearts status line the bridge uses, plus `BURN_HELPER_BRIDGE_URL` in its `env` section, so
  every Claude Code session there knows where to send. Nothing runs in the background on it.
  A bridge started there anyway, to try a change say, leaves the badge alone (no beacon, no USB
  link), so the badge can be plugged into a joined computer for development
  ([details](development.md#developing-on-another-computer)).
- What it sends: the session id, event name, tool name and the computer's name, plus the usage
  numbers from the status line. When a session starts, gets a prompt, finishes a turn or starts
  waiting, also its name (as Claude Code shows it) and its folder's name, so the badge can say
  which one is waiting. A computer joined before this was added shows its computer's name
  instead; run the join line there again to update it. Never prompts, file
  names, commands or tool output.
- If you already have a status line there, it is left alone, and that computer's usage won't
  reach the bridge: the hearts then lag whatever you spend there until another computer's status
  line reports. There are two ways to report it.

  To replace yours with the hearts one, run `python3 ~/burn-helper/bridge/install.py --force-statusline`
  (on Windows: `py $HOME\burn-helper\bridge\install.py --force-statusline`). `settings.json` is
  backed up first, and the computer stays joined. The join line can do the same: add
  `--force-statusline` after the address, or in PowerShell set `$env:BURN_HELPER_FORCE_STATUSLINE=1`
  first.

  To keep yours, have your status line command also pipe its input to `cc_statusline.py` and discard
  what that prints. In PowerShell, for example, at the top of your script:

  ```powershell
  $raw = $input | Out-String
  try { $raw | & "<python.exe>" "<burn-helper>/bridge/cc_statusline.py" | Out-Null } catch {}
  $json = $raw | ConvertFrom-Json
  ```

  If that computer signs into a different Claude account, its usage gets its own row on the badge
  and doesn't mix with the first account's hearts.
- The bridge's key goes in `BURN_HELPER_TOKEN` in the same `env` section. What the hooks and status
  line send is sealed with it (encrypted and signed), so nothing about your sessions crosses the
  network in the clear. Without it the computer sends nothing at all, so it doesn't count on the
  badge (see the [bridge](../bridge/README.md)). There is no setting that turns the seal off. A
  computer joined before the key was added stops reporting until you run its join line again.

To leave the bridge, run the same line with `--uninstall` instead of `--join ...` (on Windows,
`$env:BURN_HELPER_UNINSTALL=1` before the line instead of `BURN_HELPER_JOIN`).

## A second Claude account

To run another Claude account side by side with the first, set it up in a config folder of its own
(see [More than one Claude account](how-it-works.md#usage-meters)). On the bridge computer:

    python3 bridge/install.py --add-account work

On a joined computer, add the bridge's address and key, as they are in its join line (without the
key the bridge turns that account's reports away):

    python3 bridge/install.py --add-account work --bridge 'http://<bridge-computer>:8787/#k=<key>'

Then run `claude-work` and `/login` once with that account. On Windows the installer prints a
`claude-work` function to add to your PowerShell profile instead of a shell alias.

This needs nothing more from Tailscale. `/login` signs in to Claude only, and the second account
uses the connection the computer already has. If that computer isn't on Tailscale yet, see
[Tailscale on each computer](#tailscale-on-each-computer).

A Claude account counts once however many computers it runs on, whether it runs there with
`--add-account` or is the one signed in to that computer's `~/.claude`.

## Limits

- A session on a joined computer counts as waiting while it asks for permission or asks you a
  question. Once its turn is done it doesn't, even though Claude Code reminds you a minute later
  that it is waiting for your input. It clears as soon as that session does something: you reply,
  approve or deny, or end it. Switching to its window isn't enough: Claude Code doesn't report that.
- Sessions on joined computers count as working for 90 seconds after their last event, since the
  bridge can't see their session files. They're counted in the waiting number but not listed by
  name.
- Claude Code on the web runs in the cloud and can't reach the bridge, so those sessions only
  show up through the usage hearts.
