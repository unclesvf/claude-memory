# Image Deduplication Tool

## Quick Reference
- **CLI**: `C:\Users\scott\ebay-automation\image_dedup.py`
- **GUI**: `C:\Users\scott\ebay-automation\image_dedup_gui.py` (tkinter standalone)
- **Tests**: `C:\Users\scott\ebay-automation\test_image_dedup.py` (73 tests, all pass)
- **Branch**: `feature/orchestrator-v1`
- **Latest commit**: `e9f7e0f` — Third-pass audit (Feb 16, 2026)

## Architecture
- 3-phase pipeline: **Scan & Index** → **Hash** (MD5 + pHash) → **Compare & Report**
- SQLite DB per directory (WAL mode, busy_timeout=5000)
- GUI runs CLI as subprocess, parses `PROGRESS:` protocol lines for progress bar + ETA
- Thumbnail preloading via background thread (PIL only — PhotoImage on main thread only)

## Key Technical Decisions
1. **pHash**: 32x32 grayscale → DCT → top-left 8x8 → exclude DC → median threshold with `>=` → 64-bit hex
2. **SSIM**: Content-aware — crops to artwork bounding box, returns `min(full, cropped)`. Variance clamped to `>=0` to prevent float precision issues.
3. **Degenerate hash filter**: `ffffffffffffffff` and `0000000000000000` excluded from visual matching
4. **Grid variation protection**: Same Midjourney UUID + different grid_pos = NEVER a duplicate
5. **Keep priority**: Resolution > non-parenthetical > file size (descending)
6. **Parenthetical matching**: Scoped to same directory. Orphaned parens (no original) skipped.
7. **Non-UUID bucketing**: First 4 hex chars of pHash. Known ~84% miss rate — acceptable for Midjourney (most files have UUIDs).
8. **50MB file size guard**: Files >50MB skip `cv2.imread`, use PIL header-only for dimensions
9. **100MP pixel guard**: Images >100 megapixels skip pHash computation entirely
10. **Path traversal protection**: `--execute-plan` validates all paths under root directory

## CLI Usage
```bash
# Full pipeline (dry run by default)
python image_dedup.py "D:\path\to\images"

# With trash directory
python image_dedup.py "D:\path" --trash "D:\path\dedup_trash"

# Hash only (skip comparison)
python image_dedup.py "D:\path" --hash-only

# Rehash (clear and recompute pHash values)
python image_dedup.py "D:\path" --rehash

# Execute a deletion plan from the HTML report
python image_dedup.py "D:\path" --execute-plan dedup_plan.json

# Validate threshold (test hamming distance calibration)
python image_dedup.py "D:\path" --validate-threshold
```

## GUI Usage
```bash
# Launch with folder
python image_dedup_gui.py "D:\path\to\images"

# Launch with folder picker
python image_dedup_gui.py
```

## Databases
| Directory | DB Path | Files | Status |
|-----------|---------|-------|--------|
| `D:\Midjourney 5-24-2025` | `image_dedup.db` | ~185K | Pipeline complete, internally consistent |
| `D:\Downloads as of 1-10-2026` | `image_dedup.db` | ~99K | Clean run complete (Feb 16), rehashed |
| `D:\To print with Q-Image` | `image_dedup.db` | ~1.2K | Works |
| `D:\Midjourney Upscaled images` | `image_dedup.db` | ~1.6K | Works |

## Downloads Dir Results (Feb 16, 2026 — Clean Run)
- **Phase 1**: 99,387 files indexed in 6m 20s
- **Phase 2**: 4,686 files hashed in 47s (98 files/s)
- **Phase 3**: 514,395 pairs checked in ~2h
  - Pass 1: 0 parenthetical duplicates
  - Pass 2: 8,634 MD5-exact duplicates
  - Pass 3: 69 visual duplicates (49,888 SSIM calls, 51,323 rejected)
- **Total**: 8,703 duplicates, 5.23 GB savings
- **Report**: `D:\Downloads as of 1-10-2026\dedup_report.html` (37MB)
- Note: Previous run (with dedup_trash files included) showed 28,292 dupes / 30.20 GB

## Critical Patterns to Remember

### Thread Safety (GUI)
- **NEVER create `ImageTk.PhotoImage` on a background thread** — causes segfaults
- Use `_prepare_pil_thumbnail()` (thread-safe PIL) → cache as PIL image → convert to PhotoImage on main thread via `load_thumbnail()`
- `_preloading` flag is not locked — benign race, just wasted work
- All `self.after(0, lambda: ...)` calls are needed for thread→main-thread GUI updates

### Memory Management
- `_thumb_cache` capped at 200 entries with LRU eviction (evicts oldest 25%)
- `_pil_preload_cache` stores PIL images from background preload threads
- `_hash_worker` frees intermediates aggressively: `del bgr, alpha, white, composited, gray`
- GUI auto-scales workers: 50K+ files → 2 threads, 10K+ → 3, else → 4

### SQLite
- All connections use `PRAGMA busy_timeout=5000` to handle concurrent access
- DB retry loops MUST close connection in `finally` block (even on retry)
- `except Exception: pass` on DB operations is dangerous — always log or retry
- WAL mode for concurrent reads during GUI display + CLI pipeline

### Image Loading
- **Alpha-channel PNGs**: `_load_grayscale()` composites alpha onto white bg — `IMREAD_GRAYSCALE` drops alpha silently
- **PIL dimension pre-check**: Check via `_PILImage.open().size` BEFORE `cv2.imread` — prevents OOM on oversized images
- **PIL `MAX_IMAGE_PIXELS = None`**: Suppresses DecompressionBomb warning (we only read headers for >50MB files)

### Parenthetical Duplicates
- MUST scope to same directory (`(directory, base_name)` buckets)
- Skip groups where original doesn't exist (browser sequential downloads create `file (1).jpg`, `file (2).jpg` without `file.jpg`)
- MD5 pass still catches truly identical content regardless

### Report & Plan
- HTML report embeds thumbnails as base64 (can be 37-307MB depending on dupe count)
- Plan download via JavaScript buttons in HTML — creates `dedup_exact_plan.json` or `dedup_visual_plan.json`
- `--execute-plan` validates all paths are under root directory (path traversal protection)
- "Already gone" files tracked separately from actual errors in deletion reporting

## Bug Fix History

### Pass 1 (Feb 15): 18 bugs
- pHash formula inconsistency, failed moves still removed from DB, PIL import guard
- 5 silent `except Exception: pass`, crash log overwrite, div-by-zero, trash collision

### Pass 2 (Feb 15): 2 bugs
- `--execute-plan` didn't clean stale DB entries, `_do_move_visual` DB cleanup inconsistency

### Pass 3 (Feb 16): 17 bugs
- **GUI**: PhotoImage on background thread (segfault), unbounded thumbnail cache, DB connection leaks in 4 retry loops, error handler crash, visual move counter, dead code, unused params
- **CLI**: Path traversal in --execute-plan, SSIM negative variance, validate_threshold not directory-scoped, DB connection leak, MemoryError swallowed, busy_timeout, import cleanup, error reporting

### Pre-audit fixes (Feb 14-15): 7 crash fixes
- PIL dimension pre-check (_hash_worker + make_thumbnail_b64), cv2 WARN suppression, scan skip dirs, trash SQL filter, bucket size cap, progress reporting

**Total: 44 bugs fixed** across all sessions

## Git Commits (feature/orchestrator-v1)
| Commit | Description |
|--------|-------------|
| `e9f7e0f` | Third-pass audit: 17 bugs (GUI thread safety, path traversal, SSIM, DB leaks) |
| `0569694` | Downloads crash fixes: PIL pre-check, bucket cap, trash filter |
| `6805bed` | Second-pass audit: 2 bugs |
| `4cb481a` | First-pass audit: 18 bugs |
| `553d085` | Cross-directory false matches, orphaned parens, cascading moves |
| `52d5c77` | OOM crashes on large dirs, GUI stability redesign |

## Known Limitations
- Non-UUID prefix bucketing misses ~84% of visual duplicates for non-UUID files (performance trade-off)
- Files that permanently fail hashing (corrupt/permissions) are retried every run (no `hash_error` sentinel)
- Trash directory flattens structure (files from different subdirs get `_1`, `_2` suffixes)
- HTML report can be very large (307MB for 28K dupes) — Chrome may struggle
- JPEG SOF parser doesn't handle byte-stuffed `FF00` or SOS marker explicitly (unlikely to trigger before SOF)
