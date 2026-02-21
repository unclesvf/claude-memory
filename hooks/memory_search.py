#!/usr/bin/env python3
"""
Memory Search Hook for Claude Code
Runs on UserPromptSubmit — greps the MEMORY.md keyword index
against the user's message and writes matching topic file paths
to a temp file. Claude reads this file to load relevant context.

Scoring combines three signals:
  1. Keyword match score (0-15+) — exact match=3, partial=2, name=2
  2. Importance weight (1-10, default 5) — set per entry in MEMORY.md
  3. Recency boost — files accessed recently score higher

Exits 0 always (never blocks the prompt).
"""
import json
import sys
import os
import re
import time

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-scott", "memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")
RESULT_FILE = os.path.join(os.path.expanduser("~"), ".claude", "memory_search_result.txt")
ACCESS_LOG = os.path.join(os.path.expanduser("~"), ".claude", "memory_access_log.json")

# Recency decay: files accessed within these windows get a boost
RECENCY_WINDOWS = [
    (3600, 3.0),       # Last hour: +3
    (14400, 2.0),      # Last 4 hours: +2
    (86400, 1.0),      # Last 24 hours: +1
]


def load_access_log():
    """Load the access log tracking when each topic file was last used."""
    try:
        with open(ACCESS_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_access_log(log):
    """Save the access log."""
    try:
        with open(ACCESS_LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    except OSError:
        pass


def recency_score(filename, access_log):
    """Calculate recency boost based on when the file was last accessed."""
    last_access = access_log.get(filename, 0)
    if last_access == 0:
        return 0
    age = time.time() - last_access
    for window, boost in RECENCY_WINDOWS:
        if age <= window:
            return boost
    return 0


def parse_index(index_path):
    """Parse the Project Index section of MEMORY.md into entries.

    Supports two formats:
      **Name** | Status | keywords | [file](file.md)
      **Name** | Status | importance | keywords | [file](file.md)

    Where importance is a single digit 1-10.
    """
    entries = []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return entries

    # Try 5-field format first (with importance)
    pattern_5 = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(\d{1,2})\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )
    # Then 4-field format (without importance)
    pattern_4 = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )

    matched_positions = set()

    for m in pattern_5.finditer(content):
        matched_positions.add(m.start())
        importance = int(m.group(3))
        importance = max(1, min(10, importance))
        entries.append({
            "name": m.group(1).strip(),
            "status": m.group(2).strip(),
            "importance": importance,
            "keywords": [k.strip().lower() for k in m.group(4).split()],
            "file": m.group(6).strip(),
        })

    for m in pattern_4.finditer(content):
        if m.start() in matched_positions:
            continue
        entries.append({
            "name": m.group(1).strip(),
            "status": m.group(2).strip(),
            "importance": 5,
            "keywords": [k.strip().lower() for k in m.group(3).split()],
            "file": m.group(5).strip(),
        })

    return entries


def score_entry(entry, words, access_log):
    """Score an entry against the user's message words.

    Final score = keyword_score * (importance / 5) + recency_boost
    """
    keyword_score = 0
    name_lower = entry["name"].lower()
    keywords = entry["keywords"]

    for word in words:
        if word in keywords:
            keyword_score += 3
        elif any(word in kw or kw in word for kw in keywords):
            keyword_score += 2
        if word in name_lower:
            keyword_score += 2

    # Importance multiplier: importance=5 is neutral (1.0x), 10 is 2.0x, 1 is 0.2x
    importance_mult = entry["importance"] / 5.0
    weighted_score = keyword_score * importance_mult

    # Recency boost
    recency = recency_score(entry["file"], access_log)
    final_score = weighted_score + recency

    return final_score


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

    access_log = load_access_log()

    scored = []
    for entry in entries:
        s = score_entry(entry, words, access_log)
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
            lines.append(f"{entry['name']}|{full_path}|{score:.1f}")
            # Update access log
            access_log[entry["file"]] = time.time()

    if lines:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        save_access_log(access_log)

    sys.exit(0)


if __name__ == "__main__":
    main()
