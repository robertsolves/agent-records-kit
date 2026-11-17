"""Shared helpers for changelog.py and agent_query_log.py: project root, locked appends, date ranges."""
import json
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: two sessions writing in the same instant can interleave
    fcntl = None

DEFAULT_LIMIT = 300


def root() -> Path:
    """The project root: the folder that holds scripts/."""
    return Path(__file__).resolve().parent.parent


def die(message: str, code: int = 2):
    print(message, file=sys.stderr)
    sys.exit(code)


def one_line(text: str) -> str:
    """Entries are one line each, so a newline in the text becomes a space."""
    return " ".join(text.split())


def parse_range(text: str):
    """'START:END' (inclusive, YYYY-MM-DD, either side optional) or a single day, as (start, end) dates."""
    start_text, sep, end_text = text.partition(":")
    if not sep:
        end_text = start_text
    try:
        start = date.fromisoformat(start_text) if start_text else None
        end = date.fromisoformat(end_text) if end_text else None
    except ValueError:
        die(f"bad range '{text}': use START:END as YYYY-MM-DD, either side may be empty")
    if start and end and start > end:
        die(f"bad range '{text}': START is after END")
    return start, end


def in_range(day: date, start, end) -> bool:
    return (start is None or day >= start) and (end is None or day <= end)


def locked_append(path: Path, header: str, build):
    """Appends build(existing_text) to path under a lock, creating the file with header when it is empty."""
    with open(path, "a+", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        existing = f.read()
        if not existing.strip():
            existing = header
            f.write(header)
        addition = build(existing)
        if addition:
            f.write(addition)
        return existing


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def print_entries(entries: list, limit: int):
    """Prints the newest `limit` entries, oldest first, as JSON an agent can read."""
    truncated = len(entries) > limit
    if truncated:
        entries = entries[-limit:]
    print(json.dumps({"count": len(entries), "truncated": truncated, "entries": entries}, indent=2, ensure_ascii=False))


def today_now() -> datetime:
    return datetime.now().astimezone()


LIMIT_HELP = f"most entries to print, newest kept (default {DEFAULT_LIMIT})"