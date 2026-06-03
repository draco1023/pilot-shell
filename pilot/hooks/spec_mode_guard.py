#!/usr/bin/env python3
"""Guard for /spec invocations (UserPromptSubmit hook).

- Always blocks /spec when the user is manually in plan mode (the skill, not the
  user, enters plan mode via EnterPlanMode for the Opus planning leg).
- Warns when not in bypassPermissions mode.
- Model gate (runs in BOTH toggle states, expected model flipped):
    * Switching ON (default): the session runs `opusplan`, whose non-plan leg is
      Sonnet, so at /spec-submit time a correct user shows Sonnet. A non-Sonnet
      model (e.g. plain Opus) means they never ran `/model opusplan` -- blocked.
      A user wrongly on plain Sonnet is indistinguishable from opusplan and is
      allowed (accepted false-negative, avoids false-blocking correct users).
    * Switching OFF: the whole workflow runs on Opus and only Opus may enter plan
      mode, so a non-Opus model is blocked with a `/model opus[1m]` prompt.

Reads:
  - `permission_mode` from hook stdin (plan-mode block, bypassPermissions warn)
  - `PILOT_MODEL_SWITCH_ENABLED` from env (selects expected model; default ON)
  - `model_id` from the statusline cache at ``~/.pilot/sessions/<sid>/context-pct.json``
    -- the statusline writes this every render and Claude Code UserPromptSubmit
    stdin does NOT include the active model field.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import resolve_session_id

_CLAUDE_OPUS_PREFIX_RE = re.compile(r"^claude-opus(-|$)")
_CLAUDE_SONNET_PREFIX_RE = re.compile(r"^claude-sonnet(-|$)")


def _strip_1m(model: str) -> str:
    """Strip a single trailing ``[1m]`` alias suffix from a model id."""
    return model[:-4] if model.endswith("[1m]") else model


def _is_opus(model: str) -> bool:
    """Return True iff ``model`` resolves to an Opus alias or explicit Opus ID.

    Strips the ``[1m]`` alias suffix (explicit IDs may legitimately carry it,
    e.g. ``claude-opus-4-8[1m]``). Accepts the bare ``opus`` alias and any
    explicit ID matching ``claude-opus(-|$)`` so misspellings like
    ``claude-opusculus-1`` are rejected.
    """
    if not isinstance(model, str) or not model:
        return False
    base = _strip_1m(model)
    if base == "opus":
        return True
    return bool(_CLAUDE_OPUS_PREFIX_RE.match(base))


def _is_sonnet(model: str) -> bool:
    """Return True iff ``model`` resolves to a Sonnet alias or explicit Sonnet ID.

    Mirror of :func:`_is_opus`. Under Model Switching ON the session runs the
    ``opusplan`` model, whose non-plan leg is Sonnet -- so at ``/spec``-submit
    time (before plan mode) a correctly-configured user resolves to Sonnet.
    Accepts the bare ``sonnet`` alias and any explicit ID matching
    ``claude-sonnet(-|$)``; rejects lookalikes like ``claude-sonnetics-1``.
    """
    if not isinstance(model, str) or not model:
        return False
    base = _strip_1m(model)
    if base == "sonnet":
        return True
    return bool(_CLAUDE_SONNET_PREFIX_RE.match(base))


def _read_active_model_from_cache() -> str | None:
    """Read ``model_id`` from the statusline cache file, or None if unavailable.

    Falls through cleanly when no statusline render has run yet (e.g. the very
    first prompt after a session starts) — the caller treats None as "skip the
    Opus check" rather than as a block trigger.
    """
    cache_file = Path.home() / ".pilot" / "sessions" / resolve_session_id() / "context-pct.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    model_id = data.get("model_id") if isinstance(data, dict) else None
    return model_id if isinstance(model_id, str) and model_id else None


def _is_spec_invocation(prompt: str) -> bool:
    """Return True iff ``prompt`` is a /spec slash command (not /spec-implement etc.).

    `prompt.startswith("/spec")` overmatches sibling commands such as
    `/spec-implement`, `/spec-verify`, `/spec-plan`, `/spec-bugfix-plan`,
    `/spec-bugfix-verify`, which run on Sonnet under automated model switching
    (the opusplan default leg). Restrict to bare `/spec` or `/spec ` (with
    whitespace before any args).
    """
    if not prompt.startswith("/spec"):
        return False
    after = prompt[len("/spec") :]
    return after == "" or after[:1].isspace()


def _is_resume_existing_plan(prompt: str) -> bool:
    """Return True when /spec is resuming an existing plan, not starting a new one.

    The dispatcher routes `/spec <path/to/plan.md>` to existing-plan handling
    (status-based dispatch). Such invocations must NOT be blocked by the Opus
    gate -- the resume path runs on whichever model is active (Sonnet under
    automated model switching) for implementation/verification.

    A "resume" prompt is `/spec` followed by a token ending in `.md` (case
    insensitive). Paths containing spaces are honored when quoted, via shlex.
    A "new plan" prompt is `/spec <free-form task description>` and stays
    subject to the Opus block.
    """
    # Strip the leading "/spec" and any whitespace.
    body = prompt[len("/spec") :].strip()
    if not body:
        return False
    try:
        tokens = shlex.split(body, posix=True)
    except ValueError:
        # Unbalanced quotes — fall back to a permissive whitespace split.
        tokens = body.split(maxsplit=1)
    if not tokens:
        return False
    # First arg only — trailing flags don't change the verdict.
    return tokens[0].lower().endswith(".md")


def run_spec_mode_guard() -> int:
    """Check permission mode and active model before allowing /spec invocation."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    prompt = hook_data.get("prompt", "").strip()
    permission_mode = hook_data.get("permission_mode", "")

    if not _is_spec_invocation(prompt):
        return 0

    if permission_mode == "plan":
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": (
                        "[Pilot] /spec cannot run in Plan mode. "
                        "Press Shift+Tab to cycle to 'Bypass Permissions' mode, then try again."
                    ),
                }
            )
        )
        sys.stderr.write("\033[0;31m[Pilot] /spec blocked: Plan mode is incompatible with /spec workflow\033[0m\n")
        return 2

    # The model gate targets the *planning* leg of /spec. Resuming an existing
    # plan (`/spec <path/to/plan.md>`) dispatches to spec-implement / spec-verify,
    # which run on whichever model is active (Sonnet under automated switching).
    # Skipping the gate for resume keeps it reachable on Sonnet.
    if _is_resume_existing_plan(prompt):
        return 0

    # Model gate -- runs in BOTH toggle states, with the expected model flipped.
    # Claude Code's UserPromptSubmit stdin does not carry the active model, so it
    # is read from the statusline cache.
    #
    #   * Switching ON (default): the session runs the `opusplan` model, whose
    #     non-plan leg is Sonnet. At /spec-submit time the skill has NOT yet
    #     entered plan mode, so a correctly-configured user resolves to *Sonnet*.
    #     Anything else (e.g. plain Opus) means they never ran `/model opusplan`
    #     -- block and tell them to fix it. A user wrongly on plain Sonnet is
    #     indistinguishable from opusplan and is allowed; that false-negative is
    #     accepted to avoid false-blocking every correct user.
    #   * Switching OFF: the whole workflow runs on Opus, and only Opus may enter
    #     plan mode (planning on Sonnet is pointless) -- require Opus, block else.
    #
    # Unset env defaults to ON.
    model_switch_on = os.environ.get("PILOT_MODEL_SWITCH_ENABLED", "true").strip().lower() != "false"
    active_model = _read_active_model_from_cache()

    if model_switch_on:
        model_is_correct = _is_sonnet
        cache_warn = (
            "\033[0;33m[Pilot] Warning: could not verify active model for /spec "
            "(statusline cache unavailable). Proceeding without the model check -- "
            "if you are not on the opusplan model, run '/model opusplan' before planning.\033[0m\n"
        )
        block_reason = (
            "[Pilot] /spec with Model Switching ON requires the 'opusplan' model "
            "(planning runs on Opus, the default leg on Sonnet). Before planning it shows "
            "as Sonnet -- you are on a different model. Run '/model opusplan' and try again. "
            "(Resuming an existing plan with '/spec <path/to/plan.md>' is allowed on any model.)"
        )
        block_stderr = (
            "\033[0;31m[Pilot] /spec blocked: Model Switching is ON, so /spec must run on the "
            "opusplan model (shows as Sonnet before planning). Current model: "
            + (active_model or "unknown")
            + ". Run '/model opusplan'.\033[0m\n"
        )
    else:
        model_is_correct = _is_opus
        cache_warn = (
            "\033[0;33m[Pilot] Warning: could not verify active model for /spec "
            "(statusline cache unavailable). Proceeding without the Opus check -- "
            "if you are on Sonnet, run '/model opus[1m]' before planning.\033[0m\n"
        )
        block_reason = (
            "[Pilot] /spec requires Opus for planning (Model Switching is OFF). "
            "Run '/model opus[1m]' (or '/model opus') and try again. "
            "(Resuming an existing plan with '/spec <path/to/plan.md>' is allowed on any model.)"
        )
        block_stderr = (
            "\033[0;31m[Pilot] /spec blocked: planning requires Opus. "
            "Current model: " + (active_model or "unknown") + ". Run '/model opus[1m]' (or '/model opus').\033[0m\n"
        )

    if active_model is None:
        # Cache may not have been written yet (very first prompt of a fresh
        # session, or a transient render that omitted model_id). Fall open but
        # warn so the user knows the model check did not run.
        sys.stderr.write(cache_warn)
    elif not model_is_correct(active_model):
        print(json.dumps({"decision": "block", "reason": block_reason}))
        sys.stderr.write(block_stderr)
        return 2

    if permission_mode and permission_mode != "bypassPermissions":
        sys.stderr.write(
            f"\033[0;33m[Pilot] Warning: /spec works best in 'Bypass Permissions' mode "
            f"(current: {permission_mode}). Press Shift+Tab to switch.\033[0m\n"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": (
                            f"NOTE: Current permission mode is '{permission_mode}'. "
                            "For uninterrupted /spec execution, 'bypassPermissions' mode is recommended "
                            "(Shift+Tab to cycle). In the current mode the workflow may pause for "
                            "permission prompts. Briefly warn the user, then proceed with the workflow."
                        ),
                    }
                }
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(run_spec_mode_guard())
