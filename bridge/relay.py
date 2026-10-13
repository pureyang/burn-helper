#!/usr/bin/env python3
"""Let the badge reach the bridge from anywhere, through Tailscale Funnel.

    python3 bridge/relay.py on       publish the relay and restart the bridge
    python3 bridge/relay.py status   show the relay and check it answers from the internet
    python3 bridge/relay.py off      stop publishing it

At home the badge finds the bridge on the local network. Away from home it uses the relay:
Tailscale Funnel gives this Mac a public HTTPS address (https://<mac>.<tailnet>.ts.net) that
forwards to a second, read-only listener on 127.0.0.1:8788. That listener answers only
GET /status, and only with a random key. Plug the badge in once afterwards: the bridge hands
it the address and key over the USB cable, never over Wi-Fi.

Works with anyone's Tailscale account: the address comes from whichever tailnet this Mac is
signed into, and every install makes its own key. Tested with the Standalone Tailscale app;
Tailscale documents Funnel on macOS for the open-source tailscaled, the fallback if public DNS
never appears for your Mac. See docs/relay.md.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import burn_helper_bridge as B  # noqa: E402

LABEL = "com.burnhelper.bridge"
TS_APP = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
TS_CLI = ("/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale")     # Homebrew's tailscaled


def tailscale():
    t = shutil.which("tailscale") or next((c for c in TS_CLI if os.path.exists(c)), None) \
        or (TS_APP if os.path.exists(TS_APP) else None)
    if not t:
        sys.exit("Tailscale is not installed on this Mac. For the relay, install the open-source "
                 "tailscaled: brew install tailscale (see docs/relay.md).")
    return t



def public_ip(host):
    """The address public DNS gives for host (asked over HTTPS, so this Mac's own Tailscale DNS,
    which knows the tailnet name, cannot answer for it), or None."""
    req = urllib.request.Request("https://cloudflare-dns.com/dns-query?name=%s&type=A" % host,
                                 headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            answers = json.load(r).get("Answer") or []
        return next((a["data"] for a in answers if a.get("type") == 1), None)
    except Exception:  # noqa: BLE001
        return None


def ts(*args, check=True):
    r = subprocess.run([tailscale()] + list(args), capture_output=True, text=True, timeout=60)
    if check and r.returncode != 0:
        sys.exit("tailscale %s failed:\n%s" % (" ".join(args), (r.stdout + r.stderr).strip()))
    return r


def mac_url():
    st = json.loads(ts("status", "--json").stdout)
    if st.get("BackendState") != "Running":
        sys.exit("Tailscale is not connected (state %s). Open Tailscale and sign in." % st.get("BackendState"))
    name = (st.get("Self") or {}).get("DNSName", "").rstrip(".")
    if not name:
        sys.exit("Tailscale did not report this Mac's name; is MagicDNS on for the tailnet?")
    return "https://" + name


def save(relay):
    os.makedirs(B.STATE_DIR, exist_ok=True)
    fd = os.open(B.RELAY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(relay, f)


def restart_bridge():
    r = subprocess.run(["launchctl", "kickstart", "-k", "gui/%d/%s" % (os.getuid(), LABEL)],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print("Restarted the bridge.")
    else:
        print("Restart the bridge yourself (it is not running as %s)." % LABEL)


def check(relay):
    """Reach the relay the way the badge will: by its public address, from outside the tailnet."""
    host = relay["url"].split("://", 1)[1]
    ip = public_ip(host)
    if ip is None:
        return ("is not reachable from the internet yet: public DNS has no address for %s. Tailscale "
                "says this takes up to 10 minutes after Funnel starts; it has taken about 20. If it "
                "never appears, see docs/relay.md." % host)
    r = subprocess.run(["curl", "-s", "-m", "15", "--resolve", "%s:443:%s" % (host, ip),
                        "-H", "X-Burn-Helper-Key: " + relay["key"], relay["url"] + "/status"],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        return "answers from the internet through %s (level %s, %s agents busy)" % (ip, d.get("level"), d.get("busy"))
    except ValueError:
        return "has a public address (%s) but did not answer with the status yet." % ip


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    current = B.load_relay()
    if cmd == "on":
        relay = {"url": mac_url(), "key": current["key"] if current else secrets.token_hex(16)}
        r = ts("funnel", "--bg", str(B.RELAY_PORT), check=False)
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            sys.exit("Tailscale would not start Funnel:\n%s\n\nIf it mentions a URL, open it to allow Funnel "
                     "for this Mac, then run this again." % out)
        save(relay)
        restart_bridge()
        print("Relay on: %s" % relay["url"])
        print("Next: plug the badge into this Mac once, so it learns the relay. After that it works "
              "on any Wi-Fi with internet. Check it with: python3 bridge/relay.py status "
              "(public DNS can take 10 to 20 minutes the first time).")
    elif cmd == "off":
        ts("funnel", "--https=443", "off", check=False)
        if os.path.exists(B.RELAY_FILE):
            os.remove(B.RELAY_FILE)
        restart_bridge()
        print("Relay off. The badge falls back to the bridge on the local network.")
    elif cmd == "status":
        if not current:
            print("Relay is off. Turn it on with: python3 bridge/relay.py on")
            return 0
        print("Relay: %s" % current["url"])
        print("It %s" % check(current))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
