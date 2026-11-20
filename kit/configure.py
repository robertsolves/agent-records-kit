#!/usr/bin/env python3
"""Wires the records setup into a project for each coding agent. Run by install.sh, not by hand.

  configure.py PROJECT_DIR SRC_KIT_DIR TOOLS DRY PRIVATE [install|uninstall] [AGENTS_MD 1|0]

TOOLS is a comma list of claude, codex, gemini, opencode, kilo, cursor. What each one gets:

  every agent  AGENTS.md section (the rule), the scripts, the skills in .agents/skills
  claude       .claude/settings.json: deny rules, allow rules for the scripts, no ask rules (here or in
               settings.local.json), plus hooks that log prompts, block reads and check at Stop
  codex        .codex/config.toml: hooks that log prompts and block reads (review them once with /hooks)
  gemini       .gemini/settings.json: hooks and context.fileName including AGENTS.md, plus an ignore file
  opencode     opencode.json: deny rules for the two files
  kilo         kilo.json: deny rules for the two files, and .kilocodeignore
  cursor       .cursorignore

OpenCode, Kilo and the agents not listed have no hook that logs prompts, so they follow the AGENTS.md rule.
"""
import json
import re
import sys
from pathlib import Path

project, src = Path(sys.argv[1]), Path(sys.argv[2])
tools = set(sys.argv[3].split(","))
dry = sys.argv[4] == "1"
private = sys.argv[5] == "1"
mode = sys.argv[6] if len(sys.argv) > 6 else "install"
with_agents_md = (sys.argv[7] if len(sys.argv) > 7 else "1") == "1"

PROTECTED = ("CHANGELOG.md", "AGENT_QUERY_LOG.md")
READ_COMMANDS = ("cat", "head", "tail", "less", "more", "sed", "awk", "grep", "rg", "bat", "git show", "git diff", "git log -p")
# The scripts are the only way in, so running them never waits on a permission prompt.
SCRIPTS = ("scripts/changelog.py", "scripts/agent_query_log.py")
ALLOW = tuple(f"Bash(python3 {s} *)" for s in SCRIPTS)

# Codex and Gemini start hooks from varying folders, so the project root comes from git.
ROOT = '"$(git rev-parse --show-toplevel)"'
GUARD = f"python3 {ROOT}/.claude/hooks/guard_records.py"
LOG = f"bash {ROOT}/.claude/hooks/log_query.sh"


def say(verb, what):
    print(f"  {verb:<9} {what}")


def write(path: Path, text: str):
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def read_json(path: Path) -> dict:
    if path.exists() and path.read_text().strip():
        return json.loads(path.read_text())
    return {}


def write_json(path: Path, data: dict):
    write(path, json.dumps(data, indent=2) + "\n")


def ensure_line(name: str, line: str):
    path = project / name
    text = path.read_text() if path.exists() else ""
    if line in text.splitlines():
        return
    write(path, text + ("" if text.endswith("\n") or not text else "\n") + line + "\n")
    say("added", f"{line} -> {name}")


def agents_md():
    section = (src / "AGENTS.section.md").read_text().rstrip("\n") + "\n"
    target = project / "AGENTS.md"
    text = target.read_text() if target.exists() else "# AGENTS.md\n\nHow coding agents work in this repo.\n"
    pattern = re.compile(r"<!-- agent-records-kit:start.*?<!-- agent-records-kit:end -->\n?", re.S)
    text = pattern.sub(lambda _: section, text) if pattern.search(text) else text.rstrip("\n") + "\n\n" + section
    write(target, text)
    say("updated", "AGENTS.md (records section)")


def import_file(name: str):
    """CLAUDE.md and GEMINI.md exist only to import AGENTS.md; create one when missing."""
    existing = [p for p in project.iterdir() if p.name.lower() == name.lower()]
    if not existing:
        write(project / name, "@AGENTS.md\n")
        say("created", f"{name} (imports AGENTS.md)")
    elif "@AGENTS.md" not in existing[0].read_text():
        print(f"  note      {existing[0].name} doesn't import AGENTS.md; add the line @AGENTS.md so the records rules reach it", file=sys.stderr)


def names_ours(rule: str) -> bool:
    return any(n.lower() in rule.lower() for n in PROTECTED + SCRIPTS)


def drop_ask_rules(path: Path, data: dict) -> bool:
    """Removes "ask" rules that name the record files or the scripts. An ask rule beats every allow rule and
    bypassPermissions, so one of them turns each changelog write into a prompt the user has to answer."""
    rules = data.get("permissions", {}).get("ask")
    if not rules or not any(names_ours(r) for r in rules):
        return False
    rules[:] = [r for r in rules if not names_ours(r)]
    if not rules:
        del data["permissions"]["ask"]
    say("removed", f"ask rules for the record files from {path.relative_to(project)}")
    return True


def claude():
    path = project / ".claude" / "settings.json"
    data = read_json(path)
    deny = []
    for name in PROTECTED:
        deny += [f"Read(**/{name})", f"Edit(**/{name})", f"Write(**/{name})"]
        deny += [f"Bash({cmd} *{name}*)" for cmd in READ_COMMANDS]
    rules = data.setdefault("permissions", {}).setdefault("deny", [])
    rules += [r for r in deny if r not in rules]
    allow = data["permissions"].setdefault("allow", [])
    allow += [r for r in ALLOW if r not in allow]
    drop_ask_rules(path, data)
    local = project / ".claude" / "settings.local.json"
    if local.exists():
        local_data = read_json(local)
        if drop_ask_rules(local, local_data):
            write_json(local, local_data)
    hooks = data.setdefault("hooks", {})
    wanted = {
        "PreToolUse": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/guard_records.py"',
        "UserPromptSubmit": 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/log_query.sh"',
        "Stop": 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/record_check.sh"',
    }
    for event, command in wanted.items():
        groups = hooks.setdefault(event, [])
        if not any(h.get("command") == command for g in groups for h in g.get("hooks", [])):
            groups.append({"hooks": [{"type": "command", "command": command}]})
    write_json(path, data)
    say("merged", ".claude/settings.json (deny rules, script allow rules, 3 hooks)")


def codex():
    path = project / ".codex" / "config.toml"
    text = path.read_text() if path.exists() else ""
    if "agent-records-kit:start" in text:
        text = re.sub(r"# agent-records-kit:start.*?# agent-records-kit:end\n?", "", text, flags=re.S)
    block = f"""# agent-records-kit:start
[[hooks.PreToolUse]]

[[hooks.PreToolUse.hooks]]
type = "command"
command = '{GUARD}'
timeout = 30
statusMessage = "Checking the records rule"

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = '{LOG}'
timeout = 30
# agent-records-kit:end
"""
    write(path, (text.rstrip("\n") + "\n\n" if text.strip() else "") + block)
    say("wrote", ".codex/config.toml (2 hooks; Codex needs the project trusted and the hooks reviewed with /hooks)")


def gemini():
    path = project / ".gemini" / "settings.json"
    data = read_json(path)
    hooks = data.setdefault("hooks", {})
    for event, command, matcher in (("BeforeTool", GUARD, ".*"), ("BeforeAgent", LOG, ".*")):
        groups = hooks.setdefault(event, [])
        if not any(h.get("command") == command for g in groups for h in g.get("hooks", [])):
            groups.append({"matcher": matcher, "hooks": [{"type": "command", "command": command}]})
    write_json(path, data)
    say("merged", ".gemini/settings.json (2 hooks)")
    # Gemini reads GEMINI.md by default; this makes it read AGENTS.md too, without an extra file.
    names = data.setdefault("context", {}).get("fileName", ["GEMINI.md"])
    names = [names] if isinstance(names, str) else names
    if "AGENTS.md" not in names:
        data["context"]["fileName"] = names + ["AGENTS.md"]
        write_json(path, data)
    for name in PROTECTED:
        ensure_line(".geminiignore", name)


def permission_deny(filename: str):
    """OpenCode and Kilo share one config shape: permission.read/edit/bash maps, last match wins."""
    path = project / filename
    data = read_json(path)
    permission = data.setdefault("permission", {})
    for kind, patterns in (
        ("read", [f"**/{n}" for n in PROTECTED]),
        ("edit", [f"**/{n}" for n in PROTECTED]),
        ("bash", [f"{cmd} *{n}*" for n in PROTECTED for cmd in READ_COMMANDS]),
    ):
        current = permission.get(kind)
        if isinstance(current, str):
            current = {"*": current}
        current = current if isinstance(current, dict) else {}
        for pattern in patterns:
            current.setdefault(pattern, "deny")
        if kind == "bash":
            for script in SCRIPTS:
                current.setdefault(f"python3 {script}*", "allow")
        permission[kind] = current
    write_json(path, data)
    say("merged", f"{filename} (deny rules for {' and '.join(PROTECTED)}, allow rules for the scripts)")


def pick_config(*names):
    """The existing config file, or the first name when there is none. JSONC is left alone: we can't keep its comments."""
    for name in names:
        if (project / name).exists():
            return name
    return names[0]


def uninstall():
    """Takes out what this kit added to AGENTS.md and the agent configs; the ignore-file lines stay."""
    section = re.compile(r"\n*<!-- agent-records-kit:start.*?<!-- agent-records-kit:end -->\n?", re.S)
    agents = project / "AGENTS.md"
    if agents.exists() and section.search(agents.read_text()):
        write(agents, section.sub("\n", agents.read_text()).strip("\n") + "\n")
        say("cleaned", "AGENTS.md")
    codex_file = project / ".codex" / "config.toml"
    if codex_file.exists() and "agent-records-kit:start" in codex_file.read_text():
        text = re.sub(r"\n*# agent-records-kit:start.*?# agent-records-kit:end\n?", "", codex_file.read_text(), flags=re.S).strip()
        codex_file.write_text(text + "\n") if text else codex_file.unlink()
        say("cleaned", ".codex/config.toml")
    ours = ("guard_records.py", "log_query.sh", "record_check.sh")
    for name in (".claude/settings.json", ".gemini/settings.json"):
        path = project / name
        if not path.exists():
            continue
        data = read_json(path)
        hooks = data.get("hooks", {})
        for event in list(hooks):
            for group in hooks[event]:
                group["hooks"] = [h for h in group.get("hooks", []) if not any(o in h.get("command", "") for o in ours)]
            hooks[event] = [g for g in hooks[event] if g["hooks"]]
            if not hooks[event]:
                del hooks[event]
        if not hooks:
            data.pop("hooks", None)
        permissions = data.get("permissions", {})
        for kind in ("deny", "allow"):
            if kind in permissions:
                permissions[kind] = [r for r in permissions[kind] if not names_ours(r)]
        if permissions.get("allow") == []:
            del permissions["allow"]
        write_json(path, data)
        say("cleaned", name)
    for name in ("opencode.json", "kilo.json"):
        path = project / name
        if not path.exists():
            continue
        data = read_json(path)
        for kind, rules in data.get("permission", {}).items():
            if isinstance(rules, dict):
                for pattern in [p for p in rules if names_ours(p)]:
                    del rules[pattern]
        data["permission"] = {k: v for k, v in data.get("permission", {}).items() if v != {}}
        if not data["permission"]:
            del data["permission"]
        write_json(path, data)
        say("cleaned", name)


if mode == "uninstall":
    uninstall()
    sys.exit(0)

if with_agents_md:
    agents_md()
if "claude" in tools:
    import_file("CLAUDE.md")
    claude()
if "codex" in tools:
    codex()
if "gemini" in tools:
    gemini()
if "opencode" in tools:
    config = pick_config("opencode.json", "opencode.jsonc")
    if config.endswith("c"):
        print(f"  note      {config} has comments, so it was left alone; add deny rules for {', '.join(PROTECTED)} yourself", file=sys.stderr)
    else:
        permission_deny(config)
if "kilo" in tools:
    config = pick_config("kilo.json", "kilo.jsonc")
    if config.endswith("c"):
        print(f"  note      {config} has comments, so it was left alone; add deny rules for {', '.join(PROTECTED)} yourself", file=sys.stderr)
    else:
        permission_deny(config)
    for name in PROTECTED:
        ensure_line(".kilocodeignore", name)
if "cursor" in tools:
    for name in PROTECTED:
        ensure_line(".cursorignore", name)

ensure_line(".gitignore", "__pycache__/")
if private:
    ensure_line(".gitignore", "AGENT_QUERY_LOG.md")
