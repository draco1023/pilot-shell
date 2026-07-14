#!/usr/bin/env python3
"""Guard for /spec invocations (UserPromptSubmit hook).

- Always blocks /spec when the user is manually in plan mode (the skill, not the
  user, enters plan mode via EnterPlanMode for the Opus planning leg).
- Warns when not in bypassPermissions mode.
- Model gate (runs in BOTH toggle states, expected model flipped):
    * Switching ON (default): the session runs `opusplan`, whose non-plan leg is
      Sonnet, so at /spec-submit time a correct user shows Sonnet. A non-Sonnet
      model (e.g. plain Opus) means they never ran `/model opusplan` -- blocked,
      UNLESS settings.json shows `opusplan` is the selected model (the async
      statusline cache may lag the `/model opusplan` the user just ran).
      A user wrongly on plain Sonnet is indistinguishable from opusplan and is
      allowed (accepted false-negative, avoids false-blocking correct users).
    * Switching OFF: the whole workflow runs on Opus and only Opus may enter plan
      mode, so a non-Opus model is blocked with a `/model opus[1m]` prompt. An
      explicit `opusplan` selection is blocked with targeted guidance instead:
      turn Model Switching ON (Console) or run `/model opus[1m]`.
    * Fable-family models (e.g. `claude-fable-5`, `claude-mythos-5`, `best`)
      pass the gate in BOTH states: they run the whole workflow single-model,
      so neither prompt applies.

Reads:
  - `permission_mode` from hook stdin (plan-mode block, bypassPermissions warn)
  - `PILOT_MODEL_SWITCH_ENABLED` from env (selects expected model; default ON)
  - `model_id` from the statusline cache at ``~/.pilot/sessions/<sid>/context-pct.json``
    -- the statusline writes this every render and Claude Code UserPromptSubmit
    stdin does NOT include the active model field.
  - `model` from ``$CLAUDE_CONFIG_DIR/settings.json`` (default ``~/.claude``)
    -- the *selected* model alias, persisted synchronously by `/model`. The
    statusline cache only ever holds the *resolved* model id (opusplan resolves
    to its Sonnet leg outside plan mode), so this is the only place an explicit
    `opusplan` selection is observable. Consulted as a tie-breaker when the
    cache would block: ON + opusplan selected passes (the cache may lag the
    `/model opusplan` the user just ran); OFF + opusplan selected blocks with
    guidance naming the Model Switching toggle instead of the generic
    requires-Opus message.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import invoke_model_pin, plan_mode_sentinel_path, resolve_session_id

_CLAUDE_OPUS_PREFIX_RE = re.compile(r"^claude-opus(-|$)")
_CLAUDE_SONNET_PREFIX_RE = re.compile(r"^claude-sonnet(-|$)")
_CLAUDE_FABLE_MYTHOS_PREFIX_RE = re.compile(r"^claude-(fable|mythos)(-|$)")


_TRAILING_1M_RE = re.compile(r"(?:\[1[mM]\])+$")


def _strip_1m(model: str) -> str:
    """Strip trailing ``[1m]``/``[1M]`` alias suffixes (including doubled ones).

    Real-world cache values can carry a doubled suffix (env var + model name
    concatenation) and statusline renders may uppercase it. Anchored at the end
    so mid-string occurrences are never touched.
    """
    return _TRAILING_1M_RE.sub("", model)


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


def _is_fable(model: str) -> bool:
    """Return True iff ``model`` is a Fable-family alias or explicit ID.

    Mirror of :func:`_is_opus`. Fable-class models (Fable 5, Mythos 5) run the
    whole /spec workflow single-model -- there is no fableplan split -- so they
    pass the model gate in BOTH toggle states. Accepts the bare ``fable``,
    ``mythos``, and ``best`` aliases (``best`` resolves to Fable where
    available) and any explicit ID matching ``claude-(fable|mythos)(-|$)``
    (e.g. ``claude-fable-5``); rejects lookalikes like ``claude-fabletastic-1``.

    Accepted set is kept byte-identical to
    ``launcher/model_config.py::_is_fable_family`` (vendored mirror -- the
    package boundary forbids imports between hooks and launcher).
    """
    if not isinstance(model, str) or not model:
        return False
    base = _strip_1m(model)
    if base in ("fable", "mythos", "best"):
        return True
    return bool(_CLAUDE_FABLE_MYTHOS_PREFIX_RE.match(base))


def _is_opusplan(model: str) -> bool:
    """Return True iff ``model`` is the opusplan alias.

    Mirror of :func:`_is_opus`. Matches the bare ``opusplan`` alias after
    stripping the ``[1m]`` suffix, so a legacy ``opusplan[1m]`` value an older
    Pilot wrote to settings.json still counts.
    """
    if not isinstance(model, str) or not model:
        return False
    return _strip_1m(model) == "opusplan"


def is_single_model_fable_session() -> bool:
    """True iff the session runs single-model on a Fable-class model.

    The settings.json *selection* is authoritative: `/model` persists it
    synchronously, and an ``opusplan`` selection means model switching manages
    the legs -- the skills must still toggle plan mode even if a stale
    statusline cache shows a Fable id. Only without a usable selection does
    the async cache decide. Consumed by the /spec skills' ON_FABLE check.
    """
    selected = _read_selected_model_from_settings()
    if selected is not None:
        if _is_opusplan(selected):
            return False
        if _is_fable(selected):
            return True
    return _is_fable(_read_active_model_from_cache() or "")


def _read_selected_model_from_settings() -> str | None:
    """Read the *selected* model alias from Claude Code's settings.json, or None.

    `/model <choice>` persists the selection here synchronously ("saved as your
    default for new sessions"). Unlike the statusline cache -- async, and only
    ever holding the *resolved* model id -- this is where the ``opusplan``
    alias itself is observable. The value is global across sessions while the
    cache is per-session, so it is only consulted as a tie-breaker when the
    cache would block, never to override a cache that already passes the gate.
    """
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    try:
        data = json.loads((claude_dir / "settings.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    model = data.get("model") if isinstance(data, dict) else None
    return model if isinstance(model, str) and model else None


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


def _heartbeat_plan_pin() -> None:
    """Detached model-pin touch when this session has an open plan-mode window.

    Keeps a long planning leg's lease fresh (and self-heals a falsely swept
    lease -- touch re-checks the sentinel under the pin lock). Best-effort; the
    sentinel check short-circuits so ordinary prompts spawn no subprocess.
    """
    try:
        if plan_mode_sentinel_path().exists():
            invoke_model_pin("touch", detached=True)
    except Exception:
        pass


def run_spec_mode_guard() -> int:
    """Check permission mode and active model before allowing /spec invocation."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    prompt = hook_data.get("prompt", "").strip()
    permission_mode = hook_data.get("permission_mode", "")

    # Heartbeat the window-scoped model pin lease on every prompt while a
    # plan-mode window is open, so a long planning leg is never falsely swept.
    # Cheap sentinel .exists() gate first: non-planning prompts spawn nothing.
    _heartbeat_plan_pin()

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
    #   * Fable passes in BOTH states: a Fable session runs the whole workflow on
    #     one frontier model (no fableplan split), so prompting '/model opusplan'
    #     or '/model opus[1m]' would force a downgrade.
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

    model_ok = active_model is not None and (model_is_correct(active_model) or _is_fable(active_model))

    # The cache can never show 'opusplan' -- only its resolved leg -- so when it
    # would block, consult the alias the user actually SELECTED (settings.json,
    # written synchronously by /model) before issuing model guidance. Read lazily:
    # a cache that already passes the gate never needs (or touches) settings.
    opusplan_selected = False
    if not model_ok:
        selected_model = _read_selected_model_from_settings()
        opusplan_selected = selected_model is not None and _is_opusplan(selected_model)

    if not model_ok and opusplan_selected:
        if not model_switch_on:
            # OFF + an explicit opusplan selection is a real misconfiguration
            # (the skills skip plan mode, so planning would run opusplan's
            # Sonnet leg) -- block regardless of cache state, but name the
            # actual conflict and BOTH ways out instead of the generic
            # requires-Opus message that contradicts the user's /model choice.
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": (
                            "[Pilot] You are on the 'opusplan' model but Model Switching is OFF, "
                            "so /spec would run planning on opusplan's execution leg instead of Opus. "
                            "Either turn Model Switching ON (Pilot Console -> Settings -> "
                            "Model Switching) to use opusplan, or run '/model opus[1m]' (or "
                            "'/model opus') to run the whole workflow on Opus, then try again. "
                            "(Resuming an existing plan with '/spec <path/to/plan.md>' is allowed "
                            "on any model.)"
                        ),
                    }
                )
            )
            sys.stderr.write(
                "\033[0;31m[Pilot] /spec blocked: 'opusplan' needs Model Switching ON "
                "(Console -> Settings -> Model Switching), or run '/model opus[1m]' (or "
                "'/model opus') to stay single-model on Opus.\033[0m\n"
            )
            return 2
        # ON + opusplan selected: correctly configured. The cache may still
        # hold the pre-switch id right after `/model opusplan` (async render)
        # or the Opus leg from a plan-mode render -- blocking here would tell
        # the user to run the command they just ran. Allow.
    elif active_model is None:
        # Cache may not have been written yet (very first prompt of a fresh
        # session, or a transient render that omitted model_id). Fall open but
        # warn so the user knows the model check did not run.
        sys.stderr.write(cache_warn)
    elif not model_ok:
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
