"""Tests for codegraph_init hook — CodeGraph init/sync on SessionStart."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from codegraph_init import (
    _enable_embeddings,
    _find_codegraph_package_dir,
    _get_project_dir,
    _has_git_commits,
    _is_corrupt_db_error,
    _is_in_git_repo,
    _is_indexed,
    _is_using_wasm_sqlite,
    _recover_corrupt_db,
    _repair_native_sqlite,
    _run,
    main,
)


class TestGitDetection:
    def test_is_in_git_repo_true(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert _is_in_git_repo(tmp_path) is True

    def test_is_in_git_repo_false(self, tmp_path: Path) -> None:
        assert _is_in_git_repo(tmp_path) is False

    def test_is_in_git_repo_walks_up(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        assert _is_in_git_repo(subdir) is True

    @patch("codegraph_init.subprocess.run")
    def test_has_git_commits_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert _has_git_commits(tmp_path) is True

    @patch("codegraph_init.subprocess.run")
    def test_has_git_commits_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=128)
        assert _has_git_commits(tmp_path) is False

    @patch("codegraph_init.subprocess.run", side_effect=OSError)
    def test_has_git_commits_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        assert _has_git_commits(tmp_path) is False


class TestEnableEmbeddings:
    def test_creates_config_when_exists(self, tmp_path: Path) -> None:
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        config = cg / "config.json"
        config.write_text(json.dumps({"someKey": True}))

        _enable_embeddings(tmp_path)

        data = json.loads(config.read_text())
        assert data["enableEmbeddings"] is True
        assert data["someKey"] is True

    def test_noop_when_already_enabled(self, tmp_path: Path) -> None:
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        config = cg / "config.json"
        config.write_text(json.dumps({"enableEmbeddings": True}))
        mtime_before = config.stat().st_mtime_ns

        _enable_embeddings(tmp_path)

        assert config.stat().st_mtime_ns == mtime_before

    def test_noop_when_no_config(self, tmp_path: Path) -> None:
        _enable_embeddings(tmp_path)


class TestIsIndexed:
    def test_true_when_db_large(self, tmp_path: Path) -> None:
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        db = cg / "codegraph.db"
        db.write_bytes(b"\x00" * 2_000_000)
        assert _is_indexed(tmp_path) is True

    def test_false_when_db_small(self, tmp_path: Path) -> None:
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        db = cg / "codegraph.db"
        db.write_bytes(b"\x00" * 100_000)
        assert _is_indexed(tmp_path) is False

    def test_false_when_no_db(self, tmp_path: Path) -> None:
        assert _is_indexed(tmp_path) is False


class TestCorruptDb:
    def test_detects_malformed(self) -> None:
        assert _is_corrupt_db_error("database disk image is malformed") is True

    def test_detects_not_a_database(self) -> None:
        assert _is_corrupt_db_error("file is not a database") is True

    def test_false_for_normal_error(self) -> None:
        assert _is_corrupt_db_error("command not found") is False

    def test_recover_removes_dir(self, tmp_path: Path) -> None:
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        (cg / "codegraph.db").write_text("corrupt")
        assert _recover_corrupt_db(tmp_path) is True
        assert not cg.exists()

    def test_recover_noop_when_missing(self, tmp_path: Path) -> None:
        assert _recover_corrupt_db(tmp_path) is False


class TestWasmSqliteRepair:
    @patch("codegraph_init.subprocess.run")
    def test_detects_wasm_backend(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"[CodeGraph] Using WASM SQLite backend (native better-sqlite3 unavailable)\n",
            stderr=b"",
        )
        assert _is_using_wasm_sqlite() is True

    @patch("codegraph_init.subprocess.run")
    def test_native_backend_not_wasm(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"CodeGraph Status\n", stderr=b"")
        assert _is_using_wasm_sqlite() is False

    @patch("codegraph_init.subprocess.run", side_effect=OSError)
    def test_wasm_check_error(self, _mock_run: MagicMock) -> None:
        assert _is_using_wasm_sqlite() is False

    @patch("codegraph_init.shutil.which", return_value="/usr/bin/codegraph")
    def test_find_package_dir(self, _mock_which: MagicMock, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "node_modules" / "@colbymchenry" / "codegraph"
        pkg_dir.mkdir(parents=True)
        bin_dir = pkg_dir / "dist" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "codegraph.js").write_text("")
        (pkg_dir / "package.json").write_text(json.dumps({"name": "@colbymchenry/codegraph"}))

        with patch("codegraph_init.Path.resolve", return_value=bin_dir / "codegraph.js"):
            result = _find_codegraph_package_dir()
        assert result == pkg_dir

    @patch("codegraph_init.shutil.which", return_value=None)
    def test_find_package_dir_no_binary(self, _mock_which: MagicMock) -> None:
        assert _find_codegraph_package_dir() is None

    @patch("codegraph_init.subprocess.run")
    @patch("codegraph_init._find_codegraph_package_dir")
    def test_repair_rebuilds_bundled(self, mock_find: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "codegraph-pkg"
        pkg_dir.mkdir()
        (pkg_dir / "node_modules" / "better-sqlite3").mkdir(parents=True)
        mock_find.return_value = pkg_dir
        mock_run.return_value = MagicMock(returncode=0)

        assert _repair_native_sqlite() is True
        mock_run.assert_called_once_with(
            ["npm", "rebuild", "better-sqlite3"],
            capture_output=True,
            cwd=pkg_dir,
            timeout=180,
        )

    @patch("codegraph_init.subprocess.run")
    @patch("codegraph_init._find_codegraph_package_dir", return_value=None)
    def test_repair_falls_back_to_global(self, _mock_find: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert _repair_native_sqlite() is True
        mock_run.assert_called_once_with(
            ["npm", "install", "-g", "better-sqlite3", "--no-audit", "--no-fund"],
            capture_output=True,
            timeout=180,
        )


class TestRun:
    @patch("codegraph_init.subprocess.run")
    def test_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert _run(["codegraph", "sync"], tmp_path) is True

    @patch("codegraph_init.subprocess.run")
    def test_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        assert _run(["codegraph", "sync"], tmp_path) is False

    @patch("codegraph_init.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10))
    def test_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        assert _run(["codegraph", "sync"], tmp_path) is False


class TestGetProjectDir:
    def test_codex_workspace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_WORKSPACE", "/foo/bar")
        monkeypatch.delenv("CLAUDE_PROJECT_ROOT", raising=False)
        assert _get_project_dir() == Path("/foo/bar")

    def test_claude_project_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CODEX_WORKSPACE", raising=False)
        monkeypatch.setenv("CLAUDE_PROJECT_ROOT", "/baz/qux")
        assert _get_project_dir() == Path("/baz/qux")

    def test_codex_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_WORKSPACE", "/codex")
        monkeypatch.setenv("CLAUDE_PROJECT_ROOT", "/claude")
        assert _get_project_dir() == Path("/codex")

    def test_falls_back_to_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CODEX_WORKSPACE", raising=False)
        monkeypatch.delenv("CLAUDE_PROJECT_ROOT", raising=False)
        assert _get_project_dir() == Path.cwd()


class TestMain:
    @patch("codegraph_init.shutil.which", return_value=None)
    def test_noop_when_codegraph_missing(self, mock_which: MagicMock) -> None:
        main()

    @patch("codegraph_init.subprocess.run")
    @patch("codegraph_init.shutil.which", return_value="/usr/bin/codegraph")
    @patch("codegraph_init._get_project_dir")
    def test_init_and_index_fresh_project(
        self, mock_dir: MagicMock, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        mock_dir.return_value = tmp_path
        mock_run.return_value = MagicMock(returncode=0)

        def init_side_effect(cmd, **kwargs):
            if cmd == ["codegraph", "init"]:
                (tmp_path / ".codegraph").mkdir(exist_ok=True)
                (tmp_path / ".codegraph" / "config.json").write_text("{}")
            return MagicMock(returncode=0)

        mock_run.side_effect = init_side_effect
        main()

        init_call = call(["codegraph", "init"], capture_output=True, cwd=tmp_path, timeout=60)
        assert init_call in mock_run.call_args_list

    @patch("codegraph_init.subprocess.run")
    @patch("codegraph_init.shutil.which", return_value="/usr/bin/codegraph")
    @patch("codegraph_init._get_project_dir")
    def test_sync_when_already_indexed(
        self, mock_dir: MagicMock, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        (cg / "config.json").write_text(json.dumps({"enableEmbeddings": True}))
        (cg / "codegraph.db").write_bytes(b"\x00" * 2_000_000)
        mock_dir.return_value = tmp_path
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")

        main()

        sync_call = call(["codegraph", "sync"], capture_output=True, cwd=tmp_path, timeout=120)
        assert sync_call in mock_run.call_args_list

    @patch("codegraph_init.subprocess.run")
    @patch("codegraph_init.shutil.which", return_value="/usr/bin/codegraph")
    @patch("codegraph_init._get_project_dir")
    def test_skips_non_git_dir(
        self, mock_dir: MagicMock, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        main()
        mock_run.assert_not_called()

    @patch("codegraph_init._recover_corrupt_db", return_value=True)
    @patch("codegraph_init._run", return_value=True)
    @patch("codegraph_init.subprocess.run")
    @patch("codegraph_init.shutil.which", return_value="/usr/bin/codegraph")
    @patch("codegraph_init._get_project_dir")
    def test_recovers_corrupt_db_on_sync(
        self,
        mock_dir: MagicMock,
        _mock_which: MagicMock,
        mock_subprocess_run: MagicMock,
        mock_run: MagicMock,
        mock_recover: MagicMock,
        tmp_path: Path,
    ) -> None:
        (tmp_path / ".git").mkdir()
        cg = tmp_path / ".codegraph"
        cg.mkdir()
        (cg / "config.json").write_text(json.dumps({"enableEmbeddings": True}))
        (cg / "codegraph.db").write_bytes(b"\x00" * 2_000_000)
        mock_dir.return_value = tmp_path

        def side_effect(cmd, **_kwargs):
            if cmd == ["git", "rev-parse", "--verify", "HEAD"]:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1, stderr=b"database disk image is malformed")

        mock_subprocess_run.side_effect = side_effect

        main()

        mock_recover.assert_called_once_with(tmp_path)
        mock_run.assert_called_once_with(["codegraph", "init", "-i"], tmp_path, timeout=600)
