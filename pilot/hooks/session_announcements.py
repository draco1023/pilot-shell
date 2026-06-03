#!/usr/bin/env python3
"""SessionStart hook (Claude Code only): deliver one-time announcements.

Each announcement is re-injected into the session via `additionalContext`
every startup until the user acknowledges it (an ack sentinel file under
~/.pilot/). The injected context instructs the agent to present the message,
ask the user to acknowledge (AskUserQuestion), and -- only then -- `touch` the
ack sentinel so it never shows again. This is the post-launcher replacement for
the old full-screen launcher notice: Pilot is admin-only now, so users run
`claude` directly and never see launcher banners.

Extensible: add entries to ANNOUNCEMENTS. Stdlib only (package boundary);
never raises.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ordered list of one-time announcements. Add new entries here; each shows once
# (per machine) until acknowledged. Keep messages ASCII (no-emojis-in-source).
ANNOUNCEMENTS: list[dict[str, str]] = [
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


def render_context(pending_list: list[dict[str, str]], base: Path) -> str:
    """Build the SessionStart additionalContext for the pending announcements.

    Empty string when nothing is pending.
    """
    if not pending_list:
        return ""
    blocks: list[str] = [
        "[Pilot one-time announcement] Present the following announcement(s) to "
        "the user verbatim in a clearly formatted box. Then use AskUserQuestion "
        "with EXACTLY TWO options so the user can acknowledge or opt out. "
        "AskUserQuestion requires at least 2 options -- never call it with only 1. "
        "ONLY after the user selects an option, run the Bash `touch` command shown "
        "for that announcement so it does not appear again. "
        "Do this before continuing with the user's request."
    ]
    for a in pending_list:
        ack = _ack_path(a["id"], base)
        blocks.append(
            f"\n--- Announcement (id: {a['id']}) ---\n{a['message']}\n"
            f"Ask the user using AskUserQuestion with these two options:\n"
            f'  Option 1 label: "Got it, use automated switching"\n'
            f"  Option 1 description: I'll run `/model opusplan` and enjoy automatic Opus planning + Sonnet implementation.\n"
            f'  Option 2 label: "Disable - I want Opus for everything"\n'
            f"  Option 2 description: Turn off Model Switching in Console -> Settings -> Automation -- the full workflow will run on Opus.\n"
            f'After the user picks either option, run: touch "{ack}"'
        )
    return "\n".join(blocks)


def main() -> None:
    # Claude Code only -- Codex has no SessionStart announcement channel here.
    if not os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return
    try:
        base = _pilot_dir()
        ctx = render_context(pending(base, ANNOUNCEMENTS), base)
        if not ctx:
            return
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
