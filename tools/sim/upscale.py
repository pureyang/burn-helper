#!/usr/bin/env python3
"""Nearest-neighbour upscale of a badge screenshot PNG (stdlib only).

    python3 tools/sim/upscale.py shot.png [scale] [out.png]
"""
import struct
import sys
import zlib


def read_png(p):
    d = open(p, "rb").read()
    i = 8
    idat = b""
    w = h = ct = 0
    while i < len(d):
        ln, = struct.unpack(">I", d[i:i + 4])
        tag = d[i + 4:i + 8]
        body = d[i + 8:i + 8 + ln]
        if tag == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", body[:10])
        if tag == b"IDAT":
            idat += body
        i += 12 + ln
    raw = zlib.decompress(idat)
    bpp = 4 if ct == 6 else 3
    stride = w * bpp
    rows = []
    prev = bytearray(stride)
    o = 0
    for _ in range(h):
        f = raw[o]
        o += 1
        line = bytearray(raw[o:o + stride])
        o += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, bpp, rows


def write_png(p, w, h, bpp, rows, s):
    raw = b"".join(b"\0" + b"".join(r[x * bpp:x * bpp + 3] * s for x in range(w)) for r in rows for _ in range(s))

    def ch(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)

    open(p, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w * s, h * s, 8, 2, 0, 0, 0))
                        + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))


if __name__ == "__main__":
    src = sys.argv[1]
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    out = sys.argv[3] if len(sys.argv) > 3 else src.replace(".png", "_x%d.png" % scale)
    w, h, bpp, rows = read_png(src)
    write_png(out, w, h, bpp, rows, scale)
    print(out)
