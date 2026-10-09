"""Install the picovector stand-ins as globals so badge modules import unchanged."""
import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP = os.path.join(REPO, "badge", "apps", "claude_buddy")

sys.path.insert(0, HERE)
import pvshim  # noqa: E402


class FakeBadge:
    def __init__(self):
        self.ticks = 0
        self._mode = 0
        self.pressed_set = set()

    def mode(self, m=None):
        if m is None:
            return self._mode
        self._mode = m

    def pressed(self, b=None):
        return b in self.pressed_set if b is not None else self.pressed_set

    def held(self, b=None):
        return False

    def released(self, b=None):
        return False

    def caselights(self, *a):
        return [0, 0, 0, 0]

    def battery_level(self):
        return 82

    def usb_connected(self):
        return True

    def is_charging(self):
        return False


def install():
    import time
    if not hasattr(time, "ticks_ms"):
        t0 = time.monotonic()
        time.ticks_ms = lambda: int((time.monotonic() - t0) * 1000)
        time.ticks_diff = lambda a, b: a - b
        time.ticks_add = lambda a, b: a + b
    for name in ("color", "rect", "vec2", "image", "font", "shape"):
        setattr(builtins, name, getattr(pvshim, name))
    builtins.screen = pvshim.image(160, 120)
    builtins.screen.font = pvshim.font.sins
    builtins.badge = FakeBadge()
    for i, b in enumerate(("BUTTON_A", "BUTTON_B", "BUTTON_C", "BUTTON_UP", "BUTTON_DOWN", "BUTTON_HOME")):
        setattr(builtins, b, 100 + i)
    builtins.LORES, builtins.HIRES, builtins.VSYNC = 0, 1, 2
    if APP not in sys.path:
        sys.path.insert(0, APP)


def new_screen(w=160, h=120):
    builtins.screen = pvshim.image(w, h)
    builtins.screen.font = pvshim.font.sins
    return builtins.screen
