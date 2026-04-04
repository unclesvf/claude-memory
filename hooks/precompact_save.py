#!/usr/bin/env python3
"""
PreCompact Hook for Claude Code
Runs before context compression — saves a session snapshot so the next
session (or post-compression context) knows what was being worked on.

Reads the conversation transcript, extracts recent activity, and writes
a recovery file that memory_search.py or Claude can read on next session.

Exits 0 always (cannot block compaction).
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-scott" / "memory"
SESSION_DIR = Path.home() / ".claude" / "sessions"
RECOVERY_FILE = SESSION_DIR / "last_session.md"
COMPACTION_LOG = SESSION_DIR / "compaction_log.jsonl"


def extract_recent_activity(transcript_path, max_lines=200):
    """Parse the JSONL transcript to extract recent user messages and tool usage.

    Claude Code transcript format:
    - Each line is a JSON object with "type" field ("user", "assistant", etc.)
    - The actual message is nested under "message" with "role" and "content"
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    entries = []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except (OSError, PermissionError):
        return None

    if not entries:
        return None

    # Extract user messages (last 10)
    user_messages = []
    for entry in entries:
        if entry.get("type") == "user":
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content
                              if isinstance(p, dict) and p.get("type") == "text"]
                content = " ".join(text_parts)
            if isinstance(content, str) and len(content.strip()) > 5:
                user_messages.append(content.strip()[:500])

    # Extract tool calls from recent assistant messages
    tools_used = []
    files_touched = set()
    for entry in entries[-60:]:
        if entry.get("type") == "assistant":
            msg = entry.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})

                        if tool_name in ("Edit", "Write", "Read"):
                            fp = tool_input.get("file_path", "")
                            if fp:
                                files_touched.add(fp)
                                tools_used.append(f"{tool_name}: {fp}")
                        elif tool_name == "Bash":
                            cmd = tool_input.get("command", "")[:200]
                            if cmd:
                                tools_used.append(f"Bash: {cmd}")
                        elif tool_name in ("Glob", "Grep"):
                            pattern = tool_input.get("pattern", "")
                            tools_used.append(f"{tool_name}: {pattern}")

    return {
        "user_messages": user_messages[-10:],
        "tools_used": tools_used[-20:],
        "files_touched": sorted(files_touched),
    }


def build_recovery_markdown(activity, session_id, trigger, cwd):
    """Build a markdown recovery file from extracted activity."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# Session Snapshot — {now}",
        f"",
        f"**Session:** {session_id}",
        f"**Working Directory:** {cwd}",
        f"**Compaction Trigger:** {trigger}",
        f"",
    ]

    if activity and activity["user_messages"]:
        lines.append("## What Was Being Worked On")
        lines.append("")
        # Last 5 user messages give the best picture
        for msg in activity["user_messages"][-5:]:
            # Truncate long messages
            preview = msg[:200].replace("\n", " ")
            lines.append(f"- {preview}")
        lines.append("")

    if activity and activity["files_touched"]:
        lines.append("## Files Touched")
        lines.append("")
        for fp in activity["files_touched"][-15:]:
            lines.append(f"- `{fp}`")
        lines.append("")

    if activity and activity["tools_used"]:
        lines.append("## Recent Actions")
        lines.append("")
        for tool in activity["tools_used"][-10:]:
            lines.append(f"- {tool}")
        lines.append("")

    return "\n".join(lines)


def main():
    # Read hook input
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    transcript_path = data.get("transcript_path", "")
    trigger = data.get("trigger", "unknown")
    cwd = data.get("cwd", "")

    # Ensure session directory exists
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # Extract recent activity from transcript
    activity = extract_recent_activity(transcript_path)

    # Build and save recovery file
    recovery_md = build_recovery_markdown(activity, session_id, trigger, cwd)
    try:
        RECOVERY_FILE.write_text(recovery_md, encoding="utf-8")
    except OSError:
        pass

    # Append to compaction log
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "trigger": trigger,
        "cwd": cwd,
        "user_messages_count": len(activity["user_messages"]) if activity else 0,
        "files_touched_count": len(activity["files_touched"]) if activity else 0,
    }
    try:
        with open(COMPACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
