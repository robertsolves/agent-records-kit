# agent-records-kit

Keeps a project's `BUGS.md`, `TODO.md`, `CHANGELOG.md` and `AGENT_QUERY_LOG.md` up to date across coding agents. Agents write the changelog and query log through scripts and never open them, so those files don't fill their context. Works with Claude Code, Codex, Gemini CLI, OpenCode, Kilo, Cursor and anything that reads `AGENTS.md`.

## Install

From your project's root:

```sh
curl -fsSL https://raw.githubusercontent.com/robertsolves/agent-records-kit/main/install.sh | bash
```

Or with the other kits:

```sh
curl -fsSL https://raw.githubusercontent.com/robertsolves/agent-commands/main/kit.sh | bash -s -- add records
```

Options: `--only record-keeping,agent-history,todo-triage` (default: all), `--tools claude,codex,gemini,opencode,kilo,cursor` (default: detected), `--private` (keep the query log out of git), `--dry-run`, `--uninstall`.

Needs `python3`.

## Codex hooks

Codex ignores a project's hooks until you turn them on. The kit's two hooks log every request and block reads of `CHANGELOG.md` and `AGENT_QUERY_LOG.md`. Without them, Codex only follows the rule in `AGENTS.md`.

1. Open the project in Codex and trust it when asked.
2. Run `/hooks` and approve the two hooks (`PreToolUse` and `UserPromptSubmit`).

Codex asks again if a hook file changes.

## Tests

```sh
python3 -m unittest discover tests
```
