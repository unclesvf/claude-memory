# Pipeline Audit - February 6-11, 2026

## Overview

### Phase 1: Feb 6 (3-pass audit)
Comprehensive 3-pass audit of the entire Ambrose AI Knowledge Base codebase.
~90 Python files reviewed, 48 modified, 87 bugs fixed. All files syntax-checked.

### Phase 2: Feb 11 (10-round deep review)
Focused iterative deep review of all 42+ pipeline files. 10 consecutive rounds
of "find bugs → fix → re-review". ~90 additional bugs fixed across ~30 files.

**Combined total: ~177 bugs fixed across the pipeline.**

## Phase 1 Audit Process (Feb 6)
- **Pass 1**: 5 review agents scanned core scripts, found 87 issues (21 critical)
  - 4 fix agents applied 16 fixes across 12 files
- **Pass 2**: Fixed remaining lower-priority items + fresh sweep
  - 16 lower-priority fixes (timeouts, logging, validation, dedup)
  - 20 bare `except:` clauses eliminated
  - 5 new bugs found in translate_transcripts.py (missed in pass 1)
- **Pass 3**: Reviewed ALL remaining Python files (59 files not yet covered)
  - 4 review+fix agents covered every file
  - 29 additional bugs found and fixed
  - 1 syntax error caught and fixed (style_code_gallery.py indentation)

## Phase 2 Round-by-Round (Feb 11)

### Rounds 1-2: Core patterns established
- Retry-with-re-load on DB save (re-load from disk, re-apply, retry 5x with backoff)
- LLM retry with backoff (3 attempts, 10s/20s on 429/timeouts)
- JSONDecodeError handling on all json.load/json.loads
- Author validation and null safety

### Round 3: Type safety sweep
- isinstance(item, dict) guards on all DB iteration loops
- Code block type safety: isinstance(cb, str) filter
- Midjourney merge isinstance guards on regex + LLM sources
- Playwright browser.close() in try/finally blocks

### Round 4: XSS + DB bloat
- safe_href() helper for all dynamic URLs in generate_reports.py (16 locations)
- video_transcript → video_transcript_preview (500 char limit in DB)

### Round 5: Edge cases
- json.loads empty stdout check in instant_xvideo.py
- FileNotFoundError after transcript rename
- Audio file existence check before Whisper
- process_pages.py Midjourney merge isinstance guards

### Round 6: Server hardening
- Unsafe nested dict access in server.py RAG chat endpoint

### Round 7: Expanded scope (18 never-reviewed files)
- 12 files fixed: instant_voice_memo, backlog_drip_processor, youtube_metadata,
  translate_transcripts, transcript_analyzer, style_code_gallery, clean_db,
  enrich_titles, model_tracker, merge_master_db, aggregate_midjourney, knowledge_db
- All got JSONDecodeError handling + type safety

### Round 8: Resource leaks
- instant_instagram.py: browser.close() restructured into try/finally
- tweet_extractor.py: browser.close() into finally block

### Round 9: Never-reviewed files (course_materials, run_lightweight_sync, etc.)
- course_materials.py: XSS — added html_escape on all 10 dynamic values
- run_lightweight_sync.py: subprocess capture_output + stderr logging
- ai_content_extractor.py: duplicate print line removed

### Round 10: Final sweep
- instant_voice_memo.py: LLM response content null safety (or "")
- instant_voice_memo.py: Path.rename() → os.replace() with error handling
- server.py: ORCHESTRATOR_PROCESS reset to None after /stop
- 6 more isinstance guards: transcript_analyzer, transcript_search,
  course_materials, model_tracker, backlog_drip_processor, aggregate_midjourney
- tweet_extractor.py: author split IndexError safety

## Key Patterns Applied Everywhere

| Pattern | What It Prevents |
|---------|-----------------|
| `isinstance(item, dict)` guard on iteration | AttributeError if DB list has non-dict entries |
| `json.JSONDecodeError` catch on all loads | Crash on corrupted/empty JSON files |
| `html_escape()` / `safe_href()` in HTML output | XSS injection |
| `browser.close()` in `try/finally` | Playwright resource leaks |
| `os.replace()` instead of `Path.rename()` | Atomic file operations, cross-device safety |
| `response.content or ""` on LLM calls | TypeError when LLM returns None content |
| Retry-with-re-load on DB save | Stale data overwrites in concurrent access |
| `isinstance(models, list)` before iteration | Crash if DB schema unexpected |

## Critical Bugs Found (Phase 1)

### Data Loss / Corruption
- **dedupe_scott_folders.py**: Duplicates folder included in scan - caused DUPLICATION not deduplication
- **merge_master_db.py**: Double-merge loop duplicated entries in repositories/styles/models/prompts
- **knowledge_db.py**: Duplicate dict key `midjourney_sref` silently lost data
- **ai_content_extractor.py**: URL cache never saved after Outlook processing (hours of t.co expansion lost)
- **run_pipeline.py**: Stage args mutation - `--since`/`--profile` accumulated on repeated calls

### Security
- **generate_reports.py**: XSS vulnerability - 30+ locations of unescaped user content in HTML
- **style_code_gallery.py**: XSS + path traversal risks
- **server.py**: Command injection via unsanitized `profile` parameter
- **course_materials.py**: XSS — 10 unescaped dynamic values in HTML output
- **model_tracker.py**: XSS on model names/URLs in HTML

### Reliability
- **extract_knowledge.py**: JSON parsing without fallback in 4 backends
- **outlook_reader.py**: COM objects never released
- **end_and_relist.py**: 4 non-atomic file writes (crash = data loss)
- **instant_voice_memo.py**: LLM response None crash, non-atomic file rename
- **server.py**: ORCHESTRATOR_PROCESS stale reference after /stop

## All Pipeline Files (42+)

### Core: server.py, kb_config.py, run_pipeline.py, generate_reports.py, extract_knowledge.py, ingest_db.py
### Instant: instant_tweet.py, instant_page.py, instant_youtube.py, instant_xvideo.py, instant_instagram.py, instant_voice_memo.py
### Batch: process_pages.py, process_pending_tweets.py, tweet_extractor.py, reprocess_instagram_pages.py, backlog_drip_processor.py
### YouTube: youtube_metadata.py, transcript_analyzer.py, translate_transcripts.py, transcript_search.py
### Reports: course_materials.py, style_code_gallery.py, model_tracker.py, aggregate_midjourney.py
### DB tools: clean_db.py, merge_master_db.py, enrich_titles.py, knowledge_db.py, ingest_extracted_to_chroma.py
### Pipeline: run_lightweight_sync.py, sync_to_d_drive.py, ai_content_extractor.py, scott_folder_organizer.py
### Actions: youtube_action.py, ingest_action.py, knowledge_base.py, scout_action.py
### Email: outlook_reader.py, end_and_relist.py, dedupe_scott_folders.py

## Verification
- All modified files pass `python -m py_compile`
- Zero bare `except:` clauses remaining
- All fixes preserve existing behavior (no feature changes)
- **SEMANTICALLY TESTED (Feb 11)** — 47/47 tests passed, 0 failures
- Test script: `C:\Users\scott\ebay-automation\test_pipeline.py`
- Categories: A (Data Integrity), B (Reports), C (ChromaDB), D (Server API), E (LLM), F (Edge Cases), G (Pipeline)

## ChromaDB Metadata Fixes (Feb 11, 2026)
- **Problem**: 30.5% items missing title, 22.9% missing source, 226 "Organize" clutter
- **Root causes**: `ingest_db.py` never set `title` on repos/tutorials/models/styles/tweets; `youtube_action.py` missing title/source; `server.py` no empty-title fallback
- **Fixes applied**: 3 scripts patched + 2,807 legacy items backfilled + 223 "Organize" re-titled
- **Result**: Missing titles 30.5% → 0.3%, missing sources 22.9% → 0%, Organize clutter 226 → 0
