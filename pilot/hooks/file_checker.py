"""Unified quality gate — file length + TDD enforcement in a single hook.

Runs both checks and produces one combined warning via additionalContext
to avoid duplicate system-reminders from multiple hooks in the same group.
Warnings are non-blocking — they inform but never prevent edits.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _checkers.charset import check_charset
from _checkers.go import check_go
from _checkers.python import check_python
from _checkers.tdd import (
    has_go_test_file,
    has_python_test_file,
    has_related_failing_test,
    has_typescript_test_file,
    is_test_file,
    is_trivial_edit,
    should_skip,
)
from _checkers.typescript import TS_EXTENSIONS, check_typescript
from _lib.util import find_git_root, post_tool_use_context


def _tdd_check(tool_name: str, tool_input: dict, file_path: str) -> str:
    """Run TDD enforcement, return warning message or empty string."""
    if should_skip(file_path) or is_test_file(file_path):
        return ""
    if is_trivial_edit(tool_name, tool_input):
        return ""

    if file_path.endswith(".py"):
        path = Path(file_path).parent
        for _ in range(10):
            if has_related_failing_test(str(path), file_path):
                return ""
            if path.parent == path:
                break
            path = path.parent
        if has_python_test_file(file_path):
            return ""
        module_name = Path(file_path).stem
        return f"TDD Reminder: No test file found for '{module_name}' module\n    Consider creating test_{module_name}.py first."

    if file_path.endswith((".ts", ".tsx")):
        if has_typescript_test_file(file_path):
            return ""
        base_name = Path(file_path).stem
        return f"TDD Reminder: No test file found for this module\n    Consider creating {base_name}.test.ts first."

    if file_path.endswith(".go"):
        if has_go_test_file(file_path):
            return ""
        base_name = Path(file_path).stem
        return f"TDD Reminder: No test file found\n    Consider creating {base_name}_test.go first."

    return ""


def _extract_file_paths(tool_input: dict) -> list[str]:
    """Extract file paths from tool_input for both CC and Codex formats.

    Claude Code Edit/Write: tool_input.file_path
    Codex apply_patch: tool_input.command with '*** Update File:' / '*** Add File:' markers
    """
    file_path = tool_input.get("file_path", "")
    if file_path:
        return [file_path]

    command = tool_input.get("command", "")
    if command:
        return [p.strip() for p in re.findall(r"\*\*\* (?:Update|Add) File:\s*(.+)", command)]

    return []


def main() -> int:
    """Single entry point — file quality + TDD in one pass."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    tool_name = hook_data.get("tool_name", "")
    tool_input = hook_data.get("tool_input", {})

    file_paths = _extract_file_paths(tool_input)
    if not file_paths:
        return 0

    git_root = find_git_root()
    if git_root:
        os.chdir(git_root)

    all_reasons: list[str] = []
    for file_path_str in file_paths:
        target_file = Path(file_path_str)
        if not target_file.exists():
            continue

        file_reason = ""
        if target_file.suffix == ".py":
            _, file_reason = check_python(target_file)
        elif target_file.suffix in TS_EXTENSIONS:
            _, file_reason = check_typescript(target_file)
        elif target_file.suffix == ".go":
            _, file_reason = check_go(target_file)

        tdd_reason = _tdd_check(tool_name, tool_input, file_path_str)
        charset_reason = check_charset(target_file)
        all_reasons.extend(r for r in (file_reason, tdd_reason, charset_reason) if r)

    if all_reasons:
        print(post_tool_use_context("\n".join(all_reasons)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
