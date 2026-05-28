"""Tests for uninstall.sh — Codex cleanup coverage."""

from __future__ import annotations

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
    assert '/.pilot/' in _content()


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
