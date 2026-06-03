"""Tests for session_startup_maintenance hook -- CC-only SessionStart cleanup
of stale Claude task files (PID reuse) and dead-PID Pilot session dirs."""

from __future__ import annotations

from pathlib import Path

from session_startup_maintenance import clean_stale_session_dirs, clean_task_list


class TestCleanTaskList:
    def test_removes_json_for_current_pid(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "tasks" / "pilot-1234"
        task_dir.mkdir(parents=True)
        (task_dir / "a.json").write_text("{}")
        (task_dir / "b.json").write_text("{}")
        (task_dir / "notes.txt").write_text("keep")

        removed = clean_task_list(tmp_path, 1234)

        assert removed == 2
        assert not (task_dir / "a.json").exists()
        assert (task_dir / "notes.txt").exists()  # non-json preserved

    def test_missing_task_dir_returns_zero(self, tmp_path: Path) -> None:
        assert clean_task_list(tmp_path, 9999) == 0


class TestCleanStaleSessionDirs:
    def _alive(self, alive_pids: set[int]):
        return lambda pid: pid in alive_pids

    def test_removes_dead_pid_dir(self, tmp_path: Path) -> None:
        (tmp_path / "1111").mkdir()  # dead
        (tmp_path / "2222").mkdir()  # alive
        removed = clean_stale_session_dirs(tmp_path, my_pid=999, is_alive=self._alive({2222}))
        assert removed == 1
        assert not (tmp_path / "1111").exists()
        assert (tmp_path / "2222").exists()

    def test_keeps_current_pid_dir(self, tmp_path: Path) -> None:
        (tmp_path / "999").mkdir()
        removed = clean_stale_session_dirs(tmp_path, my_pid=999, is_alive=self._alive(set()))
        assert removed == 0
        assert (tmp_path / "999").exists()

    def test_skips_default_and_pipes(self, tmp_path: Path) -> None:
        (tmp_path / "default").mkdir()
        (tmp_path / "pipes").mkdir()
        removed = clean_stale_session_dirs(tmp_path, my_pid=999, is_alive=self._alive(set()))
        assert removed == 0
        assert (tmp_path / "default").exists()
        assert (tmp_path / "pipes").exists()

    def test_skips_non_pid_named_dirs(self, tmp_path: Path) -> None:
        """Agent-native UUID/thread dirs (no leading PID) are left untouched."""
        (tmp_path / "019e8c74-132e-7c20").mkdir()
        removed = clean_stale_session_dirs(tmp_path, my_pid=999, is_alive=self._alive(set()))
        assert removed == 0
        assert (tmp_path / "019e8c74-132e-7c20").exists()

    def test_removes_dead_pid_with_suffix(self, tmp_path: Path) -> None:
        """`{PID}-{RANDOM}` shell-alias dirs (suffix is bash $RANDOM) are reclaimed."""
        (tmp_path / "1111-22222").mkdir()
        removed = clean_stale_session_dirs(tmp_path, my_pid=999, is_alive=self._alive(set()))
        assert removed == 1
        assert not (tmp_path / "1111-22222").exists()

    def test_skips_digit_leading_uuid_dir(self, tmp_path: Path) -> None:
        """A digit-leading agent-native UUID dir must NOT be parsed as a PID and deleted.

        ~2% of CLAUDE_CODE_SESSION_ID UUIDs have an all-digit first group; the bogus
        PID is never alive, so a loose `-.*` regex would rmtree a live session's state.
        """
        live_session = tmp_path / "12345678-90ab-cdef-1234"
        live_session.mkdir()
        (live_session / "active_plan.json").write_text("{}")
        removed = clean_stale_session_dirs(tmp_path, my_pid=999, is_alive=self._alive(set()))
        assert removed == 0
        assert (live_session / "active_plan.json").exists()

    def test_missing_base_returns_zero(self, tmp_path: Path) -> None:
        assert clean_stale_session_dirs(tmp_path / "nope", my_pid=999, is_alive=self._alive(set())) == 0
