#!/usr/bin/env python3
"""Claude Code PreToolUse hook: keeps agents out of CHANGELOG.md and AGENT_QUERY_LOG.md.

Both files only grow, and one read of them costs thousands of tokens on every
later turn. Agents go through scripts/changelog.py and scripts/agent_query_log.py
instead. Any tool call that names either file is refused (exit 2, the message
goes back to the agent) unless it runs one of those scripts or stages or commits
the file with git. A call that names neither file passes untouched.

The settings.json deny rules catch the common commands; this catches the rest
(rg, python -c, Edit, Write, a Grep or Glob aimed at the file).
"""
import json
import re
import sys

PROTECTED = re.compile(r"(CHANGELOG|AGENT_QUERY_LOG)\.md", re.I)
SCRIPT = re.compile(r"^\s*(python3?\s+)?(\./)?scripts/(changelog|agent_query_log)\.py\b")
GIT_OK = re.compile(r"^\s*git\s+(add|commit|rm|restore|status|stash)\b")
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")

MESSAGE = (
    "Blocked: CHANGELOG.md and AGENT_QUERY_LOG.md are never read or edited directly; they only grow and "
    "reading them wastes your context. Use `python3 scripts/changelog.py --w \"entry\"` or `--r START:END`, "
    "and `python3 scripts/agent_query_log.py --w \"query\"` or `--r START:END`."
)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def bash_allowed(command: str) -> bool:
    """Every part of the command that names a protected file must be a script call or a git staging call."""
    for part in SEGMENT_SPLIT.split(command):
        if PROTECTED.search(part) and not (SCRIPT.match(part) or GIT_OK.match(part)):
            return False
    return True


def main():
    try:
        call = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = call.get("tool_input", {})
    if call.get("tool_name") == "Bash":
        if bash_allowed(tool_input.get("command", "")):
            return 0
    elif not any(PROTECTED.search(s) for s in strings(tool_input)):
        return 0
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
