#!/usr/bin/env python3
"""Track EnterPlanMode/ExitPlanMode state via a session-scoped sentinel file.

Registered as:
  PostToolUse(EnterPlanMode) -> writes the sentinel
  PostToolUse(ExitPlanMode)  -> deletes the sentinel
  PreToolUse(Edit|Write|MultiEdit) -> injects a warning if the sentinel is active
                                      and the target file is not a plan doc

The sentinel lives at:
  ~/.pilot/sessions/<session_id>/plan-mode-active

Purpose: ensure spec-implement never runs on Opus because ExitPlanMode was
accidentally skipped. The warning gives the model one last chance to call
ExitPlanMode before touching implementation files.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import (
    _sessions_base,
    pre_tool_use_context,
    read_hook_stdin,
    resolve_session_id,
)

try:
    from _lib.util import PLAN_MODE_SENTINEL, spec_plan_awaiting_approval
except ImportError:  # version-skewed _lib predating these names: legacy behavior
    PLAN_MODE_SENTINEL = "plan-mode-active"

    def spec_plan_awaiting_approval() -> bool:
        return False


_WARNING = (
    "[Pilot] PLAN MODE STILL ACTIVE - ExitPlanMode has NOT been called yet. "
    "Call ExitPlanMode NOW before editing any implementation file, or the "
    "entire implementation leg will run on Opus instead of Sonnet. "
    "If you are inside spec-implement and MODEL_SWITCH=true, call ExitPlanMode "
    "immediately as step 1.0 requires."
)

_PRE_APPROVAL_WARNING = (
    "[Pilot] SPEC PLAN NOT APPROVED - you are editing a non-plan file during "
    "the /spec planning leg. Do NOT start implementation and do NOT call "
    "ExitPlanMode (it is denied until approval): finish the plan and present "
    "it at the approval gate (AskUserQuestion - spec-plan Step 12.2 / "
    "spec-bugfix-plan Step 6.2). Implementation starts only after the user "
    "approves."
)


def sentinel_path() -> Path:
    session_dir = _sessions_base() / resolve_session_id()
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / PLAN_MODE_SENTINEL


def is_plan_file(file_path: str) -> bool:
    """Return True for plan doc files (docs/plans/*.md) - legitimate writes during planning."""
    p = Path(file_path)
    return p.suffix.lower() == ".md" and "plans" in p.parts


def main() -> int:
    data = read_hook_stdin()
    tool_name = data.get("tool_name", "")
    is_post = "tool_response" in data

    if is_post:
        # PostToolUse: update sentinel state
        if tool_name == "EnterPlanMode":
            response = data.get("tool_response", {})
            if isinstance(response, dict) and response.get("is_error"):
                return 0
            sentinel_path().write_text("")
        elif tool_name == "ExitPlanMode":
            response = data.get("tool_response", {})
            if isinstance(response, dict) and response.get("is_error"):
                return 0
            sentinel_path().unlink(missing_ok=True)
    else:
        # PreToolUse: warn if editing a non-plan file while plan mode is active
        if not sentinel_path().exists():
            return 0
        file_path = data.get("tool_input", {}).get("file_path", "")
        if not file_path or is_plan_file(file_path):
            return 0
        # Predicate last: it stats/reads session + plan state (and may shell
        # out to git), so the pure-string checks above short-circuit first.
        if spec_plan_awaiting_approval():
            # Planning leg with an unapproved plan: auto_approve_plan DENIES
            # ExitPlanMode right now, so the legacy "call ExitPlanMode NOW"
            # instruction would send the model straight into that denial.
            # Keep the edit-time tripwire, but point it at the approval gate.
            print(pre_tool_use_context(_PRE_APPROVAL_WARNING))
        else:
            print(pre_tool_use_context(_WARNING))

    return 0


if __name__ == "__main__":
    sys.exit(main())
