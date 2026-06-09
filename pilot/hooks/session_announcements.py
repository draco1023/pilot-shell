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
            "  - The Opus Plan model runs Opus while planning (plan mode) and Sonnet for everything else.\n"
            "  - /spec now checks your model first: if you are not on opusplan it stops and reminds you\n"
            "    to run `/model opusplan` before planning (when Model Switching is OFF it requires Opus).\n\n"
            "To disable (run entire /spec workflow on Opus instead):\n"
            "  - Open the Pilot Console -> Settings -> Automation -> turn off 'Model Switching'.\n"
            "  - Your settings.json will be patched to opus[1m] instead.\n\n"
            "Docs: https://pilot-shell.com/docs/features/model-routing"
        ),
    },
    {
        "id": "fable-5-support",
        "message": (
            "Pilot Shell -- Claude Fable 5 is fully supported.\n\n"
            "What this means:\n"
            "  - Run `/model fable` (or `fable[1m]`) and Pilot preserves your choice: settings syncs\n"
            "    and startups no longer overwrite a saved Fable model with opusplan/opus.\n"
            "  - /spec runs the WHOLE workflow on Fable in both Model Switching states -- there is\n"
            "    no 'fableplan' (yet), so plan/implement/verify stay on one frontier model and the\n"
            "    skills skip plan-mode model toggling automatically.\n"
            "  - Statusline and Console Usage show Fable 5 / Mythos 5 names and costs.\n\n"
            "Note: Fable's 1M context stays available -- Pilot never leaves\n"
            "CLAUDE_CODE_DISABLE_1M_CONTEXT=true while a Fable model is selected.\n\n"
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
