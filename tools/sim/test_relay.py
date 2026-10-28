#!/usr/bin/env python3
"""The bridge's internet relay listener: the key gate, what it reveals, and its connection cap.

Runs the real RelayServer and RelayHandler on a spare local port with a stand-in bridge.
"""
import http.client
import os
import socket
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bridge"))
import burn_helper_bridge as B  # noqa: E402

KEY = "k" * 32


class FakeBridge:
    def status(self):
        return {"level": 2, "busy": 1}


B.BRIDGE = FakeBridge()
B.RELAY = {"url": "https://example.ts.net", "key": KEY}
srv = B.RelayServer(("127.0.0.1", 0), B.RelayHandler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def get(path, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path, headers=headers or {})
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, dict(r.getheaders()), body


status, headers, body = get("/status", {"X-Burn-Helper-Key": KEY})
assert status == 200 and b'"busy":1' in body, (status, body)
assert "Python" not in headers.get("Server", ""), headers.get("Server")
assert get("/status")[0] == 404, "no key must look like nothing is there"
assert get("/status", {"X-Burn-Helper-Key": "x" * 32})[0] == 404, "wrong key"
assert get("/status?key=" + KEY)[0] == 404, "a key in the URL must not work (it would end up in logs)"
assert get("/", {"X-Burn-Helper-Key": KEY})[0] == 404, "only /status is served"
assert get("/health")[0] == 200

# hold every slot with idle connections, then check one more is turned away
idle = []
for _ in range(B.RelayServer.MAX_CONNECTIONS):
    s = socket.create_connection(("127.0.0.1", port))
    idle.append(s)
time.sleep(0.3)
extra = socket.create_connection(("127.0.0.1", port))
extra.settimeout(3)
extra.sendall(b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n")
try:
    turned_away = extra.recv(100) == b""
except (ConnectionResetError, socket.timeout):
    turned_away = True
assert turned_away, "a connection over the cap must be dropped, not served"
for s in idle:
    s.close()
time.sleep(0.5)
assert get("/status", {"X-Burn-Helper-Key": KEY})[0] == 200, "slots must free up again"
srv.shutdown()
print("PASS relay: key in header only, 404 for anything else, no Python version, %d-connection cap"
      % B.RelayServer.MAX_CONNECTIONS)
