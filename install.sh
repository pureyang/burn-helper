#!/bin/bash
# Burn Helper installer for macOS (and, to join a bridge, Linux). One line:
#
#   curl -fsSL https://raw.githubusercontent.com/pureyang/burn-helper/main/install.sh | bash
#
# or from a checkout: ./install.sh
#
# There is one bridge: the computer the badge talks to. This sets it up on this Mac.
# On any other computer, join it to that bridge instead (the bridge install prints this
# line with its address filled in):
#
#   curl -fsSL https://raw.githubusercontent.com/pureyang/burn-helper/main/install.sh | bash -s -- --join http://<bridge>:8787
#
# Options (after `| bash -s --` when piping):
#   --join URL   join the bridge at URL: only hooks and a status line, no badge, no login item
#   --yes        accept every step without asking (Wi-Fi is then set up from your phone)
#   --no-flash   never replace the badge's firmware
#   --no-badge   only set up the Mac side
#   --no-bridge  only set up the badge
#   --dry-run    show what would happen, change nothing
#   --uninstall  remove the hooks, status line and login item from this computer
#
# What it does: gets the code into ~/burn-helper, installs the Mac bridge (async
# Claude Code hooks, a hearts status line, a login item; settings.json is backed
# up first), then backs up and flashes the badge if needed, asks for Wi-Fi, and
# copies the app onto it. At the end it shows the line to run on other computers.
set -e

REPO_URL="${BURN_HELPER_REPO:-${HEARTS_LEFT_REPO:-https://github.com/pureyang/burn-helper.git}}"
REF="${BURN_HELPER_REF:-${HEARTS_LEFT_REF:-main}}"
DEST="${BURN_HELPER_DIR:-${HEARTS_LEFT_DIR:-$HOME/burn-helper}}"
PY=/usr/bin/python3

YES=0 NO_BADGE=0 NO_BRIDGE=0 DRY=0 UNINSTALL=0
JOIN="${BURN_HELPER_JOIN:-}"
BADGE_ARGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --join) [ -n "${2:-}" ] || { echo "--join needs the bridge's address, e.g. --join http://my-mac:8787" >&2; exit 2; }
            JOIN="$2"; shift ;;
    --join=*) JOIN="${1#--join=}" ;;
    --yes|-y) YES=1; BADGE_ARGS="$BADGE_ARGS --yes" ;;
    --no-flash) BADGE_ARGS="$BADGE_ARGS --no-flash" ;;
    --no-badge) NO_BADGE=1 ;;
    --no-bridge) NO_BRIDGE=1 ;;
    --dry-run) DRY=1; BADGE_ARGS="$BADGE_ARGS --dry-run" ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,31p' "${BASH_SOURCE[0]:-/dev/null}" 2>/dev/null | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '\033[1;31m\xe2\x99\xa5\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m\xe2\x99\xa5 %s\033[0m\n' "$*" >&2; exit 1; }

# yes/no question that works under `curl | bash` (stdin is the script there)
ask() {
  [ "$YES" = 1 ] && return 0
  if ! (exec < /dev/tty) 2>/dev/null; then
    say "No terminal to ask on. Rerun with: curl -fsSL <url> | bash -s -- --yes"
    return 1
  fi
  printf '%s [Y/n] ' "$1" > /dev/tty
  read -r answer < /dev/tty || answer=n
  case "$answer" in ""|y|Y|yes|YES|Yes) return 0 ;; *) return 1 ;; esac
}

say "Burn Helper: your Claude Code agents on a Tufty 2350 badge."
case "$(uname -s)" in
  Darwin)
    xcode-select -p >/dev/null 2>&1 || die "Install Apple's command line tools first (they include git and python3): xcode-select --install"
    [ -x "$PY" ] || die "$PY is missing; run: xcode-select --install" ;;
  Linux)
    [ -n "$JOIN" ] || [ "$UNINSTALL" = 1 ] || die "On Linux, join an existing bridge (a Mac or a Windows PC): add --join http://<bridge>:8787"
    PY="$(command -v python3 || true)"
    [ -n "$PY" ] || die "python3 is needed: install it with your package manager."
    command -v git >/dev/null 2>&1 || die "git is needed: install it with your package manager." ;;
  *) die "This installer is for macOS and Linux. On Windows, use install.ps1 (see the README)." ;;
esac

# 1. the code: this checkout, or a fresh clone in ~/burn-helper
ROOT=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  [ -f "$here/bridge/install.py" ] && [ -d "$here/badge" ] && ROOT="$here"
fi
if [ -z "$ROOT" ]; then
  if [ -d "$DEST/.git" ]; then
    if [ "$DRY" = 1 ]; then say "Would update $DEST from $REPO_URL ($REF)."; else
      say "Updating $DEST ..."
      git -C "$DEST" fetch --quiet origin "$REF"
      git -C "$DEST" checkout --quiet "$REF"
      git -C "$DEST" merge --ff-only --quiet "origin/$REF"
    fi
  elif [ -e "$DEST" ]; then
    die "$DEST already exists and is not a Burn Helper checkout. Set BURN_HELPER_DIR to another folder."
  elif [ "$DRY" = 1 ]; then
    say "Would clone $REPO_URL ($REF) into $DEST, then continue."
    exit 0
  else
    say "Downloading Burn Helper into $DEST ..."
    git clone --quiet --branch "$REF" "$REPO_URL" "$DEST"
  fi
  ROOT="$DEST"
fi
say "Code: $ROOT"

if [ "$UNINSTALL" = 1 ]; then
  "$PY" "$ROOT/bridge/install.py" --uninstall $([ "$DRY" = 1 ] && echo --dry-run)
  say "The badge was left as it is. To put its original firmware back:"
  say "  python3 $ROOT/scripts/badge.py bootloader && picotool load -v -x $ROOT/backup/<date>/flash-full.bin"
  exit 0
fi

[ -d "$HOME/.claude" ] || say "Claude Code does not seem to be set up yet (no ~/.claude). Install it, run it once, then rerun this."

# joining a bridge on another computer: hooks and a status line only
if [ -n "$JOIN" ]; then
  if [ "$DRY" = 1 ]; then
    "$PY" "$ROOT/bridge/install.py" --bridge "$JOIN" --dry-run
  else
    say "This adds async hooks and a hearts status line to ~/.claude/settings.json (backed up first;"
    say "undo with --uninstall) that send this computer's Claude Code activity to the bridge."
    if ask "Join the bridge at $JOIN?"; then
      "$PY" "$ROOT/bridge/install.py" --bridge "$JOIN"
    else
      say "Skipped."
    fi
  fi
  exit 0
fi

# 2. the Mac side
if [ "$NO_BRIDGE" = 0 ]; then
  if [ "$DRY" = 1 ]; then
    "$PY" "$ROOT/bridge/install.py" --dry-run
  else
    say "The bridge adds async hooks and a hearts status line to ~/.claude/settings.json"
    say "(backed up first; undo with --uninstall) and starts at login."
    if ask "Install the bridge on this Mac?"; then
      "$PY" "$ROOT/bridge/install.py"
    else
      say "Skipped the bridge."
    fi
  fi
fi

# 3. the badge
if [ "$NO_BADGE" = 0 ]; then
  # shellcheck disable=SC2086
  "$PY" "$ROOT/tools/setup_badge.py" $BADGE_ARGS
fi

ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo '<this-mac-ip>')"
say "Done. Phone panel and theme picker: http://$ip:8787/"
say "On the badge: A/C change theme, B shows info (twice: Wi-Fi debug), hold B for phone Wi-Fi setup."
if [ "$NO_BRIDGE" = 0 ]; then
  echo
  "$PY" "$ROOT/bridge/install.py" --join-help
fi
