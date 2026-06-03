"""Tests for the .NET file checker (dotnet format, single-file scoped; no per-edit build)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from _checkers.dotnet import check_dotnet


def _which(name: str):
    """shutil.which stub: dotnet is present, nothing else."""
    return "/usr/bin/dotnet" if name == "dotnet" else None


class TestCheckDotnet:
    """Observable behavior of check_dotnet after the single-file optimization."""

    def test_no_dotnet_binary_skips_checks(self, tmp_path: Path) -> None:
        """With a project present but no dotnet on PATH, no subprocess runs."""
        (tmp_path / "App.csproj").write_text("<Project />\n")
        cs = tmp_path / "Foo.cs"
        cs.write_text("namespace App; public class Foo { }\n")

        with (
            patch("_checkers.dotnet.check_file_length", return_value=""),
            patch("_checkers.dotnet.shutil.which", return_value=None),
            patch("_checkers.dotnet.subprocess.run") as mock_run,
        ):
            exit_code, reason = check_dotnet(cs)

        assert exit_code == 0
        assert reason == ""
        mock_run.assert_not_called()

    def test_test_file_is_skipped(self, tmp_path: Path) -> None:
        """A *Tests.cs file returns early without invoking any tool."""
        (tmp_path / "App.csproj").write_text("<Project />\n")
        cs = tmp_path / "FooTests.cs"
        cs.write_text("namespace App.Tests; public class FooTests { }\n")

        with (
            patch("_checkers.dotnet.check_file_length", return_value=""),
            patch("_checkers.dotnet.shutil.which", side_effect=_which),
            patch("_checkers.dotnet.subprocess.run") as mock_run,
        ):
            exit_code, reason = check_dotnet(cs)

        assert exit_code == 0
        assert reason == ""
        mock_run.assert_not_called()

    def test_format_is_scoped_to_edited_file_and_no_build_runs(self, tmp_path: Path) -> None:
        """Only `dotnet format` runs (no build), and it is scoped to the edited file via --include."""
        (tmp_path / "App.csproj").write_text("<Project />\n")
        src = tmp_path / "src"
        src.mkdir()
        cs = src / "Foo.cs"
        cs.write_text("namespace App; public class Foo { }\n")

        clean = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("_checkers.dotnet.check_file_length", return_value=""),
            patch("_checkers.dotnet.shutil.which", side_effect=_which),
            patch("_checkers.dotnet.subprocess.run", return_value=clean) as mock_run,
        ):
            check_dotnet(cs)

        commands = [call.args[0] for call in mock_run.call_args_list]
        # No build is ever invoked.
        assert all("build" not in cmd for cmd in commands), commands
        # Exactly one tool runs: dotnet format, scoped to the edited file.
        assert len(commands) == 1, commands
        fmt = commands[0]
        assert "format" in fmt
        assert "--include" in fmt
        # The path passed to --include is the edited file relative to the project root.
        include_idx = fmt.index("--include")
        assert fmt[include_idx + 1] == str(Path("src") / "Foo.cs")

    def test_format_issues_are_reported(self, tmp_path: Path) -> None:
        """A non-zero `dotnet format --verify-no-changes` surfaces a formatting reason."""
        (tmp_path / "App.csproj").write_text("<Project />\n")
        cs = tmp_path / "Foo.cs"
        cs.write_text("namespace App; public class Foo { }\n")

        needs_format = MagicMock(
            returncode=2,
            stdout="Formatted code file 'Foo.cs'.\n",
            stderr="",
        )

        with (
            patch("_checkers.dotnet.check_file_length", return_value=""),
            patch("_checkers.dotnet.shutil.which", side_effect=_which),
            patch("_checkers.dotnet.subprocess.run", return_value=needs_format),
        ):
            exit_code, reason = check_dotnet(cs)

        assert exit_code == 0
        assert "format" in reason.lower()

    def test_clean_format_produces_no_reason(self, tmp_path: Path) -> None:
        """A clean format run yields no reason."""
        (tmp_path / "App.csproj").write_text("<Project />\n")
        cs = tmp_path / "Foo.cs"
        cs.write_text("namespace App; public class Foo { }\n")

        clean = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("_checkers.dotnet.check_file_length", return_value=""),
            patch("_checkers.dotnet.shutil.which", side_effect=_which),
            patch("_checkers.dotnet.subprocess.run", return_value=clean),
        ):
            exit_code, reason = check_dotnet(cs)

        assert exit_code == 0
        assert reason == ""
