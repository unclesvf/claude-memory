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

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-yourname", "memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")
RESULT_FILE = os.path.join(os.path.expanduser("~"), ".claude", "memory_search_result.txt")
ACCESS_LOG = os.path.join(os.path.expanduser("~"), ".claude", "memory_access_log.json")
ATTN_STATE = os.path.join(os.path.expanduser("~"), ".claude", "attn_state.json")
COACTIVATION_LOG = os.path.join(os.path.expanduser("~"), ".claude", "coactivation_pairs.json")

# Stop-hook JSON memories (constraint/decision entries)
JSON_MEMORIES_INDEX = os.path.join(os.path.expanduser("~"), ".claude", "memories", "index.jsonl")
# Only surface these categories (most actionable for retrieval)
JSON_SEARCH_CATEGORIES = {"constraint", "decision"}
# Search all entries (no time limit — older constraints/decisions remain relevant)

# MemPalace fallback config
PALACE_PATH = os.path.join(os.path.expanduser("~"), ".mempalace", "palace")
PALACE_COLLECTION = "mempalace_drawers"
MEMPALACE_FALLBACK_THRESHOLD = 6  # Fall back to MemPalace when best keyword score < this
MEMPALACE_MIN_SIMILARITY = 0.25   # Minimum ChromaDB similarity score to surface

# Attention decay rate per search invocation (15%)
DECAY_RATE = 0.15

# Attention tiers
HOT_THRESHOLD = 0.8
WARM_THRESHOLD = 0.25

# Significant short words preserved in keyword matching (not filtered by len>=3)
SIGNIFICANT_SHORT_KW = {"x", "ai", "3d", "db", "ui", "ci", "cd", "ip", "os", "vm",
                        "tts", "gpu", "api", "cli", "dns", "ssl", "ssh", "stl", "csv",
                        "pdf", "llm", "rtx", "cnc", "pop", "mac", "mcp", "aws"}

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

    # Dash-list format: - [Title](file.md) — description with keywords
    pattern_dash = re.compile(
        r"^-\s+\[(.+?)\]\((.+?\.md)\)\s*[—–-]\s*(.+)$", re.MULTILINE
    )
    matched_files = {e["file"] for e in entries}
    for m in pattern_dash.finditer(content):
        filename = m.group(2).strip()
        if filename in matched_files:
            continue  # Already captured by table format
        description = m.group(3).strip()
        title = m.group(1).strip()
        # Extract keywords from description text (include significant short words)
        desc_words = [w.strip().lower() for w in re.findall(r"[a-zA-Z0-9_-]+", description)
                      if len(w) >= 3 or w.lower() in SIGNIFICANT_SHORT_KW]
        # Also add title words as keywords
        title_words = [w.strip().lower() for w in re.findall(r"[a-zA-Z0-9_-]+", title)
                       if len(w) >= 3 or w.lower() in SIGNIFICANT_SHORT_KW]
        all_keywords = list(set(desc_words + title_words))
        entries.append({
            "name": title,
            "status": "Active",
            "importance": 5,
            "keywords": all_keywords,
            "file": filename,
        })
        matched_files.add(filename)

    return entries


def score_entry(entry, words, access_log, attn_state, coact_pairs, already_matched):
    """Score an entry against the user's message.

    Final score = (keyword_score * importance_mult) + recency + attention + coactivation
    """
    keyword_score = 0
    match_count = 0  # Track how many distinct query words match
    name_lower = entry["name"].lower()
    keywords = entry["keywords"]
    file_lower = entry["file"].lower().replace(".md", "").replace("-", " ").replace("_", " ")

    for word in words:
        word_matched = False
        if word in keywords:
            keyword_score += 3
            word_matched = True
        elif any(word in kw or kw in word for kw in keywords):
            keyword_score += 2
            word_matched = True
        if word in name_lower:
            keyword_score += 2
            word_matched = True
        # Check if word matches part of the filename
        if len(word) >= 4 and word in file_lower:
            keyword_score += 2
            word_matched = True
        if word_matched:
            match_count += 1

    # Multi-word match bonus: more distinct matching words = stronger signal
    if match_count >= 3:
        keyword_score += (match_count - 2) * 2  # +2 per word beyond 2 matches

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


def search_json_memories(words, max_results=2):
    """Search stop-hook JSON memories (constraint/decision) for keyword matches.

    Returns list of (score, category, content, timestamp) tuples.
    Only searches recent entries from actionable categories.
    """
    if not os.path.exists(JSON_MEMORIES_INDEX):
        return []

    results = []
    try:
        with open(JSON_MEMORIES_INDEX, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                cat = entry.get("category", "")
                if cat not in JSON_SEARCH_CATEGORIES:
                    continue

                raw_content = entry.get("content", "")
                # Skip entries that are mostly system noise (task notifications, XML tags, etc.)
                if "<task-notification>" in raw_content or "<tool-use-id>" in raw_content:
                    continue
                # Strip XML/HTML tags for cleaner matching
                clean = re.sub(r"<[^>]+>", " ", raw_content)
                content = clean.lower().strip()
                if not content or len(content) < 20:
                    continue

                # Score by word overlap
                score = 0
                for word in words:
                    if word in content:
                        score += 3
                    elif any(word in w for w in content.split()):
                        score += 1

                if score >= 6:  # Require strong match (2+ exact keyword hits)
                    results.append((score, cat, entry.get("content", ""), entry.get("timestamp", "")))
    except OSError:
        return []

    results.sort(key=lambda x: x[0], reverse=True)
    # Deduplicate by content similarity (take highest-scoring of similar entries)
    seen_snippets = set()
    deduped = []
    for score, cat, content, ts in results:
        # Use first 100 chars as dedup key
        key = content[:100].lower().strip()
        if key not in seen_snippets:
            seen_snippets.add(key)
            deduped.append((score, cat, content, ts))
        if len(deduped) >= max_results:
            break

    return deduped


def mempalace_semantic_search(query, limit=3):
    """Fallback: semantic search via MemPalace ChromaDB when keyword scoring is weak.

    Returns list of (score, source_file, wing, room, content_preview) tuples.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=PALACE_PATH)
        col = client.get_collection(PALACE_COLLECTION)
        results = col.query(
            query_texts=[query],
            n_results=limit * 2,  # Over-fetch to filter
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        return []

    hits = []
    seen_files = set()
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, (doc, meta, dist) in enumerate(zip(docs, metas, distances)):
        # ChromaDB returns L2 distance; convert to similarity (lower distance = better)
        # Typical range: 0.0 (identical) to 2.0 (very different)
        similarity = max(0, 1.0 - dist / 2.0)
        if similarity < MEMPALACE_MIN_SIMILARITY:
            continue

        source_file = meta.get("source_file", "")
        wing = meta.get("wing", "")
        room = meta.get("room", "")

        # Deduplicate by source file (take best chunk per file)
        if source_file in seen_files:
            continue
        seen_files.add(source_file)

        # Preview: first 300 chars of the chunk
        preview = doc[:300] if doc else ""
        hits.append((similarity, source_file, wing, room, preview))

        if len(hits) >= limit:
            break

    return hits


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

    # Common English stop words that add noise to keyword matching
    STOP_WORDS = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
                  "her", "was", "one", "our", "out", "has", "have", "been", "some", "them",
                  "than", "its", "over", "also", "back", "into", "then", "what", "when",
                  "how", "who", "why", "where", "which", "this", "that", "with", "from",
                  "does", "did", "will", "would", "could", "should", "about", "just",
                  "like", "use", "used", "using", "need", "want", "set", "get", "let",
                  "see", "try", "make", "know", "take", "come", "give", "tell", "find"}
    words = set(re.findall(r"[a-z0-9]+", prompt.lower()))
    words = {w for w in words if (len(w) >= 3 or w in SIGNIFICANT_SHORT_KW) and w not in STOP_WORDS}
    # Also add hyphenated compounds from the original prompt (e.g., "x-research", "pipeline-consolidation")
    compounds = set(re.findall(r"[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*", prompt.lower()))
    words.update(compounds)

    # URL pattern detection — inject domain-specific keywords so memory matches reliably
    # This ensures that e.g. an x.com URL always surfaces x-research-setup.md
    URL_KEYWORD_MAP = {
        r"x\.com/|twitter\.com/": {"x-research", "twitter", "tweet", "bookmarks"},
        r"github\.com/": {"github", "repo", "pull", "issue"},
        r"reddit\.com/": {"reddit", "research"},
    }
    prompt_lower = prompt.lower()
    for url_pattern, inject_kw in URL_KEYWORD_MAP.items():
        if re.search(url_pattern, prompt_lower):
            words.update(inject_kw)

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

    scored.sort(key=lambda x: x[0], reverse=True)
    best_keyword_score = scored[0][0] if scored else 0

    # MemPalace fallback: when keyword scoring is weak, try semantic search
    mempalace_hits = []
    if best_keyword_score < MEMPALACE_FALLBACK_THRESHOLD:
        mempalace_hits = mempalace_semantic_search(prompt, limit=2)

    if not scored and not mempalace_hits:
        # Save decayed attention state even if no matches
        save_json(ATTN_STATE, attn_state)
        sys.exit(0)

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

        # Output matched memory files to stdout so Claude Code injects them into context.
        # Each matched file's content is printed with a header showing relevance score.
        injected = []
        for line in lines:
            parts = line.split("|")
            if len(parts) >= 3:
                name, fpath, score = parts[0], parts[1], parts[2]
                # Strip .warm suffix for display
                display_path = fpath.replace(".warm", "")
                try:
                    content = open(fpath, "r", encoding="utf-8").read()
                    injected.append(f"[Memory: {name} (score={score})] {display_path}\n{content}")
                except OSError:
                    pass
        if injected:
            output = "\n---\n".join(injected)
            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")

    # === MemPalace semantic fallback results ===
    if mempalace_hits:
        mp_parts = []
        for similarity, source_file, wing, room, preview in mempalace_hits:
            # If the source file is a memory .md, read the full file
            if os.path.exists(source_file) and source_file.endswith(".md"):
                try:
                    content = open(source_file, "r", encoding="utf-8").read()
                    mp_parts.append(
                        f"[MemPalace: {room} in {wing} (similarity={similarity:.2f})] {source_file}\n{content}"
                    )
                except OSError:
                    mp_parts.append(
                        f"[MemPalace: {room} in {wing} (similarity={similarity:.2f})] {preview}"
                    )
            else:
                mp_parts.append(
                    f"[MemPalace: {room} in {wing} (similarity={similarity:.2f})] {preview}"
                )
        if mp_parts:
            mp_output = "\n---\n".join(mp_parts)
            sys.stdout.buffer.write(b"\n---\n")
            sys.stdout.buffer.write(mp_output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")

    # === Search stop-hook JSON memories (constraint/decision) ===
    json_matches = search_json_memories(words)
    if json_matches:
        json_parts = []
        for score, cat, content, ts in json_matches:
            json_parts.append(
                f"[StopHook {cat} (score={score}, ts={ts[:10]})] {content}"
            )
        json_output = "\n---\n".join(json_parts)
        sys.stdout.buffer.write(b"\n---\n")
        sys.stdout.buffer.write(json_output.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")

    # Persist decayed attention state
    save_json(ATTN_STATE, attn_state)

    sys.exit(0)


if __name__ == "__main__":
    main()
