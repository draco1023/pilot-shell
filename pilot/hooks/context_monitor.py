#!/usr/bin/env python3
"""Context monitor - warns when context usage is high."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import (
    _get_compaction_threshold_pct,
    _get_max_context_tokens,
    get_session_cache_path,
    post_tool_use_context,
)

THRESHOLD_WARN = 65
THRESHOLD_AUTOCOMPACT = 75


def _to_effective(raw_pct: float) -> float:
    """Convert raw context % to effective % (where compaction threshold = 100%).

    Post-v12: per-skill orchestrator-window scaling is removed (per-skill model
    selection no longer exists in config.json). The cached pct from
    _resolve_context is in the main-session frame and the main-session
    compaction threshold is the right calibration.
    """
    return min(raw_pct / _get_compaction_threshold_pct() * 100, 100)


def _get_pilot_session_id() -> str:
    """Get Pilot session ID from environment."""
    return os.environ.get("PILOT_SESSION_ID", "").strip() or "unknown"


def get_session_flags(session_id: str) -> bool:
    """Get shown_80_warn flag for this session."""
    if get_session_cache_path().exists():
        try:
            with get_session_cache_path().open() as f:
                cache = json.load(f)
                if cache.get("session_id") == session_id:
                    return cache.get("shown_80_warn", False)
        except (json.JSONDecodeError, OSError):
            pass
    return False


def save_cache(tokens: int, session_id: str, shown_80_warn: bool | None = None) -> None:
    """Save context calculation to cache with session ID."""
    existing_80_warn = False
    if get_session_cache_path().exists():
        try:
            with get_session_cache_path().open() as f:
                cache = json.load(f)
                if cache.get("session_id") == session_id:
                    existing_80_warn = cache.get("shown_80_warn", False)
        except (json.JSONDecodeError, OSError):
            pass

    if shown_80_warn:
        existing_80_warn = True

    try:
        with get_session_cache_path().open("w") as f:
            json.dump(
                {
                    "tokens": tokens,
                    "timestamp": time.time(),
                    "session_id": session_id,
                    "shown_80_warn": existing_80_warn,
                },
                f,
            )
    except OSError:
        pass


def _read_statusline_context_pct() -> float | None:
    """Read authoritative context percentage from statusline cache.

    Returns None if cache is missing, corrupt, or stale (>60s).
    Cache is already scoped per Pilot session via PILOT_SESSION_ID.
    """
    pilot_session_id = os.environ.get("PILOT_SESSION_ID", "").strip()
    if not pilot_session_id:
        return None
    cache_file = Path.home() / ".pilot" / "sessions" / pilot_session_id / "context-pct.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        ts = data.get("ts")
        if ts is None or time.time() - ts > 60:
            return None
        pct = data.get("pct")
        return float(pct) if pct is not None else None
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


def _is_throttled(session_id: str) -> bool:
    """Check if context monitoring should be throttled (skipped).

    Returns True if:
    - Last check was < 30 seconds ago AND
    - Last cached context was below the warning threshold (~80% effective)

    Always returns False at high context (never throttle when approaching compaction).

    Orchestrator-aware: when a /spec orchestrator with a smaller window than main
    is active, the percentage is computed against the orchestrator's window so the
    throttle releases earlier — preventing silent skip when the orchestrator is
    already past its real compact point even though the main-frame pct looks low.
    """
    cache_path = get_session_cache_path()
    if not cache_path.exists():
        return False

    try:
        with cache_path.open() as f:
            cache = json.load(f)
            if cache.get("session_id") != session_id:
                return False

            timestamp = cache.get("timestamp")
            if timestamp is None:
                return False

            if time.time() - timestamp < 30:
                tokens = cache.get("tokens", 0)
                active_window = _get_max_context_tokens()
                percentage = (tokens / active_window) * 100
                if percentage < THRESHOLD_WARN:
                    return True

            return False
    except (json.JSONDecodeError, OSError, KeyError):
        return False


_CODEX_MODEL_WINDOWS: dict[str, int] = {
    "gpt-4.1": 1_000_000,
    "gpt-4.1-mini": 1_000_000,
    "gpt-4.1-nano": 1_000_000,
    "o4-mini": 200_000,
    "o3": 200_000,
    "codex-mini-latest": 200_000,
}
_CODEX_DEFAULT_WINDOW = 200_000


def _estimate_codex_context_pct(transcript_path: str, model: str) -> float | None:
    """Estimate context usage from Codex transcript file size.

    Uses file_size / 4 as a rough token estimate. Approximate but sufficient
    for threshold-based warnings. Returns None if file is unavailable.
    """
    if not transcript_path:
        return None
    try:
        file_size = os.path.getsize(transcript_path)
    except OSError:
        return None
    estimated_tokens = file_size // 4
    window = _CODEX_MODEL_WINDOWS.get(model, _CODEX_DEFAULT_WINDOW)
    pct = estimated_tokens / window * 100
    if pct > 100:
        return None
    return pct


def _resolve_context(
    session_id: str,
    transcript_path: str | None = None,
    model: str | None = None,
) -> tuple[float, int, bool] | None:
    """Resolve context percentage and tokens. Returns (pct, tokens, shown_80) or None.

    Tries Claude Code's statusline cache first, then falls back to Codex
    transcript file estimation when transcript_path and model are provided.
    """
    statusline_pct = _read_statusline_context_pct()
    if statusline_pct is not None:
        main_window = _get_max_context_tokens()
        shown_80_warn = get_session_flags(session_id)
        return statusline_pct, int(statusline_pct / 100 * main_window), shown_80_warn

    if transcript_path and model:
        codex_pct = _estimate_codex_context_pct(transcript_path, model)
        if codex_pct is not None:
            window = _CODEX_MODEL_WINDOWS.get(model, _CODEX_DEFAULT_WINDOW)
            tokens = int(codex_pct / 100 * window)
            shown_80_warn = get_session_flags(session_id)
            return codex_pct, tokens, shown_80_warn

    return None


def run_context_monitor() -> int:
    """Run context monitoring. Always returns 0. Uses additionalContext JSON for all messages."""
    hook_data: dict = {}
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        pass

    session_id = _get_pilot_session_id()

    if _is_throttled(session_id):
        return 0

    transcript_path = hook_data.get("transcript_path")
    model = hook_data.get("model", "")

    resolved = _resolve_context(session_id, transcript_path=transcript_path, model=model)
    if resolved is None:
        return 0

    percentage, total_tokens, shown_80_warn = resolved
    effective = _to_effective(percentage)

    save_cache(total_tokens, session_id)

    if percentage >= THRESHOLD_AUTOCOMPACT:
        print(
            post_tool_use_context(
                f"Context at {effective:.0f}%. Auto-compact approaching — no context is lost. "
                f"Continue all workflow steps normally. Do NOT skip steps, sub-agents, or verification."
            )
        )
        return 0

    if percentage >= THRESHOLD_WARN and not shown_80_warn:
        save_cache(total_tokens, session_id, shown_80_warn=True)
        print(
            post_tool_use_context(
                f"Context at {effective:.0f}%. Auto-compact will handle context automatically. "
                f"Continue working normally."
            )
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(run_context_monitor())
