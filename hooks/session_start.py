#!/usr/bin/env python3
"""
SessionStart Hook for Claude Code
Fires when a new session begins or resumes after compaction.

If a recovery file exists from a previous PreCompact save, outputs its
contents so Claude automatically knows what was being worked on.

Only injects context when the session started due to compaction or a fresh
startup (not on /clear or resume, where context is already available).
"""
import json
import sys
import os
import time
from pathlib import Path

SESSION_DIR = Path.home() / ".claude" / "sessions"
RECOVERY_FILE = SESSION_DIR / "last_session.md"
# Max age in seconds before we consider the recovery file stale (1 hour)
MAX_AGE_SECONDS = 3600


def main():
    # Read hook input
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    source = data.get("source", "")

    # Only inject recovery context on startup or after compaction
    # "resume" already has context, "clear" means user wants a fresh start
    if source not in ("startup", "compact"):
        sys.exit(0)

    # Check if recovery file exists
    if not RECOVERY_FILE.exists():
        sys.exit(0)

    # Check if recovery file is recent enough to be useful
    try:
        age = time.time() - RECOVERY_FILE.stat().st_mtime
    except OSError:
        sys.exit(0)

    if age > MAX_AGE_SECONDS:
        sys.exit(0)

    # Read and output the recovery file
    try:
        content = RECOVERY_FILE.read_text(encoding="utf-8")
    except OSError:
        sys.exit(0)

    if not content.strip():
        sys.exit(0)

    # Output as additional context for Claude
    # Plain text to stdout gets injected into Claude's context
    print(f"[Session Recovery] Previous session state recovered:\n\n{content}")

    sys.exit(0)


if __name__ == "__main__":
    main()
