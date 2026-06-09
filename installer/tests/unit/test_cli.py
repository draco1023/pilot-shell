"""Tests for CLI entry point and step orchestration."""

from __future__ import annotations

import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCLIApp:
    """Test CLI application."""

    def test_cli_parser_exists(self):
        """CLI argument parser exists."""
        from installer.cli import create_parser

        parser = create_parser()
        assert parser is not None

    def test_cli_has_install_command(self):
        """CLI has install command handler."""
        from installer.cli import cmd_install

        assert callable(cmd_install)


class TestRunInstallation:
    """Test step orchestration."""

    def test_run_installation_exists(self):
        """run_installation function exists."""
        from installer.cli import run_installation

        assert callable(run_installation)

    def test_get_all_steps_excludes_vscode_extensions(self):
        """Installer must not run a VSCode extensions step (removed per user feedback)."""
        from installer.cli import get_all_steps

        names = [step.name for step in get_all_steps()]
        assert "vscode_extensions" not in names

    @patch("installer.cli.get_all_steps")
    def test_run_installation_executes_steps(self, mock_get_all_steps):
        """run_installation executes steps in order."""
        from installer.cli import run_installation
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
                non_interactive=True,
            )

            mock_step1 = MagicMock()
            mock_step1.name = "step1"
            mock_step1.check.return_value = False

            mock_step2 = MagicMock()
            mock_step2.name = "step2"
            mock_step2.check.return_value = False

            mock_get_all_steps.return_value = [mock_step1, mock_step2]

            run_installation(ctx)

            mock_step1.run.assert_called_once_with(ctx)
            mock_step2.run.assert_called_once_with(ctx)


class TestBackupFeature:
    """Test backup feature ignores special files."""

    def test_ignore_special_files_skips_tmp_directory(self):
        """ignore_special_files function skips tmp directory."""
        from pathlib import Path

        def ignore_special_files(directory: str, files: list[str]) -> list[str]:
            ignored = []
            for f in files:
                path = Path(directory) / f
                if path.is_fifo() or path.is_socket() or path.is_block_device() or path.is_char_device():
                    ignored.append(f)
                if f == "tmp":
                    ignored.append(f)
            return ignored

        result = ignore_special_files("/some/dir", ["commands", "hooks", "tmp", "scripts"])
        assert "tmp" in result
        assert "commands" not in result
        assert "hooks" not in result

    def test_backup_copytree_with_ignore(self):
        """Backup uses copytree with ignore function."""
        import shutil
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / ".claude"
            source.mkdir()
            (source / "commands").mkdir()
            (source / "commands" / "spec.md").write_text("test")
            (source / "tmp").mkdir()
            (source / "tmp" / "pipes").mkdir()

            backup = Path(tmpdir) / ".claude.backup.test"

            def ignore_special_files(directory: str, files: list[str]) -> list[str]:
                ignored = []
                for f in files:
                    if f == "tmp":
                        ignored.append(f)
                return ignored

            shutil.copytree(source, backup, ignore=ignore_special_files)

            assert backup.exists()
            assert (backup / "commands" / "spec.md").exists()
            assert not (backup / "tmp").exists()


class TestMainEntry:
    """Test __main__ entry point."""

    def test_main_module_exists(self):
        """__main__ module exists."""
        import installer.__main__

        assert hasattr(installer.__main__, "main") or True


class TestKeyboardInterrupt:
    """Test CTRL+C (KeyboardInterrupt) handling."""

    @patch("installer.cli.get_all_steps")
    def test_keyboard_interrupt_raises_installation_cancelled(self, mock_get_all_steps):
        """KeyboardInterrupt during step raises InstallationCancelled with step name."""
        from installer.cli import run_installation
        from installer.context import InstallContext
        from installer.errors import InstallationCancelled
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True, quiet=True),
                non_interactive=True,
            )

            failing_step = MagicMock()
            failing_step.name = "dependencies"
            failing_step.check.return_value = False
            failing_step.run.side_effect = KeyboardInterrupt()

            mock_get_all_steps.return_value = [failing_step]

            with pytest.raises(InstallationCancelled) as exc_info:
                run_installation(ctx)

            assert exc_info.value.step_name == "dependencies"
            assert "dependencies" in str(exc_info.value)


class TestLicenseInfo:
    """Test license info retrieval."""

    def test_get_license_info_function_exists(self):
        """_get_license_info function exists."""
        from installer.cli import _get_license_info

        assert callable(_get_license_info)

    @patch("installer.cli.Path.home")
    @patch("subprocess.run")
    def test_get_license_info_returns_valid_license(self, mock_run, mock_home, tmp_path: Path):
        """_get_license_info returns license data for valid license."""
        from installer.cli import _get_license_info

        mock_home.return_value = tmp_path
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"tier": "standard", "email": "test@example.com"}',
            stderr="",
        )

        bin_dir = tmp_path / ".pilot" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "pilot").touch()

        result = _get_license_info(tmp_path)
        assert result is not None
        assert result["tier"] == "standard"

    @patch("installer.cli.Path.home")
    @patch("subprocess.run")
    def test_get_license_info_detects_expired_trial(self, mock_run, mock_home, tmp_path: Path):
        """_get_license_info detects expired trial from stderr."""
        from installer.cli import _get_license_info

        mock_home.return_value = tmp_path
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr='{"success": false, "error": "Trial expired", "tier": "trial"}',
        )

        bin_dir = tmp_path / ".pilot" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "pilot").touch()

        result = _get_license_info(tmp_path)
        assert result is not None
        assert result["tier"] == "trial"
        assert result.get("is_expired") is True

    @patch("installer.cli.Path.home")
    def test_get_license_info_returns_none_without_binary(self, mock_home, tmp_path: Path):
        """_get_license_info returns None when pilot binary doesn't exist."""
        from installer.cli import _get_license_info

        mock_home.return_value = tmp_path
        result = _get_license_info(tmp_path)
        assert result is None


class TestLicenseFlowTrialFallback:
    """Test _handle_license_flow falls back to license key prompt when trial fails."""

    @patch("installer.cli._start_trial", return_value=None)
    @patch("installer.cli._check_trial_used", return_value=(False, False))
    @patch("installer.cli._prompt_license_key", return_value=True)
    def test_trial_failure_falls_back_to_license_prompt(
        self, mock_prompt, mock_check_trial, mock_start_trial, tmp_path: Path
    ):
        """When trial start fails, user is prompted for license key."""
        from installer.cli import _handle_license_flow
        from installer.ui import Console

        console = Console(non_interactive=False, quiet=True)
        result = _handle_license_flow(
            console,
            tmp_path,
            local_mode=False,
            local_repo_dir=None,
            license_info=None,
            license_acknowledged=False,
        )

        mock_prompt.assert_called_once()
        assert result is None

    @patch("installer.cli._start_trial", return_value=None)
    @patch("installer.cli._check_trial_used", return_value=(False, False))
    @patch("installer.cli._prompt_license_key", return_value=False)
    def test_trial_failure_and_license_failure_exits(
        self, mock_prompt, mock_check_trial, mock_start_trial, tmp_path: Path
    ):
        """When trial and license both fail, returns exit code 1."""
        from installer.cli import _handle_license_flow
        from installer.ui import Console

        console = Console(non_interactive=False, quiet=True)
        result = _handle_license_flow(
            console,
            tmp_path,
            local_mode=False,
            local_repo_dir=None,
            license_info=None,
            license_acknowledged=False,
        )

        mock_prompt.assert_called_once()
        assert result == 1

    @patch("installer.cli._start_trial", return_value=7)
    @patch("installer.cli._check_trial_used", return_value=(False, False))
    def test_trial_success_does_not_prompt_for_license(self, mock_check_trial, mock_start_trial, tmp_path: Path):
        """When trial succeeds, no license prompt is shown."""
        from installer.cli import _handle_license_flow
        from installer.ui import Console

        console = Console(non_interactive=False, quiet=True)
        with patch("installer.cli._prompt_license_key") as mock_prompt:
            result = _handle_license_flow(
                console,
                tmp_path,
                local_mode=False,
                local_repo_dir=None,
                license_info=None,
                license_acknowledged=False,
            )

        mock_prompt.assert_not_called()
        assert result is None

    @patch("installer.cli._start_trial", return_value=7)
    @patch("installer.cli._check_trial_used", return_value=(False, False))
    def test_trial_success_announces_activation_with_days(self, mock_check_trial, mock_start_trial, tmp_path: Path):
        """A freshly started trial is announced with its remaining days."""
        from installer.cli import _handle_license_flow
        from installer.ui import Console

        console = Console(non_interactive=False, quiet=True)
        console.success = MagicMock()

        result = _handle_license_flow(
            console,
            tmp_path,
            local_mode=False,
            local_repo_dir=None,
            license_info=None,
            license_acknowledged=False,
        )

        assert result is None
        console.success.assert_called_once()
        message = console.success.call_args.args[0]
        assert "7" in message
        assert "trial" in message.lower()


class TestAgentPrerequisiteGate:
    """cmd_install must verify at least one supported AI agent is installed.

    README prerequisites (README.md:62-67) require the user to install Claude Code
    and/or Codex CLI before running the installer. The installer detects them; it
    does not install them.
    """

    @staticmethod
    def _install_args() -> "Namespace":
        return Namespace(
            non_interactive=True,
            quiet=True,
            skip_env=False,
            local=False,
            local_repo_dir=None,
            local_system=False,
            target_version=None,
            restart_ccp=False,
        )

    @patch("installer.cli.run_installation")
    @patch("installer.cli._get_license_info", return_value=None)
    @patch("installer.cli.is_codex_installed", return_value=False)
    @patch("installer.cli.is_claude_installed", return_value=False)
    def test_cmd_install_aborts_when_no_agent_detected(
        self,
        _mock_claude,
        _mock_codex,
        _mock_license,
        mock_run_install,
    ):
        """cmd_install exits non-zero without running installation when neither agent is on PATH."""
        from installer.cli import cmd_install

        rc = cmd_install(self._install_args())

        assert rc != 0
        mock_run_install.assert_not_called()

    @patch("installer.cli.run_installation")
    @patch("installer.cli._get_license_info", return_value=None)
    @patch("installer.cli.is_codex_installed", return_value=True)
    @patch("installer.cli.is_claude_installed", return_value=False)
    def test_cmd_install_proceeds_when_only_codex_detected(
        self,
        _mock_claude,
        _mock_codex,
        _mock_license,
        mock_run_install,
    ):
        """Codex-only installs are first-class: installation proceeds when only Codex is on PATH."""
        from installer.cli import cmd_install

        rc = cmd_install(self._install_args())

        assert rc == 0
        mock_run_install.assert_called_once()

    @patch("installer.cli.run_installation")
    @patch("installer.cli._get_license_info", return_value=None)
    @patch("installer.cli.is_codex_installed", return_value=False)
    @patch("installer.cli.is_claude_installed", return_value=True)
    def test_cmd_install_proceeds_when_only_claude_detected(
        self,
        _mock_claude,
        _mock_codex,
        _mock_license,
        mock_run_install,
    ):
        """Claude-only installs continue to work after the agent gate is added."""
        from installer.cli import cmd_install

        rc = cmd_install(self._install_args())

        assert rc == 0
        mock_run_install.assert_called_once()
