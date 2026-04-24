#!/usr/bin/env python3
"""
MemPalace Auto-Mine Hook for Claude Code (PostToolUse)

Fires after Write/Edit on memory files. Automatically mines new/updated
files into the MemPalace ChromaDB palace with correct wing assignment.

For NEW files: mines into palace with auto-detected wing.
For UPDATED files: deletes old drawers, re-mines with fresh content.

Runs async with 5s timeout. Exits 0 always (never blocks Claude).
"""
import json
import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime

# Paths — UPDATE MEMORY_DIR for your username (same pattern as memory_search.py)
# macOS:   Path.home() / ".claude" / "projects" / "-Users-yourname" / "memory"
# Windows: Path.home() / ".claude" / "projects" / "C--Users-yourname" / "memory"
MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-yourname" / "memory"
PALACE_PATH = Path.home() / ".mempalace" / "palace"
COLLECTION_NAME = "mempalace_drawers"
AGENT_NAME = "automine"

# Chunk parameters (match mempalace defaults)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 50

# Wing classification rules — filename prefix/keyword -> wing.
# Order matters: first match wins.
#
# These are EXAMPLE rules. Customize for your projects: each tuple is
# (predicate, wing_name) where the predicate takes (filename_lower, content_lower)
# and returns True if the file belongs to that wing.
#
# Common patterns:
#   - frontmatter prefix: f.startswith("feedback_")
#   - keyword in filename: any(k in f for k in ["frontend", "ui", "react"])
#   - content tag: "type: project" in c
#
# The last rule is a catch-all that ensures every file gets routed somewhere.
WING_RULES = [
    # User personal facts and persona
    (lambda f, _: f.startswith("user_"), "wing_personal"),
    # Feedback / corrections / preferences
    (lambda f, _: f.startswith("feedback_"), "wing_feedback"),
    # Per-session task summaries
    (lambda f, _: f.startswith(("session-", "session_")), "wing_sessions"),
    # Memory system meta (self-evolution, workflows, decay rules)
    (lambda f, c: any(k in f for k in [
        "memory", "self-evolution", "workflow", "MEMORY", "CONTEXT", "decay"
    ]), "wing_meta"),
    # --- Customize the wings below for your own projects ---
    # Example: tool/project wing
    # (lambda f, c: any(k in f for k in ["mytool", "mywebapp"]), "wing_my_projects"),
    #
    # Catch-all: must be last; routes everything else to the infrastructure wing
    (lambda f, c: True, "wing_infrastructure"),
]


def classify_wing(filename: str, content: str = "") -> str:
    """Determine which wing a memory file belongs to."""
    fname_lower = filename.lower()
    for rule_fn, wing in WING_RULES:
        try:
            if rule_fn(fname_lower, content.lower()):
                return wing
        except Exception:
            continue
    return "wing_infrastructure"


def chunk_text(content: str) -> list:
    """Split content into overlapping chunks."""
    if len(content) <= CHUNK_SIZE:
        return [{"content": content, "chunk_index": 0}]

    chunks = []
    start = 0
    idx = 0
    while start < len(content):
        end = start + CHUNK_SIZE
        chunk = content[start:end]
        if len(chunk.strip()) >= MIN_CHUNK_SIZE:
            chunks.append({"content": chunk.strip(), "chunk_index": idx})
            idx += 1
        start = end - CHUNK_OVERLAP

    return chunks


def get_collection():
    """Get the MemPalace ChromaDB collection."""
    import chromadb
    client = chromadb.PersistentClient(path=str(PALACE_PATH))
    return client.get_collection(COLLECTION_NAME)


def delete_file_drawers(collection, source_file: str) -> int:
    """Delete all drawers for a given source file. Returns count deleted."""
    try:
        existing = collection.get(where={"source_file": source_file})
        ids = existing.get("ids", [])
        if ids:
            collection.delete(ids=ids)
        return len(ids)
    except Exception:
        return 0


def mine_file(collection, filepath: Path, wing: str) -> int:
    """Mine a single file into the palace. Returns drawer count."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return 0

    if len(content) < MIN_CHUNK_SIZE:
        return 0

    room = filepath.stem  # room = filename without extension
    source_file = str(filepath)
    chunks = chunk_text(content)

    drawers_added = 0
    for chunk in chunks:
        drawer_id = f"drawer_{wing}_{room}_{hashlib.md5((source_file + str(chunk['chunk_index'])).encode()).hexdigest()[:16]}"
        try:
            collection.add(
                documents=[chunk["content"]],
                ids=[drawer_id],
                metadatas=[{
                    "wing": wing,
                    "room": room,
                    "source_file": source_file,
                    "chunk_index": chunk["chunk_index"],
                    "added_by": AGENT_NAME,
                    "filed_at": datetime.now().isoformat(),
                }],
            )
            drawers_added += 1
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            # Other errors — skip silently
            continue

    return drawers_added


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only care about Write and Edit
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    filepath = Path(file_path)

    # Only care about files in the memory directory
    try:
        if not filepath.is_relative_to(MEMORY_DIR):
            sys.exit(0)
    except (ValueError, AttributeError):
        # Python < 3.9 fallback
        try:
            filepath.relative_to(MEMORY_DIR)
        except ValueError:
            sys.exit(0)

    # Skip non-markdown and MEMORY.md index
    if filepath.suffix != ".md" or filepath.name == "MEMORY.md":
        sys.exit(0)

    # Skip if file doesn't exist (deleted?)
    if not filepath.exists():
        sys.exit(0)

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        wing = classify_wing(filepath.name, content)
        collection = get_collection()
        source_file = str(filepath)

        # Check if file was already mined (this is an update)
        existing = collection.get(where={"source_file": source_file})
        is_update = len(existing.get("ids", [])) > 0

        if is_update:
            # Delete old drawers, re-mine
            delete_file_drawers(collection, source_file)

        drawers = mine_file(collection, filepath, wing)

        # Log result (visible in hook output if debugging)
        action = "updated" if is_update else "mined"
        if drawers > 0:
            print(f"[mempalace-automine] {action} {filepath.name} → {wing} ({drawers} drawers)")

    except Exception as e:
        # Never block Claude — swallow all errors
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
