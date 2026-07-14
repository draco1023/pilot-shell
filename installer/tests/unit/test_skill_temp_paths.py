"""Workflow skills must route temp artifacts through the session-isolated
``$HOME/.pilot/sessions/<id>/`` directory, never bare ``/tmp``.

Claude Code injects a per-session scratchpad mandate ("use the session
scratchpad instead of ``/tmp``") into every session, so a skill that hardcodes
bare ``/tmp`` forces the agent to reconcile two live, authoritative instructions
on every run - wasted reasoning tokens, and a real failure tail when the agent
relocates the file at write time but reconstructs the literal ``/tmp`` path at a
later read/cleanup site. Bare ``/tmp`` is also machine-global: the
``${PILOT_SESSION_ID:-default}`` fallback collapses to a shared filename, so two
concurrent sessions (e.g. parallel worktrees) silently clobber each other's
in-flight artifacts.

The fix routes every temp artifact into ``$HOME/.pilot/sessions/<id>/`` — the
codebase's own session-isolated location, already used by these skills for
findings/flags, and agent-neutral so it works under both Claude Code and Codex
(the ``CODEX-START`` blocks have no Claude scratchpad to fall back to; see
issue #167.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[3] / "pilot" / "skills"

# The workflow skills that drive the /fix and /spec temp-artifact flows.
_WORKFLOW_SKILLS = ("fix", "spec-plan", "spec-verify")

# A bare, machine-global /tmp path used as a temp-artifact location.
_BARE_TMP = re.compile(r"/tmp/")

# An incomplete session-id chain: it collapses to the shared "default" dir when
# PILOT_SESSION_ID (IDE/desktop launches) or CLAUDE_CODE_SESSION_ID (Codex) is
# unset, bleeding per-session state (e.g. the codex-once flag) across unrelated
# sessions. The canonical chain must fall through to CODEX_THREAD_ID before
# default, matching launcher/session.py:_SESSION_ID_ENV_CHAIN and
# pilot/hooks/_lib/util.py:resolve_session_id (issue #167 completion).
_INCOMPLETE_SESSION_CHAIN = re.compile(r"\$\{(?:PILOT_SESSION_ID|CLAUDE_CODE_SESSION_ID):-default\}")


def _bare_tmp_offenders() -> list[str]:
    offenders: list[str] = []
    for skill in _WORKFLOW_SKILLS:
        for md in sorted((SKILLS_DIR / skill).rglob("*.md")):
            for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                if _BARE_TMP.search(line):
                    offenders.append(f"{md.relative_to(SKILLS_DIR)}:{lineno}: {line.strip()}")
    return offenders


def test_workflow_skills_do_not_hardcode_bare_tmp() -> None:
    offenders = _bare_tmp_offenders()
    assert not offenders, (
        "Workflow skills must write temp artifacts under "
        "$HOME/.pilot/sessions/${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}/ "
        "(session-isolated, agent-neutral), never bare /tmp - which contradicts "
        "Claude Code's session-scratchpad mandate and collides across concurrent "
        "sessions (issue #167). Offenders:\n" + "\n".join(offenders)
    )


def _incomplete_session_chain_offenders() -> list[str]:
    offenders: list[str] = []
    for md in sorted(SKILLS_DIR.rglob("*.md")):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if _INCOMPLETE_SESSION_CHAIN.search(line):
                offenders.append(f"{md.relative_to(SKILLS_DIR)}:{lineno}: {line.strip()}")
    return offenders


def test_skill_bash_resolves_full_session_chain() -> None:
    offenders = _incomplete_session_chain_offenders()
    assert not offenders, (
        "Skill bash must resolve the session id via the full agent-native chain "
        "${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}} "
        "(matching launcher/session.py and pilot/hooks/_lib/util.py), never a "
        "shorter chain that collapses to the shared 'default' dir when "
        "PILOT_SESSION_ID (IDE/desktop) or CLAUDE_CODE_SESSION_ID (Codex) is unset "
        "- that bleeds per-session state (e.g. the codex-once flag) across "
        "unrelated sessions (issue #167). Offenders:\n" + "\n".join(offenders)
    )
