#!/usr/bin/env bash
# Claude Code Stop hook: before an agent finishes, makes it stop once to file what it noticed.
#
# Fires only when the working tree has changes outside the record files, and
# only once per set of changes (it keeps a fingerprint in .git/), so it never
# loops and costs nothing on a turn that only read or answered.
set -euo pipefail

input="$(cat)"
case "$input" in *'"stop_hook_active":true'*|*'"stop_hook_active": true'*) exit 0 ;; esac

root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root"
changes="$(git status --porcelain 2>/dev/null | grep -vE '(BUGS|TODO|CHANGELOG|AGENT_QUERY_LOG)\.md$' || true)"
[ -n "$changes" ] || exit 0

stamp="$(git rev-parse --git-dir)/agent-record-check"
fingerprint="$(printf '%s' "$changes" | cksum | cut -d' ' -f1)"
[ "$(cat "$stamp" 2>/dev/null || true)" = "$fingerprint" ] && exit 0
printf '%s\n' "$fingerprint" > "$stamp"

cat <<'JSON'
{"decision": "block", "reason": "Before you finish, do the end-of-task check in AGENTS.md (\"Before you finish\"). Anything you noticed but did not fix, or left broken or unfinished, goes in BUGS.md or TODO.md now (the record-keeping skill says which). Each discrete change is committed, then logged with scripts/changelog.py --w. Then finish, naming the entries you added or closed, or saying in one line that there was nothing to record."}
JSON
