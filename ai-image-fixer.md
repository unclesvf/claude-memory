# AI Image Fixer - Full Project Details

## Overview
Standalone desktop/web app for AI-generated image analysis, defect detection, and repair.
Extracted from `image_classifier.py` in ebay-automation, now its own pip-installable package.

**Location:** `C:\Users\scott\ai-image-fixer\`
**Repo:** GitHub (main branch)
**Ports:** API on 8002, Frontend on 5174

## Architecture

### Backend (Python)
- **Package:** `ai_image_fixer` (pip-installable)
- **Framework:** FastAPI + uvicorn
- **Database:** SQLite + WAL mode + FTS5, schema version 4
- **Entry point:** `aif-server` or `python -m uvicorn ai_image_fixer.server.app:app --port 8002`

### Frontend (React + TypeScript)
- **Location:** `frontend/`
- **Stack:** Vite, React 19, TypeScript, Tailwind CSS v4, React Query, React Router, axios, recharts
- **Dev:** `npm run dev` → localhost:5174

### Tauri Desktop App
- **Location:** `src-tauri/`
- **Spawns Python sidecar** for FastAPI server
- **Build:** `npm run tauri build` → .msi/.dmg

## Completed Phases

### Phase 1: Core Python Package (18 modules)
- Two-phase image analysis: Phase 1 (local OpenCV) + Phase 2 (LLM via OpenRouter)
- Repair engines: Gemini, Grok
- Source detection: Midjourney, DALL-E, Stable Diffusion, Gemini, Grok, Mage Spaces
- CLI: `aif scan`, `aif analyze`, `aif repair`, `aif report`, `aif dedup`

### Phase 2: FastAPI REST API (29+ endpoints)
- Image CRUD, search (FTS5), upload, thumbnails, originals
- Analysis jobs with WebSocket progress
- Repair with history and verification
- Stats, settings, costs tracking
- Export, dedup, anatomy rules, scheduling

### Phase 3: React Frontend (7+ pages)
- Dashboard, Gallery, Image Detail, Search, Settings, Analytics, Duplicates
- Dark theme (Tailwind v4 CSS custom properties)
- Responsive, accessible

### Phase 4: Enhanced Features (Feb 12, 2026)
- **4a Style-Aware Prompting:** 10 art styles in `STYLE_REPAIR_HINTS` dict, passed through repair pipeline
- **4b Multi-Engine Voting:** Gemini + Grok parallel via ThreadPoolExecutor, SliderOverlay component (CSS clip-path)
- **4c Print-Readiness:** 8 standard sizes at 300 DPI (5x7 through poster), endpoint + frontend badges
- **4d Platform Export:** Etsy/Redbubble/Society6 — resize, CSV metadata, ZIP packaging
- **4e Batch Scheduling:** `job_queue` SQLite table, schedule/list/cancel endpoints

### Phase 5: Packaging (Feb 12, 2026)
- **5a pip Bundle:** StaticFiles mount for bundled frontend, `aif-server` entry point
- **5b Tauri Desktop:** `src-tauri/` with Python sidecar, window 1280x800
- **5c SaaS Prep:** JWT auth (disabled by default), `StorageBackend` abstraction (Local + S3)

### Phase 6: Nice-to-Haves (Feb 12, 2026)
- **6a Anatomy Rules:** Full CRUD + JSON import/export, merged into SPECIES_ANATOMY on startup
- **6b Defect Heatmap:** SVG overlay, 17 body region coordinates, severity-colored
- **6c Portfolio Analytics:** recharts — score distribution, style pie, subject bars, quality trend, tag cloud
- **6d Duplicate Detection:** pHash (DCT 64-bit), MD5, 3-pass scan, confidence tiers (certain/likely/maybe), undo/restore, Midjourney grid safety

## Test Suite
- **211/211 tests passing** (pytest, ~16s), **0 TypeScript errors** (strict mode)
- Tests in `tests/test_server.py` (API endpoints) and `tests/test_semantic.py` (module-level)
- `TestAuditFixes` (13 tests): thumb_stem, store_phase1, classify_image JSON, LIKE escape, file size guard, filesystem blocks, upload limit, job eviction (analysis + repair), WebSocket reconnect, DuplicatesPage confirm
- `TestSemanticFixes` (10 tests): dimension_restore target_scale, LIKE param count, LIKE all-pages, score buckets, repair accept atomic, upscale eviction, ImageDetail fields, atomic write, WebSocket logging

## DB Schema (version 4)
- v1: Base images + repair_history + costs tables
- v2: Added `phash TEXT`, `md5 TEXT` to images
- v3: Added `job_queue` table
- v4: Added `custom_anatomy_rules` table

## Key Files

| File | Purpose |
|------|---------|
| `ai_image_fixer/server/app.py` | FastAPI app with static mount |
| `ai_image_fixer/database.py` | SQLite schema v4, migrations, CRUD |
| `ai_image_fixer/analysis/local_analysis.py` | Phase 1: OpenCV + pHash + MD5 |
| `ai_image_fixer/analysis/dedup.py` | Duplicate detection (from image_dedup.py) |
| `ai_image_fixer/repair/pipeline.py` | Repair orchestration with style awareness |
| `ai_image_fixer/repair/voting.py` | Multi-engine parallel voting |
| `ai_image_fixer/reports/print_readiness.py` | Print size checking |
| `ai_image_fixer/reports/export.py` | Platform export (Etsy/Redbubble/Society6) |
| `ai_image_fixer/server/auth.py` | JWT + StorageBackend (SaaS prep) |
| `frontend/src/pages/AnalyticsPage.tsx` | recharts analytics dashboard |
| `frontend/src/pages/DuplicatesPage.tsx` | Duplicate scan & manage UI |
| `frontend/src/components/comparison/SliderOverlay.tsx` | Before/after slider |
| `frontend/src/components/comparison/DefectHeatmap.tsx` | Defect SVG overlay |

## Bug Fixes Applied (Pre-Audit)
- `repair.py` route: arg order `repair_image(cfg, file_path)` → `repair_image(file_path, cfg)`
- `processing.py`: `process_phase1()` wrong args (3 locations)
- `cli.py`: `run_repair()` swapped args
- `server/schemas.py`: `ImageDetail` didn't accept NULL DB values
- `test_server.py`: `test_export_stub` → `test_export_requires_body` after export route change
- **`_store_repair_result()` never wrote to `repair_history`** — only created `images` table entries. Fixed to call `store_repair_attempt()` with engine, prompt, attempt_number, verification data
- **Annotations ignored for "clean" images** — if Phase 2 finds no defects but user has annotations, repair now uses annotation text as the prompt (user-directed edit)
- **Sequential repair chaining** — `repair_single()` now checks `repair_history` for latest accepted version and passes its `repaired_path` as `source_override` to `repair_image()`

## Deep Code Audit (Feb 16, 2026) — Commit `3341e2f`
**3-pass review** (syntax/type → runtime → semantic) + 4 parallel semantic agents.
**~165 issues fixed across 30 files**, 23 new regression tests added.

### CRITICAL Fixes
- **`target_scale` NameError** (`dimension_restore.py:67`) — undefined variable crashed every successful ESRGAN upscale
- **Search LIKE param mismatch** (`search.py:288`) — 3 LIKE conditions per synonym but only 2 params → sqlite3.ProgrammingError
- **FTS fallback page-restricted** (`search.py:272`) — LIKE fallback only fired on page 1, pages 2+ returned empty
- **Repair acceptance race condition** (`repair.py:234-239`) — two UPDATEs without transaction → both versions accepted. Fixed with `BEGIN IMMEDIATE`
- **Score distribution overlap** (`stats.py:92`) — `range(0,10,2)` produced duplicate `8-10` bucket. Fixed to `range(0,8,2)`

### HIGH Fixes
- **Thumbnail filename collisions** (`local_analysis.py`) — same-named files in different dirs collided. Added `thumb_stem()` with MD5 path hash
- **In-place image overwrite** (`dimension_restore.py`) — no atomic write; crash during upscale lost repaired file. Now writes to `.tmp` then `replace()`
- **Missing ImageDetail fields** (`schemas.py`) — `phash` and `md5` DB columns not exposed in API response
- **Upscale job memory leak** (`images.py`) — `_upscale_jobs` dict never evicted. Added `_evict_old_upscale_jobs()`
- **Upload size limit** (`images.py`) — no enforcement. Added 200MB streaming limit

### MEDIUM Fixes
- **WebSocket auto-reconnect** (`UploadPage.tsx`) — no reconnect on disconnect; added `stopped` flag + `connect()` pattern
- **LIKE wildcard injection** (`search.py`) — `%` and `_` in user input not escaped. Added `ESCAPE '\\'`
- **Browser `confirm()` dialog** (`DuplicatesPage.tsx`) — replaced with state-based `confirmingRemove` UI
- **Filesystem browse security** (`filesystem.py`) — added `_BLOCKED_PATHS` for `.ssh`, `.gnupg`, `.aws`, etc.
- **RepairQueuePage wrong counts** — used client-side filter instead of `data?.total`
- **JSON regex** (`api_classification.py`) — non-greedy `\{[\s\S]*?\}` broke nested JSON. Changed to greedy
- **Midjourney param regex** (`source_detection.py`) — `--\w+` didn't match `--no-upscale`. Changed to `--[\w-]+(?:\s+[\d.:]+)?`
- **Color temperature boundary** (`local_analysis.py`) — hue 165 ambiguous between warm/cool. Fixed comment and boundary
- **WebSocket error logging** (`websocket.py`) — silent `except Exception: pass` → `log.debug()`

### Audit Methodology (for reuse)
1. **6 parallel file-read agents** for initial scan (~155 raw issues found)
2. **Priority triage**: CRITICAL → HIGH → MEDIUM → LOW across 6 task categories
3. **4 parallel semantic agents**: analysis pipeline, repair pipeline, server routes, frontend logic
4. **False positive filtering**: Many frontend agent findings were incorrect (e.g., DPR scaling was already correct, ImageCard `originalUrl` was local function not missing import)
5. **Regression tests written alongside each fix** — never commit a fix without a test

## UX Improvements (Feb 15, 2026)
- **Repair History UI redesigned** — color-coded cards (green=accepted, red=failed, neutral=default)
- **Failed repairs show details** — `missing_elements` and `new_defects` from verification displayed inline
- **Accept Anyway button** — yellow button for failed repairs, green for passed
- **Retry button** — on every repair history entry, re-triggers repair with current annotations
- **Auto-retry toggle** — checkbox next to Repair button, retries up to 3x on failed verification
- **Toast persistence** — repair completion/failure toasts persist until dismissed (duration=0)
- **Auto-show repair result** — after repair completes, automatically displays the latest version
- **Annotation improvements** — rectangle/area tool added, brush default 16px (was 4px) with highlighter effect, brush size controls +/- (4-40px range)
- **Auto-save annotations** — `useEffect` saves to localStorage on every change, no need to click Save before Repair

## API Keys & Environment
- **Google API key:** `AIzaSyB9os3cEP6S8fqcButQx9zyVAdc35r05fY` (PAID tier, image editing works)
- **Old stale key:** `AIzaSyARKP...` had zero image editing quota — DO NOT USE
- **`@lru_cache` on `get_config()`** caches at server startup — must fully restart server (not just --reload) when env vars change
- **Shell session stale vars:** `setx` sets for NEW processes only. Existing shells keep old values. Always verify `echo %GOOGLE_API_KEY%` before starting server
- **xAI key:** `XAI_API_KEY` set via `setx`
- **OpenRouter key:** `OPENROUTER_API_KEY` set via `setx`

## Remaining Known Issues (Post-Audit)
- `repair_history` table: some entries may share `repaired_path` (sequential repairs overwrite same file)
- Ghost PIDs on port 8002 after `Stop-Process` — Windows TCP lingering issue, resolves after ~30s
- `recharts` library makes JS bundle ~750KB — could code-split with dynamic import
- `concurrent.futures` coroutine warnings in tests (2 warnings, non-blocking, cosmetic)
- **Design-level (not bugs):** Voting pipeline doesn't support chaining; `accepted=0` semantics block sequential repair on partial repairs; verification without original image falls back to classify-only mode
- **Export platform list hardcoded** in download route — only checks etsy/redbubble/society6 dirs

## Agent Team Pattern (for reference)
- Used 3 parallel agents: backend-core, backend-features, frontend
- Coordinated via shared task list (13 tasks)
- Schema version conflicts resolved by sequential migrations (v2→v3→v4)
- All agents completed successfully with no destructive file conflicts
