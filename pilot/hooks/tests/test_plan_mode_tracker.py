"""Tests for plan_mode_tracker hook."""

from __future__ import annotations

import json
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
