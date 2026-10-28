#!/usr/bin/env python3
"""The badge stays with one bridge: the paired one, else the one in use, never flipping between
two bridges on the same network."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness  # noqa: E402

harness.install()
import net  # noqa: E402

MAC, PC = ("192.168.1.21", 8787), ("192.168.1.47", 8787)


def ago(ms):
    return net.ticks() - ms


# paired over USB with the Mac's bridge: the PC's bridge is ignored, whoever is heard first
n = net.Net([("home", "pw")], paired="mac-id")
n.up_t = net.ticks()
n._beacon(PC[0], PC[1], "pc-id")
assert n.bridge is None and PC[0] in n.others, "not ours, and ours may still show up"
n._beacon(MAC[0], MAC[1], "mac-id")
assert n.bridge == MAC
for _ in range(5):
    n._beacon(PC[0], PC[1], "pc-id")
    n._beacon(MAC[0], MAC[1], "mac-id")
    assert n.bridge == MAC, "never flips"
assert "another bridge" in "\n".join(n.dump()) and "Another bridge" in n.hint() or not n.fresh()

# the paired bridge goes quiet for over a minute: another one will do rather than nothing
n.paired_t = ago(net.PAIRED_GRACE_MS + 1000)
n.beacon_t = ago(net.NO_BEACON_MS + 1000)
n._beacon(PC[0], PC[1], "pc-id")
assert n.bridge == PC
n._beacon(MAC[0], MAC[1], "mac-id")
assert n.bridge == MAC, "and back to its own as soon as it is heard again"

# never paired: the first bridge heard stays while it keeps announcing itself
u = net.Net([("home", "pw")])
u._beacon(MAC[0], MAC[1], "")                 # an older bridge sends no id
assert u.bridge == MAC
u._beacon(PC[0], PC[1], "pc-id")
assert u.bridge == MAC, "the one in use stays"
u.beacon_t = ago(net.NO_BEACON_MS + 1000)
u._beacon(PC[0], PC[1], "pc-id")
assert u.bridge == PC, "it went quiet: take the other"
print("PASS bridge choice: the paired bridge always; unpaired, the one in use while it is there; "
      "a second bridge on the network is noted, not followed")
