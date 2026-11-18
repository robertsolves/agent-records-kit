<!-- agent-records-kit:start (managed by agent-records-kit; re-running the installer replaces everything between these markers) -->
## Records

- `BUGS.md`: defects. A defect is any real failure (wrong output, crash, lost data, a check that can never fire), however small. Edit it.
- `TODO.md`: work that is not a defect: polish, deferred work, improvements, open questions. A `Blocker:` line names what waits on a person. Edit it.
- `CHANGELOG.md`: one entry per discrete change. Write only through `scripts/changelog.py`.
- `AGENT_QUERY_LOG.md`: the user's requests. Write only through `scripts/agent_query_log.py`.

When you notice a defect you are not fixing, add it to `BUGS.md` now. When you notice other unfinished or improvable work, add it to `TODO.md` now. Chat output is not a record. The `record-keeping` skill has the entry formats and how to close an entry.

### Reading

- Never open `BUGS.md` or `TODO.md` whole. Search: `rg -n --max-count 5 '<file or symbol>' BUGS.md TODO.md`.
- Never read, search, tail or edit `CHANGELOG.md` or `AGENT_QUERY_LOG.md`, and don't ask permission: the request is denied. Read them through the scripts, which print JSON for a date range (`START:END` as `YYYY-MM-DD`, either side may be empty):

  ```sh
  python3 scripts/changelog.py --r 2026-11-01:2026-11-17
  python3 scripts/agent_query_log.py --r 2026-11-17
  ```

  Use them when you pick up unfamiliar work: the changelog gives what changed and the commit, the query log gives what the user asked. See the `agent-history` skill.

### After each discrete change

A discrete change is one fix, feature or behaviour change. Formatting is not one.

1. Commit it with a short, plain message.
2. Log it: `python3 scripts/changelog.py --w "<entry>"`. Repeat `--w` for several entries.

- Write one line per entry, for agents: what changed and why, naming files or symbols. Don't restate the diff; the script adds the commit hash.
- Commit before you log, or the hash is wrong.
- Never edit an old entry. Never check for duplicates.
- A fixed bug: delete its `BUGS.md` entry in the same change. A finished task: delete its `TODO.md` entry; never tick it or keep a done list.

### Query log

- In Claude Code, Codex and Gemini CLI a hook logs each prompt. Do nothing.
- In any other agent, your first action on each new user request is to log it verbatim, through a quoted heredoc so quotes and backticks in the request stay literal:

  ```sh
  python3 scripts/agent_query_log.py --w - <<'EOF'
  <the user's request, verbatim>
  EOF
  ```

  Don't paraphrase it, don't log your own sub-tasks. Repeats are ignored.

Both scripts set the timestamp. Never pass a date or time.

### Before you finish

- Every defect you left unfixed is in `BUGS.md`. Every piece of unfinished work is in `TODO.md`.
- Every discrete change is committed and logged.
- Your final message lists the entries you added or closed, or says `nothing to record`.
<!-- agent-records-kit:end -->
