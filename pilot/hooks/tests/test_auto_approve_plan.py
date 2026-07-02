"""Tests for auto_approve_plan hook - approval-state-aware ExitPlanMode gate."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent.parent / "auto_approve_plan.py"
SESSION = "test-session"


def _setup_spec_state(
    tmp_path: Path,
    *,
    approved: str = "No",
    status: str = "PENDING",
    sentinel: bool = True,
    plan_file: bool = True,
    plan_in_project: bool = True,
) -> Path:
    """Create the session + plan state the hook inspects. Returns the plan path."""
    session_dir = tmp_path / "home" / ".pilot" / "sessions" / SESSION
    session_dir.mkdir(parents=True, exist_ok=True)
    plan_parent = tmp_path / "project" if plan_in_project else tmp_path / "elsewhere"
    plans_dir = plan_parent / "docs" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / "2026-07-02-test-feature.md"
    if plan_file:
        plan_path.write_text(f"# Test Feature\n\nStatus: {status}\nApproved: {approved}\nType: Feature\n")
    (session_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_path), "status": status}))
    if sentinel:
        (session_dir / "plan-mode-active").write_text("")
    return plan_path


def _run(tmp_path: Path, hook_path: Path = HOOK_PATH, project_root_env: bool = True) -> tuple[int, dict]:
    """Run the hook hermetically (isolated HOME/session/project) and parse its output."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir(exist_ok=True)
    project.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PILOT_SESSION_ID"] = SESSION
    if project_root_env:
        env["CLAUDE_PROJECT_ROOT"] = str(project)
    else:
        env.pop("CLAUDE_PROJECT_ROOT", None)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env.pop("CODEX_THREAD_ID", None)
    env.pop("PYTHONPATH", None)  # a leaked path to pilot/hooks would defeat the orphan-_lib isolation
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
    )
    return result.returncode, json.loads(result.stdout.strip())


def _decision(data: dict) -> dict:
    return data["hookSpecificOutput"]["decision"]


class TestAutoApprovePlan:
    def test_allows_without_spec_state(self, tmp_path):
        """No registered plan / no plan-mode sentinel -> plain allow (legacy behavior)."""
        code, data = _run(tmp_path)
        assert code == 0
        assert data["hookSpecificOutput"]["hookEventName"] == "PermissionRequest"
        decision = _decision(data)
        assert decision["behavior"] == "allow"
        perms = decision["updatedPermissions"]
        assert any(p.get("type") == "setMode" and p.get("mode") == "bypassPermissions" for p in perms)

    def test_allow_message_does_not_claim_plan_approval(self, tmp_path):
        """The allow message must NOT signal that the plan is approved.

        Regression guard: emitting "Plan auto-approved" made agents misread the
        auto-allowed ExitPlanMode (a model-switch/permission action) as the user
        approving the plan, so they skipped the real /spec approval gate
        (spec-plan/steps/12-approval.md). The message must perform the permission
        action while explicitly disclaiming plan approval.
        """
        _, data = _run(tmp_path)
        message = _decision(data)["message"].lower()
        assert "approved" not in message, f"misleading approval wording: {message!r}"
        assert "not plan approval" in message, f"missing disclaimer: {message!r}"

    def test_denies_while_plan_awaits_approval(self, tmp_path):
        """Premature ExitPlanMode during the /spec planning leg must be denied.

        Regression guard for the field report where the model followed the harness
        plan-mode reminder ("present the plan for approval via ExitPlanMode") and
        called ExitPlanMode BEFORE the AskUserQuestion approval gate. With an active
        plan-mode sentinel and a registered PENDING, unapproved plan, the hook must
        deny and re-anchor the model to the approval gate - including the escape
        hatch (sentinel path) for non-/spec or abandoned plan-mode legs.
        """
        _setup_spec_state(tmp_path, approved="No")
        code, data = _run(tmp_path)
        assert code == 0
        decision = _decision(data)
        assert decision["behavior"] == "deny"
        message = decision["message"]
        assert "askuserquestion" in message.lower()
        assert "plan-mode-active" in message  # escape hatch names the sentinel
        assert "updatedPermissions" not in decision  # allow-only field per hook schema

    def test_allows_after_plan_approved(self, tmp_path):
        _setup_spec_state(tmp_path, approved="Yes")
        _, data = _run(tmp_path)
        decision = _decision(data)
        assert decision["behavior"] == "allow"
        assert any(p.get("mode") == "bypassPermissions" for p in decision["updatedPermissions"])

    def test_allows_without_plan_mode_sentinel(self, tmp_path):
        """No EnterPlanMode sentinel = no plan-mode leg in flight -> never deny.

        A stale PENDING plan must not trap a user who entered plan mode manually
        (Shift+Tab does not call the EnterPlanMode tool, so no sentinel exists).
        """
        _setup_spec_state(tmp_path, approved="No", sentinel=False)
        _, data = _run(tmp_path)
        assert _decision(data)["behavior"] == "allow"

    def test_allows_when_plan_file_missing(self, tmp_path):
        """Registered plan path that no longer exists -> fail open (allow)."""
        _setup_spec_state(tmp_path, approved="No", plan_file=False)
        _, data = _run(tmp_path)
        assert _decision(data)["behavior"] == "allow"

    def test_allows_when_plan_file_undecodable(self, tmp_path):
        """Unreadable/undecodable plan file -> fail open (allow), never a deny trap.

        A deny here would be unrecoverable: 'set Approved: Yes' can never clear a
        decode error, so the session would be stuck in plan mode.
        """
        plan_path = _setup_spec_state(tmp_path, approved="No")
        plan_path.write_bytes(b"Status: PENDING\nApproved: No\n\xe9\xff")
        _, data = _run(tmp_path)
        assert _decision(data)["behavior"] == "allow"

    def test_allows_when_plan_outside_project(self, tmp_path):
        """Cross-session bleed guard: a plan from another repo never denies here."""
        _setup_spec_state(tmp_path, approved="No", plan_in_project=False)
        _, data = _run(tmp_path)
        assert _decision(data)["behavior"] == "allow"

    def test_allows_when_project_root_undetermined(self, tmp_path):
        """No CLAUDE_PROJECT_ROOT and a non-git cwd -> fail open (allow).

        plan_in_current_project returns True when the root cannot be
        determined; for the deny consumer that would be fail-closed, letting a
        stale plan deny ExitPlanMode in an unrelated non-git directory.
        """
        _setup_spec_state(tmp_path, approved="No")
        _, data = _run(tmp_path, project_root_env=False)
        assert _decision(data)["behavior"] == "allow"

    def test_allows_when_lib_util_unavailable(self, tmp_path):
        """A version-skewed install (hook without _lib) degrades to plain allow.

        The hook must always print a decision and exit 0; an ImportError crash
        would drop Claude Code back to the interactive permission dialog.
        """
        orphan_hook = tmp_path / "orphan" / "auto_approve_plan.py"
        orphan_hook.parent.mkdir(parents=True)
        shutil.copy(HOOK_PATH, orphan_hook)
        _setup_spec_state(tmp_path, approved="No")  # deny state, but guard can't load
        code, data = _run(tmp_path, hook_path=orphan_hook)
        assert code == 0
        assert _decision(data)["behavior"] == "allow"
