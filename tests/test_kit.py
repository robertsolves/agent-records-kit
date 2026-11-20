"""Tests for agent-records-kit. Run: python3 -m unittest discover tests

Every test installs the kit into a throwaway git repo with the real install.sh, so they
exercise what a user gets. Needs python3 and bash; nothing else.
"""
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
INSTALL = KIT / "install.sh"
TODAY = date.today().isoformat()


def run(args, cwd, stdin=None, check=False):
    return subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True, check=check)


def git_commit(project, message="change"):
    run(["git", "add", "-A"], project)
    run(["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-qm", message, "--allow-empty"], project)


class Project(unittest.TestCase):
    """A fresh git repo; subclasses decide what to install."""

    tools = "claude"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)
        run(["git", "init", "-q"], self.project)
        # changelog.py commits, so the repo needs an identity whatever the machine's git config says.
        for key, value in (("user.name", "t"), ("user.email", "t@t.t"), ("commit.gpgsign", "false")):
            run(["git", "config", key, value], self.project)

    def git(self, *args):
        return run(["git", *args], self.project).stdout.split()

    def install(self, *extra, tools=None):
        return run(["bash", str(INSTALL), "--project", str(self.project), "--tools", tools or self.tools, *extra], self.project)

    def script(self, name, *args, stdin=None):
        return run([sys.executable, str(self.project / "scripts" / name), *args], self.project, stdin=stdin)

    def read(self, script, range_text):
        result = self.script(script, "--r", range_text)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class Changelog(Project):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.install().returncode, 0)

    def test_write_then_read(self):
        self.assertEqual(self.script("changelog.py", "--w", "first, with a comma", "--w", "second").returncode, 0)
        data = self.read("changelog.py", TODAY)
        self.assertEqual([e["entry"] for e in data["entries"]], ["first, with a comma", "second"])
        self.assertFalse(data["truncated"])

    def test_commit_hash_is_recorded(self):
        git_commit(self.project)
        head = run(["git", "rev-parse", "--short", "HEAD"], self.project).stdout.strip()
        self.script("changelog.py", "--w", "after a commit")
        self.assertEqual(self.read("changelog.py", TODAY)["entries"][0]["commit"], head)

    def test_commits_its_own_line_and_nothing_else(self):
        git_commit(self.project)
        (self.project / "staged.txt").write_text("mine\n")
        run(["git", "add", "staged.txt"], self.project)
        result = self.script("changelog.py", "--w", "a change")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("committed", result.stdout)
        self.assertEqual(self.git("log", "-1", "--format=%s"), ["Changelog:", "a", "change"])
        self.assertIn("CHANGELOG.md", self.git("show", "--name-only", "--format=", "HEAD"))
        self.assertNotIn("staged.txt", self.git("show", "--name-only", "--format=", "HEAD"))
        self.assertEqual(self.git("diff", "--cached", "--name-only"), ["staged.txt"])
        self.assertEqual(self.git("status", "--porcelain", "--", "CHANGELOG.md", "AGENT_QUERY_LOG.md"), [])

    def test_ignored_file_is_written_but_not_committed(self):
        (self.project / ".gitignore").write_text("CHANGELOG.md\n")
        git_commit(self.project)
        head = self.git("rev-parse", "HEAD")
        result = self.script("changelog.py", "--w", "kept local")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not committed", result.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.read("changelog.py", TODAY)["count"], 1)

    def test_failed_commit_exits_1_and_keeps_the_line(self):
        git_commit(self.project)
        hook = Path(self.project / ".git" / "hooks" / "pre-commit")
        hook.write_text("#!/bin/sh\necho refused >&2\nexit 1\n")
        hook.chmod(0o755)
        result = self.script("changelog.py", "--w", "blocked by a hook")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refused", result.stderr)
        self.assertEqual(self.read("changelog.py", TODAY)["count"], 1)

    def test_no_commit_means_no_hash(self):
        self.script("changelog.py", "--w", "before any commit")
        self.assertIsNone(self.read("changelog.py", TODAY)["entries"][0]["commit"])

    def test_newlines_fold_into_one_line(self):
        self.script("changelog.py", "--w", "two\nlines")
        self.assertEqual(self.read("changelog.py", TODAY)["entries"][0]["entry"], "two lines")

    def test_ranges(self):
        self.script("changelog.py", "--w", "today")
        for range_text, count in ((f"{TODAY}:", 1), (f":{TODAY}", 1), ("2000-01-01:2000-01-02", 0), (TODAY, 1)):
            self.assertEqual(self.read("changelog.py", range_text)["count"], count, range_text)

    def test_limit_keeps_the_newest(self):
        self.script("changelog.py", "--w", "a", "--w", "b", "--w", "c")
        data = json.loads(self.script("changelog.py", "--r", TODAY, "--limit", "2").stdout)
        self.assertTrue(data["truncated"])
        self.assertEqual([e["entry"] for e in data["entries"]], ["b", "c"])

    def test_bad_input_exits_2(self):
        for args in (["--r", "bad"], ["--r", "2026-02-01:2026-01-01"], [], ["--w", " "], ["--w", "x", "--r", TODAY]):
            self.assertEqual(self.script("changelog.py", *args).returncode, 2, args)

    def test_concurrent_writers_lose_nothing(self):
        with ThreadPoolExecutor(12) as pool:
            results = list(pool.map(lambda i: self.script("changelog.py", "--w", f"entry {i}"), range(24)))
        self.assertEqual([r.returncode for r in results], [0] * 24, [r.stderr for r in results if r.returncode])
        self.assertEqual(self.read("changelog.py", TODAY)["count"], 24)
        self.assertEqual(self.git("status", "--porcelain", "--", "CHANGELOG.md"), [])

    def test_one_heading_per_day(self):
        self.script("changelog.py", "--w", "a")
        self.script("changelog.py", "--w", "b")
        text = (self.project / "CHANGELOG.md").read_text()
        self.assertEqual(text.count(f"## {TODAY}"), 1)

    def test_no_bytecode_left_behind(self):
        self.script("changelog.py", "--w", "a")
        self.assertFalse((self.project / "scripts" / "__pycache__").exists())


class QueryLog(Project):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.install().returncode, 0)

    def test_stdin_keeps_quotes_backticks_and_substitutions_literal(self):
        request = "Run `cat CHANGELOG.md` and \"quote\" $(whoami) it's"
        self.script("agent_query_log.py", "--w", "-", stdin=request + "\nsecond line\n")
        query = self.read("agent_query_log.py", TODAY)["entries"][0]["query"]
        self.assertEqual(query, request + " second line")

    def test_repeat_is_skipped(self):
        self.script("agent_query_log.py", "--w", "same")
        again = self.script("agent_query_log.py", "--w", "same")
        self.assertIn("skipped", again.stdout)
        self.assertEqual(self.read("agent_query_log.py", TODAY)["count"], 1)

    def test_empty_is_skipped(self):
        self.assertIn("skipped", self.script("agent_query_log.py", "--w", "-", stdin="  \n").stdout)

    def test_older_line_format_is_readable(self):
        log = self.project / "AGENT_QUERY_LOG.md"
        log.write_text(log.read_text() + "- 2026-11-16 20:00 | old style | with a pipe\n")
        self.script("agent_query_log.py", "--w", "new style")
        entries = self.read("agent_query_log.py", "2026-11-16:")["entries"]
        self.assertEqual([e["query"] for e in entries], ["old style | with a pipe", "new style"])

    def test_hook_logs_prints_nothing_and_never_fails(self):
        hook = self.project / ".claude" / "hooks" / "log_query.sh"
        result = run(["bash", str(hook)], self.project, stdin=json.dumps({"prompt": "from the hook"}))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        garbage = run(["bash", str(hook)], self.project, stdin="not json")
        self.assertEqual((garbage.returncode, garbage.stdout), (0, ""))
        self.assertEqual(self.read("agent_query_log.py", TODAY)["entries"][0]["query"], "from the hook")


class Guard(Project):
    def setUp(self):
        super().setUp()
        self.install()

    def rc(self, tool, **tool_input):
        payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
        guard = self.project / ".claude" / "hooks" / "guard_records.py"
        return run([sys.executable, str(guard)], self.project, stdin=payload).returncode

    def test_blocks_every_way_in(self):
        blocked = [
            ("Read", {"file_path": "/x/CHANGELOG.md"}),
            ("Read", {"file_path": "/x/AGENT_QUERY_LOG.md"}),
            ("Edit", {"file_path": "a/changelog.md", "old_string": "a"}),
            ("Write", {"file_path": "CHANGELOG.md", "content": "x"}),
            ("Grep", {"pattern": "x", "path": "CHANGELOG.md"}),
            ("Bash", {"command": "cat CHANGELOG.md"}),
            ("Bash", {"command": 'cat "CHANGELOG.md"'}),
            ("Bash", {"command": "rg foo docs/CHANGELOG.md"}),
            ("Bash", {"command": "python3 -c \"print(open('AGENT_QUERY_LOG.md').read())\""}),
            ("Bash", {"command": "git add CHANGELOG.md && cat CHANGELOG.md"}),
            ("Bash", {"command": "git diff CHANGELOG.md"}),
            ("Bash", {"command": "git add CHANGELOG.md && git commit -m x"}),
            ("Bash", {"command": "git commit -m x -- AGENT_QUERY_LOG.md"}),
        ]
        for tool, tool_input in blocked:
            self.assertEqual(self.rc(tool, **tool_input), 2, (tool, tool_input))

    def test_allows_the_scripts_and_other_files(self):
        allowed = [
            ("Bash", {"command": 'python3 scripts/changelog.py --w "fix CHANGELOG.md bug"'}),
            ("Bash", {"command": "python3 scripts/agent_query_log.py --r 2026-11-17"}),
            ("Bash", {"command": "git add -A && git commit -m x"}),
            ("Bash", {"command": "ls"}),
            ("Edit", {"file_path": "README.md", "old_string": "see CHANGELOG.md", "new_string": "x"}),
            ("Read", {"file_path": "BUGS.md"}),
            ("Read", {"file_path": "/x/OLD_CHANGELOG.md"}),
            ("Edit", {"file_path": "/x/OLD_CHANGELOG.md", "old_string": "a"}),
            ("Read", {"file_path": "/x/CHANGELOG.md.bak"}),
        ]
        for tool, tool_input in allowed:
            self.assertEqual(self.rc(tool, **tool_input), 0, (tool, tool_input))

    def test_garbage_input_passes(self):
        guard = self.project / ".claude" / "hooks" / "guard_records.py"
        self.assertEqual(run([sys.executable, str(guard)], self.project, stdin="junk").returncode, 0)


class Installer(Project):
    def snapshot(self):
        return {str(p.relative_to(self.project)): (p.read_text() if p.is_file() and not p.is_symlink() else "")
                for p in sorted(self.project.rglob("*")) if ".git" not in p.parts}

    def test_creates_the_record_files_and_never_overwrites_them(self):
        (self.project / "BUGS.md").write_text("my bugs\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((self.project / "BUGS.md").read_text(), "my bugs\n")
        for name in ("TODO.md", "CHANGELOG.md", "AGENT_QUERY_LOG.md"):
            self.assertTrue((self.project / name).exists(), name)
        self.assertFalse((self.project / "MANUAL_TODO.md").exists())

    def test_rerun_changes_nothing(self):
        self.install(tools="all")
        before = self.snapshot()
        self.install(tools="all")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.project / "AGENTS.md").read_text().count("agent-records-kit:start"), 1)

    def test_dry_run_writes_nothing(self):
        result = self.install("--dry-run", tools="all")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), {})

    def test_every_generated_config_parses(self):
        self.install(tools="all")
        tomllib.loads((self.project / ".codex" / "config.toml").read_text())
        for name in (".claude/settings.json", ".gemini/settings.json", "opencode.json", "kilo.json"):
            json.loads((self.project / name).read_text())
        gemini = json.loads((self.project / ".gemini" / "settings.json").read_text())
        self.assertIn("AGENTS.md", gemini["context"]["fileName"])
        self.assertFalse((self.project / "GEMINI.md").exists())

    def test_scripts_are_allowed_and_ask_rules_for_the_records_removed(self):
        local = self.project / ".claude" / "settings.local.json"
        local.parent.mkdir()
        local.write_text(json.dumps({"permissions": {"ask": ["Bash(*CHANGELOG.md*)", "Read(/AGENT_QUERY_LOG.md)", "Bash(rm *)"]}}))
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(json.loads(local.read_text())["permissions"]["ask"], ["Bash(rm *)"])
        allow = json.loads((self.project / ".claude" / "settings.json").read_text())["permissions"]["allow"]
        self.assertIn("Bash(python3 scripts/changelog.py *)", allow)
        self.assertIn("Bash(python3 scripts/agent_query_log.py *)", allow)

    def test_existing_agents_md_keeps_its_content(self):
        (self.project / "AGENTS.md").write_text("# Mine\n\nkeep me\n")
        self.install()
        text = (self.project / "AGENTS.md").read_text()
        self.assertTrue(text.startswith("# Mine\n\nkeep me\n"))
        self.assertIn("## Records", text)

    def test_no_agents_md_flag_and_it_is_remembered(self):
        self.install("--no-agents-md")
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.install()
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_only_picks_skills_and_ignores_foreign_names(self):
        self.install("--only", "agent-history")
        skills = sorted(p.name for p in (self.project / ".agents" / "skills").iterdir())
        self.assertEqual(skills, ["agent-history"])
        self.install("--only", "find-bandaids")
        skills = sorted(p.name for p in (self.project / ".agents" / "skills").iterdir())
        self.assertEqual(skills, ["agent-history", "record-keeping", "todo-triage"])

    def test_private_keeps_the_query_log_out_of_git(self):
        self.install("--private")
        self.assertIn("AGENT_QUERY_LOG.md", (self.project / ".gitignore").read_text().splitlines())

    def test_unknown_tool_is_refused(self):
        result = self.install(tools="nope")
        self.assertNotEqual(result.returncode, 0)

    def test_install_then_uninstall_restores_existing_config(self):
        claude = self.project / ".claude" / "settings.json"
        claude.parent.mkdir()
        claude.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"], "deny": ["Read(./secret)"]},
                                      "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
        opencode = self.project / "opencode.json"
        opencode.write_text(json.dumps({"permission": {"bash": {"*": "ask"}}}))
        (self.project / "AGENTS.md").write_text("# AGENTS.md\n\nmine\n")
        before = {p: json.loads(p.read_text()) for p in (claude, opencode)}
        agents_before = (self.project / "AGENTS.md").read_text()

        self.install(tools="claude,opencode")
        self.assertNotEqual(json.loads(claude.read_text()), before[claude])
        uninstall = run(["bash", str(INSTALL), "--project", str(self.project), "--uninstall"], self.project)
        self.assertEqual(uninstall.returncode, 0, uninstall.stderr)

        for path, content in before.items():
            self.assertEqual(json.loads(path.read_text()), content, path.name)
        self.assertEqual((self.project / "AGENTS.md").read_text(), agents_before)
        self.assertFalse((self.project / "scripts").exists())
        self.assertTrue((self.project / "CHANGELOG.md").exists())

    def test_uninstall_without_install_fails_cleanly(self):
        result = run(["bash", str(INSTALL), "--project", str(self.project), "--uninstall"], self.project)
        self.assertNotEqual(result.returncode, 0)

    def test_default_project_is_the_current_directory_not_the_git_root(self):
        sub = self.project / "nested"
        sub.mkdir()
        run(["bash", str(INSTALL), "--tools", "claude"], sub)
        self.assertTrue((sub / "scripts" / "changelog.py").exists())
        self.assertFalse((self.project / "scripts").exists())


if __name__ == "__main__":
    unittest.main()
