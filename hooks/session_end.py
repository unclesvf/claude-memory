#!/usr/bin/env python3
"""
SessionEnd Hook for Claude Code
Fires when the session terminates (any reason: user exit, crash, timeout).

Writes a structured session summary to ~/.claude/sessions/. Complements
PreCompact (which handles mid-session compaction) by capturing the final
state when the session actually ends.

Also prunes old file_tracking.jsonl entries (>24h) and old .warm files.

Exits 0 always (cannot block termination).
"""
import json
import sys
import os
import time
from datetime import datetime
from pathlib import Path

SESSION_DIR = Path.home() / ".claude" / "sessions"
FILE_TRACKING = Path.home() / ".claude" / "file_tracking.jsonl"
MEMORIES_DIR = Path.home() / ".claude" / "memories"
MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-scott" / "memory"

MAX_TRACKING_AGE = 86400  # 24 hours


def extract_session_stats(transcript_path):
    """Extract basic stats from the transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    user_count = 0
    assistant_count = 0
    tool_count = 0
    files = set()

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    etype = entry.get("type", "")
                    role = entry.get("message", {}).get("role", "")

                    if etype == "user" or role == "user":
                        user_count += 1
                    elif etype == "assistant" or role == "assistant":
                        assistant_count += 1
                        # Count tool uses
                        content = entry.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_use":
                                    tool_count += 1
                                    fp = block.get("input", {}).get("file_path", "")
                                    if fp:
                                        files.add(fp)
                except (json.JSONDecodeError, KeyError):
                    continue
    except (OSError, PermissionError):
        return None

    return {
        "user_turns": user_count,
        "assistant_turns": assistant_count,
        "tool_calls": tool_count,
        "files_touched": sorted(files),
    }


def prune_tracking_log():
    """Remove file tracking entries older than 24 hours."""
    if not FILE_TRACKING.exists():
        return

    now = time.time()
    kept = []
    try:
        with open(FILE_TRACKING, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if now - entry.get("timestamp", 0) < MAX_TRACKING_AGE:
                        kept.append(line.strip())
                except (json.JSONDecodeError, KeyError):
                    continue

        # Rewrite with only recent entries
        tmp = str(FILE_TRACKING) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n" if kept else "")
        os.replace(tmp, str(FILE_TRACKING))
    except OSError:
        pass


def cleanup_warm_files():
    """Remove .warm temp files created by memory_search.py."""
    try:
        for f in MEMORY_DIR.glob("*.warm"):
            try:
                f.unlink()
            except OSError:
                pass
    except OSError:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    transcript_path = data.get("transcript_path", "")

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # Extract session stats
    stats = extract_session_stats(transcript_path)

    # Write session summary
    now = datetime.now()
    summary = {
        "session_id": session_id,
        "ended_at": now.isoformat(),
        "stats": stats,
    }

    summary_file = SESSION_DIR / f"session_{now.strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except OSError:
        pass

    # Prune old tracking entries
    prune_tracking_log()

    # Clean up .warm temp files
    cleanup_warm_files()

    # Prune old session summary files (keep last 20)
    try:
        session_files = sorted(SESSION_DIR.glob("session_*.json"))
        if len(session_files) > 20:
            for old_file in session_files[:-20]:
                try:
                    old_file.unlink()
                except OSError:
                    pass
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
