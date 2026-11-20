#!/usr/bin/env python3
"""Writes to and reads CHANGELOG.md without an agent ever opening the file.

  python3 scripts/changelog.py --w "what changed and why" [--w "another entry"]
  python3 scripts/changelog.py --r 2026-11-01:2026-11-17      # JSON, either side may be empty

Commit first, then write: each entry records the hash of HEAD, so it points at
the diff. The script then commits the file itself, with the query log when git
keeps that too, and nothing else that is staged, so no agent ever has to name
either file in a command. When git ignores the file, or there is no repo,
nothing is committed. Dates and times come from the clock; never pass one.
Entries go under a `## YYYY-MM-DD` heading as `- HH:MM <hash> <text>`.

The file's own layout decides where: a file whose day headings run newest first
gets the entry at the top of today's section (or a new section above the first
one); any other file, including a new one, is appended to. Older lines that are
a bare `- <text>` are read too, with no time or commit.
"""
import argparse
import re
import subprocess
import sys
import time
from datetime import date

sys.dont_write_bytecode = True  # keep __pycache__ out of the project
from _records import (LIMIT_HELP, DEFAULT_LIMIT, die, in_range, locked_rewrite, one_line,
                      parse_range, print_entries, read_text, root, today_now)

FILE = root() / "CHANGELOG.md"
QUERY_LOG = root() / "AGENT_QUERY_LOG.md"
HEADER = (
    "# Changelog\n\n"
    "Written and read only by `scripts/changelog.py`. Don't open this file.\n\n---\n"
)
LINE = re.compile(r"^- (?:(\d\d:\d\d) ([0-9a-f]{7,40}|-) )?(.*)$")
HEADING = re.compile(r"^## (\d{4}-\d\d-\d\d)$", re.M)


def run_git(*args):
    return subprocess.run(["git", "-C", str(root()), *args], capture_output=True, text=True)


def git(*args):
    result = run_git(*args)
    return result.stdout.strip() if result.returncode == 0 else ""


def commit_records(entries, outcome):
    """Commits the two record files and nothing else. Runs under the file lock, so parallel writers take turns.

    The query log rides along when git keeps it (the hook writes it on every prompt, so it never gets a commit of its own)."""
    if run_git("rev-parse", "--git-dir").returncode != 0:
        outcome.append("not committed: no git repo")
        return
    names = [path.name for path in (FILE, QUERY_LOG)
             if path.exists() and run_git("check-ignore", "-q", "--", path.name).returncode != 0]
    if FILE.name not in names:
        outcome.append("not committed: git ignores the file")
        return
    subject = one_line(entries[0])
    subject = subject if len(subject) <= 60 else subject[:59] + "…"
    message = f"Changelog: {subject}" + (f" (+{len(entries) - 1} more)" if len(entries) > 1 else "")
    for attempt in range(10):
        result = run_git("add", "--", *names)
        if result.returncode == 0:
            # --only commits these paths from the working tree and leaves everything else in the index alone.
            result = run_git("commit", "-q", "--only", "-m", message, "--", *names)
        if result.returncode == 0:
            outcome.append("committed")
            return
        if "index.lock" not in result.stderr:
            break
        time.sleep(0.1 * (attempt + 1))  # another git command holds the index; wait our turn
    die(f"the entry is written, but the commit failed:\n{result.stderr.strip()}\n"
        f"Tell the user what failed. Don't commit or open {' or '.join(names)} yourself.", 1)


def newest_first(headings):
    return len(headings) > 1 and headings[0] > headings[-1]


def with_entries(existing, day, lines):
    """The file text with the new lines added where the file's own layout puts them."""
    headings = HEADING.findall(existing)
    if not newest_first(headings):
        text = "" if existing.endswith("\n") else "\n"
        if not headings or headings[-1] != day:
            text += f"\n## {day}\n\n"
        return existing + text + "\n".join(lines) + "\n"
    block = "\n".join(lines) + "\n"
    heading = re.search(rf"^## {day}\n\n?", existing, re.M)
    if heading:
        return existing[:heading.end()] + block + existing[heading.end():]
    first = HEADING.search(existing)
    return existing[:first.start()] + f"## {day}\n\n{block}\n" + existing[first.start():]


def write(entries):
    now = today_now()
    day = now.strftime("%Y-%m-%d")
    head = git("rev-parse", "--short", "HEAD") or "-"
    if git("status", "--porcelain", "--", ".", ":!CHANGELOG.md", ":!AGENT_QUERY_LOG.md"):
        print("note: uncommitted changes exist; the hash points at the last commit, not them", file=sys.stderr)
    lines = [f"- {now:%H:%M} {head} {one_line(e)}" for e in entries]

    outcome = []
    locked_rewrite(FILE, HEADER, lambda existing: with_entries(existing, day, lines), then=lambda: commit_records(entries, outcome))
    print(f"logged {len(lines)} under ## {day}, {outcome[0]}")


def read(range_text, limit):
    start, end = parse_range(range_text)
    entries, day = [], None
    text = read_text(FILE)
    for raw in text.splitlines():
        heading = HEADING.match(raw)
        if heading:
            day = date.fromisoformat(heading.group(1))
            continue
        m = LINE.match(raw)
        if m and day and in_range(day, start, end):
            entries.append({"date": day.isoformat(), "time": m.group(1),
                            "commit": None if m.group(2) in (None, "-") else m.group(2), "entry": m.group(3)})
    if newest_first(HEADING.findall(text)):
        entries.reverse()  # print oldest first whatever the file's layout
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
