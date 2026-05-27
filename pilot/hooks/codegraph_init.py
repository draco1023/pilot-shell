"""SessionStart hook: ensure CodeGraph is initialized and synced for the current project.

Mirrors the logic from launcher/codegraph.py ensure_codegraph(), adapted as a
hook script. Runs on both Claude Code (async) and Codex CLI (sync) SessionStart.

Non-fatal: failures are silent — the session proceeds without CodeGraph.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _is_in_git_repo(directory: Path) -> bool:
    current = directory.resolve()
    while True:
        if (current / ".git").exists():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _has_git_commits(directory: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            cwd=directory,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _enable_embeddings(project_dir: Path) -> None:
    config_path = project_dir / ".codegraph" / "config.json"
    if not config_path.exists():
        return
    try:
        config = json.loads(config_path.read_text())
        if config.get("enableEmbeddings") is True:
            return
        config["enableEmbeddings"] = True
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    except (json.JSONDecodeError, OSError):
        pass


def _is_indexed(project_dir: Path) -> bool:
    db_path = project_dir / ".codegraph" / "codegraph.db"
    if not db_path.exists():
        return False
    try:
        return db_path.stat().st_size > 1_000_000
    except OSError:
        return False


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> bool:
    try:
        result = subprocess.run(cmd, capture_output=True, cwd=cwd, timeout=timeout)
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _is_corrupt_db_error(stderr: str) -> bool:
    lower = stderr.lower()
    return (
        "database disk image is malformed" in lower
        or "file is not a database" in lower
        or "database is corrupt" in lower
        or "sqlite_corrupt" in lower
    )


def _recover_corrupt_db(project_dir: Path) -> bool:
    codegraph_dir = project_dir / ".codegraph"
    if not codegraph_dir.exists():
        return False
    try:
        shutil.rmtree(codegraph_dir)
    except OSError:
        return False
    return True


def _is_using_wasm_sqlite() -> bool:
    try:
        result = subprocess.run(
            ["codegraph", "status"],
            capture_output=True,
            timeout=10,
        )
        output = (result.stdout or b"").decode("utf-8", errors="replace")
        output += (result.stderr or b"").decode("utf-8", errors="replace")
        return "WASM SQLite backend" in output
    except (subprocess.SubprocessError, OSError):
        return False


def _find_codegraph_package_dir() -> Path | None:
    codegraph_bin = shutil.which("codegraph")
    if not codegraph_bin:
        return None
    try:
        real_path = Path(codegraph_bin).resolve()
        current = real_path.parent
        for _ in range(5):
            pkg_json = current / "package.json"
            if pkg_json.exists():
                try:
                    pkg = json.loads(pkg_json.read_text())
                    if pkg.get("name") == "@colbymchenry/codegraph":
                        return current
                except (json.JSONDecodeError, OSError):
                    pass
            parent = current.parent
            if parent == current:
                break
            current = parent
    except (OSError, ValueError):
        pass
    return None


def _repair_native_sqlite() -> bool:
    pkg_dir = _find_codegraph_package_dir()
    if pkg_dir and (pkg_dir / "node_modules" / "better-sqlite3").exists():
        try:
            result = subprocess.run(
                ["npm", "rebuild", "better-sqlite3"],
                capture_output=True,
                cwd=pkg_dir,
                timeout=180,
            )
            if result.returncode == 0:
                return True
        except (subprocess.SubprocessError, OSError):
            pass
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "better-sqlite3", "--no-audit", "--no-fund"],
            capture_output=True,
            timeout=180,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _get_project_dir() -> Path:
    for var in ("CODEX_WORKSPACE", "CLAUDE_PROJECT_ROOT"):
        val = os.environ.get(var, "").strip()
        if val:
            return Path(val)
    return Path.cwd()


def main() -> None:
    if not shutil.which("codegraph"):
        return

    project_dir = _get_project_dir()

    if not _is_in_git_repo(project_dir):
        return
    if not _has_git_commits(project_dir):
        return

    if _is_using_wasm_sqlite():
        _repair_native_sqlite()

    codegraph_dir = project_dir / ".codegraph"

    if not codegraph_dir.exists():
        if not _run(["codegraph", "init"], project_dir, timeout=60):
            return
        if not codegraph_dir.exists():
            return

    _enable_embeddings(project_dir)

    if not _is_indexed(project_dir):
        _run(["codegraph", "index"], project_dir, timeout=600)
        return

    result = subprocess.run(
        ["codegraph", "sync"],
        capture_output=True,
        cwd=project_dir,
        timeout=120,
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        if _is_corrupt_db_error(stderr) and _recover_corrupt_db(project_dir):
            _run(["codegraph", "init", "-i"], project_dir, timeout=600)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    finally:
        sys.exit(0)
