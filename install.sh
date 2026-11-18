#!/usr/bin/env bash
# Adds the agent-records-kit setup to a project: BUGS / TODO / CHANGELOG / AGENT_QUERY_LOG, the scripts
# that write and read the last two, the skills, and for each coding agent you use the hooks and
# permission rules that keep it out of those two big files. Safe to run again.
#
#   curl -fsSL https://raw.githubusercontent.com/robertsolves/agent-records-kit/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/robertsolves/agent-records-kit/main/install.sh | bash -s -- --tools all
#   ./install.sh --project ~/code/my-app --dry-run
#
# Record files the project already has are never touched. Scripts, hooks and skills are the kit's,
# so re-running replaces them. AGENTS.md gets the records section between two markers: re-running
# replaces what is between them and nothing else. Agent config files are merged, not replaced.

set -euo pipefail

OWNER=robertsolves
REPO=agent-records-kit
BRANCH=main
ALL_TOOLS="claude codex gemini opencode kilo cursor"

usage() {
  cat <<EOF
Usage: install.sh [options]

  --project DIR   project to set up (default: the current directory)
  --tools LIST    comma list of: claude, codex, gemini, opencode, kilo, cursor, or "all".
                  Default "auto": whatever the project folders or your PATH show.
                  Agents not listed (Antigravity, Copilot, Windsurf, Freebuff...) read the
                  AGENTS.md rule, which every install adds.
  --private       keep AGENT_QUERY_LOG.md out of git (prompts can contain secrets)
  --only SKILLS   comma list of skills to install: record-keeping, agent-history, todo-triage (default: all)
  --no-agents-md  leave AGENTS.md alone
  --uninstall     remove the scripts, hooks, skills and config entries this installed
                  (your record files stay)
  --dry-run       print what would change, change nothing
  -h, --help      this text
EOF
}

project="" tools="auto" only="" private=0 dry=0 agents_md=1 uninstall=0
while [ $# -gt 0 ]; do
  case "$1" in
    --project) project="${2:?--project needs a directory}"; shift ;;
    --tools) tools="${2:?--tools needs a list}"; shift ;;
    --private) private=1 ;;
    --no-agents-md) agents_md=0 ;;
    --uninstall) uninstall=1 ;;
    --only) only="${2:?--only needs a list}"; shift ;;
    --copy|--force) ;;
    --dry-run) dry=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

die() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }
command -v python3 >/dev/null || die "python3 is needed (the scripts and the hooks are Python, stdlib only)"

# The kit's files: next to this script, or downloaded.
src=""
script="${BASH_SOURCE[0]:-}"
if [ -n "$script" ] && [ -f "$script" ]; then
  src="$(cd "$(dirname "$script")" && pwd)/kit"
fi
if [ -z "$src" ] || [ ! -d "$src" ]; then
  command -v curl >/dev/null || die "curl is needed to download $OWNER/$REPO"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL "https://codeload.github.com/$OWNER/$REPO/tar.gz/refs/heads/$BRANCH" | tar -xz -C "$tmp" \
    || die "could not download $OWNER/$REPO"
  src="$tmp/$REPO-$BRANCH/kit"
fi

if [ -z "$project" ]; then
  project="$(pwd)"
fi
[ -d "$project" ] || die "no such directory: $project"
project="$(cd "$project" && pwd)"

manifest_dir="$project/.agents/.installed"
manifest="$manifest_dir/$REPO.txt"
options_file="$manifest_dir/$REPO.options"

# Re-runs (kit.sh update) reuse the choices of the first install.
if [ -f "$options_file" ] && [ "$uninstall" -eq 0 ]; then
  if [ "$tools" = auto ]; then
    saved="$(sed -n 's/^tools=//p' "$options_file")"
    [ -n "$saved" ] && tools="$saved"
  fi
  [ -z "$only" ] && only="$(sed -n 's/^only=//p' "$options_file")"
  grep -qx 'private=1' "$options_file" && private=1
  grep -qx 'agents_md=0' "$options_file" && agents_md=0
fi

has() { command -v "$1" >/dev/null 2>&1; }
exists() { local f; for f in "$@"; do [ -e "$project/$f" ] && return 0; done; return 1; }

if [ "$tools" = "auto" ]; then
  tools=""
  { exists .claude CLAUDE.md || has claude; } && tools="$tools,claude"
  { exists .codex || has codex; } && tools="$tools,codex"
  { exists .gemini GEMINI.md .geminiignore || has gemini; } && tools="$tools,gemini"
  { exists .opencode opencode.json opencode.jsonc || has opencode; } && tools="$tools,opencode"
  { exists .kilo .kilocode kilo.json kilo.jsonc .kilocodeignore || has kilo || has kilocode; } && tools="$tools,kilo"
  { exists .cursor .cursorignore; } && tools="$tools,cursor"
  tools="${tools#,}"
  [ -n "$tools" ] || tools="claude"
elif [ "$tools" = "all" ]; then
  tools="${ALL_TOOLS// /,}"
fi
for t in ${tools//,/ }; do
  case " $ALL_TOOLS " in *" $t "*) ;; *) die "unknown tool '$t' (known: ${ALL_TOOLS// /, })" ;; esac
done

say() { printf '  %-9s %s\n' "$1" "$2"; }
kept=()
skills="record-keeping agent-history todo-triage"
# kit.sh passes one --only list to every kit; use it only when it names one of this kit's skills.
if [ -n "$only" ]; then
  picked=""
  for s in $skills; do case ",$only," in *",$s,"*) picked="$picked $s" ;; esac; done
  [ -n "$picked" ] && skills="${picked# }"
fi
owned=()   # paths this kit owns, written to the manifest so --uninstall can remove them

if [ "$uninstall" -eq 1 ]; then
  [ -f "$manifest" ] || die "nothing to uninstall: $manifest is missing"
  echo "Removing agent-records-kit from $project"
  if [ "$dry" -eq 0 ]; then
    while IFS= read -r path; do
      [ -n "$path" ] && rm -rf "${project:?}/$path"
    done < "$manifest"
    python3 "$src/configure.py" "$project" "$src" "$tools" 0 0 uninstall
    rm -f "$manifest" "$options_file"
    rmdir "$manifest_dir" "$project/.claude/hooks" "$project/.claude/skills" "$project/.agents/skills" "$project/.agents" "$project/scripts" 2>/dev/null || true
  fi
  echo "Done. BUGS.md, TODO.md, CHANGELOG.md and AGENT_QUERY_LOG.md were left alone."
  exit 0
fi

# Kit-owned file: always copied.
put() { # $1 = path in kit and in project
  if [ "$dry" -eq 0 ]; then mkdir -p "$project/$(dirname "$1")"; cp "$src/$1" "$project/$1"; fi
  owned+=("$1")
  say "wrote" "$1"
}

# Project-owned file: created only when missing.
seed() { # $1 = path in kit, $2 = path in project
  if [ -e "$project/$2" ]; then kept+=("$2"); return; fi
  if [ "$dry" -eq 0 ]; then mkdir -p "$project/$(dirname "$2")"; cp "$src/$1" "$project/$2"; fi
  say "created" "$2"
}

echo "Installing agent-records-kit into $project (agents: ${tools//,/, })"

for f in scripts/_records.py scripts/changelog.py scripts/agent_query_log.py \
         .claude/hooks/guard_records.py .claude/hooks/log_query.sh .claude/hooks/record_check.sh; do
  put "$f"
done
if [ "$dry" -eq 0 ]; then chmod +x "$project"/.claude/hooks/* "$project"/scripts/changelog.py "$project"/scripts/agent_query_log.py; fi

# Skills live in .agents/skills (Codex, OpenCode, Kilo and Gemini read it) and are linked for Claude Code.
for skill in $skills; do
  if [ "$dry" -eq 0 ]; then
    rm -rf "$project/.agents/skills/$skill"
    mkdir -p "$project/.agents/skills" "$project/.claude/skills"
    cp -R "$src/.agents/skills/$skill" "$project/.agents/skills/$skill"
    [ -e "$project/.claude/skills/$skill" ] || ln -s "../../.agents/skills/$skill" "$project/.claude/skills/$skill"
  fi
  owned+=(".agents/skills/$skill")
  [ -L "$project/.claude/skills/$skill" ] && owned+=(".claude/skills/$skill")
  say "wrote" ".agents/skills/$skill (linked into .claude/skills)"
done

seed templates/BUGS.md BUGS.md
seed templates/TODO.md TODO.md
seed templates/CHANGELOG.md CHANGELOG.md
seed templates/AGENT_QUERY_LOG.md AGENT_QUERY_LOG.md

python3 "$src/configure.py" "$project" "$src" "$tools" "$dry" "$private" install "$agents_md"

if [ "$dry" -eq 0 ]; then
  mkdir -p "$manifest_dir"
  printf '%s\n' "${owned[@]}" > "$manifest"
  { echo "tools=$tools"; echo "only=$only"; echo "private=$private"; echo "agents_md=$agents_md"; } > "$options_file"
fi

echo
if [ "${#kept[@]}" -gt 0 ]; then echo "Left alone, already there: ${kept[*]}"; fi
echo "Done."
case ",$tools," in *,codex,*) echo "Codex: the hooks stay off until you trust this project and review the hooks with /hooks." ;; esac
case ",$tools," in *,opencode,*|*,kilo,*) echo "OpenCode and Kilo have no prompt hook, so they log requests by following the AGENTS.md rule." ;; esac
if [ "$dry" -eq 1 ]; then echo "(dry run: nothing was changed)"; fi
exit 0
