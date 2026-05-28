"""Pilot Files installation step — agent-neutral Pilot Shell-managed assets.

This step always runs and installs:

- ``hooks`` → ``~/.pilot/hooks/`` — Python hook scripts + ``hooks.json``
  (referenced from both Claude and Codex agent configs)
- ``pilot_home`` → ``~/.pilot/`` — Console scripts, UI assets, ``.mcp.json``,
  shared app config, package metadata
- ``skills`` → ``~/.claude/skills/`` — the canonical Pilot-managed skill
  source. Claude Code reads it natively; ``CodexFilesStep`` adapts it into
  ``~/.agents/skills/``. Skills install here regardless of whether Claude
  Code itself is installed, because Codex's adapter needs the decomposed
  skill structure (``manifest.json`` + fragments) to build its own loadable
  ``SKILL.md`` files.

Categories that target ``~/.claude/`` *exclusively* (``rules``, ``agents``,
``settings``) are owned by :class:`installer.steps.claude_files.ClaudeFilesStep`
and gated on ``is_claude_installed()``. ``PilotFilesStep`` caches the
download metadata in two named keys on ``ctx.config`` (see
``PILOT_FILES_CACHE_CATEGORIES_KEY`` / ``PILOT_FILES_CACHE_CONFIG_KEY``
below) so the Claude step can reuse it without a second GitHub round-trip.
"""

from __future__ import annotations

from pathlib import Path

from installer.context import InstallContext
from installer.downloads import download_files_parallel, get_repo_files
from installer.platform_utils import is_claude_installed
from installer.steps.base import BaseStep
from installer.steps.claude_files import ClaudeFilesStep

# Inter-step cache keys on ``ctx.config``. ``PilotFilesStep`` writes both;
# ``ClaudeFilesStep`` reads both. Keep these names in sync with the reader
# (claude_files.py imports them). The leading underscore marks them as
# inter-step cache (not user-facing config) — separate from the public
# ``installed_files`` key which both steps append to.
PILOT_FILES_CACHE_CATEGORIES_KEY = "_pilot_files_categories"
PILOT_FILES_CACHE_CONFIG_KEY = "_pilot_files_config"


class PilotFilesStep(BaseStep):
    """Installs Pilot Shell-managed agent-neutral assets.

    Uses ``ClaudeFilesStep`` *by composition* (not inheritance) to reuse the
    shared download/categorize/install/cleanup helpers without inheriting
    Claude-only methods like ``_install_settings`` / ``_merge_hooks_into_settings``
    / ``_merge_app_config`` / ``_merge_mcp_servers_into_claude_json`` /
    ``_reapply_customization``. This avoids the LSP violation of
    "PilotFilesStep IS-A ClaudeFilesStep" — Pilot is a separate concept that
    happens to share the file-install plumbing.

    When Claude Code is not installed on this system, ``ClaudeFilesStep``
    will skip — so this step also runs ``_cleanup_stale_managed_files`` to
    remove any leftover Pilot-managed files from a previous Claude install.
    When Claude *is* installed, that cleanup is deferred to
    ``ClaudeFilesStep`` so the union of pilot + Claude installed files is
    used to decide what's stale (avoids temporarily removing live Claude
    rules/agents between the two steps).
    """

    name = "pilot_files"

    _PILOT_CATEGORIES = ("hooks", "pilot_home", "skills")

    def __init__(self) -> None:
        # Composition target — used purely as a bag of file-install helpers.
        # Its public run() and Claude-specific methods are NEVER invoked from
        # this step.
        self._installer = ClaudeFilesStep()

    def check(self, ctx: InstallContext) -> bool:
        """Always run — Pilot runtime is required for both agents."""
        return False

    def run(self, ctx: InstallContext) -> None:
        ui = ctx.ui
        config = self._installer._create_download_config(ctx)

        if ui:
            ui.status("Installing Pilot Shell-managed assets...")

        pilot_files = get_repo_files("pilot", config)
        if not pilot_files:
            self._installer._handle_no_files(ui, config)
            return

        categories = self._installer._categorize_files(pilot_files, ctx)

        ctx.config[PILOT_FILES_CACHE_CATEGORIES_KEY] = categories
        ctx.config[PILOT_FILES_CACHE_CONFIG_KEY] = config

        self._installer._cleanup_old_directories(ctx, config, ui)

        pilot_categories = {cat: files for cat, files in categories.items() if cat in self._PILOT_CATEGORIES and files}
        installed_files, file_count, failed_files = self._installer._install_categories(
            pilot_categories, ctx, config, ui
        )
        existing_installed = list(ctx.config.get("installed_files", []))
        ctx.config["installed_files"] = existing_installed + installed_files

        self._stage_raw_rules_for_codex(categories.get("rules", []), config)
        self._installer._make_scripts_executable(Path.home() / ".pilot" / "scripts")
        self._installer._build_skill_md_files(ctx, ui)

        # When Claude Code is NOT installed, ClaudeFilesStep will skip — we own
        # the cleanup/manifest tail here. cleanup_stale MUST run before
        # save_pilot_manifest, otherwise we'd read the freshly-saved manifest
        # and find nothing stale. When Claude Code IS installed, both calls are
        # deferred to ClaudeFilesStep so they see the union of pilot + Claude
        # installed files.
        if not is_claude_installed():
            self._installer._cleanup_stale_managed_files(ctx)
            self._installer._save_pilot_manifest(ctx)

        self._installer._report_results(ui, file_count, failed_files)

    def _stage_raw_rules_for_codex(self, rule_files: list, config) -> None:
        """Download RAW (un-adapted) rule sources to ``~/.pilot/rules/``.

        ``CodexFilesStep._install_codex_rules`` falls back through three source
        candidates: ``local_repo_dir/pilot/rules`` → ``~/.pilot/rules`` →
        ``~/.claude/rules``. Without this stage, non-local installs land on the
        third candidate, which has either been Claude-adapted by
        ``ClaudeFilesStep`` (so Codex sees CC-ONLY unwrapped + CODEX-START
        deleted — the wrong content for Codex) or is empty/wiped on Codex-only
        systems. Staging raw rules at ``~/.pilot/rules`` makes the second
        fallback authoritative for the Codex adapter.
        """
        if not rule_files:
            return
        pilot_rules_dir = Path.home() / ".pilot" / "rules"
        pilot_rules_dir.mkdir(parents=True, exist_ok=True)
        dest_paths = [pilot_rules_dir / Path(fi.path).name for fi in rule_files]
        download_files_parallel(rule_files, dest_paths, config)
