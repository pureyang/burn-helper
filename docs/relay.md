# Away from home: the internet relay

At home the badge finds the bridge on your network by itself. Anywhere else it can reach your
Mac through Tailscale Funnel, using your own Tailscale account: the badge joins any Wi-Fi with
internet (a phone hotspot works) and gets the same status over HTTPS.

## What you need

- Tailscale on the Mac, signed in to your account (the free plan works).
- Funnel allowed for the Mac. Tailscale needs MagicDNS and HTTPS certificates on for the
  tailnet, and the `funnel` attribute in the tailnet policy; the first `tailscale funnel` run
  offers to turn these on.
- The Mac awake and online while you are away. It sleeps by default: **System Settings →
  Energy → Prevent automatic sleeping when the display is off**.

## Turn it on

1. On the Mac: `python3 ~/burn-helper/bridge/relay.py on`
2. Plug the badge into the Mac once. It shows **INTERNET RELAY READY**: the bridge has handed it
   the relay's address and key over the cable.
3. Check it: `python3 ~/burn-helper/bridge/relay.py status` should say the relay answers from the
   internet. The first time, Tailscale's public DNS for your Mac can take a while: Tailscale says
   up to 10 minutes, and it took about 20 in our test.

That's it. Away from home the badge switches to the relay by itself, and back on your home
network it uses the local bridge again. Desktop mode shows `DATA INTERNET RELAY` while it is on
the relay.

## How it works

- Funnel publishes `https://<your-mac>.<your-tailnet>.ts.net`, which forwards to a second
  listener the bridge runs on `127.0.0.1:8788`.
- That listener answers only `GET /status`, and only with the right key; everything else gets
  "not found". It cannot change anything on the Mac.
- The key is random for each install, saved in `~/.claude/burn-helper/relay.json` (readable only
  by you), and reaches the badge over the USB cable only, never over Wi-Fi.
- The badge switches to the relay after 10 seconds on Wi-Fi without hearing the bridge on the
  local network, and polls it every 5 seconds over one kept-open HTTPS connection. Before
  sending the key it checks the certificate against Let's Encrypt's roots, and sets its clock
  from an internet time server if it is wrong (TLS needs the right date).
- The animation keeps running: the connection and handshake are done a step at a time between
  frames, with one pause of up to about a second when a new connection's certificate is
  checked.

## Turn it off

`python3 ~/burn-helper/bridge/relay.py off` stops publishing and deletes the key. Turning it on
again makes a new key, so plug the badge in once more after that.

## If it does not work

- **`relay.py status` never finds a public address.** Check in the Tailscale admin console that
  Funnel is allowed for this Mac. We tested with Tailscale's Standalone Mac app; Tailscale
  documents Funnel on macOS for the open-source `tailscaled`, so if yours never publishes,
  quit the Tailscale app and switch: `brew install tailscale`, `sudo brew services start
  tailscale`, `sudo tailscale up`. The Mac may come back under a new tailnet name, so run
  `relay.py on` again and plug the badge in once.
- **The badge's Wi-Fi report says "relay poll failed: HTTP 404".** The key changed: plug the badge
  into the Mac once.
- **"Bridge not answering" away from home.** The Mac is asleep or offline.
- **Testing at home.** Send `@RELAY 1` over USB to make the badge use the relay even when the
  local bridge is there, and `@RELAY 0` to go back (see [development](development.md)).

The relay's address includes your Mac's and tailnet's names, so treat it as semi-private; what
it serves (agent counts, usage, and the names of sessions waiting for you) needs the key.
