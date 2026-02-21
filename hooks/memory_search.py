#!/usr/bin/env python3
"""
Memory Search Hook for Claude Code
Runs on UserPromptSubmit — greps the MEMORY.md keyword index
against the user's message and writes matching topic file paths
to a temp file. Claude reads this file to load relevant context.

Exits 0 always (never blocks the prompt).
"""
import json
import sys
import os
import re

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-scott", "memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")
RESULT_FILE = os.path.join(os.path.expanduser("~"), ".claude", "memory_search_result.txt")


def parse_index(index_path):
    """Parse the Project Index section of MEMORY.md into entries."""
    entries = []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return entries

    pattern = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )
    for m in pattern.finditer(content):
        entries.append({
            "name": m.group(1).strip(),
            "status": m.group(2).strip(),
            "keywords": [k.strip().lower() for k in m.group(3).split()],
            "file": m.group(5).strip(),
        })
    return entries


def score_entry(entry, words):
    """Score an entry against the user's message words."""
    score = 0
    name_lower = entry["name"].lower()
    keywords = entry["keywords"]

    for word in words:
        if word in keywords:
            score += 3
        elif any(word in kw or kw in word for kw in keywords):
            score += 2
        if word in name_lower:
            score += 2

    return score


def main():
    # Clear previous results
    try:
        os.remove(RESULT_FILE)
    except FileNotFoundError:
        pass

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    prompt = data.get("prompt", "").strip()
    if not prompt or len(prompt) < 3:
        sys.exit(0)

    entries = parse_index(MEMORY_INDEX)
    if not entries:
        sys.exit(0)

    words = set(re.findall(r"[a-z0-9]+", prompt.lower()))
    words = {w for w in words if len(w) >= 3}

    if not words:
        sys.exit(0)

    scored = []
    for entry in entries:
        s = score_entry(entry, words)
        if s >= 4:
            scored.append((s, entry))

    if not scored:
        sys.exit(0)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]

    lines = []
    for score, entry in top:
        full_path = os.path.join(MEMORY_DIR, entry["file"])
        if os.path.exists(full_path):
            lines.append(f"{entry['name']}|{full_path}|{score}")

    if lines:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    sys.exit(0)


if __name__ == "__main__":
    main()
