# KDP Formatter — Project Details

## Overview
Amazon KDP book formatting tool. Takes source content → produces upload-ready files.
- **eBook mode**: Markdown/TXT/DOCX → EPUB + DOCX with front matter, TOC, metadata
- **Coloring Book mode**: PNG/JPG images or PDF → KDP-ready interior PDF at 300 DPI

## Location & Ports
- **Project:** `C:\Users\scott\kdp-formatter\`
- **Backend:** FastAPI on port **8003** (avoid 8000=vLLM, 8001=Ambrose, 8002=AI Image Fixer)
- **Frontend:** React+Vite+TS on port **5175** (avoid 5173=Ambrose, 5174=AI Image Fixer)

## Quick Start
```bash
# Backend
cd C:\Users\scott\kdp-formatter
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8003

# Frontend
cd C:\Users\scott\kdp-formatter\frontend
npm run dev

# Tests
cd C:\Users\scott\kdp-formatter
python -m pytest tests/ -v  # 42/42 passing

# Frontend build check
cd frontend && npx tsc --noEmit && npm run build
```

## Dependencies
**Python:** fastapi, uvicorn, python-multipart, python-docx, Pillow, Jinja2, ebooklib, reportlab, markdown, PyMuPDF, pydantic
**npm:** react, react-dom, vite, typescript (standard Vite React-TS template)

## Architecture

### Backend Files
| File | Purpose |
|------|---------|
| `backend/app.py` | FastAPI entry, CORS, workspace cleanup on startup |
| `backend/config.py` | All KDP constants: trim sizes, margins, spine formula, paper thickness |
| `backend/models/project.py` | BookProject, Chapter, PageImage pydantic models |
| `backend/models/metadata.py` | KDPMetadata with validators (7 keywords max, 4000 char desc) |
| `backend/models/kdp_specs.py` | TrimSize, PaperType enums |
| `backend/routers/ebook.py` | Create project, upload manuscript, chapter CRUD, export EPUB/DOCX |
| `backend/routers/coloring.py` | Create project, upload images/PDF, page management, export interior PDF |
| `backend/routers/cover.py` | Cover upload/validate, spine calculator, template PDF, preview endpoints |
| `backend/routers/metadata.py` | Metadata CRUD, project settings (trim/paper/bleed) |
| `backend/services/markdown_parser.py` | Split MD on `# ` headings, convert to HTML via `markdown` lib |
| `backend/services/docx_reader.py` | Split DOCX on Heading 1/2 styles, fallback to single chapter |
| `backend/services/ebook_builder.py` | Assemble EPUB (ebooklib) + DOCX (python-docx) with Jinja2 front matter |
| `backend/services/coloring_builder.py` | Image analysis, DPI/grayscale prep, reportlab interior PDF assembly |
| `backend/services/cover_service.py` | Cover validation, spine calc, full-wrap dimensions, template PDF with guide lines |
| `backend/services/preview_service.py` | PyMuPDF PDF→PNG rendering, HTML preview wrapper |
| `backend/templates/` | Jinja2: title_page.html, copyright_page.html, toc.html |

### Frontend Files
| File | Purpose |
|------|---------|
| `src/App.tsx` | Root: view routing (home/ebook/coloring) |
| `src/pages/HomePage.tsx` | Mode picker cards |
| `src/pages/EbookWizard.tsx` | 5-step: Upload → Metadata → Chapters → Preview → Export |
| `src/pages/ColoringWizard.tsx` | 5-step: Upload → Settings → Arrange → Preview → Export |
| `src/api/client.ts` | All API calls with fetch wrapper |
| `src/types/index.ts` | TS interfaces matching backend models |

### API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/ebook/create` | New eBook project |
| POST | `/api/ebook/{id}/upload` | Upload MD/TXT/DOCX |
| GET | `/api/ebook/{id}/chapters` | List chapters |
| PUT | `/api/ebook/{id}/chapters` | Reorder/rename all chapters |
| PUT | `/api/ebook/{id}/chapters/{idx}` | Edit single chapter |
| POST | `/api/ebook/{id}/export` | Export EPUB and/or DOCX |
| GET | `/api/ebook/{id}/export/{fmt}` | Download exported file |
| POST | `/api/coloring/create` | New coloring book project |
| POST | `/api/coloring/{id}/upload` | Upload images/PDF |
| GET | `/api/coloring/{id}/pages` | List pages with validation |
| PUT | `/api/coloring/{id}/pages` | Reorder pages |
| DELETE | `/api/coloring/{id}/pages/{idx}` | Remove page |
| POST | `/api/coloring/{id}/export` | Export interior PDF |
| GET | `/api/coloring/{id}/export/pdf` | Download interior PDF |
| GET/PUT | `/api/metadata/{id}` | Get/update metadata |
| GET | `/api/metadata/{id}/validate` | Check KDP readiness |
| PUT | `/api/metadata/{id}/settings` | Update trim/paper/bleed |
| POST | `/api/cover/{id}/upload` | Upload cover image |
| GET | `/api/cover/{id}/spine` | Calculate spine width |
| GET | `/api/cover/{id}/template` | Download cover template PDF |
| GET | `/api/cover/{id}/preview/page/{n}` | Preview page as PNG |
| GET | `/api/cover/{id}/preview/info` | Preview page count |
| GET | `/api/health` | Health check |
| GET | `/api/trim-sizes` | List all KDP trim sizes |

## KDP Specs Embedded in Code
- **15 trim sizes** from 5x8 to 8.5x11
- **Paper thickness:** white=0.002252, cream=0.0025, standard_color=0.002347, premium_color=0.002602 inches/page
- **Inside margins:** 0.375" (24-150pp), 0.500" (151-300), 0.625" (301-500), 0.750" (501-700), 0.875" (701-828)
- **Bleed:** 0.125" on each edge
- **eBook cover:** 1600x2560 JPEG RGB
- **Min DPI:** 300, Max pages: 828, Min pages: 24
- **Keywords:** max 7, Description: max 4000 chars

## Project Workspace
Each project gets `backend/workspace/{uuid}/` with:
- `uploads/` — original files
- `images/` — normalized coloring pages
- `prepared/` — processed images ready for PDF
- `exports/` — EPUB, DOCX, PDF outputs
- `preview/` — cached preview PNGs
- `project.json` — serialized BookProject state
Auto-cleanup: workspaces older than 24h deleted on server startup.

## Status & Next Steps
- **Built:** Feb 16, 2026 — one session, all features functional
- **AUDITED:** Feb 17, 2026 — 22 bugs found and fixed
- **Tests:** 63/63 passing (42 original + 21 new audit tests)
- **Frontend:** Clean build, 0 TS errors
- **After audit:** Consider adding drag-reorder for chapters/pages, cover image upload preview, DOCX HTML-to-formatted-paragraphs instead of strip-tags

## Audit Summary (Feb 17, 2026)
- **22 bugs fixed** across 12 files in single pass
- Key fixes:
  - **CRASH**: `cover.py:34` — Path + str TypeError from operator precedence
  - **PATH TRAVERSAL** (x2): upload handlers used raw `file.filename` — now sanitized via `Path(filename).name`
  - **XSS** (x4): Jinja2 autoescape enabled, `html.escape()` on EPUB titles, preview HTML, DOCX run text
  - **RESOURCE LEAKS** (x5): PIL Images and fitz docs now use `with`/`try-finally`
  - **SILENT BUG**: `export_ebook` formats param was query (ignored JSON body) — now uses `Body()`
  - **FORMAT CHECK**: Cover validation checks `img.format` not file extension
  - **CODE QUALITY**: 4x `_get_project` deduped into `backend/project_utils.py`, unused imports removed, duplicate CORS removed
- New file: `backend/project_utils.py` — shared `get_project()`, `save_project()`, `sanitize_filename()`
- Test file: `tests/test_audit_fixes.py` — 21 tests covering all critical bugs
