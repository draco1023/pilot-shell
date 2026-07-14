#!/usr/bin/env python3
"""Track EnterPlanMode/ExitPlanMode state via a session-scoped sentinel file.

Registered as:
  PostToolUse(EnterPlanMode) -> writes the sentinel
  PostToolUse(ExitPlanMode)  -> deletes the sentinel
  PreToolUse(Edit|Write|MultiEdit) -> injects a warning if the sentinel is active
                                      and the target file is not a plan doc;
                                      for plan-doc writes, verifies the observed
                                      planning-leg model (see below)

The sentinel lives at:
  ~/.pilot/sessions/<session_id>/plan-mode-active

Purpose: ensure spec-implement never runs on Opus because ExitPlanMode was
accidentally skipped. The warning gives the model one last chance to call
ExitPlanMode before touching implementation files.

Planning-leg model check: with Model Switching ON, plan mode under opusplan
must run on Opus - but Claude Code can silently serve the Sonnet leg instead
(Opus usage-limit fallback on Max plans, or the session was never on the
opusplan model). EnterPlanMode itself cannot observe this (the statusline has
not re-rendered in the new mode yet), so the check runs at the first plan-doc
write after EnterPlanMode: by then the statusline cache carries a post-lever
render (cache mtime > sentinel mtime) and its model_id is authoritative. On a
mismatch a once-per-planning-leg warning is injected so the workflow reports
the real model instead of narrating an unverified "switched to Opus".
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import (
    _sessions_base,
    invoke_model_pin,
    pre_tool_use_context,
    read_hook_stdin,
    resolve_session_id,
)
from spec_mode_guard import _is_fable, _is_opus

try:
    from _lib.util import PLAN_MODE_SENTINEL, PRE_PLAN_MODE_RECORD, spec_plan_awaiting_approval
except ImportError:  # version-skewed _lib predating these names: legacy behavior
    PLAN_MODE_SENTINEL = "plan-mode-active"
    PRE_PLAN_MODE_RECORD = "pre-plan-permission-mode"

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

# Written once per planning leg when the model check below fires; reset by the
# next EnterPlanMode so a new leg (uneven switching) gets a fresh warning.
PLAN_MODEL_WARNED_MARKER = "plan-model-warned"

_MODEL_MISMATCH_WARNING = (
    "[Pilot] PLANNING-LEG MODEL CHECK: Model Switching is ON and plan mode is "
    "active, but the observed session model is '{model_id}' - planning is NOT "
    "running on Opus or Fable (the configured plan models). Likely causes: (1) "
    "Opus usage limit fallback on your Claude plan - under opusplan, Claude Code "
    "silently serves Sonnet while the Opus pool is exhausted and switches back "
    "when it frees up (this looks like 'uneven' mid-planning switching; check "
    "/usage); (2) the session is not on the opusplan model - run /model opusplan. "
    "Tell the user in one short paragraph which model planning is actually "
    "running on and why, then continue planning on the current model. Do NOT "
    "re-call EnterPlanMode and do NOT claim planning runs on Opus."
)


def sentinel_path() -> Path:
    session_dir = _sessions_base() / resolve_session_id()
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / PLAN_MODE_SENTINEL


def _planning_leg_model_context() -> str | None:
    """Return the mismatch warning when planning is observably not on Opus.

    Fires at most once per planning leg, and only on evidence: the statusline
    cache must carry a render newer than the EnterPlanMode sentinel (an older
    render still shows the pre-lever leg and proves nothing). Opus- and
    Fable-family models are the expected legs; anything else (Sonnet, Haiku)
    means the opusplan plan-mode switch did not take effect.
    """
    if os.environ.get("PILOT_MODEL_SWITCH_ENABLED", "true").strip().lower() == "false":
        return None

    sentinel = sentinel_path()
    session_dir = sentinel.parent
    marker = session_dir / PLAN_MODEL_WARNED_MARKER
    if marker.exists():
        return None

    cache = session_dir / "context-pct.json"
    try:
        sentinel_mtime = sentinel.stat().st_mtime
        cache_mtime = cache.stat().st_mtime
        data = json.loads(cache.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if cache_mtime <= sentinel_mtime:
        return None

    model_id = data.get("model_id") if isinstance(data, dict) else None
    if not isinstance(model_id, str) or not model_id:
        return None
    if _is_opus(model_id) or _is_fable(model_id):
        return None

    marker.write_text("")
    return _MODEL_MISMATCH_WARNING.format(model_id=model_id)


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
                # PreToolUse already opened the window; a failed EnterPlanMode
                # means plan mode never engaged -- unwind WITHOUT plan-exit's
                # exec-window logic.
                invoke_model_pin("plan-abort", detached=False)
                return 0
            sentinel = sentinel_path()
            sentinel.write_text("")
            # New planning leg: allow the model check to warn again.
            (sentinel.parent / PLAN_MODEL_WARNED_MARKER).unlink(missing_ok=True)
            # Idempotent re-assert of the window the PreToolUse hook opened
            # (covers hooks-config skews where only PostToolUse fired).
            invoke_model_pin("plan-enter", detached=False)
        elif tool_name == "ExitPlanMode":
            response = data.get("tool_response", {})
            if isinstance(response, dict) and response.get("is_error"):
                return 0
            sentinel_path().unlink(missing_ok=True)
            # Close the plan window (and open the execution window when config +
            # a registered plan call for it -- the binary decides). Synchronous.
            invoke_model_pin("plan-exit", detached=False)
    else:
        # PreToolUse(EnterPlanMode): the mode has not flipped to "plan" yet,
        # so permission_mode is the pre-plan mode. Record it as the bypass
        # evidence auto_approve_plan requires to arm the post-exit restore
        # (a shift-tab plan entry records nothing - it never calls the tool).
        if tool_name == "EnterPlanMode":
            record = sentinel_path().parent / PRE_PLAN_MODE_RECORD
            mode = data.get("permission_mode")
            if isinstance(mode, str) and mode:
                record.write_text(mode)
            else:
                # No field (older Claude Code): clear stale evidence so a
                # previous leg's record cannot arm a later restore.
                record.unlink(missing_ok=True)
            # Open the window-scoped plan-mode pin BEFORE the mode flips: the
            # first planning request fires immediately after EnterPlanMode
            # returns, so a PostToolUse-only open can land too late for it.
            # SYNCHRONOUS so open/close order equals program order.
            invoke_model_pin("plan-enter", detached=False)
            return 0
        # PreToolUse: warn if editing a non-plan file while plan mode is active
        if not sentinel_path().exists():
            return 0
        file_path = data.get("tool_input", {}).get("file_path", "")
        if not file_path:
            return 0
        if is_plan_file(file_path):
            # Plan-doc write mid-planning: heartbeat the plan-mode pin lease so a
            # long planning leg is never falsely swept (detached -- must not
            # block the edit; touch is order-safe, it re-checks the sentinel
            # under the lock).
            invoke_model_pin("touch", detached=True)
            # The statusline has re-rendered since EnterPlanMode, so the observed
            # planning-leg model is now verifiable.
            context = _planning_leg_model_context()
            if context:
                print(pre_tool_use_context(context))
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
