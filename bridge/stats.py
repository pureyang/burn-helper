#!/usr/bin/env python3
"""Read the bridge's history (the optional SQLite file): how long sessions waited for you, and each
day's usage.

    python3 bridge/stats.py                 the last 14 days, and the longest waits
    python3 bridge/stats.py --days 30       a longer stretch
    python3 bridge/stats.py --sessions      waits added up by session
    python3 bridge/stats.py --csv waits     print a table as CSV (waits or daily)

Turn the history on with: python3 bridge/install.py --tracking on
"""
import argparse
import csv
import os
import sqlite3
import sys
import time


STATE_DIR = os.path.expanduser(os.environ.get("BURN_HELPER_STATE_DIR") or os.path.join("~", ".claude", "burn-helper"))


def span(s):
    s = int(s or 0)
    if s >= 3600:
        return "%dh%02dm" % (s // 3600, s % 3600 // 60)
    if s >= 60:
        return "%dm%02ds" % (s // 60, s % 60)
    return "%ds" % s


def connect(state_dir=None):
    state_dir = state_dir or STATE_DIR
    path = os.path.join(state_dir, "tracking.db")
    if not os.path.exists(path):
        sys.exit("No history yet (%s). Turn it on with: python3 bridge/install.py --tracking on" % path)
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True)


def report(db, days=14, sessions=False, out=print):
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - days * 86400))
    rows = db.execute("SELECT day, tool_calls, prompts, turns, waits, wait_seconds, longest_wait, five_hour_peak, "
                      "seven_day_used FROM daily WHERE day >= ? ORDER BY day DESC", (since,)).fetchall()
    out("Day         Tools  Prompts  Turns  Waits  Waited    Longest  5h peak  Week")
    for day, tools, prompts, turns, waits, wsec, longest, peak, week in rows:
        out("%-10s %6d %8d %6d %6d %8s %8s %8s %5s" % (
            day, tools, prompts, turns, waits, span(wsec), span(longest),
            "-" if peak is None else "%d%%" % peak, "-" if week is None else "%d%%" % week))
    if not rows:
        out("(nothing recorded in the last %d days)" % days)
    tot = db.execute("SELECT COUNT(*), COALESCE(SUM(seconds),0), COALESCE(AVG(seconds),0), COALESCE(MAX(seconds),0) "
                     "FROM waits WHERE started >= ? AND ended IS NOT NULL", (time.time() - days * 86400,)).fetchone()
    out("")
    out("%d waits in %d days: %s in all, %s on average, %s at most." % (tot[0], days, span(tot[1]), span(tot[2]), span(tot[3])))
    if sessions:
        out("")
        out("Session                          Computer        Waits  Total     Average   Longest")
        for name, comp, n, total, avg, mx in db.execute(
                "SELECT COALESCE(name, session), COALESCE(computer,''), COUNT(*), SUM(seconds), AVG(seconds), MAX(seconds) "
                "FROM waits WHERE started >= ? AND ended IS NOT NULL GROUP BY COALESCE(name, session), computer "
                "ORDER BY SUM(seconds) DESC LIMIT 20", (time.time() - days * 86400,)):
            out("%-32s %-14s %6d %8s %9s %9s" % (name[:32], comp[:14], n, span(total), span(avg), span(mx)))
    else:
        out("")
        out("Longest waits:")
        for name, comp, why, started, secs in db.execute(
                "SELECT COALESCE(name, session), COALESCE(computer,''), COALESCE(why,''), started, seconds "
                "FROM waits WHERE started >= ? AND ended IS NOT NULL ORDER BY seconds DESC LIMIT 5",
                (time.time() - days * 86400,)):
            out("  %-8s %s  %-30s %s %s" % (span(secs), time.strftime("%a %H:%M", time.localtime(started)),
                                          name[:30], comp[:14], why))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--sessions", action="store_true", help="add up the waits by session")
    ap.add_argument("--csv", choices=("waits", "daily"), help="print a whole table as CSV")
    args = ap.parse_args(argv)
    db = connect()
    if args.csv:
        cur = db.execute("SELECT * FROM %s ORDER BY 1" % args.csv)
        w = csv.writer(sys.stdout)
        w.writerow([c[0] for c in cur.description])
        w.writerows(cur.fetchall())
        return 0
    report(db, args.days, args.sessions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
