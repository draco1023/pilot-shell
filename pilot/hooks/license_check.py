"""SessionStart hook: verify Pilot Shell license before the session proceeds.

Reads cached license state via `pilot verify --json`. If the license is
invalid or expired, outputs {"continue": false} to halt the session.
Uses the existing 24h TTL cache in auth.py so this adds no network latency
on the happy path.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def main() -> None:
    pilot_bin = Path.home() / ".pilot" / "bin" / "pilot"
    if not pilot_bin.is_file():
        _allow()
        return

    try:
        result = subprocess.run(
            [str(pilot_bin), "verify", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        _allow()
        return

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        _allow()
        return

    if data.get("valid", False):
        _allow()
        return

    tier = data.get("tier", "")
    if tier == "trial" and data.get("trial_expired", False):
        _block("Pilot Shell trial expired. Run: pilot activate <license-key>")
    else:
        _block("Pilot Shell license invalid. Run: pilot activate <license-key>")


def _allow() -> None:
    print(json.dumps({"continue": True}))


def _block(reason: str) -> None:
    print(json.dumps({"continue": False, "stopReason": reason}))


if __name__ == "__main__":
    main()
