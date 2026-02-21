# Ambrose AI Knowledge Base

**Location:** `C:\Users\scott\ebay-automation\` (scripts) + `D:\AI-Knowledge-Base\` (data)
**Status:** Production Ready - February 2, 2026
**Full Documentation:** `PROJECT_STATUS.md`

## What It Does

Full-stack AI knowledge extraction system:
- Extracts GitHub repos, HuggingFace models, YouTube tutorials from Outlook emails
- LLM backends: **OpenRouter (Qwen 3 235B - recommended)** or local vLLM (Qwen2.5-7B)
- Downloads transcripts, analyzes content, builds ChromaDB vector search
- Generates HTML reports, course materials, Midjourney style galleries
- React frontend (Cortex) for semantic search

## Cloud API Keys

| Service | Purpose | Env Variable |
|---------|---------|--------------|
| **OpenRouter** | Multi-model LLM access (Qwen 3, DeepSeek, Gemini, etc.) | `OPENROUTER_API_KEY` |
| **DeepInfra** | Orpheus TTS for lesson narration | `DEEPINFRA_API_KEY` |

### OpenRouter Configuration

**Model:** Qwen 3 235B MoE (`qwen/qwen3-235b-a22b-2507`)
- 262k token context window - sends whole transcripts instead of chunks
- 25% more extractions than Qwen 2.5
- ~$0.01 per video (cheapest input tokens)

**extract_knowledge.py Optimizations:**
- `max_tokens=8000` - Large JSON output for comprehensive extraction
- `timeout=300` - 5 minutes for massive transcripts (126k+ tokens)
- Context-aware chunking: Whole transcripts sent when <262k tokens
- JSON repair fallback: Uses `json_repair` package when output is malformed
- `LLM_BACKEND=openrouter` environment variable

**Usage:**
```bash
LLM_BACKEND=openrouter python extract_knowledge.py --force
setx LLM_BACKEND openrouter
```

**Other Models Tested:**
- **Qwen 2.5 72B** - Previous recommendation, still good
- **DeepSeek V3.2** - Fastest, good quality
- Test script: `C:\Users\scott\ebay-automation\openrouter_test.py`
- Comparison script: `C:\Users\scott\ebay-automation\compare_models.py`

### Orpheus TTS Voices (DeepInfra)
- **Female:** tara, leah, jess, mia
- **Male:** leo, dan, zac
- Supports emotion tags: `<sigh>`, `<chuckle>`, `<laugh>`, `<gasp>`
- Test script: `C:\Users\scott\ebay-automation\test_orpheus_tts.py`

## Quick Commands

```bash
python run_pipeline.py                    # Full pipeline
python run_pipeline.py --no-open          # Without browser
python run_pipeline.py status             # Status
python run_pipeline.py --stage llm        # Single stage
python run_pipeline.py --list-stages      # List stages

# Server (port 8001)
cd C:\Users\scott\ebay-automation
python -m uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend (port 5173)
cd C:\Users\scott\ebay-automation\frontend
npm run dev
```

## Pipeline Stages (11 total)

1. **extract** - Extract URLs from emails (runs FIRST)
2. **organize** - Organize Outlook emails into subfolders
3. **youtube** - Fetch video metadata/transcripts
4. **analyze** - Extract tools, tips from transcripts
5. **search** - Build FTS5 search index
6. **llm** - vLLM/QWEN knowledge extraction (4 hour timeout)
7. **reports** - Generate HTML reports
8. **gallery** - Generate Midjourney sref gallery
9. **models** - Generate AI model tracking report
10. **courses** - Generate course materials
11. **sync** - Sync to D: drive

## Key Files

| File | Purpose |
|------|---------|
| `run_pipeline.py` | Master orchestration script |
| `server.py` | FastAPI backend (port 8001) + Chrome extension endpoints |
| `extract_knowledge.py` | vLLM/Ollama knowledge extraction |
| `instant_youtube.py` | Instant YouTube processing |
| `instant_xvideo.py` | X.com video processing |
| `instant_page.py` | Instant web page processing |
| `process_pages.py` | Batch web page LLM extraction |
| `ai_content_extractor.py` | Email URL extraction |
| `scott_folder_organizer.py` | Email organization |
| `kb_config.py` | Shared configuration |

## ChromaDB

Path: `C:\Users\scott\ebay-automation\data\knowledge_base\`
Collection: `uncles_wisdom`
Both server.py and orchestrator actions use this same path.

## Current Stats (Feb 2, 2026)

- 124 GitHub repos, 45 HuggingFace models, 51+ YouTube tutorials
- 52+ extracted knowledge files (YouTube + Google Drive)
- 882+ tweets saved, 44 with Qwen extraction
- 22 web pages processed with Midjourney sref/profile extraction

## Google Drive Integration

**Status:** Active - rclone configured with OAuth
**Tracker:** `D:\AI-Knowledge-Base\gdrive_extraction_tracker.json`

```bash
rclone ls gdrive:
rclone copy gdrive:filename.docx .
rclone copy gdrive: . --include "*.docx" --drive-export-formats docx
```

### Extracted Content (8 knowledge files)

| File | Content |
|------|---------|
| Ultimate Clawdbot from Robert Scribble | Scoble's 5,620 post trend analysis |
| Nano Banana Pro Prompting Guidelines | Google Gemini 3 image gen guide |
| Digital Marketing Tools Cheat Sheet | 30+ AI tools curated list |
| AI Agents Weekly (Jan 31) | Project Genie, Kimi K2.5, MCP Apps |
| UV Printing Masterclass | EUFYmake E1 technical guide |
| Laser Engraving Fabric Guide | CO2 laser on textiles |
| Maverick's Viral Prompt Library | Writing prompts, banned words |
| X.com Tweets (8 posts) | OpenClaw ecosystem, Moltworker |

### Key Knowledge Discovered

- **Moltworker** - Run Clawdbot on Cloudflare Workers (no hardware)
- **OpenClaw Ecosystem** - bankrbot, moltbook, 4claw.org, openwork.bot, clawarena.ai
- **Local Memory Embeddings** - Ollama gemma-300M (328MB) for free private semantic memory
- **Maverick's Banned Words** - Avoid: delve, embark, craft, realm, game-changer, unlock, tapestry
