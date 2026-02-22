#!/usr/bin/env python3
"""
Memory Search Hook for Claude Code (v2 — attention decay + co-activation)
Runs on UserPromptSubmit — matches user's message against the MEMORY.md
keyword index and injects relevant topic files into Claude's context.

Scoring combines FIVE signals:
  1. Keyword match score (0-15+) — exact match=3, partial=2, name=2
  2. Importance weight (1-10, default 5) — set per entry in MEMORY.md
  3. Recency boost — files accessed recently score higher
  4. Attention score (0.0-1.0) — decays 15% per turn, boosted by file access
  5. Co-activation boost — files frequently accessed together warm each other

Injection tiers (from claude-cognitive):
  - HOT (attention > 0.8): Full file content injected
  - WARM (attention 0.25-0.8): First section only (up to first ## heading)
  - COLD (attention < 0.25): Skipped entirely

Exits 0 always (never blocks the prompt).
"""
import json
import sys
import os
import re
import time
from pathlib import Path

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-scott", "memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")
RESULT_FILE = os.path.join(os.path.expanduser("~"), ".claude", "memory_search_result.txt")
ACCESS_LOG = os.path.join(os.path.expanduser("~"), ".claude", "memory_access_log.json")
ATTN_STATE = os.path.join(os.path.expanduser("~"), ".claude", "attn_state.json")
COACTIVATION_LOG = os.path.join(os.path.expanduser("~"), ".claude", "coactivation_pairs.json")

# Attention decay rate per search invocation (15%)
DECAY_RATE = 0.15

# Attention tiers
HOT_THRESHOLD = 0.8
WARM_THRESHOLD = 0.25

# Recency decay windows
RECENCY_WINDOWS = [
    (3600, 3.0),       # Last hour: +3
    (14400, 2.0),      # Last 4 hours: +2
    (86400, 1.0),      # Last 24 hours: +1
]


def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def recency_score(filename, access_log):
    last_access = access_log.get(filename, 0)
    if last_access == 0:
        return 0
    age = time.time() - last_access
    for window, boost in RECENCY_WINDOWS:
        if age <= window:
            return boost
    return 0


def get_attention_score(filename, attn_state):
    """Get the current attention score for a file (0.0-1.0)."""
    scores = attn_state.get("scores", {})
    # Check both full path and just the filename
    full_path = os.path.join(MEMORY_DIR, filename)
    for key in (filename, full_path):
        if key in scores:
            return scores[key].get("score", 0.0)
    return 0.0


def get_coactivation_boost(filename, matched_files, pairs):
    """Get co-activation boost from files that are already matched."""
    boost = 0.0
    full_path = os.path.join(MEMORY_DIR, filename)
    for other_file in matched_files:
        other_full = os.path.join(MEMORY_DIR, other_file)
        # Check both orderings of the pair key
        for a, b in [(full_path, other_full), (filename, other_file)]:
            key_ab = f"{a}||{b}"
            key_ba = f"{b}||{a}"
            canonical = key_ab if a < b else key_ba
            if canonical in pairs:
                count = pairs[canonical].get("count", 0)
                # Logarithmic boost: more co-accesses = stronger, but diminishing
                if count > 0:
                    import math
                    boost += min(2.0, math.log2(count + 1))
    return boost


def decay_all_scores(attn_state):
    """Apply 15% decay to all attention scores."""
    scores = attn_state.get("scores", {})
    for key in list(scores.keys()):
        old_score = scores[key].get("score", 0.0)
        new_score = old_score * (1 - DECAY_RATE)
        if new_score < 0.01:
            # Evict fully cold entries to keep state file small
            del scores[key]
        else:
            scores[key]["score"] = round(new_score, 4)
    attn_state["scores"] = scores
    return attn_state


def parse_index(index_path):
    """Parse the Project Index section of MEMORY.md into entries."""
    entries = []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return entries

    # 5-field format (with importance)
    pattern_5 = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(\d{1,2})\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )
    # 4-field format (without importance)
    pattern_4 = re.compile(
        r"\*\*(.+?)\*\*\s*\|\s*(\w[\w\s]*?)\s*\|\s*(.+?)\s*\|\s*\[(.+?)\]\((.+?)\)"
    )

    matched_positions = set()

    for m in pattern_5.finditer(content):
        matched_positions.add(m.start())
        importance = max(1, min(10, int(m.group(3))))
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


def score_entry(entry, words, access_log, attn_state, coact_pairs, already_matched):
    """Score an entry against the user's message.

    Final score = (keyword_score * importance_mult) + recency + attention + coactivation
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

    importance_mult = entry["importance"] / 5.0
    weighted_keyword = keyword_score * importance_mult
    recency = recency_score(entry["file"], access_log)
    attention = get_attention_score(entry["file"], attn_state) * 3.0  # Scale to match other signals
    coact = get_coactivation_boost(entry["file"], already_matched, coact_pairs)

    final_score = weighted_keyword + recency + attention + coact
    return final_score


def extract_first_section(filepath, max_chars=2000):
    """For WARM tier: extract content up to the first ## heading (or max_chars)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(max_chars * 2)  # Read extra to find heading
    except OSError:
        return ""

    # Find second heading (first ## after the title)
    lines = content.split("\n")
    result = []
    heading_count = 0
    for line in lines:
        if line.startswith("## "):
            heading_count += 1
            if heading_count >= 2:
                break
        result.append(line)

    section = "\n".join(result)
    return section[:max_chars]


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

    # Load all state
    access_log = load_json(ACCESS_LOG)
    attn_state = load_json(ATTN_STATE, {"scores": {}, "last_update": 0})
    coact_pairs = load_json(COACTIVATION_LOG)

    # Decay all attention scores on each prompt (15% per turn)
    attn_state = decay_all_scores(attn_state)

    # Two-pass scoring: first pass gets keyword matches, second adds co-activation
    # Pass 1: score without co-activation
    preliminary = []
    for entry in entries:
        s = score_entry(entry, words, access_log, attn_state, {}, [])
        if s >= 2:  # Lower threshold for preliminary pass
            preliminary.append((s, entry))
    preliminary.sort(key=lambda x: x[0], reverse=True)
    already_matched = [e["file"] for _, e in preliminary[:5]]

    # Pass 2: re-score with co-activation from preliminary matches
    scored = []
    for entry in entries:
        s = score_entry(entry, words, access_log, attn_state, coact_pairs, already_matched)
        if s >= 4:
            scored.append((s, entry))

    if not scored:
        # Save decayed attention state even if no matches
        save_json(ATTN_STATE, attn_state)
        sys.exit(0)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]

    lines = []
    for score, entry in top:
        full_path = os.path.join(MEMORY_DIR, entry["file"])
        if os.path.exists(full_path):
            # Determine injection tier based on attention score
            attention = get_attention_score(entry["file"], attn_state)

            # Boost attention for matched files (they're being referenced)
            attn_scores = attn_state.get("scores", {})
            attn_scores[entry["file"]] = {
                "score": min(1.0, attention + 0.3),  # Boost but cap at 1.0
                "last_access": time.time(),
            }
            attn_state["scores"] = attn_scores

            if attention >= HOT_THRESHOLD:
                # HOT: full content — use existing format
                lines.append(f"{entry['name']}|{full_path}|{score:.1f}")
            elif attention >= WARM_THRESHOLD:
                # WARM: first section only — write truncated version to temp
                section = extract_first_section(full_path)
                if section:
                    warm_path = full_path + ".warm"
                    try:
                        with open(warm_path, "w", encoding="utf-8") as f:
                            f.write(section + f"\n\n<!-- WARM tier: showing first section only. Score: {score:.1f}, Attention: {attention:.2f} -->\n")
                        lines.append(f"{entry['name']}|{warm_path}|{score:.1f}")
                    except OSError:
                        lines.append(f"{entry['name']}|{full_path}|{score:.1f}")
                else:
                    lines.append(f"{entry['name']}|{full_path}|{score:.1f}")
            else:
                # COLD but still scored above threshold — include full
                # (this handles the case where keyword score alone is high enough)
                lines.append(f"{entry['name']}|{full_path}|{score:.1f}")

            # Update access log
            access_log[entry["file"]] = time.time()

    if lines:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        save_json(ACCESS_LOG, access_log)

    # Persist decayed attention state
    save_json(ATTN_STATE, attn_state)

    sys.exit(0)


if __name__ == "__main__":
    main()
