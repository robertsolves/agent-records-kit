#!/usr/bin/env python3
"""Writes to and reads CHANGELOG.md without an agent ever opening the file.

  python3 scripts/changelog.py --w "what changed and why" [--w "another entry"]
  python3 scripts/changelog.py --r 2026-11-01:2026-11-17      # JSON, either side may be empty

Commit first, then write: each entry records the hash of HEAD, so it points at
the diff. Dates and times come from the clock; never pass one. Entries are
appended under a `## YYYY-MM-DD` heading as `- HH:MM <hash> <text>`.
"""
import argparse
import re
import subprocess
import sys
from datetime import date

sys.dont_write_bytecode = True  # keep __pycache__ out of the project
from _records import (LIMIT_HELP, DEFAULT_LIMIT, die, in_range, locked_append, one_line,
                      parse_range, print_entries, read_text, root, today_now)

FILE = root() / "CHANGELOG.md"
HEADER = (
    "# Changelog\n\n"
    "Written and read only by `scripts/changelog.py`. Don't open this file.\n\n---\n"
)
LINE = re.compile(r"^- (\d\d:\d\d) ([0-9a-f]{7,40}|-) (.*)$")


def git(*args):
    result = subprocess.run(["git", "-C", str(root()), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def write(entries):
    now = today_now()
    day = now.strftime("%Y-%m-%d")
    head = git("rev-parse", "--short", "HEAD") or "-"
    if git("status", "--porcelain", "--", ".", ":!CHANGELOG.md", ":!AGENT_QUERY_LOG.md"):
        print("note: uncommitted changes exist; the hash points at the last commit, not them", file=sys.stderr)
    lines = [f"- {now:%H:%M} {head} {one_line(e)}" for e in entries]

    def build(existing):
        headings = re.findall(r"^## (\d{4}-\d\d-\d\d)$", existing, re.M)
        text = "" if existing.endswith("\n") else "\n"
        if not headings or headings[-1] != day:
            text += f"\n## {day}\n\n"
        return text + "\n".join(lines) + "\n"

    locked_append(FILE, HEADER, build)
    print(f"logged {len(lines)} under ## {day}")


def read(range_text, limit):
    start, end = parse_range(range_text)
    entries, day = [], None
    for raw in read_text(FILE).splitlines():
        heading = re.match(r"^## (\d{4}-\d\d-\d\d)$", raw)
        if heading:
            day = date.fromisoformat(heading.group(1))
            continue
        m = LINE.match(raw)
        if m and day and in_range(day, start, end):
            entries.append({"date": day.isoformat(), "time": m.group(1),
                            "commit": None if m.group(2) == "-" else m.group(2), "entry": m.group(3)})
    print_entries(entries, limit)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--w", action="append", metavar="ENTRY", help="log an entry; repeat for several")
    p.add_argument("--r", metavar="START:END", help="print entries in a date range as JSON")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=LIMIT_HELP)
    a = p.parse_args()
    if bool(a.w) == bool(a.r):
        die("give exactly one of --w ENTRY or --r START:END")
    if a.w:
        if any(not e.strip() for e in a.w):
            die("an entry is empty")
        write(a.w)
    else:
        read(a.r, a.limit)


if __name__ == "__main__":
    main()
