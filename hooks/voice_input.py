#!/usr/bin/env python3
"""
Voice Input Hook — checks for new F9 voice transcriptions.
Runs on UserPromptSubmit. If new voice input exists, injects it into context.
"""
import json
import os
import sys
from pathlib import Path

VOICE_INPUT = Path.home() / ".claude" / "voice" / "voice_input.jsonl"
VOICE_CURSOR = Path.home() / ".claude" / "voice" / "voice_cursor.txt"


def main():
    if not VOICE_INPUT.exists():
        return

    # Read cursor (last processed line number)
    cursor = 0
    if VOICE_CURSOR.exists():
        try:
            cursor = int(VOICE_CURSOR.read_text().strip())
        except (ValueError, OSError):
            cursor = 0

    # Read new lines
    lines = VOICE_INPUT.read_text(encoding="utf-8").strip().splitlines()
    new_lines = lines[cursor:]

    if not new_lines:
        return

    # Extract text from new entries
    messages = []
    for line in new_lines:
        try:
            entry = json.loads(line)
            text = entry.get("text", "").strip()
            if text:
                messages.append(text)
        except json.JSONDecodeError:
            continue

    # Update cursor
    VOICE_CURSOR.write_text(str(len(lines)))

    if not messages:
        return

    # Deduplicate consecutive identical messages
    deduped = [messages[0]]
    for msg in messages[1:]:
        if msg != deduped[-1]:
            deduped.append(msg)

    # Output for Claude's context
    output = "[Voice Input via F9] " + " | ".join(deduped)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Never block the prompt
