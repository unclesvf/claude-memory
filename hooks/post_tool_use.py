#!/usr/bin/env python3
"""
PostToolUse Hook for Claude Code
Fires after every successful tool call. Silently tracks file operations
(Read, Edit, Write) by appending to a JSONL log.

This data feeds into:
  - Stop hook (knows which files were touched this session)
  - Attention scoring (co-activation: files accessed together boost each other)
  - Memory search (recency boost from real file access, not just keyword match)

Zero interruption to Claude — async-compatible, fast, append-only.
Exits 0 always.
"""
import json
import sys
import os
import time
from pathlib import Path

FILE_TRACKING = Path.home() / ".claude" / "file_tracking.jsonl"
ATTN_STATE = Path.home() / ".claude" / "attn_state.json"
COACTIVATION_LOG = Path.home() / ".claude" / "coactivation_pairs.json"

# Tools that touch files
FILE_TOOLS = {"Read", "Edit", "Write"}
# Max age for tracking entries (24 hours) — older entries pruned on write
MAX_AGE = 86400
# Co-activation window: files accessed within this many seconds are "together"
COACTIVATION_WINDOW = 120  # 2 minutes


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only track file operations
    if tool_name not in FILE_TOOLS:
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    now = time.time()

    # Append to tracking log
    entry = {
        "timestamp": now,
        "tool": tool_name,
        "file_path": file_path,
    }

    try:
        FILE_TRACKING.parent.mkdir(parents=True, exist_ok=True)
        with open(FILE_TRACKING, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    # Update attention state — boost this file to HOT
    update_attention(file_path, now)

    # Update co-activation pairs — files accessed close together
    update_coactivation(file_path, now)

    sys.exit(0)


def update_attention(file_path, now):
    """Boost the attention score of the accessed file to 1.0 (HOT)."""
    try:
        if ATTN_STATE.exists():
            with open(ATTN_STATE, "r", encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = {"scores": {}, "last_update": now}

        state["scores"][file_path] = {
            "score": 1.0,
            "last_access": now,
        }
        state["last_update"] = now

        # Atomic write
        tmp = str(ATTN_STATE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, str(ATTN_STATE))
    except (OSError, json.JSONDecodeError):
        pass


def update_coactivation(file_path, now):
    """Track co-activation: files accessed within 2 min of each other are related."""
    try:
        # Read recent entries from tracking log to find co-activated files
        recent_files = []
        if FILE_TRACKING.exists():
            with open(FILE_TRACKING, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if now - entry.get("timestamp", 0) < COACTIVATION_WINDOW:
                            fp = entry.get("file_path", "")
                            if fp and fp != file_path:
                                recent_files.append(fp)
                    except (json.JSONDecodeError, KeyError):
                        continue

        if not recent_files:
            return

        # Load or create co-activation pairs
        if COACTIVATION_LOG.exists():
            with open(COACTIVATION_LOG, "r", encoding="utf-8") as f:
                pairs = json.load(f)
        else:
            pairs = {}

        # Record bidirectional pairs
        for other in set(recent_files):
            key_ab = f"{file_path}||{other}"
            key_ba = f"{other}||{file_path}"
            # Use canonical ordering
            key = key_ab if file_path < other else key_ba

            if key not in pairs:
                pairs[key] = {"count": 0, "first_seen": now, "last_seen": now}
            pairs[key]["count"] += 1
            pairs[key]["last_seen"] = now

        # Atomic write
        tmp = str(COACTIVATION_LOG) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pairs, f, indent=2)
        os.replace(tmp, str(COACTIVATION_LOG))

    except (OSError, json.JSONDecodeError):
        pass


if __name__ == "__main__":
    main()
