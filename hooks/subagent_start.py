#!/usr/bin/env python3
"""
SubagentStart Hook for Claude Code
Fires when a subagent is spawned via the Task tool. Reads the subagent's
task description, matches against the memory index, and injects the top
matching topic file contents so subagents have relevant context.

This prevents subagents from operating blind — they get the same memory
context as the main agent for their specific task.

Exits 0 always.
"""
import json
import sys
import os
import re
from pathlib import Path

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-scott", "memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")


def parse_index(index_path):
    """Parse the Project Index section of MEMORY.md into entries."""
    entries = []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return entries

    pattern_5 = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(\d{1,2})\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )
    pattern_4 = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )

    matched_positions = set()
    for m in pattern_5.finditer(content):
        matched_positions.add(m.start())
        importance = max(1, min(10, int(m.group(3))))
        entries.append({
            "name": m.group(1).strip(),
            "importance": importance,
            "keywords": [k.strip().lower() for k in m.group(4).split()],
            "file": m.group(6).strip(),
        })

    for m in pattern_4.finditer(content):
        if m.start() in matched_positions:
            continue
        entries.append({
            "name": m.group(1).strip(),
            "importance": 5,
            "keywords": [k.strip().lower() for k in m.group(3).split()],
            "file": m.group(5).strip(),
        })

    return entries


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # The subagent's task description/prompt
    task_prompt = data.get("task_prompt", "") or data.get("prompt", "")
    if not task_prompt or len(task_prompt) < 5:
        sys.exit(0)

    entries = parse_index(MEMORY_INDEX)
    if not entries:
        sys.exit(0)

    words = set(re.findall(r"[a-z0-9]+", task_prompt.lower()))
    words = {w for w in words if len(w) >= 3}
    if not words:
        sys.exit(0)

    # Score entries
    scored = []
    for entry in entries:
        score = 0
        name_lower = entry["name"].lower()
        for word in words:
            if word in entry["keywords"]:
                score += 3
            elif any(word in kw or kw in word for kw in entry["keywords"]):
                score += 2
            if word in name_lower:
                score += 2

        importance_mult = entry["importance"] / 5.0
        final = score * importance_mult

        if final >= 4:
            scored.append((final, entry))

    if not scored:
        sys.exit(0)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:2]  # Inject max 2 files to keep subagent context lean

    output_parts = ["[Memory Context for Subagent]"]
    for score, entry in top:
        full_path = os.path.join(MEMORY_DIR, entry["file"])
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read(3000)  # Cap at 3KB per file
                output_parts.append(f"\n--- {entry['name']} (relevance: {score:.1f}) ---")
                output_parts.append(content)
            except OSError:
                continue

    if len(output_parts) > 1:
        output = "\n".join(output_parts)
        # Windows cp1252 can't handle Unicode arrows etc — force utf-8
        sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
