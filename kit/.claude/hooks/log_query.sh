#!/usr/bin/env bash
# Claude Code UserPromptSubmit hook: logs the user's prompt to AGENT_QUERY_LOG.md.
#
# Prints nothing, because anything a UserPromptSubmit hook prints is added to the
# prompt, and never blocks, so a failure here can't get in the user's way.
python3 "$(dirname "$0")/../../scripts/agent_query_log.py" --hook >/dev/null 2>&1 || true
exit 0
