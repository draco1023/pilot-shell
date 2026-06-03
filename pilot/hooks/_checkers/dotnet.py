"""Dotnet file checker — single-file dotnet format check (no per-edit build)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from _lib.util import BLUE, NC, check_file_length

DOTNET_EXTENSIONS = {".cs", ".razor"}
DEBUG = os.environ.get("HOOK_DEBUG", "").lower() == "true"


def debug_log(message: str) -> None:
    """Print debug message if enabled."""
    if DEBUG:
        print(f"{BLUE}[DEBUG]{NC} {message}", file=sys.stderr)


def find_project_root(file_path: Path) -> Path | None:
    """Find nearest directory with a .csproj or .sln file."""
    current = file_path.parent
    depth = 0
    while current != current.parent:
        if list(current.glob("*.csproj")) or list(current.glob("*.sln")):
            return current
        current = current.parent
        depth += 1
        if depth > 20:
            break
    return None


def _find_nearest_csproj(file_path: Path) -> Path | None:
    """Find the nearest .csproj file by walking up from file_path."""
    current = file_path.parent
    for _ in range(20):
        csproj_files = list(current.glob("*.csproj"))
        if csproj_files:
            return csproj_files[0]
        if current.parent == current:
            break
        current = current.parent
    return None


def check_dotnet(file_path: Path) -> tuple[int, str]:
    """Check .NET file with a single-file `dotnet format`. Returns (0, reason)."""
    if file_path.stem.endswith("Tests") or file_path.stem.endswith("Test"):
        return 0, ""
    if ".Tests" in str(file_path) or ".Test" in str(file_path):
        return 0, ""

    length_warning = check_file_length(file_path)

    project_root = find_project_root(file_path)
    if not project_root:
        return 0, length_warning

    dotnet_bin = shutil.which("dotnet")
    if not dotnet_bin:
        return 0, length_warning

    csproj = _find_nearest_csproj(file_path)

    results: dict[str, tuple] = {}
    has_issues = False

    has_issues, results = _run_dotnet_format(dotnet_bin, csproj, project_root, file_path, has_issues, results)

    if has_issues:
        parts = []
        for tool_name, (count, _) in results.items():
            parts.append(f"{count} {tool_name}")
        reason = f"Dotnet: {', '.join(parts)} in {file_path.name}"
        details = _format_dotnet_issues(file_path, results)
        if details:
            reason = f"{reason}\n{details}"
        if length_warning:
            reason = f"{reason}\n{length_warning}"
        return 0, reason

    return 0, length_warning


def _run_dotnet_format(
    dotnet_bin: str,
    csproj: Path | None,
    project_root: Path,
    file_path: Path,
    has_issues: bool,
    results: dict[str, tuple],
) -> tuple[bool, dict[str, tuple]]:
    """Run dotnet format --verify-no-changes scoped to the edited file and collect results."""
    try:
        cmd = [dotnet_bin, "format", "--verify-no-changes", "--no-restore", "--verbosity", "q"]
        if csproj:
            cmd.append(str(csproj))

        try:
            include_path = file_path.relative_to(project_root)
        except ValueError:
            include_path = file_path
        cmd.extend(["--include", str(include_path)])

        debug_log(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=project_root,
            timeout=60,
        )
        debug_log(f"Format exit code: {result.returncode}")

        if result.returncode != 0:
            output = result.stdout + result.stderr
            # Collect filenames that need formatting
            format_lines = [
                line.strip()
                for line in output.splitlines()
                if line.strip() and not line.strip().startswith("The dotnet format command")
            ]
            if format_lines:
                has_issues = True
                results["format"] = (len(format_lines), format_lines)
            else:
                # Non-zero exit but no specific lines — still report
                has_issues = True
                results["format"] = (1, ["Code formatting issues detected"])
    except subprocess.TimeoutExpired:
        debug_log("Format check timed out")
    except Exception:
        pass
    return has_issues, results


def _format_dotnet_issues(file_path: Path, results: dict[str, tuple]) -> str:
    """Format .NET diagnostic issues as plain text."""
    lines: list[str] = []
    try:
        display_path = file_path.relative_to(Path.cwd())
    except ValueError:
        display_path = file_path
    lines.append(f".NET Issues found in: {display_path}")

    if "format" in results:
        count, format_lines = results["format"]
        plural = "file" if count == 1 else "files"
        lines.append(f"Format: {count} {plural} need formatting (run `dotnet format`)")
        for line in format_lines[:10]:
            lines.append(f"  {line}")
        if count > 10:
            lines.append(f"  ... and {count - 10} more")

    lines.append("Fix .NET issues above before continuing")
    return "\n".join(lines)
