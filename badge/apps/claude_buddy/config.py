# Where the badge gets its Wi-Fi networks and (optionally) a fixed bridge address.
#
#   /system/secrets.py            WIFI_SSID / WIFI_PASSWORD (stock firmware file),
#                                 optional WIFI_EXTRA = [("ssid", "pass"), ...]
#                                 optional BRIDGE = "192.168.1.20:8787"
#   /state/claude_buddy_net.json  networks and bridge added from a phone via the
#                                 setup portal (hold B). Tried first.

import json

NET_FILE = "/state/claude_buddy_net.json"


def _secrets():
    try:
        import secrets
        return secrets
    except Exception:  # noqa: BLE001
        return None


def load_portal():
    try:
        with open(NET_FILE) as f:
            d = json.loads(f.read())
        if isinstance(d, dict):
            return d
    except Exception:  # noqa: BLE001
        pass
    return {"networks": [], "bridge": ""}


def save_portal(d):
    try:
        import os
        try:
            os.mkdir("/state")
        except OSError:
            pass
        with open(NET_FILE, "w") as f:
            f.write(json.dumps(d))
        return True
    except Exception:  # noqa: BLE001
        return False


def networks():
    out = []
    for n in load_portal().get("networks", []):
        if isinstance(n, (list, tuple)) and len(n) == 2 and n[0]:
            out.append((n[0], n[1]))
    s = _secrets()
    if s is not None:
        ssid = getattr(s, "WIFI_SSID", "")
        if ssid:
            out.append((ssid, getattr(s, "WIFI_PASSWORD", "")))
        for n in getattr(s, "WIFI_EXTRA", []) or []:
            if n and n[0]:
                out.append((n[0], n[1]))
    seen = []
    uniq = []
    for n in out:
        if n[0] not in seen:
            seen.append(n[0])
            uniq.append(n)
    return uniq


def _parse_bridge(v):
    v = (v or "").strip()
    if not v:
        return None
    if v.startswith("http://"):
        v = v[7:]
    v = v.split("/")[0]
    if ":" in v:
        host, port = v.rsplit(":", 1)
        try:
            return (host, int(port))
        except ValueError:
            return None
    return (v, 8787)


def bridge():
    b = _parse_bridge(load_portal().get("bridge", ""))
    if b:
        return b
    s = _secrets()
    return _parse_bridge(getattr(s, "BRIDGE", "") if s else "")
