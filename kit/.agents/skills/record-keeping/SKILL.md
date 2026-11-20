---
name: record-keeping
description: "Decides where a problem or leftover piece of work gets written down: BUGS.md for anything with a real failure, TODO.md for work with no failure, CHANGELOG.md for every change. Covers how to add, update or close an entry without duplicating it. Use when you notice a bug outside your task, when a task ends with something still broken or left undone, when you fix something BUGS.md or TODO.md lists, or when you tidy either file."
---

# BUGS.md, TODO.md and CHANGELOG.md

Write down what you notice along the way. Don't go hunting for it. A chat summary is not a record: anything left broken or undone when your task ends gets written down without being asked.

## Step 1: Fix it or file it

- **Part of your task and fixable now:** fix it. Nothing gets filed.
- **Outside your task, or not fixable now** (it needs a decision, a credential, or would blow up the diff): file it (Step 2).
- **A small job noticed in passing:** don't fix it inline. File it in `TODO.md` as `**[P3] [SIMPLE]**` with `Effort: <15min`, but only if all three hold: it touches one file or one block, it changes no behaviour and no name other code depends on, and an existing check (a test, the linter, a script) shows whether it worked. At most three per session.

## Step 2: Pick the file

Ask these in order. The first yes wins.

1. **Does it have a real failure?** Wrong output, a crash, lost data, a check that can never fire. It goes in `BUGS.md`, even if it's one line. Style, naming or "could be cleaner" is never a bug.
2. **Otherwise** (polish, deferred work, an improvement, an open question): it goes in `TODO.md`. If it waits on a person (a decision, a login, a key, a real device), say so in its `Blocker:` line, for example `Blocker: needs a decision on X`.

Never file one thing in both `BUGS.md` and `TODO.md`.

## Step 3: Check it isn't already there

Never open these files whole. Search for the file or symbol first:

```sh
rg -n --max-count 5 '<file name or symbol>' BUGS.md TODO.md
```

If it's already listed, update that entry (new evidence, a corrected line number, higher confidence) instead of adding another.

## Step 4: Write the entry

Read the file's own entry format:

```sh
rg -n -A 12 '^## Entry format' <the file>
```

Fill every field. Each entry cites evidence as `path:line` and gives today's date as YYYY-MM-DD. A `BUGS.md` entry states its confidence (`suspected`, `likely` or `confirmed`). A `TODO.md` entry starts with a priority tag (`**[P0]**` to `**[P3]**`). Add new entries at the top of the file's `## Open` section with your file-edit tool.

## Step 5: Close what you resolve

- **You fixed a bug:** delete its `BUGS.md` entry and log it with `scripts/changelog.py --w` in the same change. Every bug fix gets an entry, listed or not.
- **You did a TODO:** delete its `TODO.md` entry. Never tick it (`- [x]`) or move it to a done list; git and the changelog keep the history. Log it with `scripts/changelog.py --w` if behaviour, UI, the API, the schema or deployment changed.
- **You decided not to fix a bug:** move it to `BUGS.md`'s **Accepted limitations** with the reason and what would change the decision.
- **It was a false alarm:** delete the entry.
- **A TODO turned out to be a defect:** move it to `BUGS.md`. Don't copy it.

## CHANGELOG.md and AGENT_QUERY_LOG.md are script-only

Never name either file in a command: not whole, not a line range, not a search, not a diff, not `git add`. They only grow, and every read is paid for again on every later turn. A hook blocks the attempt, so don't ask the user for permission either. Use the scripts:

```sh
python3 scripts/changelog.py --w "what changed and why"     # after committing each discrete change; it commits the entry itself
python3 scripts/changelog.py --r 2026-11-01:2026-11-17       # what changed, as JSON, with commit hashes
```

An entry is one line written for the next agent: what changed and why, naming the files or symbols. The script adds the commit hash, so commit first and don't restate the diff. Never edit an older line. A duplicate costs nothing; a read costs thousands of tokens. The query log works the same way (`scripts/agent_query_log.py`); the `agent-history` skill covers reading both.

## Done means

- `rg -n --max-count 5 '<file or symbol>' BUGS.md TODO.md` shows exactly one entry for what you filed, and none for what you closed.
- Every discrete change is committed and has its changelog entry, added by `scripts/changelog.py` (exit 0).
- Nothing left broken or undone at the end of your task exists only in your chat summary.
- Your final message names the entries you added or closed.
