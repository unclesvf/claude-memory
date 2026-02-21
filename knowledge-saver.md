# Knowledge Saver System

**Status:** Production Ready with Full Tweet Pipeline + Markdown Logging
**Chrome Extension:** `C:\Users\scott\tweet-saver-extension\`
**Server:** FastAPI on port 8001
**Extraction Log:** `D:\AI-Knowledge-Base\extraction_log.md`

## What It Does

| Content Type | How to Save | Processing |
|--------------|-------------|------------|
| **X.com Tweets** | Click "Save" button on any tweet | Instant Qwen 3 extraction for 100+ char tweets |
| **X.com Video Tweets** | Click "Save" on tweet with video | Background: yt-dlp → local Whisper (GPU) → Qwen 3 |
| **YouTube Videos** | Click extension icon → "Save Video" | Background: transcript → Qwen 3 |
| **Web Pages** | Click extension icon → "Save Page" | Background: content → Qwen 3 + Midjourney regex |
| **iOS Shortcut** | Share any URL → "Save to KB" | Auto-detects type, processes accordingly |

## Server Endpoints (port 8001)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/save` | POST | **Universal endpoint** - auto-detects content type |
| `/tweets` | POST | Save tweet with content, triggers Qwen extraction |
| `/tweets` | GET | List tweets with filters |
| `/tweets/stats` | GET | Extraction statistics |
| `/pages/save` | POST | Save web page content |
| `/youtube/save` | POST | Save YouTube video |

## Key Scripts

| Script | Purpose |
|--------|---------|
| `instant_tweet.py` | Tweet LLM extraction via Qwen 3 235B on OpenRouter |
| `instant_youtube.py` | YouTube transcript → Qwen 3 extraction |
| `instant_xvideo.py` | X.com video: yt-dlp → local Whisper (GPU) → Qwen 3 |
| `instant_page.py` | Web page instant processing |
| `process_pending_tweets.py` | Batch process tweets with content but no extraction |
| `ingest_db.py` | Ingest all content into ChromaDB |

## Quick Commands

```bash
python process_pending_tweets.py      # Process pending tweets
python ingest_db.py                   # Re-ingest to ChromaDB
python generate_reports.py            # Regenerate HTML reports
curl http://localhost:8001/tweets/stats  # Check stats
```

## Tweet Processing Pipeline

1. Chrome Extension saves tweet via `/tweets` POST
2. server.py stores in master_db.json
3. instant_tweet.py runs Qwen 3 for tweets >= 100 chars
4. Extraction stored in tweet's `extracted_knowledge` field
5. ingest_db.py adds to ChromaDB for Cortex search
6. generate_reports.py includes in HTML reports

## Midjourney Data Extraction

Uses **regex pre-extraction** for sref codes, profile codes, prompts, parameters from mangled DOM text. Merged with LLM extraction for complete coverage.

## iOS Shortcut

**Tailscale IP:** `100.127.29.22`
POST to `http://100.127.29.22:8001/save` with `{"url": "...", "source": "ios"}`
Docs: `C:\Users\scott\ebay-automation\docs\ios-shortcut-setup.md`

## Data Storage

- **Tweets/YouTube/Pages**: `D:\AI-Knowledge-Base\master_db.json`
- **X.com Video Audio**: `D:\AI-Knowledge-Base\xvideos\`
- **X.com Transcripts**: `D:\AI-Knowledge-Base\xvideos\transcripts\`
- **Extraction Log**: `D:\AI-Knowledge-Base\extraction_log.md`
- **ChromaDB**: `C:\Users\scott\ebay-automation\data\knowledge_base\`

## X.com Video Pipeline

yt-dlp → Local Whisper (base model, GPU) → Qwen 3 via OpenRouter. Transcripts stored in `D:\AI-Knowledge-Base\xvideos\transcripts\`.

## Legacy: Email-based Tweet Extraction

Script: `tweet_extractor.py` — Playwright + cookie auth from `x_cookies.json`
Pipeline stage: `python run_pipeline.py --stage tweets`

## Troubleshooting

- **Tweets not extracted?** Check 100+ chars, run `process_pending_tweets.py`, verify `OPENROUTER_API_KEY`
- **Not in Cortex?** Run `ingest_db.py`, restart server
- **X.com blocks?** Use Chrome extension, not Playwright
- **Whisper?** `pip install openai-whisper`, requires ffmpeg
