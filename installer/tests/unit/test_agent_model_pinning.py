"""Shipped Claude subagents must pin a full base model id, not a 1m-inheriting alias.

The ``[1m]`` context-window suffix on ``ANTHROPIC_DEFAULT_OPUS_MODEL`` /
``ANTHROPIC_DEFAULT_SONNET_MODEL`` applies to *all* usage of the ``opus`` and
``sonnet`` aliases, including subagents whose frontmatter says ``model: sonnet``.
A subagent spawned from a ``[1m]`` parent then inherits the 1M context window and
dies with "Extra usage is required for 1M context" (claude-code#44117, #42082).
Pinning a full base model id (e.g. ``claude-sonnet-4-6``) bypasses the alias and
keeps subagents on the standard 200K window.
"""

from __future__ import annotations

import re
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[3] / "pilot" / "agents"
_BARE_ALIASES = frozenset({"sonnet", "opus", "haiku", "inherit"})


def _frontmatter_model_lines() -> list[tuple[str, str]]:
    """Return (filename, model) for every agent file with a frontmatter model line."""
    found: list[tuple[str, str]] = []
    for md in sorted(AGENTS_DIR.glob("*.md")):
        match = re.search(r"^model:\s*(.+)$", md.read_text(encoding="utf-8"), flags=re.MULTILINE)
        if match:
            found.append((md.name, match.group(1).strip()))
    return found


def test_shipped_claude_agents_pin_base_model_ids() -> None:
    offenders = [
        f"{name}: model={model!r}"
        for name, model in _frontmatter_model_lines()
        if model in _BARE_ALIASES or "[1m]" in model or not model.startswith("claude-")
    ]
    assert not offenders, (
        "Shipped Claude agents must pin a full base model id (e.g. claude-sonnet-4-6) so they "
        "do not inherit the parent's 1M context window and fail with a billing error. Offenders: "
        + "; ".join(offenders)
    )
