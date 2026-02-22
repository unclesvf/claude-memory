#!/usr/bin/env python3
"""
Stop Hook for Claude Code
Fires after Claude finishes responding. Analyzes the transcript tail
to detect memories worth saving across 6 structured categories.

Categories:
  1. session_summary — Work resume snapshots (what happened, what's next)
  2. decision — Architectural choices with rationale (why X over Y)
  3. runbook — Error fix procedures (symptom → fix → verification)
  4. constraint — Known limitations, things that cannot work
  5. tech_debt — Deferred work items
  6. preference — User conventions and workflow preferences

Uses a stop_hook_active guard file to prevent infinite loops.
Uses hash deduplication to prevent re-inserting the same fact.
Writes structured JSON to ~/.claude/memories/<category>/.

Exits 0 normally. Exits 2 to block (not used — we never block Stop).
"""
import json
import sys
import os
import re
import hashlib
import time
from datetime import datetime
from pathlib import Path

# Directories
MEMORIES_DIR = Path.home() / ".claude" / "memories"
GUARD_FILE = Path.home() / ".claude" / "stop_hook_active"
HASH_FILE = Path.home() / ".claude" / "memory_hashes.json"
PATTERN_FILE = Path.home() / ".claude" / "pattern_tracker.json"
FILE_TRACKING = Path.home() / ".claude" / "file_tracking.jsonl"

# Category detection keywords — deterministic triage, zero LLM cost
CATEGORY_SIGNALS = {
    "decision": {
        "keywords": [
            "decided", "chose", "picked", "went with", "instead of",
            "over", "rather than", "trade-off", "tradeoff", "approach",
            "architecture", "design choice", "opted for", "selected",
            "because", "rationale", "reason we", "better than",
        ],
        "patterns": [
            r"(?:decided|chose|picked|went with|opted for)\s+(?:to\s+)?(?:use|go with|implement)",
            r"(?:instead of|rather than|over)\s+\w+",
            r"(?:the reason|because)\s+(?:we|it|this)",
        ],
        "min_score": 3,
    },
    "runbook": {
        "keywords": [
            "fixed", "fix", "error", "bug", "issue", "solved",
            "solution", "workaround", "the problem was", "root cause",
            "traceback", "exception", "crash", "hang", "timeout",
            "symptom", "resolved", "debugging", "debugged",
        ],
        "patterns": [
            r"(?:the\s+)?(?:fix|solution|workaround)\s+(?:is|was|for)",
            r"(?:error|bug|issue|problem)\s+(?:was|is|in|with)",
            r"(?:fixed|resolved|solved)\s+(?:by|with|using)",
        ],
        "min_score": 3,
    },
    "constraint": {
        "keywords": [
            "cannot", "can't", "won't work", "doesn't work",
            "not possible", "limitation", "restricted", "blocked",
            "incompatible", "unsupported", "deprecated", "never",
            "do not", "don't", "must not", "avoid", "breaks",
        ],
        "patterns": [
            r"(?:cannot|can't|won't|doesn't)\s+(?:work|use|run|do)",
            r"(?:never|do not|don't|must not|avoid)\s+\w+",
            r"(?:limitation|restriction|incompatible|unsupported)",
        ],
        "min_score": 3,
    },
    "tech_debt": {
        "keywords": [
            "todo", "hack", "temporary", "workaround", "later",
            "eventually", "should refactor", "needs cleanup",
            "technical debt", "shortcut", "bandaid", "band-aid",
            "quick fix", "not ideal", "revisit", "come back to",
        ],
        "patterns": [
            r"(?:todo|hack|temporary|workaround)",
            r"(?:should|need to|needs to)\s+(?:refactor|clean|fix|revisit)",
            r"(?:come back|revisit|eventually|later)\s+(?:to|and)",
        ],
        "min_score": 2,
    },
    "preference": {
        "keywords": [
            "always", "prefer", "convention", "style", "workflow",
            "i like", "i want", "use this", "standard", "default",
            "my way", "the way i", "don't like", "hate",
            "batch size", "format", "naming",
        ],
        "patterns": [
            r"(?:always|prefer|convention|standard|default)\s+\w+",
            r"(?:i\s+(?:like|want|prefer|hate|don't like))\s+",
            r"(?:use|do|make)\s+(?:it|this|that)\s+(?:this way|like this)",
        ],
        "min_score": 2,
    },
}


def load_json_file(path, default=None):
    """Load a JSON file, returning default on any error."""
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json_file(path, data):
    """Atomic save: write to temp file then rename."""
    tmp = str(path) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, str(path))
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def content_hash(text):
    """MD5 hash of normalized text for deduplication."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def is_duplicate(text, hashes):
    """Check if this content has already been saved."""
    h = content_hash(text)
    return h in hashes


def record_hash(text, hashes):
    """Record a content hash to prevent future duplicates."""
    h = content_hash(text)
    hashes[h] = time.time()
    return hashes


def extract_transcript_tail(transcript_path, tail_entries=30):
    """Read the last N entries from the JSONL transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return []

    entries = []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (OSError, PermissionError):
        return []

    return entries[-tail_entries:]


def extract_text_from_entries(entries):
    """Extract readable text from transcript entries."""
    texts = []
    for entry in entries:
        msg = entry.get("message", {})
        content = msg.get("content", "")
        role = msg.get("role", entry.get("type", ""))

        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        # Include tool results for runbook detection
                        sub = block.get("content", "")
                        if isinstance(sub, str):
                            texts.append(sub[:500])

    return "\n".join(texts)


def score_category(text, category_name, signals):
    """Score text against a category's keyword and pattern signals."""
    text_lower = text.lower()
    score = 0

    # Keyword hits
    for kw in signals["keywords"]:
        count = text_lower.count(kw)
        if count > 0:
            score += min(count, 3)  # Cap at 3 per keyword

    # Pattern hits (more specific = higher value)
    for pattern in signals["patterns"]:
        matches = re.findall(pattern, text_lower)
        score += len(matches) * 2

    return score


def extract_relevant_snippet(text, category_name, signals, max_chars=800):
    """Extract the most relevant portion of text for a given category."""
    text_lower = text.lower()
    sentences = re.split(r"(?<=[.!?\n])\s+", text)

    scored_sentences = []
    for sent in sentences:
        sent_lower = sent.lower()
        s = 0
        for kw in signals["keywords"]:
            if kw in sent_lower:
                s += 1
        for pattern in signals["patterns"]:
            if re.search(pattern, sent_lower):
                s += 2
        if s > 0:
            scored_sentences.append((s, sent))

    scored_sentences.sort(key=lambda x: x[0], reverse=True)

    result = []
    total_len = 0
    for _, sent in scored_sentences:
        if total_len + len(sent) > max_chars:
            break
        result.append(sent.strip())
        total_len += len(sent)

    return " ".join(result) if result else ""


def update_pattern_tracker(category, snippet, pattern_tracker):
    """Track pattern occurrences for threshold-based graduation.

    Patterns need 3+ occurrences before they're considered stable enough
    to graduate to MEMORY.md rules.
    """
    h = content_hash(snippet)
    key = f"{category}:{h}"

    if key not in pattern_tracker:
        pattern_tracker[key] = {
            "category": category,
            "first_seen": time.time(),
            "last_seen": time.time(),
            "count": 1,
            "snippet_preview": snippet[:200],
            "graduated": False,
        }
    else:
        pattern_tracker[key]["last_seen"] = time.time()
        pattern_tracker[key]["count"] += 1

    return pattern_tracker


def save_memory(category, snippet, hashes):
    """Save a memory entry as JSON to the category directory."""
    cat_dir = MEMORIES_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    if is_duplicate(snippet, hashes):
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    entry = {
        "category": category,
        "timestamp": datetime.now().isoformat(),
        "content": snippet,
        "hash": content_hash(snippet),
    }

    filename = f"{timestamp}_{content_hash(snippet)[:8]}.json"
    filepath = cat_dir / filename

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
    except OSError:
        return False

    record_hash(snippet, hashes)
    return True


def build_session_summary(entries, files_from_tracking):
    """Build a session summary from recent transcript entries."""
    user_msgs = []
    assistant_snippets = []

    for entry in entries:
        msg = entry.get("message", {})
        role = msg.get("role", entry.get("type", ""))
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, str):
                user_msgs.append(content[:300])
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        user_msgs.append(block.get("text", "")[:300])

        elif role == "assistant":
            if isinstance(content, str):
                assistant_snippets.append(content[:200])
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        assistant_snippets.append(block.get("text", "")[:200])

    summary_parts = []
    if user_msgs:
        summary_parts.append("Tasks: " + " | ".join(user_msgs[-5:]))
    if files_from_tracking:
        summary_parts.append("Files: " + ", ".join(files_from_tracking[-10:]))
    if assistant_snippets:
        summary_parts.append("Actions: " + " | ".join(assistant_snippets[-3:]))

    return "\n".join(summary_parts)


def get_recent_files_from_tracking(max_age_seconds=3600):
    """Read recent file paths from the PostToolUse tracking log."""
    files = set()
    try:
        if not FILE_TRACKING.exists():
            return []
        with open(FILE_TRACKING, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if time.time() - entry.get("timestamp", 0) < max_age_seconds:
                        fp = entry.get("file_path", "")
                        if fp:
                            files.add(fp)
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass
    return sorted(files)


def main():
    # === GUARD: Prevent infinite loops ===
    # If the guard file exists, this is a re-entry — just clean up and exit
    if GUARD_FILE.exists():
        try:
            GUARD_FILE.unlink()
        except OSError:
            pass
        sys.exit(0)

    # Set the guard before doing any work
    try:
        GUARD_FILE.touch()
    except OSError:
        sys.exit(0)

    try:
        _run()
    finally:
        # Always clean up the guard
        try:
            GUARD_FILE.unlink()
        except OSError:
            pass


def _run():
    # Read hook input
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    transcript_path = data.get("transcript_path", "")
    stop_reason = data.get("stop_reason", "end_turn")

    # Only process normal end-of-turn stops
    if stop_reason not in ("end_turn",):
        sys.exit(0)

    # Extract transcript tail
    entries = extract_transcript_tail(transcript_path)
    if not entries:
        sys.exit(0)

    # Get full text for category analysis
    full_text = extract_text_from_entries(entries)
    if not full_text or len(full_text) < 50:
        sys.exit(0)

    # Load dedup hashes and pattern tracker
    hashes = load_json_file(HASH_FILE, {})
    pattern_tracker = load_json_file(PATTERN_FILE, {})

    # Ensure memories directory exists
    MEMORIES_DIR.mkdir(parents=True, exist_ok=True)

    saved_count = 0

    # Score each category
    for cat_name, signals in CATEGORY_SIGNALS.items():
        score = score_category(full_text, cat_name, signals)
        if score >= signals["min_score"]:
            snippet = extract_relevant_snippet(full_text, cat_name, signals)
            if snippet and len(snippet) > 20:
                # Update pattern tracker
                pattern_tracker = update_pattern_tracker(cat_name, snippet, pattern_tracker)
                # Save the memory
                if save_memory(cat_name, snippet, hashes):
                    saved_count += 1

    # Always try to save a session summary (lightweight)
    recent_files = get_recent_files_from_tracking()
    summary = build_session_summary(entries, recent_files)
    if summary and len(summary) > 30:
        if not is_duplicate(summary, hashes):
            save_memory("session_summary", summary, hashes)

    # Persist hashes and pattern tracker
    save_json_file(HASH_FILE, hashes)
    save_json_file(PATTERN_FILE, pattern_tracker)

    sys.exit(0)


if __name__ == "__main__":
    main()
