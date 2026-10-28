#!/usr/bin/env python3
"""Copy the badge/ folder onto the Tufty's /system over USB serial.

    python3 tools/deploy.py            copy changed files, then restart the badge
    python3 tools/deploy.py --all      copy everything
    python3 tools/deploy.py --no-reset leave the badge at the REPL afterwards
    python3 tools/deploy.py --shot out.png   restart, wait, then pull a screenshot
    python3 tools/deploy.py --shot-only out.png [--view 0-2] [--page 0-2] [--demo 0|1|2]
        screenshot now (view 1 Desktop, 2 Debug; page 2 of Debug = Wi-Fi debug;
        demo 1 = tagged demo, 2 = untagged)

The stock firmware mounts /system read-only. Outside USB disk mode nothing else
is using that FAT volume, so this remounts it read-write for the copy, then
unmounts it (flushing writes) and resets.

badge/secrets.py (git-ignored) is installed as /system/secrets.py when present.
Works on macOS, Linux and Windows (use `py` instead of `python3` there; it needs pyserial).
"""
import base64
import hashlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from badge import Badge  # noqa: E402
import portable  # noqa: E402  (badge.py puts bridge/ on the path)

SRC = os.path.join(REPO, "badge")
# app folders from earlier versions, removed so the launcher does not list them
OLD_APPS = ("/system/apps/claude_buddy", "/system/apps/hearts_left")

REMOVE = """
import os
def _rm(p):
    try:
        st = os.stat(p)
    except OSError:
        return 0
    if st[0] & 0x4000:
        for n in os.listdir(p):
            _rm(p + '/' + n)
        os.rmdir(p)
    else:
        os.remove(p)
    return 1
print('removed', sum(_rm(p) for p in %r))
"""
SKIP = ("secrets.example.py",)

REMOUNT = """
import vfs, rp2, os
_sz = rp2.Flash().ioctl(4, 0) * rp2.Flash().ioctl(5, 0)
try:
    vfs.umount('/system')
except OSError:
    pass
vfs.mount(vfs.VfsFat(rp2.Flash(start=0, len=_sz - 1024 * 1024)), '/system')
print('rw-ok')
"""

HASHES = """
import os, hashlib, binascii
def _walk(p):
    for n in os.listdir(p):
        q = p + '/' + n
        if os.stat(q)[0] & 0x4000:
            _walk(q)
        else:
            h = hashlib.sha256()
            with open(q, 'rb') as f:
                while True:
                    b = f.read(1024)
                    if not b: break
                    h.update(b)
            print(q, binascii.hexlify(h.digest()).decode())
for _p in ('/system/apps/burn_helper',):
    try:
        _walk(_p)
    except OSError:
        pass
for _f in ('/system/main.py', '/system/secrets.py'):
    try:
        h = hashlib.sha256(open(_f, 'rb').read())
        print(_f, binascii.hexlify(h.digest()).decode())
    except OSError:
        pass
"""


def local_files():
    out = {}
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f in SKIP or f.endswith(".pyc") or f.startswith("."):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, SRC).replace(os.sep, "/")
            out["/system/" + rel] = p
    return out


def put(b, remote, data):
    d = os.path.dirname(remote)
    parts = d.strip("/").split("/")
    mk = "import os\n"
    acc = ""
    for part in parts:
        acc += "/" + part
        mk += "try:\n os.mkdir(%r)\nexcept OSError:\n pass\n" % acc
    out, err = b.exec(mk + "f=open(%r,'wb')\nf.close()\n" % remote)
    if err.strip():
        raise RuntimeError(err)
    step = 3000
    for i in range(0, len(data), step):
        chunk = base64.b64encode(data[i:i + step]).decode()
        out, err = b.exec("import binascii\nf=open(%r,'ab')\nf.write(binascii.a2b_base64(%r))\nf.close()\n" % (remote, chunk))
        if err.strip():
            raise RuntimeError(err)


def pull(b, remote, local):
    out, err = b.exec("import binascii\nf=open(%r,'rb')\nd=f.read()\nf.close()\nprint(binascii.b2a_base64(d).decode().strip())\n" % remote, timeout=60)
    if err.strip():
        raise RuntimeError(err)
    open(local, "wb").write(base64.b64decode(out.strip()))


def wait_for_port(timeout=30.0):
    """After a restart the badge's USB port comes back after a few seconds (longer on Windows)."""
    end = time.time() + timeout
    while time.time() < end:
        if os.environ.get("BADGE_PORT") or portable.find_ports():
            return
        time.sleep(0.5)


def screenshot(path, wait=12.0, view=None, demo=None, page=None):
    """Ask the running app for its current frame over USB and save it as a PNG."""
    time.sleep(wait)
    wait_for_port()
    b = Badge()
    try:
        if demo is not None:
            b.write(b"@DEMO %d\n" % demo)
            time.sleep(0.3)
        if page is not None:
            b.write(b"@PAGE %d\n" % page)
            time.sleep(0.3)
        if view is not None:
            b.write(b"@VIEW %d\n" % view)
            time.sleep(0.6)
        for attempt in range(3):
            b.read(0.3)
            b.write(b"@SHOT\n")
            got = b.read(15.0, idle=0, until=b"@END")
            if b"@PNG " in got and b"@END" in got:
                blob = got.split(b"@PNG ", 1)[1].split(b"@END", 1)[0]
                data = b"".join(base64.b64decode(p) for p in blob.split())
                open(path, "wb").write(data)
                if b"@INFO " in got:
                    print("  " + got.split(b"@INFO ", 1)[1].split(b"\n", 1)[0].decode(errors="replace").strip())
                return path
            time.sleep(2)
        raise RuntimeError("badge app did not answer @SHOT (is the Burn Helper app running?)")
    finally:
        b.close()


def main(argv):
    everything = "--all" in argv
    reset = "--no-reset" not in argv
    shot = None
    if "--shot" in argv:
        shot = argv[argv.index("--shot") + 1]
    view = int(argv[argv.index("--view") + 1]) if "--view" in argv else None
    demo = int(argv[argv.index("--demo") + 1]) if "--demo" in argv else None
    page = int(argv[argv.index("--page") + 1]) if "--page" in argv else None
    if "--shot-only" in argv:
        print("screenshot:", screenshot(argv[argv.index("--shot-only") + 1], wait=0, view=view, demo=demo, page=page))
        return
    files = local_files()
    b = Badge()
    out, err = b.exec(REMOUNT)
    if "rw-ok" not in out:
        sys.exit("could not remount /system read-write: %s %s" % (out, err))
    remote = {}
    if not everything:
        out, err = b.exec(HASHES, timeout=60)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 2:
                remote[parts[0]] = parts[1]
    sent = 0
    for rpath in sorted(files):
        data = open(files[rpath], "rb").read()
        h = hashlib.sha256(data).hexdigest()
        if remote.get(rpath) == h:
            continue
        put(b, rpath, data)
        sent += 1
        print("  sent", rpath, len(data), "bytes")
    # drop files the badge still has from earlier versions (renamed or deleted here)
    keep = sorted(r.rsplit("/", 1)[1] for r in files if r.startswith("/system/apps/burn_helper/") and r.count("/") == 4)
    out, err = b.exec("import os\nkeep = %r\nfor n in os.listdir('/system/apps/burn_helper'):\n"
                      "    if n not in keep and not (os.stat('/system/apps/burn_helper/' + n)[0] & 0x4000):\n"
                      "        os.remove('/system/apps/burn_helper/' + n)\n        print('pruned', n)\n" % (keep,))
    for line in out.splitlines():
        if line.startswith("pruned"):
            print("  removed stale", line.split(" ", 1)[1])
    out, err = b.exec(REMOVE % (OLD_APPS,))
    if "removed 1" in out or "removed 2" in out:
        print("  removed old app folder(s):", ", ".join(OLD_APPS))
    out, err = b.exec("import vfs\nvfs.umount('/system')\nprint('flushed')\n")
    print("%d file(s) updated, %d unchanged. %s" % (sent, len(files) - sent, out.strip()))
    if reset:
        b.raw_repl()
        b.write(b"import machine\nmachine.reset()\x04")
        print("Badge restarting.")
    b.close()
    if shot:
        print("screenshot:", screenshot(shot))


if __name__ == "__main__":
    main(sys.argv[1:])
