"""A small CPython stand-in for the badge's `picovector` drawing API.

It implements the subset the Burn Helper app uses, with the same pixel rules
measured on the real Tufty 2350: nearest-neighbour scaled blits, negative-width
flips, alpha-blended pens, and the ROM pixel fonts (".ppf") rendered with the
firmware's advance rules (glyph width + 1, space = (height + 2) // 4).
"""
import math
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FONT_DIR = os.path.join(HERE, ".cache", "fonts")


# ----------------------------------------------------------------- fonts

def _vu(b, i):
    v = 0
    while True:
        c = b[i]
        i += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, i


def extract_fonts():
    """Pull the ROM fonts out of the stock firmware UF2 into .cache/fonts."""
    if os.path.isdir(FONT_DIR) and os.listdir(FONT_DIR):
        return
    uf2 = os.path.join(REPO, "firmware", "tufty-v3.1.1-micropython.uf2")
    data = open(uf2, "rb").read()
    blocks = {}
    for i in range(0, len(data), 512):
        b = data[i:i + 512]
        m0, m1, flags, addr, size = struct.unpack("<5I", b[:20])
        if m0 == 0x0A324655 and m1 == 0x9E5D5157:
            blocks[addr] = b[32:32 + size]
    base = 0x10200000
    end = max(a + len(d) for a, d in blocks.items() if a >= base and a < 0x10300000)
    img = bytearray(end - base)
    for a, d in blocks.items():
        if base <= a < end:
            img[a - base:a - base + len(d)] = d
    assert img[:3] == b"\xd2\xcd\x31", "ROMFS header not found"
    os.makedirs(FONT_DIR, exist_ok=True)

    def parse(i, stop, path):
        while i < stop:
            kind, i = _vu(img, i)
            ln, i = _vu(img, i)
            p = i
            i += ln
            if kind in (4, 5):
                nl, q = _vu(img, p)
                name = img[q:q + nl].decode()
                q += nl
                full = path + "/" + name
                if kind == 4:
                    parse(q, p + ln, full)
                elif full.startswith("/fonts/"):
                    out = b""
                    while q < p + ln:
                        k2, q = _vu(img, q)
                        l2, q = _vu(img, q)
                        if k2 == 2:
                            out += bytes(img[q:q + l2])
                        q += l2
                    open(os.path.join(FONT_DIR, name), "wb").write(out)

    ln, i = _vu(img, 3)
    parse(i, i + ln, "")


class PixelFont:
    def __init__(self, path):
        d = open(path, "rb").read()
        cnt, self.w, self.h = struct.unpack_from(">HHH", d, 8)
        self.bpr = (self.w + 7) // 8
        base = 46 + cnt * 6
        self.glyphs = {}
        for i in range(cnt):
            cp, gw = struct.unpack_from(">IH", d, 46 + i * 6)
            off = base + i * self.h * self.bpr
            rows = [int.from_bytes(d[off + y * self.bpr: off + (y + 1) * self.bpr], "big") for y in range(self.h)]
            self.glyphs[cp] = (gw, rows)
        self.space = (self.h + 2) // 4

    def advance(self, ch):
        if ch == " ":
            return self.space
        g = self.glyphs.get(ord(ch))
        return (g[0] + 1) if g else 0


class _Fonts:
    def __getattr__(self, name):
        extract_fonts()
        p = os.path.join(FONT_DIR, name + ".ppf")
        if not os.path.exists(p):
            raise AttributeError(name)
        f = PixelFont(p)
        setattr(self, name, f)
        return f


font = _Fonts()


# ----------------------------------------------------------------- basics

class color:
    __slots__ = ("r", "g", "b", "a")

    def __init__(self, r, g, b, a=255):
        self.r = int(max(0, min(255, r)))
        self.g = int(max(0, min(255, g)))
        self.b = int(max(0, min(255, b)))
        self.a = int(max(0, min(255, a)))

    @staticmethod
    def rgb(r, g, b, a=255):
        return color(r, g, b, a)

    @staticmethod
    def hsv(h, s, v, a=255):
        h = (h % 256) / 256.0 * 6
        s /= 255.0
        v /= 255.0
        i = int(h)
        f = h - i
        p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
        r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
        return color(r * 255, g * 255, b * 255, a)

    def __repr__(self):
        return "color.rgb(%d, %d, %d, %d)" % (self.r, self.g, self.b, self.a)


for _n, _v in (("black", (0, 0, 0)), ("white", (255, 255, 255)), ("red", (255, 0, 0)),
               ("green", (0, 255, 0)), ("blue", (0, 0, 255)), ("yellow", (255, 255, 0)),
               ("grey", (128, 128, 128)), ("orange", (255, 128, 0)), ("navy", (0, 0, 128)),
               ("lime", (128, 255, 0))):
    setattr(color, _n, color(*_v))


class vec2:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class rect:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _Shape:
    def __init__(self, kind, args):
        self.kind = kind
        self.args = args


class shape:
    @staticmethod
    def circle(x, y, r):
        return _Shape("circle", (x, y, r))

    @staticmethod
    def rectangle(x, y, w, h):
        return _Shape("rect", (x, y, w, h))


# ----------------------------------------------------------------- image

class image:
    OFF = 0
    X2 = 1
    X4 = 2

    def __init__(self, w, h, _parent=None, _ox=0, _oy=0):
        self.width = int(w)
        self.height = int(h)
        if _parent is None:
            self._buf = bytearray(self.width * self.height * 4)
            self._stride = self.width
            self._ox = 0
            self._oy = 0
        else:
            self._buf = _parent._buf
            self._stride = _parent._stride
            self._ox = _parent._ox + _ox
            self._oy = _parent._oy + _oy
        self.pen = color(255, 255, 255)
        self.alpha = 255
        self.font = None
        self.antialias = 0

    @property
    def clip(self):
        return rect(0, 0, self.width, self.height)

    # pixels
    def _blend(self, x, y, r, g, b, a):
        if not (0 <= x < self.width and 0 <= y < self.height) or a <= 0:
            return
        i = ((self._oy + y) * self._stride + self._ox + x) * 4
        buf = self._buf
        if a >= 255:
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b
            buf[i + 3] = 255
            return
        da = buf[i + 3]
        ia = 255 - a
        buf[i] = (r * a + buf[i] * ia + 127) // 255
        buf[i + 1] = (g * a + buf[i + 1] * ia + 127) // 255
        buf[i + 2] = (b * a + buf[i + 2] * ia + 127) // 255
        buf[i + 3] = min(255, a + (da * ia) // 255)

    def get(self, x, y):
        i = ((self._oy + y) * self._stride + self._ox + x) * 4
        b = self._buf
        return color(b[i], b[i + 1], b[i + 2], b[i + 3])

    def _penrgba(self):
        p = self.pen
        return p.r, p.g, p.b, (p.a * self.alpha) // 255

    def put(self, x, y):
        r, g, b, a = self._penrgba()
        self._blend(int(x), int(y), r, g, b, a)

    def clear(self):
        self.rectangle(0, 0, self.width, self.height)

    def rectangle(self, x, y=None, w=None, h=None):
        if isinstance(x, rect):
            x, y, w, h = x.x, x.y, x.w, x.h
        r, g, b, a = self._penrgba()
        x0 = max(0, int(math.floor(x)))
        y0 = max(0, int(math.floor(y)))
        x1 = min(self.width, int(math.floor(x + w)))
        y1 = min(self.height, int(math.floor(y + h)))
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                self._blend(xx, yy, r, g, b, a)

    def line(self, x0, y0, x1, y1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        r, g, b, a = self._penrgba()
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._blend(x0, y0, r, g, b, a)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def triangle(self, x0, y0, x1, y1, x2, y2):
        r, g, b, a = self._penrgba()
        pts = sorted([(x0, y0), (x1, y1), (x2, y2)], key=lambda p: p[1])
        ys = int(math.floor(pts[0][1]))
        ye = int(math.ceil(pts[2][1]))

        def xs_at(y):
            out = []
            for (ax, ay), (bx, by) in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[0], pts[2])):
                if ay == by:
                    continue
                if min(ay, by) <= y <= max(ay, by):
                    out.append(ax + (y - ay) * (bx - ax) / (by - ay))
            return out

        for yy in range(ys, ye):
            xs = xs_at(yy + 0.5)
            if len(xs) >= 2:
                for xx in range(int(math.floor(min(xs) + 0.5)), int(math.floor(max(xs) + 0.5))):
                    self._blend(xx, yy, r, g, b, a)

    def shape(self, s):
        r, g, b, a = self._penrgba()
        if s.kind == "circle":
            cx, cy, rad = s.args
            for yy in range(int(cy - rad - 1), int(cy + rad + 2)):
                for xx in range(int(cx - rad - 1), int(cx + rad + 2)):
                    if (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 <= rad * rad:
                        self._blend(xx, yy, r, g, b, a)
        elif s.kind == "rect":
            self.rectangle(*s.args)

    def window(self, x, y=None, w=None, h=None):
        if isinstance(x, rect):
            x, y, w, h = x.x, x.y, x.w, x.h
        return image(w, h, _parent=self, _ox=int(x), _oy=int(y))

    def blit(self, src, a, b=None):
        if b is None:
            sr = rect(0, 0, src.width, src.height)
            dst = a
        else:
            sr, dst = a, b
        if isinstance(dst, vec2):
            dst = rect(dst.x, dst.y, sr.w, sr.h)
        flip = dst.w < 0
        dw = abs(dst.w)
        dh = dst.h
        if dw == 0 or dh == 0:
            return
        x0 = int(math.floor(dst.x))
        y0 = int(math.floor(dst.y))
        alpha = self.alpha * src.alpha // 255
        for yy in range(int(dh)):
            ty = y0 + yy
            if ty < 0 or ty >= self.height:
                continue
            syy = int(sr.y + yy * sr.h / dh)
            for xx in range(int(dw)):
                tx = x0 + xx
                if tx < 0 or tx >= self.width:
                    continue
                sxx = int(sr.x + xx * sr.w / dw)
                if flip:
                    sxx = int(sr.x + sr.w - 1 - (xx * sr.w / dw))
                i = ((src._oy + syy) * src._stride + src._ox + sxx) * 4
                sa = src._buf[i + 3]
                if sa:
                    self._blend(tx, ty, src._buf[i], src._buf[i + 1], src._buf[i + 2], sa * alpha // 255)

    def measure_text(self, s):
        f = self.font
        return float(sum(f.advance(c) for c in s)), float(f.h)

    def text(self, s, x, y):
        f = self.font
        r, g, b, a = self._penrgba()
        cx = int(x)
        y = int(y)
        for ch in s:
            if ch == " ":
                cx += f.space
                continue
            gl = f.glyphs.get(ord(ch))
            if not gl:
                continue
            gw, rows = gl
            for yy, row in enumerate(rows):
                if not row:
                    continue
                for xx in range(f.w):
                    if row >> (f.bpr * 8 - 1 - xx) & 1:
                        self._blend(cx + xx, y + yy, r, g, b, a)
            cx += gw + 1
        return rect(x, y, cx - x, f.h)

    # ---- export
    def to_png(self, path, scale=1, alpha=False):
        w, h = self.width, self.height
        n = 4 if alpha else 3
        raw = bytearray()
        for y in range(h):
            row = bytearray()
            for x in range(w):
                i = ((self._oy + y) * self._stride + self._ox + x) * 4
                px = bytes(self._buf[i:i + n])
                row += px * scale
            line = b"\x00" + bytes(row)
            raw += line * scale

        def chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 6 if alpha else 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
        open(path, "wb").write(png)
