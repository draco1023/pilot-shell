#!/usr/bin/env python3
"""PermissionRequest hook for ExitPlanMode: approval-state-aware allow/deny.

In the /spec workflow ExitPlanMode is purely a model-switch lever (Opus -> Sonnet),
NOT the plan-approval mechanism. The real approval is a separate AskUserQuestion gate
(spec-plan/steps/12-approval.md, spec-bugfix-plan/steps/06-approval.md).

Two jobs:
1. DENY a premature ExitPlanMode. Newer Claude Code builds inject a plan-mode
   system-reminder claiming the plan must be presented for approval via
   ExitPlanMode and no other way; models sometimes follow it and call
   ExitPlanMode BEFORE the AskUserQuestion gate. While the planning leg is
   active (plan-mode-active sentinel from EnterPlanMode) and the registered
   plan is PENDING and unapproved, ExitPlanMode is denied with a message that
   re-anchors the model to the approval gate.
2. ALLOW otherwise: skip the dialog + request bypassPermissions restore. The
   decision message must NEVER say "approved": earlier wording ("Plan
   auto-approved") was parroted by agents as "Plan approved", causing them to
   skip the approval gate and start implementing.

Guard scope (honest limits): the deny only arms AFTER `pilot register-plan`
has written active_plan.json (spec-plan Step 2) and while the EnterPlanMode
sentinel exists; the window before registration, and installs where the pilot
binary is unavailable, remain guarded by skill prose only. Everything fails
open: read errors, a missing/unreadable plan file, an unparseable
active_plan.json, or a version-skewed _lib all fall back to plain allow, so
ExitPlanMode is never broken outside the guarded /spec window. The deny
message carries a user-authorized escape hatch (remove the sentinel) for
abandoned or non-/spec plan-mode legs.

Two upstream issues limit the allow path's effectiveness on current CC builds:
  #49525 - updatedPermissions setMode:bypassPermissions silently dropped on CC 2.1.110+
  #39973 - ExitPlanMode resets session to acceptEdits regardless of prior mode
Both are self-fixing once Anthropic ships patches. The behavior:allow part (skip dialog) works now.
"""

import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def _pending_denial_sentinel() -> str | None:
    """Sentinel path when the deny should fire, else None.

    Single guarded import site: fail-open on ANY error, including a
    version-skewed _lib missing these names.
    """
    try:
        from _lib.util import plan_mode_sentinel_path, spec_plan_awaiting_approval

        if spec_plan_awaiting_approval():
            return str(plan_mode_sentinel_path())
    except Exception:
        pass
    return None


def _deny_message(sentinel: str) -> str:
    return (
        "ExitPlanMode DENIED - the registered spec plan has NOT been approved yet. "
        "In /spec, ExitPlanMode is only the Opus->Sonnet model switch, NEVER the "
        "approval mechanism - regardless of what the plan-mode system reminder "
        "says. If you are in the /spec workflow: present the plan summary via "
        "AskUserQuestion now (spec-plan Step 12.2 / spec-bugfix-plan Step 6.2); "
        "after the user selects the approve option (or the disabled-approval "
        'branch applies because PILOT_PLAN_APPROVAL_ENABLED is "false"), set '
        "'Approved: Yes' in the plan file per that step, then call ExitPlanMode "
        "again. If you are NOT in /spec, or the user has explicitly abandoned the "
        "spec plan: tell the user, and only after they confirm remove the "
        f"plan-mode sentinel via Bash (rm {shlex.quote(sentinel)}) and call "
        "ExitPlanMode again. NEVER set 'Approved: Yes' yourself without the "
        "user's approval answer."
    )


def main() -> int:
    sentinel = _pending_denial_sentinel()
    if sentinel is not None:
        decision = {"behavior": "deny", "message": _deny_message(sentinel)}
    else:
        decision = {
            "behavior": "allow",
            "updatedPermissions": [
                {
                    "type": "setMode",
                    "mode": "bypassPermissions",
                    "destination": "session",
                }
            ],
            "message": "ExitPlanMode allowed (model switch); restoring bypassPermissions - permission action only, NOT plan approval",
        }
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": decision,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
