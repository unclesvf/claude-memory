# Claude Code Memory — Keyword Index

## User Preferences
- **Don't ask, just fix**: Implement obvious fixes immediately. Don't stop to ask.
- **Always build tests**: Create semantic test suites before shipping.
- Scott values speed and initiative over caution.

## Voice Transcription (Wispr Flow)
- Auctiva→"Octiva", Fotor→"photor", estates→"states", Kimi→"QEMI"/"Kimi"
- Claude Code→"Clio code", Qwen→"qwen-TTS", de-dupe→"DDupont"/"D-Duke"
- STL→"estal", claude-mem→"Clio MIM"/"Cloud Mem"

## Path Display on Windows
- Ensure backslashes visible: `scott\.claude` not `scott.claude`

---

## Project Index
<!-- Each entry: name | status | keywords | file -->

**Ambrose/Cortex KB** | Production | pipeline server chromadb qwen openrouter tweets cortex frontend reports | [ambrose-project.md](ambrose-project.md)

**Knowledge Saver** | Production | chrome extension tweet save youtube page iOS shortcut whisper ingest | [knowledge-saver.md](knowledge-saver.md)

**Image Dedup** | Complete | duplicate photos hash perceptual GUI scan downloads | [image-dedup-project.md](image-dedup-project.md)

**AI Image Fixer** | Stable | repair fix gemini grok inpaint defect upscale | [ai-image-fixer.md](ai-image-fixer.md)

**Image Classifier** | Complete | classify label OpenCV sqlite gallery defect sort midjourney | [image-classifier.md](image-classifier.md)

**Image Upscaling** | In Progress | ESRGAN HAT SUPIR upscale 4x ultrasharp spandrel | [supir-upscaling-debug.md](supir-upscaling-debug.md)

**KDP Formatter** | Pending Audit | kindle book epub pdf coloring reportlab | [kdp-formatter.md](kdp-formatter.md)

**Photo Processor** | Complete | ebay photo background removal rembg tag crop | [photo-processing-pipeline.md](photo-processing-pipeline.md)

**Blender MCP** | Active | 3d model stl print hobbit house mesh addon | [blender-mcp.md](blender-mcp.md)

**Auctiva Pipeline** | Working | csv listing upload playwright photo assign shipping | [auctiva-csv-upload.md](auctiva-csv-upload.md)

**eBay Listing Tool** | Working | linda email outlook title price relist end | [ebay-listing-automation.md](ebay-listing-automation.md)

**Cloudflare Domains** | Active | dns domain pages ssl email migration wrangler a2 | [cloudflare-setup.md](cloudflare-setup.md)

**Chrome Extension (MCP)** | Working | browser automation claude-in-chrome named pipe | [chrome-extension-debug.md](chrome-extension-debug.md)

**Pipeline Audit** | Complete | bugs audit fix security isinstance xss atomic | [pipeline-audit-feb2026.md](pipeline-audit-feb2026.md)

**eBay Dispute DB5** | Won | buyer appeal danbury mint swap return refund | [ebay-danbury-mint-dispute.md](ebay-danbury-mint-dispute.md)

**Education/History** | Active | american history lessons vercel tts edge-tts marp | [education-project.md](education-project.md)

**CLI Tools** | Reference | fzf zoxide bat ripgrep pandoc ffmpeg imagemagick | [cli-tools.md](cli-tools.md)

**claude-mem Plugin** | Audited | memory plugin bun sqlite 37777 | [claude-mem-audit.md](claude-mem-audit.md)

---

## Critical Pitfalls (always loaded — prevents repeat mistakes)

### Image/CV
- NEVER create `ImageTk.PhotoImage` on background thread — segfault
- PIL dimension pre-check BEFORE `cv2.imread` — SVGs can be 596MB decoded
- Alpha-channel PNGs: composite onto white before grayscale
- DO NOT use `AutoPipelineForInpainting` — use `StableDiffusionXLInpaintPipeline`
- SUPIR: DO NOT globally disable SDPA — monkey-patch OpenCLIP only

### SQLite
- `busy_timeout=5000` on all connections for concurrent access
- Close DB connections in `finally` blocks — leaked connections hold WAL locks

### Printing
- DO NOT use Word COM automation — hangs with 32-bit Office
- Working: `WINWORD.EXE /q /n /mFilePrintDefault /mFileExit "file.docx"`
- Printers: HP Officejet Pro 8620 (Network), ET-8550 (Epson photo)

### PyTorch
- Must be `+cu128` not `+cpu` — verify with `torch.cuda.is_available()`

---

## Layered Memory System (this file)
- MEMORY.md = slim keyword index, always loaded (~60 lines)
- Topic files = full details, loaded on demand by keyword match
- ChromaDB = semantic search across all memory files via Cortex
- **Hook**: On each prompt, `~/.claude/hooks/memory_search.py` writes matching topic files to `~/.claude/memory_search_result.txt`. Check this file with Read tool when starting a task to load relevant context.
- **Re-sync ChromaDB**: `cd C:\Users\scott\ebay-automation && python ingest_memory.py`
