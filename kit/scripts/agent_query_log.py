#!/usr/bin/env python3
"""Writes to and reads AGENT_QUERY_LOG.md: every request the user made to an agent.

  python3 scripts/agent_query_log.py --w "the user's request, verbatim"
  python3 scripts/agent_query_log.py --w - <<'EOF'      # request on stdin: safe for quotes and backticks
  python3 scripts/agent_query_log.py --r 2026-11-17            # JSON, START:END or one day
  ... --hook                                                    # Claude Code UserPromptSubmit hook

The timestamp comes from the clock. Writing the same query twice within two
minutes is ignored, so the hook and an agent following the rule never double up.
"""
import argparse
import json
import re
import sys
from datetime import datetime

sys.dont_write_bytecode = True  # keep __pycache__ out of the project
from _records import (LIMIT_HELP, DEFAULT_LIMIT, die, in_range, locked_append, one_line,
                      parse_range, print_entries, read_text, root, today_now)

FILE = root() / "AGENT_QUERY_LOG.md"
HEADER = (
    "# Agent query log\n\n"
    "Every request made to an agent, oldest first. Written and read only by "
    "`scripts/agent_query_log.py`. Don't open this file.\n\n---\n\n"
)
LINE = re.compile(r"^- (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d): (.*)$")
DUPLICATE_WINDOW_SECONDS = 120


def write(query) -> bool:
    """Logs the query; False when it was empty or a repeat."""
    query = one_line(query)
    if not query:
        return False
    now = today_now()
    added = []

    def build(existing):
        for raw in reversed(existing.splitlines()):
            m = LINE.match(raw)
            if m:
                seen = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                close = (now.replace(tzinfo=None) - seen).total_seconds() < DUPLICATE_WINDOW_SECONDS
                if close and m.group(2) == query:
                    return ""
                break
        added.append(query)
        return f"- {now:%Y-%m-%d %H:%M:%S}: {query}\n"

    locked_append(FILE, HEADER, build)
    return bool(added)


def read(range_text, limit):
    start, end = parse_range(range_text)
    entries = []
    for raw in read_text(FILE).splitlines():
        m = LINE.match(raw)
        if m and in_range(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").date(), start, end):
            entries.append({"timestamp": m.group(1), "query": m.group(2)})
    print_entries(entries, limit)


def hook():
    """UserPromptSubmit: logs the prompt, prints nothing (stdout would join the prompt), never blocks."""
    try:
        write(json.load(sys.stdin).get("prompt", ""))
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--w", metavar="QUERY", help="log a request")
    p.add_argument("--r", metavar="START:END", help="print requests in a date range as JSON")
    p.add_argument("--hook", action="store_true", help="Claude Code hook mode: read the prompt from stdin JSON")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=LIMIT_HELP)
    a = p.parse_args()
    if a.hook:
        return hook()
    if bool(a.w) == bool(a.r):
        die("give exactly one of --w QUERY or --r START:END")
    if a.w:
        query = sys.stdin.read() if a.w == "-" else a.w
        print("logged" if write(query) else "skipped (empty or a repeat)")
    else:
        read(a.r, a.limit)


if __name__ == "__main__":
    main()
