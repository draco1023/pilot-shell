"""Tests for uninstall.sh — Codex cleanup coverage."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

UNINSTALL_SH = Path(__file__).parent.parent.parent.parent / "uninstall.sh"


def _content() -> str:
    return UNINSTALL_SH.read_text()


def test_uninstall_sh_has_remove_codex_files_function():
    """uninstall.sh must define a remove_codex_files function."""
    assert "remove_codex_files()" in _content()


def test_uninstall_sh_remove_codex_files_called_in_main_flow():
    """remove_codex_files must be called in the main uninstall sequence."""
    content = _content()
    assert content.count("remove_codex_files") >= 2, (
        "Expected at least 2 occurrences: the function definition and a call site"
    )


def test_uninstall_sh_codex_dir_respects_codex_home():
    """CODEX_DIR must be defined honouring the CODEX_HOME env var."""
    content = _content()
    assert "CODEX_HOME" in content
    assert ".codex" in content


def test_uninstall_sh_agents_skills_dir_defined():
    """~/.agents/skills path must be referenced for skills cleanup."""
    assert ".agents/skills" in _content()


def test_uninstall_sh_codex_hooks_cleanup_uses_pilot_path_marker():
    """Pilot hooks are identified by /.pilot/ in command strings — mirrors _is_pilot_managed_entry."""
    assert "/.pilot/" in _content()


def test_uninstall_sh_codex_config_toml_mcp_block_removed():
    """Managed MCP block start marker must be present so the removal logic can strip it."""
    assert "pilot-shell managed MCP servers" in _content()


def test_uninstall_sh_codex_agents_md_cleaned():
    """AGENTS.md cleanup must use the PILOT:START and PILOT:END markers."""
    content = _content()
    assert "PILOT:START" in content
    assert "PILOT:END" in content


def test_uninstall_sh_codex_skills_removed():
    """Known Pilot skill names must appear in the skills cleanup block."""
    content = _content()
    assert "spec-plan" in content
    assert "spec-implement" in content
    assert "spec-bugfix-plan" in content


def test_uninstall_removes_shell_wrappers_and_codex_env_block(tmp_path: Path):
    """Uninstall should remove Pilot shell wrappers and Codex managed env vars."""
    home = tmp_path / "home"
    home.mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text(
        "\n".join(
            [
                "# before",
                "# Pilot Shell",
                'export PATH="$HOME/.pilot/bin:$HOME/.bun/bin:$PATH"',
                'alias pilot="$HOME/.pilot/bin/pilot"',
                'alias ccp="$HOME/.pilot/bin/pilot"',
                'claude() { local _sid="$$-$RANDOM"; PILOT_SESSION_ID=$_sid CLAUDE_CODE_TASK_LIST_ID="pilot-$_sid" command claude "$@"; }',
                'codex() { PILOT_SESSION_ID="$$-$RANDOM" command codex "$@"; }',
                "# after",
                "",
            ]
        )
    )

    codex_dir = home / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        "\n".join(
            [
                'approval_policy = "never"',
                "# --- pilot-shell managed env vars ---",
                "[shell_environment_policy.set]",
                'PILOT_PLAN_APPROVAL_ENABLED = "false"',
                "# --- end pilot-shell managed env vars ---",
                'model = "gpt-5"',
                "",
            ]
        )
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)
    result = subprocess.run(["bash", str(UNINSTALL_SH), "--yes"], env=env, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    shell_content = zshrc.read_text()
    assert "claude()" not in shell_content
    assert "codex()" not in shell_content
    assert "alias pilot=" not in shell_content
    assert "# before" in shell_content
    assert "# after" in shell_content

    codex_config = (codex_dir / "config.toml").read_text()
    assert "pilot-shell managed env vars" not in codex_config
    assert "PILOT_PLAN_APPROVAL_ENABLED" not in codex_config
    assert 'approval_policy = "never"' in codex_config
    assert 'model = "gpt-5"' in codex_config
