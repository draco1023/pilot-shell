"""Tests for plan_mode_tracker hook."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_mode_tracker import is_plan_file, main


def _run_main(stdin_data: dict, session_dir: Path, awaiting_approval: bool = False) -> tuple[int, str]:
    """Run main() with patched session dir and stdin, return (exit_code, stdout)."""
    with (
        patch("plan_mode_tracker._sessions_base", return_value=session_dir),
        patch("plan_mode_tracker.resolve_session_id", return_value="test-session"),
        patch("plan_mode_tracker.read_hook_stdin", return_value=stdin_data),
        patch("plan_mode_tracker.spec_plan_awaiting_approval", return_value=awaiting_approval),
    ):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main()
        return code, buf.getvalue()


class TestIsPlanFile:
    def test_plan_md_is_plan_file(self):
        assert is_plan_file("docs/plans/2026-06-03-my-plan.md") is True

    def test_nested_plans_dir(self):
        assert is_plan_file("/home/user/repo/docs/plans/foo.md") is True

    def test_implementation_ts_is_not_plan(self):
        assert is_plan_file("src/components/hero.tsx") is False

    def test_json_in_plans_dir_is_not_plan(self):
        assert is_plan_file("docs/plans/data.json") is False

    def test_md_outside_plans_is_not_plan(self):
        assert is_plan_file("README.md") is False


class TestSentinelTracking:
    def test_enter_plan_mode_writes_sentinel(self, tmp_path):
        stdin = {
            "tool_name": "EnterPlanMode",
            "tool_input": {},
            "tool_response": {"result": "ok"},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0
        assert (tmp_path / "test-session" / "plan-mode-active").exists()

    def test_enter_plan_mode_skips_sentinel_on_error(self, tmp_path):
        stdin = {
            "tool_name": "EnterPlanMode",
            "tool_input": {},
            "tool_response": {"is_error": True},
        }
        _run_main(stdin, tmp_path)
        assert not (tmp_path / "test-session" / "plan-mode-active").exists()

    def test_pre_enter_plan_mode_records_permission_mode(self, tmp_path):
        """PreToolUse(EnterPlanMode) fires before the mode flips to plan, so
        the observed permission_mode is the pre-plan mode - the bypass
        evidence auto_approve_plan needs to arm the post-exit restore."""
        stdin = {
            "tool_name": "EnterPlanMode",
            "tool_input": {},
            "permission_mode": "bypassPermissions",
        }
        code, out = _run_main(stdin, tmp_path)
        assert code == 0
        assert out == ""
        record = tmp_path / "test-session" / "pre-plan-permission-mode"
        assert record.read_text() == "bypassPermissions"

    def test_pre_enter_plan_mode_without_mode_clears_stale_record(self, tmp_path):
        """No permission_mode field (older Claude Code) -> clear any stale
        record so a previous leg's evidence cannot arm a later restore."""
        record = tmp_path / "test-session" / "pre-plan-permission-mode"
        record.parent.mkdir(parents=True)
        record.write_text("bypassPermissions")
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}}
        code, out = _run_main(stdin, tmp_path)
        assert code == 0
        assert out == ""
        assert not record.exists()

    def test_exit_plan_mode_deletes_sentinel(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {
            "tool_name": "ExitPlanMode",
            "tool_input": {},
            "tool_response": {"result": "ok"},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0
        assert not sentinel.exists()

    def test_exit_plan_mode_no_error_if_sentinel_missing(self, tmp_path):
        stdin = {
            "tool_name": "ExitPlanMode",
            "tool_input": {},
            "tool_response": {"result": "ok"},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0

    def test_exit_plan_mode_keeps_sentinel_on_error_response(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {
            "tool_name": "ExitPlanMode",
            "tool_input": {},
            "tool_response": {"is_error": True},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0
        assert sentinel.exists(), "sentinel must survive a failed ExitPlanMode"


class TestPreToolUseWarning:
    def test_warns_for_impl_file_when_sentinel_active(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Edit", "tool_input": {"file_path": "src/auth.ts"}}
        code, stdout = _run_main(stdin, tmp_path)
        assert code == 0
        data = json.loads(stdout)
        context = data["hookSpecificOutput"]["additionalContext"]
        assert "ExitPlanMode" in context
        assert "PLAN MODE" in context

    def test_no_warn_for_plan_file_when_sentinel_active(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Write", "tool_input": {"file_path": "docs/plans/2026-06-03-my-plan.md"}}
        code, stdout = _run_main(stdin, tmp_path)
        assert code == 0
        assert stdout.strip() == ""

    def test_no_warn_when_sentinel_absent(self, tmp_path):
        stdin = {"tool_name": "Edit", "tool_input": {"file_path": "src/auth.ts"}}
        code, stdout = _run_main(stdin, tmp_path)
        assert code == 0
        assert stdout.strip() == ""

    def test_no_warn_when_no_file_path(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Edit", "tool_input": {}}
        _, stdout = _run_main(stdin, tmp_path)
        assert stdout.strip() == ""

    def test_pre_approval_warning_while_plan_awaits_approval(self, tmp_path):
        """While the spec plan is unapproved, the warning must NOT instruct
        calling ExitPlanMode (auto_approve_plan denies it in that window) but
        must still fire as an edit-time tripwire pointing at the approval gate.
        """
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Edit", "tool_input": {"file_path": "src/auth.ts"}}
        code, stdout = _run_main(stdin, tmp_path, awaiting_approval=True)
        assert code == 0
        data = json.loads(stdout)
        context = data["hookSpecificOutput"]["additionalContext"]
        assert "NOT APPROVED" in context
        assert "Call ExitPlanMode NOW" not in context


class TestModelPinWindow:
    """EnterPlanMode/ExitPlanMode drive the window-scoped model slot pins."""

    def _run_with_pin(self, stdin: dict, session_dir: Path) -> list:
        calls = []

        def record(op: str, *, detached: bool) -> None:
            calls.append((op, detached))

        with (
            patch("plan_mode_tracker._sessions_base", return_value=session_dir),
            patch("plan_mode_tracker.resolve_session_id", return_value="test-session"),
            patch("plan_mode_tracker.read_hook_stdin", return_value=stdin),
            patch("plan_mode_tracker.spec_plan_awaiting_approval", return_value=False),
            patch("plan_mode_tracker.invoke_model_pin", side_effect=record),
        ):
            import io
            from contextlib import redirect_stdout

            with redirect_stdout(io.StringIO()):
                main()
        return calls

    def test_pre_enter_plan_mode_opens_window_before_mode_flips(self, tmp_path):
        # PreToolUse (no tool_response): the pin must land BEFORE plan mode
        # engages so the first planning request already resolves to the
        # configured Plan Model.
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}, "permission_mode": "bypassPermissions"}
        calls = self._run_with_pin(stdin, tmp_path)
        assert calls == [("plan-enter", False)]

    def test_enter_plan_mode_opens_window_synchronously(self, tmp_path):
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": {"result": "ok"}}
        calls = self._run_with_pin(stdin, tmp_path)
        assert calls == [("plan-enter", False)]

    def test_enter_plan_mode_error_unwinds_pre_opened_window(self, tmp_path):
        # Pre already opened the window; a failed EnterPlanMode must unwind it
        # (plan-abort, NOT plan-exit -- no exec window on the abort path).
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": {"is_error": True}}
        assert self._run_with_pin(stdin, tmp_path) == [("plan-abort", False)]

    def test_exit_plan_mode_closes_window_synchronously(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")
        stdin = {"tool_name": "ExitPlanMode", "tool_input": {}, "tool_response": {"result": "ok"}}
        calls = self._run_with_pin(stdin, tmp_path)
        assert calls == [("plan-exit", False)]

    def test_exit_plan_mode_error_does_not_close_window(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")
        stdin = {"tool_name": "ExitPlanMode", "tool_input": {}, "tool_response": {"is_error": True}}
        assert self._run_with_pin(stdin, tmp_path) == []

    def test_rapid_enter_then_exit_preserves_order(self, tmp_path):
        # Synchronous calls => program order; a detached pair could reorder.
        enter = {"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": {"result": "ok"}}
        exit_ = {"tool_name": "ExitPlanMode", "tool_input": {}, "tool_response": {"result": "ok"}}
        calls = self._run_with_pin(enter, tmp_path) + self._run_with_pin(exit_, tmp_path)
        assert calls == [("plan-enter", False), ("plan-exit", False)]
        assert all(detached is False for _, detached in calls)

    def test_plan_doc_write_heartbeats_detached(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")
        stdin = {"tool_name": "Write", "tool_input": {"file_path": "docs/plans/2026-07-14-x.md"}}
        calls = self._run_with_pin(stdin, tmp_path)
        assert ("touch", True) in calls


class TestPlanningLegModelCheck:
    """Observed-model verification for the /spec planning leg.

    With Model Switching ON, plan mode under opusplan must run on Opus.
    Claude Code can silently serve the Sonnet leg instead (Opus usage-limit
    fallback on Max plans, or the session was never on opusplan). The hook
    verifies the observed model from the statusline cache at the first
    plan-file write after EnterPlanMode and warns once per planning leg.
    """

    PLAN_WRITE = {"tool_name": "Write", "tool_input": {"file_path": "docs/plans/2026-07-06-fix.md"}}

    def _setup_leg(self, tmp_path, model_id, cache_fresh=True):
        """Create sentinel + statusline cache; cache render post-dates the sentinel unless stale."""
        session = tmp_path / "test-session"
        session.mkdir(parents=True, exist_ok=True)
        sentinel = session / "plan-mode-active"
        sentinel.write_text("")
        os.utime(sentinel, (1_000_000, 1_000_000))
        cache = session / "context-pct.json"
        cache.write_text(json.dumps({"model_id": model_id}))
        stamp = 1_000_100 if cache_fresh else 999_900
        os.utime(cache, (stamp, stamp))
        return session

    def _run(self, tmp_path, switch="true"):
        env = {"PILOT_MODEL_SWITCH_ENABLED": switch}
        with patch.dict(os.environ, env):
            return _run_main(self.PLAN_WRITE, tmp_path)

    def test_warns_when_planning_leg_not_on_opus(self, tmp_path):
        session = self._setup_leg(tmp_path, "claude-sonnet-5")
        code, stdout = self._run(tmp_path)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "NOT running on Opus" in context
        assert "claude-sonnet-5" in context
        assert "/model opusplan" in context
        assert "usage limit" in context.lower()
        assert (session / "plan-model-warned").exists()

    def test_silent_when_planning_leg_on_opus(self, tmp_path):
        self._setup_leg(tmp_path, "claude-opus-4-8")
        _, stdout = self._run(tmp_path)
        assert stdout.strip() == ""

    def test_silent_when_model_switch_off(self, tmp_path):
        self._setup_leg(tmp_path, "claude-sonnet-5")
        _, stdout = self._run(tmp_path, switch="false")
        assert stdout.strip() == ""

    def test_silent_on_fable_family_model(self, tmp_path):
        self._setup_leg(tmp_path, "claude-fable-5[1m]")
        _, stdout = self._run(tmp_path)
        assert stdout.strip() == ""

    def test_silent_when_cache_render_predates_sentinel(self, tmp_path):
        """A render from before EnterPlanMode proves nothing - no warning."""
        self._setup_leg(tmp_path, "claude-sonnet-5", cache_fresh=False)
        _, stdout = self._run(tmp_path)
        assert stdout.strip() == ""

    def test_silent_when_cache_missing(self, tmp_path):
        session = tmp_path / "test-session"
        session.mkdir(parents=True)
        (session / "plan-mode-active").write_text("")
        _, stdout = self._run(tmp_path)
        assert stdout.strip() == ""

    def test_warns_only_once_per_planning_leg(self, tmp_path):
        self._setup_leg(tmp_path, "claude-sonnet-5")
        _, first = self._run(tmp_path)
        assert first.strip() != ""
        _, second = self._run(tmp_path)
        assert second.strip() == ""

    def test_enter_plan_mode_resets_warned_marker(self, tmp_path):
        """A new planning leg gets a fresh chance to warn (uneven switching)."""
        session = tmp_path / "test-session"
        session.mkdir(parents=True)
        (session / "plan-model-warned").write_text("")
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": {"result": "ok"}}
        _run_main(stdin, tmp_path)
        assert not (session / "plan-model-warned").exists()
