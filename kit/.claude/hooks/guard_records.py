#!/usr/bin/env python3
"""Claude Code PreToolUse hook: keeps agents out of CHANGELOG.md and AGENT_QUERY_LOG.md.

Both files only grow, and one read of them costs thousands of tokens on every
later turn. Agents go through scripts/changelog.py and scripts/agent_query_log.py
instead; changelog.py commits the files itself, so not even git needs them named.
Any tool call that names either file is refused (exit 2, the message goes back to
the agent, and the user is never asked) unless it runs one of those scripts. A
call that names neither file passes untouched.

The settings.json deny rules catch the common commands; this catches the rest
(rg, python -c, Edit, Write, a Grep or Glob aimed at the file).

For every tool except Bash only the fields that name a file are checked. Docs and
skills mention the two files all the time, and an Edit whose text merely says
"CHANGELOG.md" must still go through.
"""
import json
import re
import sys

# Not part of a longer name: OLD_CHANGELOG.md and CHANGELOG.md.bak are other files.
# A trailing full stop is fine ("cat CHANGELOG.md."); a dot and a word character is an extension.
PROTECTED = re.compile(r"(?<![\w.-])(CHANGELOG|AGENT_QUERY_LOG)\.md(?![\w-]|\.\w)", re.I)
SCRIPT = re.compile(r"^\s*(python3?\s+)?(\./)?scripts/(changelog|agent_query_log)\.py\b")
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
# The tool_input fields that name a file or a folder. Glob's `pattern` is a path glob; Grep's is a regex over contents.
PATH_FIELDS = ("file_path", "path", "notebook_path", "glob")

MESSAGE = (
    "Blocked: CHANGELOG.md and AGENT_QUERY_LOG.md are never read or edited directly; they only grow and "
    "reading them wastes your context. Use `python3 scripts/changelog.py --w \"entry\"` or `--r START:END`, "
    "and `python3 scripts/agent_query_log.py --w \"query\"` or `--r START:END`. changelog.py commits the files "
    "itself: never stage, commit or diff them by name, and never ask the user about them."
)


def named_paths(tool_name: str, tool_input: dict):
    """The strings in a non-Bash tool call that point at a file."""
    for field in PATH_FIELDS:
        value = tool_input.get(field)
        if isinstance(value, str):
            yield value
    if tool_name == "Glob" and isinstance(tool_input.get("pattern"), str):
        yield tool_input["pattern"]


def bash_allowed(command: str) -> bool:
    """Every part of the command that names a protected file must be a call to one of the scripts."""
    for part in SEGMENT_SPLIT.split(command):
        if PROTECTED.search(part) and not SCRIPT.match(part):
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
    elif not any(PROTECTED.search(s) for s in named_paths(call.get("tool_name", ""), tool_input)):
        return 0
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
