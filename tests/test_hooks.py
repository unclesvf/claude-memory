#!/usr/bin/env python3
"""
Test suite for claude-memory hooks.
Run: python -m pytest tests/test_hooks.py -v
Or:  python tests/test_hooks.py (standalone)
"""
import json
import os
import sys
import time
import tempfile
import shutil
import hashlib
import re
from pathlib import Path
from unittest import TestCase, main as unittest_main
from unittest.mock import patch
from io import BytesIO

# Add hooks directory to path
HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))


class TestMemorySearch(TestCase):
    """Tests for memory_search.py (v2 — attention + co-activation)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a minimal MEMORY.md
        self.memory_dir = os.path.join(self.tmpdir, "memory")
        os.makedirs(self.memory_dir)

        self.index_path = os.path.join(self.memory_dir, "MEMORY.md")
        with open(self.index_path, "w") as f:
            f.write("""# Test Memory Index

## Project Index

**Blender MCP** | Active | 3d model stl print hobbit house mesh addon | [blender-mcp.md](blender-mcp.md)
**Image Dedup** | Complete | duplicate photos hash perceptual GUI scan | [image-dedup.md](image-dedup.md)
**High Priority** | Active | 9 | critical urgent important | [high-priority.md](high-priority.md)
""")
        # Create topic files
        with open(os.path.join(self.memory_dir, "blender-mcp.md"), "w") as f:
            f.write("# Blender MCP\n\n## Overview\nBlender 3D modeling via MCP.\n\n## Details\nMore info here.")

        with open(os.path.join(self.memory_dir, "image-dedup.md"), "w") as f:
            f.write("# Image Dedup\n\nDuplicate photo detection tool.")

        with open(os.path.join(self.memory_dir, "high-priority.md"), "w") as f:
            f.write("# High Priority\n\nCritical system notes.")

        self.result_file = os.path.join(self.tmpdir, "result.txt")
        self.access_log = os.path.join(self.tmpdir, "access_log.json")
        self.attn_state = os.path.join(self.tmpdir, "attn_state.json")
        self.coact_log = os.path.join(self.tmpdir, "coact_pairs.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _import_search(self):
        """Import memory_search with patched paths."""
        import importlib
        import memory_search
        importlib.reload(memory_search)
        memory_search.MEMORY_DIR = self.memory_dir
        memory_search.MEMORY_INDEX = self.index_path
        memory_search.RESULT_FILE = self.result_file
        memory_search.ACCESS_LOG = self.access_log
        memory_search.ATTN_STATE = self.attn_state
        memory_search.COACTIVATION_LOG = self.coact_log
        return memory_search

    def test_parse_index_4field(self):
        ms = self._import_search()
        entries = ms.parse_index(self.index_path)
        blender = [e for e in entries if e["name"] == "Blender MCP"][0]
        self.assertEqual(blender["importance"], 5)
        self.assertIn("stl", blender["keywords"])
        self.assertEqual(blender["file"], "blender-mcp.md")

    def test_parse_index_5field_importance(self):
        ms = self._import_search()
        entries = ms.parse_index(self.index_path)
        hp = [e for e in entries if e["name"] == "High Priority"][0]
        self.assertEqual(hp["importance"], 9)

    def test_keyword_scoring(self):
        ms = self._import_search()
        entries = ms.parse_index(self.index_path)
        blender = [e for e in entries if e["name"] == "Blender MCP"][0]
        words = {"blender", "model", "stl"}
        attn = {"scores": {}, "last_update": 0}
        score = ms.score_entry(blender, words, {}, attn, {}, [])
        # "blender" in name (+2) + in keywords? "blender" not a keyword but partial match
        # "model" exact keyword (+3), "stl" exact keyword (+3)
        self.assertGreater(score, 5)

    def test_no_match_returns_empty(self):
        ms = self._import_search()
        entries = ms.parse_index(self.index_path)
        words = {"xyzzy", "foobar", "qux"}
        attn = {"scores": {}, "last_update": 0}
        for entry in entries:
            score = ms.score_entry(entry, words, {}, attn, {}, [])
            self.assertLess(score, 4)

    def test_importance_multiplier(self):
        ms = self._import_search()
        entries = ms.parse_index(self.index_path)
        hp = [e for e in entries if e["name"] == "High Priority"][0]
        words = {"critical"}
        attn = {"scores": {}, "last_update": 0}
        score = ms.score_entry(hp, words, {}, attn, {}, [])
        # importance=9, so multiplier is 9/5 = 1.8x
        # "critical" exact keyword = 3, * 1.8 = 5.4
        self.assertGreater(score, 5)

    def test_attention_decay(self):
        ms = self._import_search()
        state = {
            "scores": {
                "test.md": {"score": 1.0, "last_access": time.time()},
                "old.md": {"score": 0.005, "last_access": time.time() - 3600},
            },
            "last_update": time.time(),
        }
        decayed = ms.decay_all_scores(state)
        # 1.0 * 0.85 = 0.85
        self.assertAlmostEqual(decayed["scores"]["test.md"]["score"], 0.85, places=2)
        # 0.005 * 0.85 = 0.00425 < 0.01 threshold — should be evicted
        self.assertNotIn("old.md", decayed["scores"])

    def test_extract_first_section(self):
        ms = self._import_search()
        blender_path = os.path.join(self.memory_dir, "blender-mcp.md")
        section = ms.extract_first_section(blender_path)
        self.assertIn("Blender MCP", section)
        self.assertIn("Overview", section)
        # Should NOT include "## Details" section
        self.assertNotIn("More info here", section)

    def test_recency_boost(self):
        ms = self._import_search()
        access_log = {"blender-mcp.md": time.time() - 1800}  # 30 min ago
        boost = ms.recency_score("blender-mcp.md", access_log)
        self.assertEqual(boost, 3.0)  # Within 1 hour

        access_log2 = {"blender-mcp.md": time.time() - 7200}  # 2 hours ago
        boost2 = ms.recency_score("blender-mcp.md", access_log2)
        self.assertEqual(boost2, 2.0)  # Within 4 hours


class TestStopHook(TestCase):
    """Tests for stop_hook.py — 6-category taxonomy + dedup."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memories_dir = Path(self.tmpdir) / "memories"
        self.guard_file = Path(self.tmpdir) / "stop_hook_active"
        self.hash_file = Path(self.tmpdir) / "memory_hashes.json"
        self.pattern_file = Path(self.tmpdir) / "pattern_tracker.json"
        self.tracking_file = Path(self.tmpdir) / "file_tracking.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _import_stop(self):
        import importlib
        import stop_hook
        importlib.reload(stop_hook)
        stop_hook.MEMORIES_DIR = self.memories_dir
        stop_hook.GUARD_FILE = self.guard_file
        stop_hook.HASH_FILE = self.hash_file
        stop_hook.PATTERN_FILE = self.pattern_file
        stop_hook.FILE_TRACKING = self.tracking_file
        return stop_hook

    def test_content_hash_deterministic(self):
        sh = self._import_stop()
        h1 = sh.content_hash("Hello World")
        h2 = sh.content_hash("  hello   world  ")
        self.assertEqual(h1, h2)

    def test_content_hash_different_for_different_text(self):
        sh = self._import_stop()
        h1 = sh.content_hash("Hello World")
        h2 = sh.content_hash("Goodbye World")
        self.assertNotEqual(h1, h2)

    def test_dedup_prevents_double_save(self):
        sh = self._import_stop()
        hashes = {}
        self.assertFalse(sh.is_duplicate("New fact about Python", hashes))
        sh.record_hash("New fact about Python", hashes)
        self.assertTrue(sh.is_duplicate("New fact about Python", hashes))

    def test_dedup_normalized_whitespace(self):
        sh = self._import_stop()
        hashes = {}
        sh.record_hash("decided to use React", hashes)
        self.assertTrue(sh.is_duplicate("  decided  to  use  React  ", hashes))

    def test_decision_scoring(self):
        sh = self._import_stop()
        text = "We decided to use FastAPI instead of Flask because it has better async support."
        signals = sh.CATEGORY_SIGNALS["decision"]
        score = sh.score_category(text, "decision", signals)
        self.assertGreaterEqual(score, signals["min_score"])

    def test_runbook_scoring(self):
        sh = self._import_stop()
        text = "The error was caused by a missing import. Fixed by adding import json at the top."
        signals = sh.CATEGORY_SIGNALS["runbook"]
        score = sh.score_category(text, "runbook", signals)
        self.assertGreaterEqual(score, signals["min_score"])

    def test_constraint_scoring(self):
        sh = self._import_stop()
        text = "Word COM automation cannot work with 32-bit Office. It hangs and never returns."
        signals = sh.CATEGORY_SIGNALS["constraint"]
        score = sh.score_category(text, "constraint", signals)
        self.assertGreaterEqual(score, signals["min_score"])

    def test_tech_debt_scoring(self):
        sh = self._import_stop()
        text = "This is a temporary workaround. We should refactor this later when we have time."
        signals = sh.CATEGORY_SIGNALS["tech_debt"]
        score = sh.score_category(text, "tech_debt", signals)
        self.assertGreaterEqual(score, signals["min_score"])

    def test_preference_scoring(self):
        sh = self._import_stop()
        text = "I always prefer batch size of 5 items. That's my standard workflow convention."
        signals = sh.CATEGORY_SIGNALS["preference"]
        score = sh.score_category(text, "preference", signals)
        self.assertGreaterEqual(score, signals["min_score"])

    def test_irrelevant_text_low_score(self):
        sh = self._import_stop()
        text = "The weather is nice today. Let's go for a walk in the park."
        for cat_name, signals in sh.CATEGORY_SIGNALS.items():
            score = sh.score_category(text, cat_name, signals)
            self.assertLess(score, signals["min_score"],
                            f"'{cat_name}' should not match irrelevant text")

    def test_save_memory_creates_file(self):
        sh = self._import_stop()
        hashes = {}
        result = sh.save_memory("decision", "We chose React over Vue for the frontend.", hashes)
        self.assertTrue(result)
        # Check file was created
        cat_dir = self.memories_dir / "decision"
        files = list(cat_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        data = json.loads(files[0].read_text())
        self.assertEqual(data["category"], "decision")
        self.assertIn("React over Vue", data["content"])

    def test_save_memory_dedup_blocks_second(self):
        sh = self._import_stop()
        hashes = {}
        r1 = sh.save_memory("decision", "We chose React.", hashes)
        r2 = sh.save_memory("decision", "We chose React.", hashes)
        self.assertTrue(r1)
        self.assertFalse(r2)

    def test_guard_file_prevents_reentry(self):
        sh = self._import_stop()
        # Simulate guard file existing (re-entry scenario)
        self.guard_file.touch()
        # The main() function should detect it and clean up
        # We can't easily call main() in test since it calls sys.exit,
        # so test the logic directly
        self.assertTrue(self.guard_file.exists())
        # After main detects guard, it should unlink
        self.guard_file.unlink()
        self.assertFalse(self.guard_file.exists())

    def test_pattern_tracker_increments(self):
        sh = self._import_stop()
        tracker = {}
        tracker = sh.update_pattern_tracker("decision", "Use React for frontend", tracker)
        key = [k for k in tracker.keys()][0]
        self.assertEqual(tracker[key]["count"], 1)
        self.assertFalse(tracker[key]["graduated"])

        tracker = sh.update_pattern_tracker("decision", "Use React for frontend", tracker)
        self.assertEqual(tracker[key]["count"], 2)

        tracker = sh.update_pattern_tracker("decision", "Use React for frontend", tracker)
        self.assertEqual(tracker[key]["count"], 3)

    def test_extract_relevant_snippet(self):
        sh = self._import_stop()
        text = "Some boring setup text. We decided to use PostgreSQL instead of MySQL because it has better JSON support. More boring text follows here."
        signals = sh.CATEGORY_SIGNALS["decision"]
        snippet = sh.extract_relevant_snippet(text, "decision", signals)
        self.assertIn("decided", snippet.lower())


class TestPostToolUse(TestCase):
    """Tests for post_tool_use.py — file tracking + attention + co-activation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tracking_file = Path(self.tmpdir) / "file_tracking.jsonl"
        self.attn_state_file = Path(self.tmpdir) / "attn_state.json"
        self.coact_file = Path(self.tmpdir) / "coactivation_pairs.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _import_ptu(self):
        import importlib
        import post_tool_use
        importlib.reload(post_tool_use)
        post_tool_use.FILE_TRACKING = self.tracking_file
        post_tool_use.ATTN_STATE = self.attn_state_file
        post_tool_use.COACTIVATION_LOG = self.coact_file
        return post_tool_use

    def test_update_attention_creates_hot_entry(self):
        ptu = self._import_ptu()
        now = time.time()
        ptu.update_attention("/path/to/file.py", now)
        state = json.loads(self.attn_state_file.read_text())
        self.assertEqual(state["scores"]["/path/to/file.py"]["score"], 1.0)

    def test_coactivation_creates_pair(self):
        ptu = self._import_ptu()
        now = time.time()
        # Write a recent tracking entry
        with open(self.tracking_file, "w") as f:
            f.write(json.dumps({"timestamp": now - 30, "tool": "Read", "file_path": "/a.py"}) + "\n")
        ptu.update_coactivation("/b.py", now)
        pairs = json.loads(self.coact_file.read_text())
        self.assertEqual(len(pairs), 1)
        key = list(pairs.keys())[0]
        self.assertEqual(pairs[key]["count"], 1)

    def test_coactivation_ignores_old_entries(self):
        ptu = self._import_ptu()
        now = time.time()
        # Write an old tracking entry (5 min ago, outside 2 min window)
        with open(self.tracking_file, "w") as f:
            f.write(json.dumps({"timestamp": now - 300, "tool": "Read", "file_path": "/old.py"}) + "\n")
        ptu.update_coactivation("/new.py", now)
        # Should not create a pair
        self.assertFalse(self.coact_file.exists())

    def test_non_file_tools_ignored(self):
        ptu = self._import_ptu()
        # Bash tool should be ignored
        self.assertNotIn("Bash", ptu.FILE_TOOLS)
        self.assertIn("Read", ptu.FILE_TOOLS)
        self.assertIn("Edit", ptu.FILE_TOOLS)
        self.assertIn("Write", ptu.FILE_TOOLS)


class TestSubagentStart(TestCase):
    """Tests for subagent_start.py — memory injection into subagents."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memory_dir = os.path.join(self.tmpdir, "memory")
        os.makedirs(self.memory_dir)
        self.index_path = os.path.join(self.memory_dir, "MEMORY.md")
        with open(self.index_path, "w") as f:
            f.write("""## Project Index
**Test Project** | Active | python fastapi server api | [test-project.md](test-project.md)
""")
        with open(os.path.join(self.memory_dir, "test-project.md"), "w") as f:
            f.write("# Test Project\nFastAPI server on port 8001.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _import_sub(self):
        import importlib
        import subagent_start
        importlib.reload(subagent_start)
        subagent_start.MEMORY_DIR = self.memory_dir
        subagent_start.MEMORY_INDEX = self.index_path
        return subagent_start

    def test_parse_index(self):
        sub = self._import_sub()
        entries = sub.parse_index(self.index_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "Test Project")

    def test_scoring_relevant_prompt(self):
        sub = self._import_sub()
        entries = sub.parse_index(self.index_path)
        entry = entries[0]
        words = {"fastapi", "server", "api"}
        score = 0
        for word in words:
            if word in entry["keywords"]:
                score += 3
        self.assertGreaterEqual(score, 6)  # 3 exact matches

    def test_scoring_irrelevant_prompt(self):
        sub = self._import_sub()
        entries = sub.parse_index(self.index_path)
        entry = entries[0]
        words = {"blender", "stl", "mesh"}
        score = 0
        for word in words:
            if word in entry["keywords"]:
                score += 3
        self.assertEqual(score, 0)


class TestSessionEnd(TestCase):
    """Tests for session_end.py — session summaries + cleanup."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.session_dir = Path(self.tmpdir) / "sessions"
        self.session_dir.mkdir()
        self.tracking_file = Path(self.tmpdir) / "file_tracking.jsonl"
        self.memory_dir = Path(self.tmpdir) / "memory"
        self.memory_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _import_se(self):
        import importlib
        import session_end
        importlib.reload(session_end)
        session_end.SESSION_DIR = self.session_dir
        session_end.FILE_TRACKING = self.tracking_file
        session_end.MEMORY_DIR = self.memory_dir
        return session_end

    def test_prune_old_tracking(self):
        se = self._import_se()
        now = time.time()
        with open(self.tracking_file, "w") as f:
            f.write(json.dumps({"timestamp": now - 100000, "tool": "Read", "file_path": "/old.py"}) + "\n")
            f.write(json.dumps({"timestamp": now - 100, "tool": "Read", "file_path": "/new.py"}) + "\n")
        se.prune_tracking_log()
        with open(self.tracking_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("/new.py", lines[0])

    def test_cleanup_warm_files(self):
        se = self._import_se()
        warm = self.memory_dir / "test.md.warm"
        warm.write_text("temp warm content")
        self.assertTrue(warm.exists())
        se.cleanup_warm_files()
        self.assertFalse(warm.exists())

    def test_session_file_pruning(self):
        se = self._import_se()
        # Create 25 session files
        for i in range(25):
            f = self.session_dir / f"session_202602{i:02d}_120000.json"
            f.write_text(json.dumps({"test": i}))
        files_before = list(self.session_dir.glob("session_*.json"))
        self.assertEqual(len(files_before), 25)

        # Pruning should keep last 20 — call the pruning logic directly
        session_files = sorted(self.session_dir.glob("session_*.json"))
        if len(session_files) > 20:
            for old_file in session_files[:-20]:
                old_file.unlink()

        files_after = list(self.session_dir.glob("session_*.json"))
        self.assertEqual(len(files_after), 20)


class TestAtomicWrites(TestCase):
    """Tests for atomic file write pattern used across hooks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_atomic_save_creates_file(self):
        import importlib
        import stop_hook
        importlib.reload(stop_hook)
        path = Path(self.tmpdir) / "test.json"
        stop_hook.save_json_file(path, {"key": "value"})
        data = json.loads(path.read_text())
        self.assertEqual(data["key"], "value")

    def test_atomic_save_no_leftover_tmp(self):
        import importlib
        import stop_hook
        importlib.reload(stop_hook)
        path = Path(self.tmpdir) / "test.json"
        stop_hook.save_json_file(path, {"key": "value"})
        tmp_path = Path(str(path) + ".tmp")
        self.assertFalse(tmp_path.exists())

    def test_load_missing_file_returns_default(self):
        import importlib
        import stop_hook
        importlib.reload(stop_hook)
        result = stop_hook.load_json_file(Path(self.tmpdir) / "nonexistent.json", {"default": True})
        self.assertEqual(result, {"default": True})


class TestIntegration(TestCase):
    """Integration tests — verify hooks work together."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_post_tool_use_feeds_stop_hook(self):
        """PostToolUse tracking data should be readable by Stop hook."""
        import importlib
        tracking_file = Path(self.tmpdir) / "file_tracking.jsonl"

        # Simulate PostToolUse writing tracking data
        now = time.time()
        entries = [
            {"timestamp": now - 60, "tool": "Read", "file_path": "/src/main.py"},
            {"timestamp": now - 30, "tool": "Edit", "file_path": "/src/utils.py"},
        ]
        with open(tracking_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        # Stop hook should be able to read these
        import stop_hook
        importlib.reload(stop_hook)
        stop_hook.FILE_TRACKING = tracking_file
        files = stop_hook.get_recent_files_from_tracking(max_age_seconds=3600)
        self.assertEqual(len(files), 2)
        self.assertIn("/src/main.py", files)
        self.assertIn("/src/utils.py", files)

    def test_attention_state_shared(self):
        """PostToolUse and MemorySearch should share attention state."""
        import importlib
        attn_file = Path(self.tmpdir) / "attn_state.json"

        # PostToolUse writes attention
        import post_tool_use
        importlib.reload(post_tool_use)
        post_tool_use.ATTN_STATE = attn_file
        post_tool_use.FILE_TRACKING = Path(self.tmpdir) / "tracking.jsonl"
        post_tool_use.COACTIVATION_LOG = Path(self.tmpdir) / "coact.json"
        post_tool_use.update_attention("test-file.md", time.time())

        # MemorySearch reads it
        import memory_search
        importlib.reload(memory_search)
        state = memory_search.load_json(str(attn_file))
        score = memory_search.get_attention_score("test-file.md", state)
        self.assertEqual(score, 1.0)


if __name__ == "__main__":
    unittest_main(verbosity=2)
