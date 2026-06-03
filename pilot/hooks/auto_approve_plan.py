#!/usr/bin/env python3
"""PreToolUse hook for ExitPlanMode: auto-approve + request bypassPermissions restore.

Two upstream issues limit effectiveness on current CC builds:
  #49525 - updatedPermissions setMode:bypassPermissions silently dropped on CC 2.1.110+
  #39973 - ExitPlanMode resets session to acceptEdits regardless of prior mode
Both are self-fixing once Anthropic ships patches. The behavior:allow part (skip dialog) works now.
"""

import json
import sys

print(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": "allow",
                    "updatedPermissions": [
                        {
                            "type": "setMode",
                            "mode": "bypassPermissions",
                            "destination": "session",
                        }
                    ],
                    "message": "Plan auto-approved; restoring bypassPermissions",
                },
            }
        }
    )
)
sys.exit(0)
