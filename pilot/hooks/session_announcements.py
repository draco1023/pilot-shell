#!/usr/bin/env python3
"""SessionStart hook (Claude Code only): deliver one-time announcements.

Each announcement is injected into the session via `additionalContext` exactly
once. The hook touches the ack sentinel itself before injecting, so the message
shows once regardless of session outcome -- no AskUserQuestion round-trip needed.

Extensible: add entries to ANNOUNCEMENTS. Stdlib only (package boundary);
never raises.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Ordered list of one-time announcements. Add new entries here; each shows once
# (per machine) until acknowledged. Keep messages ASCII (no-emojis-in-source).
ANNOUNCEMENTS: list[dict[str, str]] = [
    {
        "id": "opusplan-sonnet-default",
        "message": (
            "Pilot Shell -- Quick tip: opusplan shows Sonnet outside /spec.\n\n"
            "When your session is on the opusplan model, Claude Code resolves to SONNET\n"
            "for all regular (quick-mode) prompts -- only plan mode (inside /spec planning)\n"
            "runs on Opus.\n\n"
            "This is by design: opusplan is optimised for /spec and /fix planning legs.\n\n"
            "  - Quick-mode on Opus?  ->  /model opus[1m]   (then back to opusplan before /spec)\n"
            "  - /spec + /fix?        ->  stay on opusplan  (automated switching handles the rest)\n\n"
            "Docs: https://pilot-shell.com/docs/features/model-routing"
        ),
    },
    {
        "id": "automated-model-switching",
        "message": (
            "Pilot Shell -- Automated Model Switching is now ON by default.\n\n"
            "What changed:\n"
            "  - /spec now runs PLANNING on Opus and IMPLEMENTATION + VERIFICATION on Sonnet automatically.\n"
            "  - No more manual '/model ...' step between planning and implementation.\n"
            "  - Pilot sets the Opus Plan model in your settings.json, so new Claude sessions start on it automatically.\n\n"
            "What you need to do:\n"
            "  - Run `/model opusplan` in this session (future sessions set this automatically).\n"
            "  - The Opus Plan model runs the Plan Model while planning (plan mode) and the Execution\n"
            "    Model for everything else -- both configurable in Console -> Settings -> Model\n"
            "    Switching, and both at the 1M context tier.\n"
            "  - /spec now checks your model first: if you are not on opusplan it stops and reminds you\n"
            "    to run `/model opusplan` before planning (when Model Switching is OFF it requires Opus).\n\n"
            "To disable (run entire /spec workflow on Opus instead):\n"
            "  - Open the Pilot Console -> Settings -> Model Switching -> turn off 'Model Switching'.\n"
            "  - Your settings.json will be patched to `opus[1m]` (Opus at 1M; on Max, 1M needs usage credits).\n\n"
            "Docs: https://pilot-shell.com/docs/features/model-routing"
        ),
    },
    {
        "id": "fable-5-support",
        "message": (
            "Pilot Shell -- Claude Fable 5 is fully supported.\n\n"
            "What this means:\n"
            "  - With Model Switching OFF, run `/model fable` (or `fable[1m]`) and Pilot preserves\n"
            "    your choice: settings syncs and startups no longer overwrite a saved Fable model.\n"
            "  - A single-model Fable session runs the WHOLE /spec workflow on Fable -- plan /\n"
            "    implement / verify stay on one frontier model and the skills skip plan-mode\n"
            "    model toggling automatically.\n"
            "  - Statusline and Console Usage show Fable 5 / Mythos 5 names and costs.\n\n"
            "Note: Fable's 1M context stays available -- Pilot never leaves\n"
            "CLAUDE_CODE_DISABLE_1M_CONTEXT=true while a Fable model is selected.\n\n"
            "Docs: https://pilot-shell.com/docs/features/model-routing"
        ),
    },
    {
        "id": "model-switching-1m-planning",
        "message": (
            "Pilot Shell -- Model Switching now runs BOTH legs at 1M context.\n\n"
            "What changed:\n"
            "  - The opusplan planning leg (Opus 4.8) now runs at 1M instead of 200K: Pilot pins\n"
            "    ANTHROPIC_DEFAULT_OPUS_MODEL to the opus [1m] ID. The Sonnet 5 execution leg\n"
            "    was already natively 1M.\n"
            "  - Console -> Settings -> Model Switching shows the Plan and Execution models\n"
            "    (Opus 4.8 planning, Sonnet 5 execution by default).\n\n"
            "Behavior change:\n"
            "  - While Model Switching is ON, it now also overrides a manually saved /model choice\n"
            "    (including a saved Fable model) on the next settings sync or restart. Turn Model\n"
            "    Switching OFF to control the model entirely via /model.\n\n"
            "On Max, 1M context draws usage credits (enable via /usage-credits if prompted).\n\n"
            "Docs: https://pilot-shell.com/docs/features/model-routing"
        ),
    },
    {
        "id": "configurable-plan-exec-models",
        "message": (
            "Pilot Shell -- Model Switching now has configurable Plan and Execution models.\n\n"
            "What is new (Console -> Settings -> Model Switching, two dropdowns):\n"
            "  - Plan Model:      Opus 4.8 (1M)  or  Fable 5 (1M)\n"
            "  - Execution Model: Sonnet 5 (1M)  or  Opus 4.8 (1M)  (requires a Fable plan model)\n\n"
            "Claude Code has no native `fableplan`, so Pilot applies these as WINDOW-SCOPED pins:\n"
            "  - A Fable plan model pins the opus slot to Fable ONLY between EnterPlanMode and\n"
            "    ExitPlanMode. Outside a planning window, /model opus and fast mode mean real Opus\n"
            "    again. Need real Opus in another session meanwhile? /model claude-opus-4-8[1m]\n"
            "  - An Opus execution model pins the sonnet slot to Opus ONLY while a /spec runs\n"
            "    (implementation start until the plan is verified); it reverts to Sonnet 5 when\n"
            "    the spec is verified. Want Sonnet in another session meanwhile? /model claude-sonnet-5\n\n"
            "Parallel sessions are safe (refcounted leases; a crashed session's pin reclaims\n"
            "automatically). Defaults are unchanged (Opus planning / Sonnet execution) -- opt in\n"
            "only if you want Fable-quality planning or Opus-quality implementation.\n\n"
            "Docs: https://pilot-shell.com/docs/features/model-routing"
        ),
    },
]


def _pilot_dir() -> Path:
    return Path.home() / ".pilot"


def _ack_path(announce_id: str, base: Path) -> Path:
    """Ack sentinel path: ``<base>/.announce-<id>-ack``."""
    return base / f".announce-{announce_id}-ack"


def pending(base: Path, announcements: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return announcements whose ack sentinel does not yet exist."""
    result: list[dict[str, str]] = []
    for a in announcements:
        try:
            if not _ack_path(a["id"], base).exists():
                result.append(a)
        except OSError:
            result.append(a)
    return result


def render_context(pending_list: list[dict[str, str]]) -> str:
    """Build the SessionStart additionalContext for the pending announcements.

    Empty string when nothing is pending.
    Ack sentinels are touched by the hook before this context is injected.
    """
    if not pending_list:
        return ""
    blocks: list[str] = [
        "[Pilot one-time announcement] Display the following announcement(s) to "
        "the user as clearly formatted text output. "
        "Do NOT use AskUserQuestion. "
        "Just show the announcement text, then continue with the user's request."
    ]
    for a in pending_list:
        blocks.append(f"\n--- Announcement ---\n{a['message']}")
    return "\n".join(blocks)


def main() -> None:
    # Claude Code only -- Codex has no SessionStart announcement channel here.
    if not os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return
    try:
        base = _pilot_dir()
        pending_list = pending(base, ANNOUNCEMENTS)
        ctx = render_context(pending_list)
        if not ctx:
            return
        # Touch ack sentinels now so each announcement shows exactly once.
        for a in pending_list:
            try:
                _ack_path(a["id"], base).touch()
            except OSError:
                pass
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": ctx,
                    }
                }
            )
        )
    except Exception:
        # SessionStart hook: never raise / never block the session.
        return


if __name__ == "__main__":
    main()
