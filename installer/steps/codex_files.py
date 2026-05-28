"""Installer step for Codex CLI-specific file installation.

Installs hooks, skills, MCP config, and rules for Codex users.
Only runs when the Codex CLI binary is detected on the system.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from installer.context import InstallContext
from installer.steps.base import BaseStep

# Vendored from launcher.agent_runtime — installer cannot import from launcher
# (see .claude/rules/pilot-shell-package-boundaries.md).

_CODEX_BINARY_NAME = "codex"


def _is_codex_installed() -> bool:
    """Check if Codex CLI is available on this system."""
    if shutil.which(_CODEX_BINARY_NAME):
        return True
    for candidate in [
        Path.home() / ".codex" / "bin" / "codex",
        Path("/usr/local/bin/codex"),
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False


def _get_codex_config_dir() -> Path:
    """Resolve the Codex config directory, respecting CODEX_HOME env var."""
    env_dir = os.environ.get("CODEX_HOME")
    if env_dir:
        p = Path(env_dir)
        if not p.is_absolute():
            raise ValueError(f"CODEX_HOME must be an absolute path, got: {env_dir}")
        return p
    return Path.home() / ".codex"


class CodexFilesStep(BaseStep):
    """Install Pilot Shell assets for Codex CLI."""

    name = "codex_files"

    def check(self, ctx: InstallContext) -> bool:
        return False

    def run(self, ctx: InstallContext) -> None:
        if not _is_codex_installed():
            if ctx.ui:
                ctx.ui.info("Codex CLI not detected — skipping Codex file installation")
            return

        if ctx.ui:
            ctx.ui.status("Installing Codex CLI integration...")

        try:
            self._install_codex_hooks(ctx)
            self._install_codex_skills(ctx)
            self._install_codex_agents(ctx)
        except ValueError as e:
            if ctx.ui:
                ctx.ui.warning(f"Skipping Codex file installation: {e}")
            return
        try:
            self._install_codex_config(ctx)
            self._install_codex_mcp(ctx)
        except _TomlStructureError as e:
            if ctx.ui:
                ctx.ui.warning(f"Skipping Codex TOML config due to structure error: {e}")
        except ValueError as e:
            if ctx.ui:
                ctx.ui.warning(f"Skipping Codex file installation: {e}")
            return
        self._install_codex_rules(ctx)

        if ctx.ui:
            ctx.ui.success("Installed Codex CLI integration")

    def _install_codex_hooks(self, ctx: InstallContext) -> None:
        """Install hooks.json for Codex CLI."""
        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)

        template_path = self._find_codex_hooks_template(ctx)
        if template_path is None:
            return

        try:
            incoming = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        self._merge_codex_hooks(codex_dir, incoming)

    def _find_codex_hooks_template(self, ctx: InstallContext) -> Path | None:
        """Locate the codex_hooks.json template from install source."""
        if ctx.local_mode and ctx.local_repo_dir:
            candidate = ctx.local_repo_dir / "pilot" / "hooks" / "codex_hooks.json"
            if candidate.is_file():
                return candidate

        pilot_home = Path.home() / ".pilot"
        candidate = pilot_home / "hooks" / "codex_hooks.json"
        if candidate.is_file():
            return candidate

        return None

    def _merge_codex_hooks(self, codex_dir: Path, incoming: dict[str, Any]) -> None:
        """Write or merge hooks into ~/.codex/hooks.json.

        Pilot Shell-managed hook entries are identified by commands containing
        '/.pilot/' in their command string. User-added entries are preserved.
        """
        hooks_file = codex_dir / "hooks.json"
        incoming_hooks = incoming.get("hooks", {})

        if not hooks_file.exists():
            hooks_file.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(hooks_file, json.dumps(incoming, indent=2) + "\n")
            return

        try:
            existing = json.loads(hooks_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _atomic_write(hooks_file, json.dumps(incoming, indent=2) + "\n")
            return

        existing_hooks = existing.get("hooks", {})

        merged: dict[str, list[Any]] = {}

        all_events = set(existing_hooks.keys()) | set(incoming_hooks.keys())
        for event in all_events:
            existing_entries = existing_hooks.get(event, [])
            incoming_entries = incoming_hooks.get(event, [])

            user_entries = [e for e in existing_entries if not _is_pilot_managed_entry(e)]

            merged[event] = incoming_entries + user_entries

        result = dict(existing)
        result["hooks"] = merged
        _atomic_write(hooks_file, json.dumps(result, indent=2) + "\n")

    def _install_codex_mcp(self, ctx: InstallContext) -> None:
        """Generate MCP server config in ~/.codex/config.toml from .mcp.json."""
        pilot_home = Path.home() / ".pilot"
        mcp_json_path = pilot_home / ".mcp.json"
        if not mcp_json_path.is_file():
            return

        try:
            mcp_data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        toml_block = _mcp_json_to_toml(mcp_data)
        if not toml_block.strip():
            return

        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)
        config_path = codex_dir / "config.toml"

        marker_start = "# --- pilot-shell managed MCP servers ---"
        marker_end = "# --- end pilot-shell managed MCP servers ---"

        existing = ""
        if config_path.is_file():
            try:
                existing = config_path.read_text(encoding="utf-8")
            except OSError:
                pass

        if marker_start in existing:
            start_idx = existing.index(marker_start)
            if marker_end in existing:
                end_idx = existing.index(marker_end) + len(marker_end)
            else:
                end_idx = start_idx + len(marker_start)
            before = existing[:start_idx].rstrip("\n")
            after = existing[end_idx:].lstrip("\n")
            if before and after:
                preserved = before + "\n\n" + after
            else:
                preserved = before or after
        else:
            preserved = existing

        managed_block = f"\n{marker_start}\n{toml_block}{marker_end}\n"
        final = preserved.rstrip("\n") + "\n" + managed_block if preserved.strip() else managed_block.lstrip("\n")
        _validate_toml_structure(final)
        _atomic_write(config_path, final)

    def _install_codex_rules(self, ctx: InstallContext) -> None:
        """Merge Pilot Shell rules into ~/.codex/AGENTS.md between markers."""
        rules_dir: Path | None = None
        if ctx.local_mode and ctx.local_repo_dir:
            candidate = ctx.local_repo_dir / "pilot" / "rules"
            if candidate.is_dir():
                rules_dir = candidate
        if rules_dir is None:
            pilot_home = Path.home() / ".pilot"
            candidate = pilot_home / "rules"
            if candidate.is_dir():
                rules_dir = candidate
        if rules_dir is None:
            rules_dir = Path.home() / ".claude" / "rules"
        if not rules_dir.is_dir():
            return

        rule_files = sorted(f for f in rules_dir.iterdir() if f.suffix == ".md" and f.is_file())
        if not rule_files:
            return

        parts: list[str] = []
        for rule_file in rule_files:
            try:
                content = rule_file.read_text(encoding="utf-8").strip()
                adapted = _adapt_invocation_syntax(content)
                parts.append(adapted)
            except OSError:
                continue

        if not parts:
            return

        codex_preamble = (
            "## Codex Compatibility\n\n"
            "This agent is Codex CLI. The following Claude Code tools are NOT available:\n\n"
            "- **`AskUserQuestion`** — not supported. When instructions say to use `AskUserQuestion`, "
            "instead present numbered options as plain text and ask the user to reply with a number or "
            "free text. Format: `1. Option A — description\\n2. Option B — description\\n"
            "Reply with a number or type your preference:`\n"
            "- **`suppressOutput`** — parsed but not implemented in hook responses. Never rely on it.\n"
            "- **`systemMessage`** — surfaced as a UI warning or event-stream message; do not use it for hidden context.\n\n"
            "Tool name mapping: `Edit`/`Write` → `apply_patch` (Codex uses `apply_patch` for file edits, "
            "but `Edit`/`Write` work as aliases).\n\n"
            "Skill invocation: use `$skill-name` (not `/skill-name`).\n"
        )

        managed_content = codex_preamble + "\n\n" + "\n\n".join(parts)
        block = f"<!-- PILOT:START -->\n{managed_content}\n<!-- PILOT:END -->"

        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)
        agents_md = codex_dir / "AGENTS.md"

        if agents_md.is_file():
            try:
                existing = agents_md.read_text(encoding="utf-8")
            except OSError:
                existing = ""

            if "<!-- PILOT:START -->" in existing and "<!-- PILOT:END -->" in existing:
                start = existing.index("<!-- PILOT:START -->")
                end = existing.index("<!-- PILOT:END -->") + len("<!-- PILOT:END -->")
                if start < end:
                    final = existing[:start] + block + existing[end:]
                else:
                    final = existing.rstrip("\n") + "\n\n" + block + "\n"
            else:
                final = existing.rstrip("\n") + "\n\n" + block + "\n"
        else:
            final = block + "\n"

        _atomic_write(agents_md, final)

    def _install_codex_config(self, ctx: InstallContext) -> None:
        """Set Codex full-access config in ~/.codex/config.toml.

        Top-level keys are inserted before the first [section] header so they
        don't accidentally land inside an unrelated TOML table.
        """
        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)
        config_path = codex_dir / "config.toml"

        existing = ""
        if config_path.is_file():
            try:
                existing = config_path.read_text(encoding="utf-8")
            except OSError:
                pass

        required_top_level = {
            "approval_policy": '"never"',
            "sandbox_mode": '"danger-full-access"',
            "model_reasoning_effort": '"xhigh"',
            "model_reasoning_summary": '"concise"',
            "personality": '"pragmatic"',
            "check_for_update_on_startup": "true",
            "file_opener": '"vscode"',
        }
        changed = False
        section_match = re.search(r"(?m)^\[", existing)
        top_level_scope = existing[: section_match.start()] if section_match else existing
        for key, value in required_top_level.items():
            if not re.search(rf"(?m)^{re.escape(key)}\s*=", top_level_scope):
                existing = _insert_top_level_key(existing, key, value)
                sm = re.search(r"(?m)^\[", existing)
                top_level_scope = existing[: sm.start()] if sm else existing
                changed = True

        deprecated_keys = ["bypass_hook_trust"]
        for key in deprecated_keys:
            pattern = rf"(?m)^{re.escape(key)}\s*=\s*[^\n]*\n?"
            if re.search(pattern, top_level_scope):
                existing = re.sub(pattern, "", existing)
                changed = True

        required_features = {
            "apps": "false",
            "hooks": "true",
            "memories": "true",
            "mentions_v2": "true",
            "plugins": "true",
            "terminal_resize_reflow": "true",
            "tool_call_mcp_elicitation": "true",
            "tool_search": "true",
            "tool_suggest": "true",
            "undo": "true",
        }
        existing, features_changed = _ensure_section_keys(existing, "features", required_features)
        changed = changed or features_changed

        if "[sandbox_workspace_write]" not in existing:
            if existing and not existing.endswith("\n\n"):
                existing = existing.rstrip("\n") + "\n\n"
            existing += "[sandbox_workspace_write]\nnetwork_access = true\n"
            changed = True

        required_tui = {
            "status_line": '["project-name", "model-with-reasoning", "branch-changes", "context-used", "task-progress", "run-state", "five-hour-limit", "weekly-limit"]',
            "status_line_use_colors": "true",
        }
        existing, tui_changed = _ensure_section_keys(existing, "tui", required_tui)
        changed = changed or tui_changed

        if "[notice]" not in existing:
            if existing and not existing.endswith("\n\n"):
                existing = existing.rstrip("\n") + "\n\n"
            existing += "[notice]\nhide_full_access_warning = true\n"
            changed = True
        elif "hide_full_access_warning" not in existing:
            idx = existing.index("[notice]")
            end = existing.index("\n", idx) + 1
            existing = existing[:end] + "hide_full_access_warning = true\n" + existing[end:]
            changed = True

        if changed:
            _validate_toml_structure(existing)
            _atomic_write(config_path, existing)

    _CODEX_SUPPORTED_SKILLS = frozenset(
        {
            "spec",
            "spec-plan",
            "spec-bugfix-plan",
            "spec-implement",
            "spec-verify",
            "spec-bugfix-verify",
            "fix",
            "prd",
            "benchmark",
            "setup-rules",
            "create-skill",
        }
    )

    _CODEX_STALE_SKILLS = frozenset({"bot-boot", "bot-channel-task", "bot-defaults", "bot-heartbeat", "bot-jobs"})
    _CODEX_MANAGED_REVIEW_AGENTS = frozenset({"changes-review", "spec-review"})

    def _install_codex_skills(self, ctx: InstallContext) -> None:
        """Install supported Pilot Shell skills to ~/.agents/skills/ for Codex.

        All non-bot skills are shipped to Codex. Bot skills (bot-boot, bot-channel-task,
        bot-defaults, bot-heartbeat, bot-jobs) depend on Claude Code cron/remote-control.
        Stale bot-* skills from older installs are cleaned up.
        """
        claude_skills_dir = Path.home() / ".claude" / "skills"
        agents_skills_dir = Path.home() / ".agents" / "skills"

        if not claude_skills_dir.is_dir():
            return

        # Clean up stale bot-* skills from older installs
        if agents_skills_dir.is_dir():
            for name in self._CODEX_STALE_SKILLS:
                stale = agents_skills_dir / name
                if stale.is_dir():
                    shutil.rmtree(stale, ignore_errors=True)

        decomposed = [
            p
            for p in sorted(claude_skills_dir.iterdir())
            if p.is_dir() and (p / "manifest.json").is_file() and p.name in self._CODEX_SUPPORTED_SKILLS
        ]

        for skill_dir in decomposed:
            try:
                codex_content = build_codex_skill_md(skill_dir)
            except Exception as e:
                if ctx.ui:
                    ctx.ui.warning(f"Failed to build SKILL.md for {skill_dir.name}: {e}")
                continue

            dest_dir = agents_skills_dir / skill_dir.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write(dest_dir / "SKILL.md", codex_content)

    def _find_codex_review_agents_source(self, ctx: InstallContext) -> Path | None:
        """Locate the source markdown agents used to build Codex custom agents."""
        if getattr(ctx, "local_mode", False) is True and getattr(ctx, "local_repo_dir", None):
            candidate = ctx.local_repo_dir / "pilot" / "agents"
            if candidate.is_dir():
                return candidate

        candidate = Path.home() / ".claude" / "agents"
        if candidate.is_dir():
            return candidate

        return None

    def _install_codex_agents(self, ctx: InstallContext) -> None:
        """Install Pilot-managed review agents as Codex custom-agent TOML files."""
        source_dir = self._find_codex_review_agents_source(ctx)
        if source_dir is None:
            return

        codex_agents_dir = _get_codex_config_dir() / "agents"
        codex_agents_dir.mkdir(parents=True, exist_ok=True)

        for agent_name in sorted(self._CODEX_MANAGED_REVIEW_AGENTS):
            source = source_dir / f"{agent_name}.md"
            if not source.is_file():
                continue
            try:
                codex_content = build_codex_review_agent_toml(source)
            except Exception as e:
                if ctx.ui:
                    ctx.ui.warning(f"Failed to build Codex agent for {agent_name}: {e}")
                continue
            target = codex_agents_dir / f"{agent_name}.toml"
            if target.exists() and not _is_pilot_managed_codex_review_agent(target):
                if ctx.ui:
                    ctx.ui.warning(f"Preserving user-created Codex agent: {target}")
                continue
            _atomic_write(target, codex_content)


def _ensure_section_keys(
    content: str,
    section: str,
    keys: dict[str, str],
) -> tuple[str, bool]:
    """Ensure keys exist inside a ``[section]`` table, creating it if needed.

    Returns (updated_content, changed). Existing user values are preserved —
    only missing keys are added.
    """
    header = f"[{section}]"
    changed = False

    if header not in content:
        if content and not content.endswith("\n\n"):
            content = content.rstrip("\n") + "\n\n"
        lines = [header]
        for k, v in keys.items():
            lines.append(f"{k} = {v}")
        content += "\n".join(lines) + "\n"
        return content, True

    idx = content.index(header)
    end = content.index("\n", idx) + 1

    next_section = re.search(r"(?m)^\[", content[end:])
    section_end = end + next_section.start() if next_section else len(content)
    section_text = content[end:section_end]

    for key, value in keys.items():
        if not re.search(rf"(?m)^{re.escape(key)}\s*=", section_text):
            content = content[:end] + f"{key} = {value}\n" + content[end:]
            insertion_len = len(f"{key} = {value}\n")
            end += insertion_len
            section_end += insertion_len
            section_text = content[end:section_end]
            changed = True

    return content, changed


def _insert_top_level_key(content: str, key: str, value: str) -> str:
    """Insert a key=value pair into the top-level scope of a TOML string.

    Inserts before the first ``[section]`` header so the key doesn't
    accidentally land inside an unrelated table.
    """
    line = f"{key} = {value}\n"
    m = re.search(r"(?m)^\[", content)
    if m:
        pos = m.start()
        prefix = content[:pos]
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        return prefix + line + content[pos:]
    if content and not content.endswith("\n"):
        content += "\n"
    return content + line


def _mcp_json_to_toml(mcp_data: dict[str, Any]) -> str:
    """Convert .mcp.json mcpServers dict to TOML [mcp_servers.*] sections."""
    servers = mcp_data.get("mcpServers", {})
    if not isinstance(servers, dict):
        return ""

    lines: list[str] = []
    for name, config in servers.items():
        if not isinstance(config, dict):
            continue
        lines.append(f"[mcp_servers.{name}]")

        server_type = config.get("type", "")
        if server_type == "http" or "url" in config:
            url = config.get("url", "")
            if url:
                lines.append(f'url = "{url}"')
        else:
            cmd = config.get("command", "")
            if cmd:
                lines.append(f'command = "{cmd}"')
            args = config.get("args")
            if isinstance(args, list) and args:
                args_str = ", ".join(f'"{a}"' for a in args)
                lines.append(f"args = [{args_str}]")

        env = config.get("env")
        if isinstance(env, dict) and env:
            lines.append("")
            lines.append(f"[mcp_servers.{name}.env]")
            for k, v in env.items():
                lines.append(f'{k} = "{v}"')

        lines.append("")

    return "\n".join(lines) + "\n" if lines else ""


_PILOT_SKILL_NAMES = frozenset(
    {
        "spec",
        "spec-plan",
        "spec-bugfix-plan",
        "spec-implement",
        "spec-verify",
        "spec-bugfix-verify",
        "setup-rules",
        "create-skill",
        "prd",
        "benchmark",
        "fix",
        "bot-boot",
        "bot-channel-task",
        "bot-defaults",
        "bot-heartbeat",
        "bot-jobs",
    }
)

_SKILL_INVOCATION_RE = re.compile(
    r"(?<![a-zA-Z0-9_/])/"
    r"(" + "|".join(re.escape(s) for s in sorted(_PILOT_SKILL_NAMES, key=len, reverse=True)) + r")"
    r"(?![a-zA-Z0-9_/])"
)


def build_codex_skill_md(skill_dir: Path) -> str:
    """Build a Codex-format SKILL.md with YAML frontmatter from a decomposed skill.

    Reads the manifest.json, builds the skill content (same as Claude Code),
    extracts name/description from the orchestrator's frontmatter, prepends
    Codex-style YAML frontmatter, and adapts invocation syntax (/ → $).
    """
    from installer.skill_builder import build_skill_md

    content = build_skill_md(skill_dir)

    name, description = _extract_skill_metadata(content)
    description = _adapt_invocation_syntax(description)

    adapted = _adapt_invocation_syntax(content)

    if adapted.startswith("---\n"):
        end = adapted.find("\n---", 3)
        if end != -1:
            adapted = adapted[end + 4 :].lstrip("\n")

    frontmatter = f"---\nname: {name}\ndescription: {description}\n---\n\n"
    return frontmatter + adapted


def build_codex_review_agent_toml(agent_file: Path) -> str:
    """Build a Codex custom-agent TOML file from a Pilot review-agent markdown file."""
    content = agent_file.read_text(encoding="utf-8")
    metadata, body = _extract_agent_metadata(content)
    name = metadata.get("name") or agent_file.stem
    description = metadata.get("description") or f"Pilot {name} review agent."
    instructions = _adapt_review_agent_instructions_for_codex(body)
    return (
        "# pilot-shell managed Codex review agent\n"
        f"name = {_toml_string(name)}\n"
        f"description = {_toml_string(description)}\n"
        f"developer_instructions = {_toml_string(instructions)}\n"
    )


def _extract_agent_metadata(content: str) -> tuple[dict[str, str], str]:
    """Extract simple YAML frontmatter key/value pairs from a markdown agent."""
    if not content.startswith("---\n"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    metadata: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, content[end + 4 :].lstrip("\n")


def _adapt_review_agent_instructions_for_codex(body: str) -> str:
    """Convert Claude Code output-file review agents into Codex final-response agents."""
    adapted = body
    adapted = adapted.replace(" (excluding the final Write)", "")
    adapted = adapted.replace(" → Write output (1)", " → final JSON response")
    adapted = re.sub(
        r"\*\*⛔ MANDATORY: Write output\.\*\*.*?(?=\n\n)",
        (
            "**⛔ MANDATORY: Return output.** Your final response MUST be the JSON object. "
            "At the tool-call budget, stop exploring and return what you have. "
            "No final JSON means the parent workflow cannot continue."
        ),
        adapted,
        flags=re.DOTALL,
    )
    adapted = adapted.replace("### 4. Write Output", "### 4. Return Output")
    adapted = adapted.replace("### 5. Write Output", "### 5. Return Output")
    adapted = adapted.replace("**Write JSON to `output_path` as your FINAL action.**", "**Return JSON as your final response.**")
    adapted = adapted.replace("Write JSON to `output_path` as your FINAL action.", "Return JSON as your final response.")
    adapted = adapted.replace("The orchestrator provides:", "The parent prompt provides:")
    adapted = adapted.replace(", `output_path`", "")
    adapted = adapted.replace("`output_path`, ", "")
    adapted = adapted.replace("`output_path`", "the parent prompt")
    adapted = adapted.replace("write what you have", "return what you have")
    adapted = adapted.replace("No file = orchestrator stalls.", "No final JSON = parent workflow cannot continue.")
    adapted = re.sub(r"\n{3,}", "\n\n", adapted).strip()
    return (
        "Pilot-managed Codex review agent. Return ONLY valid JSON as the final response. "
        "Do not write files, do not wrap JSON in markdown, and do not include commentary outside the JSON object.\n\n"
        + adapted
    )


def _toml_string(value: str) -> str:
    """Serialize a Python string as a TOML basic string."""
    return json.dumps(value)


def _is_pilot_managed_codex_review_agent(agent_file: Path) -> bool:
    try:
        content = agent_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return "pilot-shell managed Codex review agent" in content or "Pilot-managed Codex review agent" in content


def _extract_skill_metadata(content: str) -> tuple[str, str]:
    """Extract name and description from Claude Code YAML frontmatter in skill content."""
    name = ""
    description = ""

    if content.startswith("---\n"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_block = content[4:end]
            for line in fm_block.split("\n"):
                if line.startswith("name:"):
                    name = line[5:].strip()
                elif line.startswith("description:"):
                    description = line[12:].strip()

    return name or "unknown", description or ""


_CC_ONLY_RE = re.compile(
    r"<!-- CC-ONLY -->\n?.*?<!-- /CC-ONLY -->\n?",
    re.DOTALL,
)

_CODEX_BLOCK_RE = re.compile(
    r"<!-- CODEX-START\n(.*?)CODEX-END -->(?:\n?)",
    re.DOTALL,
)

_SKILL_CALL_RE = re.compile(
    r"Skill\(\s*(?:skill\s*=\s*)?['\"]([^'\"]+)['\"]\s*"
    r"(?:,\s*args\s*=\s*['\"]([^'\"]*)['\"])?\s*\)"
)

_ASK_USER_QUESTION_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)AskUserQuestion\(\n(?P<body>.*?)(?=^[ \t]*\)\s*$)^[ \t]*\)\s*$",
    re.DOTALL | re.MULTILINE,
)


def _adapt_invocation_syntax(content: str) -> str:
    """Replace /skill-name with $skill-name and adapt Codex-incompatible tool references.

    Processing order:
    1. Strip ``<!-- CC-ONLY -->`` … ``<!-- /CC-ONLY -->`` blocks (CC-specific sections).
    2. Unwrap ``<!-- CODEX-START`` … ``CODEX-END -->`` blocks (Codex alternatives hidden as HTML comments).
    3. Replace ``Skill(skill='X', args='Y')`` calls with Codex skill-instruction handoffs.
    4. Replace ``/skill-name`` with ``$skill-name`` for user-facing references.
    5. Replace ``AskUserQuestion`` with plain-text alternative note.
    """
    adapted = _CC_ONLY_RE.sub("", content)

    adapted = _CODEX_BLOCK_RE.sub(lambda m: m.group(1), adapted)

    def _replace_skill_call(m: re.Match[str]) -> str:
        skill = m.group(1)
        args = m.group(2) or ""
        if args:
            return f"the `${skill}` skill instructions with arguments: `{args}`"
        return f"the `${skill}` skill instructions"

    adapted = _SKILL_CALL_RE.sub(_replace_skill_call, adapted)

    def _replace_ask_user_question_block(m: re.Match[str]) -> str:
        body = m.group("body").rstrip()
        return f"{m.group('indent')}Present numbered options in plain text using this prompt and option list:\n{body}"

    adapted = _ASK_USER_QUESTION_BLOCK_RE.sub(_replace_ask_user_question_block, adapted)

    adapted = _SKILL_INVOCATION_RE.sub(lambda m: "$" + m.group(1), adapted)
    adapted = adapted.replace(
        "AskUserQuestion(multiSelect: true)",
        "plain-text numbered options with multi-select",
    )
    for old, new in (
        ("`AskUserQuestion` tool", "`plain-text numbered options` format"),
        ("AskUserQuestion tool", "plain-text numbered options format"),
        ("`AskUserQuestion` calls", "`plain-text numbered options` prompts"),
        ("AskUserQuestion calls", "plain-text numbered options prompts"),
        ("`AskUserQuestion` call", "`plain-text numbered options` prompt"),
        ("AskUserQuestion call", "plain-text numbered options prompt"),
    ):
        adapted = adapted.replace(old, new)
    adapted = adapted.replace(
        "AskUserQuestion",
        "plain-text numbered options",
    )
    return adapted


def _is_pilot_managed_entry(entry: dict[str, Any]) -> bool:
    """Check if a hook entry is Pilot Shell-managed (references ~/.pilot/ paths)."""
    for hook in entry.get("hooks", []):
        cmd = hook.get("command", "")
        if "/.pilot/" in cmd:
            return True
    return False


class _TomlStructureError(Exception):
    """Raised when generated TOML content has structural problems."""


_TOML_SECTION_RE = re.compile(r"\[[\w._-]+\]")
_TOML_QUOTED_RE = re.compile(r'"[^"]*"')


def _validate_toml_structure(content: str) -> None:
    """Validate TOML content won't cause Codex parse errors.

    Checks every line for a [section] header appearing mid-line — the
    corruption pattern that concatenates sections when newlines are lost.
    Quoted strings are blanked before matching so values like
    "semble[mcp]" don't trigger false positives.
    Raises _TomlStructureError with the offending line number and content.
    """
    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        unquoted = _TOML_QUOTED_RE.sub("", stripped)
        match = _TOML_SECTION_RE.search(unquoted)
        if match and match.start() > 0:
            raise _TomlStructureError(f"line {lineno}: section header not at start of line: {stripped!r}")


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))
