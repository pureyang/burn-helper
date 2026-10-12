# Making themes

A theme is one Python file that draws the badge's 160×120 screen for a given status. This page
is what a theme must provide and how much it can cost. The numbers were measured on a real
Tufty 2350 (stock firmware v3.1.1, MicroPython 1.29), not guessed.

## The contract

Create `badge/apps/burn_helper/theme_<id>.py` with a class that subclasses `scene.Theme`:

```python
import scene as S

class Theme(S.Theme):
    name = "mytheme"        # the id: lowercase, matches the file name
    label = "MY THEME"      # shown on the badge while it loads

    def build(self):
        """Make every sprite and backdrop once. Called once, with a LOADING screen up."""

    def draw(self, st, t):
        """Draw one frame. st is the Status below, t is milliseconds."""
```

`draw` runs up to 25 times a second. Rules that keep the badge stable:

- Never raise inside `draw`. An exception drops the badge into the firmware's error screen
  until a button is pressed.
- Do all allocation in `build`. Building images or strings every frame fragments the heap.
- Do not read files or touch the network in `draw`.
- Use original characters and names. Do not base a theme on a film, game or other
  trademarked work (this repo's own themes were renamed for that reason).

### What a theme receives (`st`)

| Field | Meaning |
|---|---|
| `st.level` | the gait: 0 sleep, 1 idle, 2 walk, 3 run, 4 sprint (`S.SLEEP` .. `S.SPRINT`) |
| `st.tier`, `st.agents` | activity level 0 to 15 (`S.tier_for`) and the agents working it is based on |
| `st.busy`, `st.waiting`, `st.idle` | sessions working now, sessions waiting for you, sessions idle |
| `st.waiting_list` | `[(name, seconds waiting)]` for the waiting sessions, when the bridge sends it |
| `st.sessions`, `st.subagents` | open sessions, running subagents |
| `st.tpm`, `st.tools` | tool calls per minute, tool calls today |
| `st.hearts` | 5-hour budget left in half units, 0 to 20, or `None` if unknown |
| `st.week` | 7-day budget left, 0 to 1, or `None` |
| `st.left5`, `st.left7` | microseconds until each limit resets (`gfx.countdown()` formats it) |
| `st.online` | fresh data from the bridge. When false, show `st.net` and a "no signal" look |
| `st.demo` | demo mode is running |

### What a theme should show

At minimum: an animation for each of the five gaits, the 5-hour budget (ten icons), the weekly
budget (a bar), the reset countdown, a state for "waiting for you" (`st.waiting > 0`), and an
offline state. The 15 activity levels come for free: `scene.Theme.draw` speeds the scroll up
with the level and draws `fx.py`'s speed lines, sparks, haze, edge and hyperspace over the
scene area (y 22 to 107), so keep the top bar above y 22 and the caption from y 108. A theme
can also use `st.tier` or `st.agents` for its own touches, as Forrest's crowd does. `figure.py` builds consistent walk, run and sprint cycles from a small posed
skeleton, and `gfx.py` has the shared pieces (`heart_set`, `draw_hearts`, `meter`, `countdown`,
`bubble`, pixel text). Look at `theme_hero.py` for the smallest complete example.

## Budgets

| Resource | Measured | Recommended for a theme |
|---|---|---|
| Heap | 8 MB total; 7.3 MB free with all three bundled themes loaded (775 KB used) | 600 KB of sprites, 1.5 MB at the very most |
| Cost of a bundled theme | 157, 190 and 344 KB | |
| Sprite cost | about 4 bytes per pixel: a 26×26 frame is 2.7 KB, an 8-frame cycle about 21 to 26 KB | |
| Build time | 1.4 s (157 KB) to 2.2 s (344 KB), about 6 to 9 ms per KB | under 4 s |
| Frame time | 11 to 14 ms to draw, capped at 25 fps (40 ms) | under 25 ms |
| Flash for the app | 10.4 MB free on `/system`, 0.5 MB on `/state` | keep code and assets under 200 KB |

The bundled themes hold between 39 and 72 images each. The expensive part of a theme is its
number of distinct frames, not its logic. A theme with the five levels at 8 frames each plus
a few event animations is well inside the budget.

## Adding a theme today

1. Write `theme_<id>.py` as above.
2. Register the id in four places, which is the main barrier to community themes right now:
   `THEMES` and `LABELS` in `badge/apps/burn_helper/__init__.py`, `THEMES` and the phone-panel
   button in `bridge/burn_helper_bridge.py`, and `THEMES` in `tools/simulate.py`.
3. Preview it without a badge: `python3 tools/simulate.py <id>` writes every level to
   `tools/sim/out/`.
4. Put it on the badge: `python3 tools/deploy.py`. Then run `python3 tools/netdebug.py`: its
   "memory" lines show the heap each theme took and how long it took to build.

## Suggested next steps

- Discover themes by scanning for `theme_*.py` on the badge, so step 2 disappears. The bridge
  would accept any well-formed id and let the badge decide.
- Keep only the active theme in memory. Today every theme that was shown stays loaded.
- Pre-render sprites to flash and load them, so a large theme builds in well under a second
  instead of seconds.
