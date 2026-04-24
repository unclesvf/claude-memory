#!/usr/bin/env python3
"""
Telegram Memory Search — callable script for memory lookup on Telegram messages.

Since Telegram channel messages bypass the UserPromptSubmit hook, this script
provides the same memory search functionality as a standalone callable.

Usage:
    python telegram_memory_search.py "search query here"

Outputs matched memory file contents to stdout (same format as the hook).
"""
import json
import os
import re
import sys
import time
from pathlib import Path

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-yourname", "memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")
ACCESS_LOG = os.path.join(os.path.expanduser("~"), ".claude", "memory_access_log.json")
ATTN_STATE = os.path.join(os.path.expanduser("~"), ".claude", "attn_state.json")
COACTIVATION_LOG = os.path.join(os.path.expanduser("~"), ".claude", "coactivation_pairs.json")

# Import the scoring functions from the main hook
sys.path.insert(0, os.path.dirname(__file__))
from memory_search import (
    parse_index, score_entry, load_json, save_json,
    decay_all_scores, get_attention_score, extract_first_section,
    SIGNIFICANT_SHORT_KW, HOT_THRESHOLD, WARM_THRESHOLD,
)

STOP_WORDS = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
              "her", "was", "one", "our", "out", "has", "have", "been", "some", "them",
              "than", "its", "over", "also", "back", "into", "then", "what", "when",
              "how", "who", "why", "where", "which", "this", "that", "with", "from",
              "does", "did", "will", "would", "could", "should", "about", "just",
              "like", "use", "used", "using", "need", "want", "set", "get", "let",
              "see", "try", "make", "know", "take", "come", "give", "tell", "find"}


def main():
    # Fix Windows encoding
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("Usage: python telegram_memory_search.py 'search query'", file=sys.stderr)
        sys.exit(1)

    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt or len(prompt) < 3:
        sys.exit(0)

    entries = parse_index(MEMORY_INDEX)
    if not entries:
        sys.exit(0)

    words = set(re.findall(r"[a-z0-9]+", prompt.lower()))
    words = {w for w in words if (len(w) >= 3 or w in SIGNIFICANT_SHORT_KW) and w not in STOP_WORDS}
    compounds = set(re.findall(r"[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*", prompt.lower()))
    words.update(compounds)
    if not words:
        sys.exit(0)

    access_log = load_json(ACCESS_LOG)
    attn_state = load_json(ATTN_STATE, {"scores": {}, "last_update": 0})
    coact_pairs = load_json(COACTIVATION_LOG)

    # Don't decay on Telegram searches — only the main hook should decay
    # (otherwise Telegram messages would double-decay attention)

    # Two-pass scoring
    preliminary = []
    for entry in entries:
        s = score_entry(entry, words, access_log, attn_state, {}, [])
        if s >= 2:
            preliminary.append((s, entry))
    preliminary.sort(key=lambda x: x[0], reverse=True)
    already_matched = [e["file"] for _, e in preliminary[:5]]

    scored = []
    for entry in entries:
        s = score_entry(entry, words, access_log, attn_state, coact_pairs, already_matched)
        if s >= 4:
            scored.append((s, entry))

    if not scored:
        print("No memory matches.", file=sys.stderr)
        sys.exit(0)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]

    for score, entry in top:
        full_path = os.path.join(MEMORY_DIR, entry["file"])
        if os.path.exists(full_path):
            attention = get_attention_score(entry["file"], attn_state)

            # Determine content to show
            if attention >= HOT_THRESHOLD:
                try:
                    content = open(full_path, "r", encoding="utf-8").read()
                except OSError:
                    continue
            elif attention >= WARM_THRESHOLD:
                content = extract_first_section(full_path) or open(full_path, "r", encoding="utf-8").read()
            else:
                try:
                    content = open(full_path, "r", encoding="utf-8").read()
                except OSError:
                    continue

            # Truncate if very long
            if len(content) > 3000:
                content = content[:3000] + "\n\n[... truncated]"

            print(f"[Memory: {entry['name']} (score={score:.1f}, attn={attention:.2f})]")
            print(content)
            print("---")

            # Update access log
            access_log[entry["file"]] = time.time()

    save_json(ACCESS_LOG, access_log)


if __name__ == "__main__":
    main()
