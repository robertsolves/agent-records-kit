---
name: agent-history
description: "Reads the change history and the user's earlier requests without opening the files: scripts/changelog.py --r for what changed and in which commit, scripts/agent_query_log.py --r for what the user asked. Use when you pick up unfamiliar or half-done work, resume after a crash, are asked what changed or what was asked earlier, or need the commit behind a behaviour. Never open CHANGELOG.md or AGENT_QUERY_LOG.md."
---

# Reading the change history and the query log

Never open, search or tail `CHANGELOG.md` or `AGENT_QUERY_LOG.md`. A hook blocks it. Use the scripts; they print JSON for a date range.

- What changed, and in which commit: `python3 scripts/changelog.py --r START:END`
- What the user asked, in their words: `python3 scripts/agent_query_log.py --r START:END`
- Why a change was made: the changelog entry, then `git show --stat <commit>`.
- What a half-finished session was doing: the query log for that day, then the changelog for the same day.

`START:END` is inclusive, as `YYYY-MM-DD`. Either side may be empty. One date means that day.

- Use the narrowest range that can answer.
- Output is the newest 300 entries. If `"truncated": true`, narrow the range. Don't raise `--limit`.
- Quote entries by date and commit hash.
