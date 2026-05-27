"""Tests for installer.steps.codex_files — Codex-specific file installation."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from installer.steps.codex_files import (
    CodexFilesStep,
    _TomlStructureError,
    _ensure_section_keys,
    _validate_toml_structure,
)


class TestCodexFilesStepCheck:
    def test_check_returns_false_always(self) -> None:
        step = CodexFilesStep()
        ctx = MagicMock()
        assert step.check(ctx) is False


class TestCodexFilesStepSkipsWhenNoCodex:
    def test_run_is_noop_when_codex_not_installed(self, tmp_path: Path) -> None:
        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with patch(
            "installer.steps.codex_files._is_codex_installed",
            return_value=False,
        ):
            step.run(ctx)


class TestCodexHooksInstallation:
    def test_installs_hooks_json_to_codex_dir(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        pilot_home = tmp_path / ".pilot"
        hooks_src = pilot_home / "hooks"
        hooks_src.mkdir(parents=True)

        codex_hooks_template = tmp_path / "source" / "pilot" / "hooks" / "codex_hooks.json"
        codex_hooks_template.parent.mkdir(parents=True)
        codex_hooks_template.write_text(
            json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo test"}]}]}})
        )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = tmp_path / "source"
        ctx.project_dir = tmp_path / "project"

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_hooks(ctx)

        hooks_file = codex_dir / "hooks.json"
        assert hooks_file.exists()
        data = json.loads(hooks_file.read_text())
        assert "hooks" in data
        assert "SessionStart" in data["hooks"]

    def test_real_template_injects_memory_context_on_codex_startup(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = repo_root

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step._install_codex_hooks(ctx)

        data = json.loads((codex_dir / "hooks.json").read_text())
        context_commands = [
            hook["command"]
            for entry in data["hooks"]["SessionStart"]
            for hook in entry.get("hooks", [])
        ]
        assert any('worker-service.cjs" hook codex context' in command for command in context_commands)

    def test_real_template_has_all_hook_events(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = repo_root

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step._install_codex_hooks(ctx)

        data = json.loads((codex_dir / "hooks.json").read_text())
        hooks = data["hooks"]
        assert "SessionStart" in hooks
        assert "UserPromptSubmit" in hooks
        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert "Stop" in hooks
        assert "PreCompact" in hooks

    def test_merge_preserves_user_posttooluse_hooks(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        user_hooks = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "my-custom-hook.sh"}
                        ],
                    }
                ]
            }
        }
        (codex_dir / "hooks.json").write_text(json.dumps(user_hooks))

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = repo_root

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step._install_codex_hooks(ctx)

        data = json.loads((codex_dir / "hooks.json").read_text())
        all_commands = [
            hook["command"]
            for entry in data["hooks"]["PostToolUse"]
            for hook in entry.get("hooks", [])
        ]
        assert any("my-custom-hook.sh" in cmd for cmd in all_commands)
        assert any("observation" in cmd for cmd in all_commands)


class TestCodexSkillsInstallation:
    def test_builds_codex_skill_with_frontmatter(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        skill_dir = tmp_path / "skills" / "fix"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [{"id": "step-1", "file": "steps/01-impl.md"}],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: fix\ndescription: Bugfix workflow\nuser-invocable: true\n---\n\n# /fix\n\nFix bugs fast."
        )
        steps_dir = skill_dir / "steps"
        steps_dir.mkdir()
        (steps_dir / "01-impl.md").write_text("## Step 1\n\nImplement the fix.")

        result = build_codex_skill_md(skill_dir)
        assert result.startswith("---\n")
        assert "name: fix" in result
        assert "description: Bugfix workflow" in result
        assert "# /fix" in result or "# $fix" in result
        assert "Implement the fix." in result

    def test_codex_skill_adapts_invocation_syntax(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        skill_dir = tmp_path / "skills" / "spec"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: spec\ndescription: Spec workflow\n---\n\nRun /spec to plan. Also /fix for bugs."
        )

        result = build_codex_skill_md(skill_dir)
        assert "$spec" in result
        assert "$fix" in result

    def test_installs_skills_to_agents_dir(self, tmp_path: Path) -> None:
        agents_skills_dir = tmp_path / ".agents" / "skills"
        pilot_skills_dir = tmp_path / ".claude" / "skills"

        skill_dir = pilot_skills_dir / "fix"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text("---\nname: fix\ndescription: Bugfix\n---\n\n# Fix\n\nContent.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        skill_md = agents_skills_dir / "fix" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        assert content.startswith("---\n")
        assert "name: fix" in content

    def test_setup_rules_codex_skill_creates_project_agents_md(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills/setup-rules"))

        assert "Codex reads project instructions from repo-root `AGENTS.md`" in result
        assert "If `AGENTS.md` does not exist, create it" in result
        assert "Never create AGENTS.md if it doesn't exist" not in result

    def test_create_skill_codex_skill_uses_agents_skill_paths(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills/create-skill"))

        assert ".agents/skills/{slug}-{name}/SKILL.md" in result
        assert "~/.agents/skills/{slug}-{name}/SKILL.md" in result
        assert (
            "Skills in `.agents/skills/` (project) or `~/.agents/skills/` "
            "(global) are available to Codex"
        ) in result
        assert (
            "Skills in `.claude/skills/` (project) or `~/.claude/skills/` "
            "(global) are automatically available to Claude"
        ) not in result

    def test_benchmark_codex_skill_describes_codex_materialization(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills/benchmark"))

        assert ".agents/skills/<name>/" in result
        assert "root `AGENTS.md`" in result
        assert "--agent codex" in result
        assert "with/.claude/skills/<name>/" not in result


class TestCodexRulesInstallation:
    def test_creates_agents_md_with_markers(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "testing.md").write_text("## Testing\n\nTest rules here.")
        (rules_dir / "verification.md").write_text("## Verification\n\nVerify rules.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        agents_md = codex_dir / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "<!-- PILOT:START -->" in content
        assert "<!-- PILOT:END -->" in content
        assert "## Testing" in content
        assert "## Verification" in content

    def test_preserves_user_content_outside_markers(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "AGENTS.md").write_text(
            "# My Project\n\nCustom instructions.\n\n<!-- PILOT:START -->\nold pilot content\n<!-- PILOT:END -->\n\nMore user content."
        )
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "testing.md").write_text("## Testing\n\nNew rules.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        content = (codex_dir / "AGENTS.md").read_text()
        assert "# My Project" in content
        assert "Custom instructions." in content
        assert "More user content." in content
        assert "New rules." in content
        assert "old pilot content" not in content

    def test_adapts_invocation_syntax(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "workflow.md").write_text("## Workflow\n\nRun /spec to start. Use /fix for bugs.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        content = (codex_dir / "AGENTS.md").read_text()
        assert "$spec" in content
        assert "$fix" in content

    def test_real_rules_generate_codex_safe_agents_md(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        rules_dir = tmp_path / ".claude" / "rules"
        shutil.copytree(Path("pilot/rules"), rules_dir, dirs_exist_ok=True)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        content = (codex_dir / "AGENTS.md").read_text()
        assert "## Codex Compatibility" in content
        assert "update_plan" in content
        preamble_end = "Skill invocation: use `$skill-name` (not `/skill-name`)."
        assert preamble_end in content
        rules_body = content.split(preamble_end, 1)[1]
        for forbidden in (
            "<!-- CC-ONLY -->",
            "<!-- CODEX-START",
            "AskUserQuestion",
            "TaskCreate",
            "TaskList",
            "TaskOutput",
            "Skill()",
            "Skill(",
            "Skill(skill=",
            "Skill('",
            "Agent(",
            "Task(",
            "suppressOutput",
            "hookSpecificOutput",
            "CLAUDE_CODE_TASK_LIST_ID",
            "CLAUDE_PROJECT_ROOT",
            "WebFetch",
            "WebSearch",
            "Bash(",
            "Read(",
            "Write(",
            "Edit(",
            "plain-text numbered options(",
            "plain-text numbered options tool",
            "/fix",
            "/prd",
        ):
            assert forbidden not in rules_body
        assert re.search(r"(^|[^A-Za-z0-9_`])/(spec|fix|prd)([^A-Za-z0-9_/]|$)", rules_body) is None
        for forbidden in ("Run /spec", "Use /spec", "invoke /spec"):
            assert forbidden not in content


class TestCodexMcpConfiguration:
    def test_generates_toml_for_stdio_server(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import _mcp_json_to_toml

        mcp = {"mcpServers": {"context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp@2.2.4"]}}}
        toml = _mcp_json_to_toml(mcp)
        assert "[mcp_servers.context7]" in toml
        assert 'command = "npx"' in toml
        assert 'args = ["-y", "@upstash/context7-mcp@2.2.4"]' in toml

    def test_generates_toml_for_http_server(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import _mcp_json_to_toml

        mcp = {"mcpServers": {"grep-mcp": {"type": "http", "url": "https://mcp.grep.app"}}}
        toml = _mcp_json_to_toml(mcp)
        assert "[mcp_servers.grep-mcp]" in toml
        assert 'url = "https://mcp.grep.app"' in toml

    def test_generates_toml_with_env_vars(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import _mcp_json_to_toml

        mcp = {
            "mcpServers": {
                "web-search": {
                    "command": "npx",
                    "args": ["-y", "open-websearch"],
                    "env": {"MODE": "stdio", "ENGINE": "duckduckgo"},
                }
            }
        }
        toml = _mcp_json_to_toml(mcp)
        assert "[mcp_servers.web-search.env]" in toml
        assert 'MODE = "stdio"' in toml
        assert 'ENGINE = "duckduckgo"' in toml

    def test_installs_mcp_to_codex_config_toml(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)

        mcp_json = tmp_path / ".pilot" / ".mcp.json"
        mcp_json.parent.mkdir(parents=True)
        mcp_json.write_text(json.dumps({"mcpServers": {"test-server": {"command": "echo", "args": ["hello"]}}}))

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_mcp(ctx)

        config = (codex_dir / "config.toml").read_text()
        assert "[mcp_servers.test-server]" in config

    def test_preserves_user_mcp_entries(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "config.toml").write_text('[mcp_servers.my-server]\ncommand = "my-cmd"\n\n')

        mcp_json = tmp_path / ".pilot" / ".mcp.json"
        mcp_json.parent.mkdir(parents=True)
        mcp_json.write_text(json.dumps({"mcpServers": {"pilot-server": {"command": "echo", "args": ["hello"]}}}))

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_mcp(ctx)

        config = (codex_dir / "config.toml").read_text()
        assert "my-server" in config
        assert "pilot-server" in config


class TestAdaptInvocationSyntax:
    def test_strips_cc_only_blocks(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Before.\n<!-- CC-ONLY -->\nCC-specific content here.\n<!-- /CC-ONLY -->\nAfter."
        result = _adapt_invocation_syntax(content)
        assert "CC-specific content" not in result
        assert "Before." in result
        assert "After." in result

    def test_unwraps_codex_blocks(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Before.\n<!-- CODEX-START\nCodex alternative here.\nCODEX-END -->\nAfter."
        result = _adapt_invocation_syntax(content)
        assert "Codex alternative here." in result
        assert "CODEX-START" not in result
        assert "CODEX-END" not in result
        assert "Before." in result
        assert "After." in result

    def test_cc_only_stripped_and_codex_revealed(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = (
            "Shared.\n"
            "<!-- CC-ONLY -->\nLaunch subagent.\n<!-- /CC-ONLY -->\n"
            "<!-- CODEX-START\nSkip reviewers (Codex).\nCODEX-END -->\n"
            "More shared."
        )
        result = _adapt_invocation_syntax(content)
        assert "Launch subagent" not in result
        assert "Skip reviewers (Codex)." in result
        assert "Shared." in result
        assert "More shared." in result

    def test_transforms_skill_calls(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Then invoke Skill(skill='spec-implement', args='docs/plans/plan.md')"
        result = _adapt_invocation_syntax(content)
        assert "the `$spec-implement` skill instructions with arguments: `docs/plans/plan.md`" in result
        assert "Skill(" not in result

    def test_transforms_skill_calls_without_args(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Skill(skill='spec-verify')"
        result = _adapt_invocation_syntax(content)
        assert "the `$spec-verify` skill instructions" in result
        assert "Skill(" not in result

    def test_transforms_skill_calls_with_single_quotes(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = """Skill('spec', args='implement feature — PRD: docs/prd/file.md')"""
        result = _adapt_invocation_syntax(content)
        assert "$spec" in result
        assert "Skill(" not in result

    def test_transforms_ask_user_question_blocks(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = """AskUserQuestion(
  question="Ready?",
  options=["Yes", "No"]
)"""
        result = _adapt_invocation_syntax(content)
        assert "Present numbered options in plain text" in result
        assert 'question="Ready?"' in result
        assert 'options=["Yes", "No"]' in result
        assert "AskUserQuestion" not in result
        assert "plain-text numbered options(" not in result

    def test_real_spec_skill_uses_codex_phase_handoff(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills/spec"))
        assert "Codex has no callable phase-dispatch tool" in result
        assert "continue immediately with the `$spec-plan` skill instructions" in result
        assert "Skill(skill=" not in result
        assert "Skill('" not in result

    @pytest.mark.parametrize(
        "skill_name",
        ["spec", "spec-plan", "spec-bugfix-plan", "spec-implement", "spec-verify", "spec-bugfix-verify", "prd", "fix", "benchmark", "setup-rules", "create-skill"],
    )
    def test_real_codex_skills_do_not_expose_claude_tool_calls(self, skill_name: str) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills") / skill_name)
        assert "<!-- CC-ONLY -->" not in result
        assert "<!-- CODEX-START" not in result
        for forbidden in (
            "AskUserQuestion",
            "TaskList",
            "TaskCreate",
            "TaskOutput",
            "Skill()",
            "Skill(",
            "Agent(",
            "Task(",
            "suppressOutput",
            "hookSpecificOutput",
            "CLAUDE_CODE_TASK_LIST_ID",
            "CLAUDE_PROJECT_ROOT",
            "WebFetch",
            "WebSearch",
            "ToolSearch",
            "Bash(",
            "Read(",
            "Write(",
            "Edit(",
            "plain-text numbered options(",
            "plain-text numbered options tool",
        ):
            assert forbidden not in result
        assert re.search(r"(^|[^A-Za-z0-9_`])/(spec|fix|prd|setup-rules|create-skill|benchmark)([^A-Za-z0-9_/]|$)", result) is None

    def test_multiline_cc_only_block(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Step 1.\n<!-- CC-ONLY -->\nLine 1.\nLine 2.\nLine 3.\n<!-- /CC-ONLY -->\nStep 2."
        result = _adapt_invocation_syntax(content)
        assert "Line 1" not in result
        assert "Line 2" not in result
        assert "Step 1." in result
        assert "Step 2." in result

    def test_preserves_user_hooks_in_existing_codex_hooks(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)

        existing = {
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo user-hook"}]}]}
        }
        (codex_dir / "hooks.json").write_text(json.dumps(existing))

        incoming = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo pilot"}]}]}}

        step = CodexFilesStep()
        step._merge_codex_hooks(codex_dir, incoming)

        result = json.loads((codex_dir / "hooks.json").read_text())
        assert "SessionStart" in result["hooks"]
        assert "PreToolUse" in result["hooks"]
        assert result["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "echo user-hook"


class TestTomlValidation:
    def test_valid_toml_passes(self) -> None:
        content = (
            'approval_policy = "never"\n'
            "\n"
            "[notice]\n"
            "hide_full_access_warning = true\n"
            "\n"
            "[sandbox_workspace_write]\n"
            "network_access = true\n"
        )
        _validate_toml_structure(content)

    def test_section_concatenated_on_value_line(self) -> None:
        content = "[notice]\nhide_full_access_warning = true[sandbox_workspace_write]\nnetwork_access = true\n"
        with pytest.raises(_TomlStructureError, match="section header not at start of line"):
            _validate_toml_structure(content)

    def test_section_concatenated_on_key_line(self) -> None:
        content = "bypass_hook_trust = true[notice]\nhide_full_access_warning = true\n"
        with pytest.raises(_TomlStructureError, match="line 1"):
            _validate_toml_structure(content)

    def test_exact_regression_notice_sandbox(self) -> None:
        """Exact reproduction of the real-world bug: hide_full_access_warning = true[sandbox_workspace_write]."""
        content = "[notice]\nhide_full_access_warning = true[sandbox_workspace_write]\nnetwork_access = true\n"
        with pytest.raises(_TomlStructureError):
            _validate_toml_structure(content)

    def test_comments_and_blanks_ignored(self) -> None:
        content = "# comment with [fake] section\n\n[real]\nkey = true\n"
        _validate_toml_structure(content)

    def test_managed_marker_comments_ignored(self) -> None:
        content = (
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.codegraph]\n"
            'command = "codegraph"\n'
            "# --- end pilot-shell managed MCP servers ---\n"
        )
        _validate_toml_structure(content)

    def test_brackets_inside_quoted_values_ignored(self) -> None:
        content = 'args = ["--from", "semble[mcp]", "semble"]\n'
        _validate_toml_structure(content)

    def test_array_values_with_brackets_ignored(self) -> None:
        content = '[mcp_servers.semble]\ncommand = "uvx"\nargs = ["--from", "semble[mcp]", "semble"]\n'
        _validate_toml_structure(content)

    def test_dotted_and_quoted_section_names(self) -> None:
        content = '[hooks.state."/path/to/file:event:0:0"]\ntrusted_hash = "sha256:abc"\n'
        _validate_toml_structure(content)


class TestEnsureSectionKeys:
    def test_creates_section_when_missing(self) -> None:
        content = 'approval_policy = "never"\n'
        result, changed = _ensure_section_keys(content, "features", {"memories": "true", "hooks": "true"})
        assert changed is True
        assert "[features]" in result
        assert "memories = true" in result
        assert "hooks = true" in result
        _validate_toml_structure(result)

    def test_adds_missing_keys_to_existing_section(self) -> None:
        content = "[features]\nmemories = true\n\n[notice]\nhide = true\n"
        result, changed = _ensure_section_keys(content, "features", {"hooks": "true", "memories": "true"})
        assert changed is True
        assert "hooks = true" in result
        assert result.count("memories") == 1  # not duplicated

    def test_noop_when_all_keys_present(self) -> None:
        content = "[features]\nmemories = true\nhooks = true\n"
        result, changed = _ensure_section_keys(content, "features", {"memories": "true", "hooks": "true"})
        assert changed is False
        assert result == content


class TestTuiStatuslineConfiguration:
    def test_installs_tui_statusline_on_fresh_config(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text('approval_policy = "never"\n')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert "[tui]" in result
        assert "status_line" in result
        assert "project-name" in result
        assert "model-with-reasoning" in result
        assert "status_line_use_colors = true" in result
        _validate_toml_structure(result)

    def test_preserves_existing_tui_settings(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text(
            'approval_policy = "never"\n'
            "\n"
            "[tui]\n"
            'status_line = ["project-name", "run-state"]\n'
            "status_line_use_colors = false\n"
        )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert 'status_line = ["project-name", "run-state"]' in result
        assert "status_line_use_colors = false" in result
        assert result.count("status_line =") == 1


class TestDeprecatedKeyRemoval:
    def test_removes_bypass_hook_trust(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text(
            'approval_policy = "never"\n'
            "bypass_hook_trust = true\n"
            "\n"
            "[features]\n"
            "hooks = true\n"
        )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert "bypass_hook_trust" not in result
        assert "hooks = true" in result
        assert "undo = true" in result
        assert "mentions_v2 = true" in result
        assert "tool_search = true" in result
        assert "apps = true" in result


class TestMcpMarkerReplacement:
    """Regression tests: MCP managed block replacement must not corrupt surrounding sections."""

    def _make_step_with_mcp_json(self, tmp_path: Path, mcp_data: dict) -> tuple[CodexFilesStep, Path]:
        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / ".mcp.json").write_text(json.dumps(mcp_data))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        return CodexFilesStep(), codex_dir / "config.toml"

    @patch("installer.steps.codex_files._get_codex_config_dir")
    @patch("installer.steps.codex_files.Path.home")
    def test_second_install_preserves_section_newlines(
        self, mock_home: MagicMock, mock_codex_dir: MagicMock, tmp_path: Path
    ) -> None:
        mock_home.return_value = tmp_path
        mock_codex_dir.return_value = tmp_path / ".codex"
        step, config_path = self._make_step_with_mcp_json(
            tmp_path, {"mcpServers": {"codegraph": {"command": "codegraph", "args": ["serve", "--mcp"]}}}
        )

        initial = (
            'approval_policy = "never"\n'
            "\n"
            "[notice]\n"
            "hide_full_access_warning = true\n"
            "\n"
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.codegraph]\n"
            'command = "codegraph"\n'
            'args = ["serve", "--mcp"]\n'
            "\n"
            "# --- end pilot-shell managed MCP servers ---\n"
            "\n"
            "[sandbox_workspace_write]\n"
            "network_access = true\n"
        )
        config_path.write_text(initial)

        ctx = MagicMock()
        step._install_codex_mcp(ctx)

        result = config_path.read_text()
        _validate_toml_structure(result)
        assert "[notice]" in result
        assert "[sandbox_workspace_write]" in result

    @patch("installer.steps.codex_files._get_codex_config_dir")
    @patch("installer.steps.codex_files.Path.home")
    def test_markers_between_user_sections_preserved(
        self, mock_home: MagicMock, mock_codex_dir: MagicMock, tmp_path: Path
    ) -> None:
        mock_home.return_value = tmp_path
        mock_codex_dir.return_value = tmp_path / ".codex"
        step, config_path = self._make_step_with_mcp_json(
            tmp_path, {"mcpServers": {"ctx7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]}}}
        )

        initial = (
            "[notice]\n"
            "hide_full_access_warning = true\n"
            "\n"
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.old]\n"
            'command = "old"\n'
            "\n"
            "# --- end pilot-shell managed MCP servers ---\n"
            "\n"
            "[sandbox_workspace_write]\n"
            "network_access = true\n"
        )
        config_path.write_text(initial)

        ctx = MagicMock()
        step._install_codex_mcp(ctx)

        result = config_path.read_text()
        assert "[notice]" in result
        assert "[sandbox_workspace_write]" in result
        assert "mcp_servers.ctx7" in result
        assert "mcp_servers.old" not in result
        _validate_toml_structure(result)
