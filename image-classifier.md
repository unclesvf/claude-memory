# AI Image Classifier - Implementation Details

## Script Location
`C:\Users\scott\ebay-automation\image_classifier.py`

## Architecture
- **Single self-contained script** (~2,540 lines), no modifications to shared files
- Only imports `get_logger` from `kb_config.py`
- SQLite database with WAL mode for concurrent access
- ThreadPoolExecutor for Phase 2 parallelism (each thread gets own DB connection)

## Database
- **Path**: `D:\AI-Knowledge-Base\image_classifier.db`
- **Schema**: `images` table + `images_fts` FTS5 virtual table with sync triggers
- Indexes on: source, subject_type, defect_severity, score_average, score_print_viability, art_style, file_hash, source_dir

## Processing Phases
### Phase 1 (Local, Free, ~100 images/sec)
- File metadata (size, SHA-256 of first 64KB)
- PIL dimensions (header-only read)
- OpenCV k-means dominant colors (5 colors, downscaled to 256px)
- Color temperature (warm/cool/neutral from HSV hue analysis)
- Average brightness (V channel)
- Source detection from filename regex

### Phase 2 (Gemini 2.0 Flash via OpenRouter, ~$0.0004/image)
- Base64 JPEG at 1024px max side, quality 85
- Structured JSON prompt for: subject_type, description, character_details, art_style, aesthetics (7 scores 1-10), defects, commercial_tags
- 3 retries with exponential backoff, rate limit handling (429)
- json_repair fallback for malformed responses
- Per-thread SQLite connections for thread safety

## Source Detection Patterns
- `wolverine1970_[prompt]_[UUID].png` → midjourney
- `wolverine1970_[prompt]_[UUID]_[0-3].png` → midjourney (grid variant)
- `wolverine1970_httpss.mj.run..._[prompt]_[UUID].png` → midjourney (reference image)
- `Gemini_Generated_Image_[hash].png` → gemini
- `grok[-_]...` → grok
- Directory name fallback: "midjourney" in parent → midjourney

## Output Locations
- **DB**: `D:\AI-Knowledge-Base\image_classifier.db`
- **Thumbnails**: `D:\AI-Knowledge-Base\thumbnails\` (300px JPEG, MD5 filename)
- **Defect sort**: `D:\AI-Knowledge-Base\ToFix\{Minor,Moderate,Severe}\` (copies, not moves)
- **HTML report**: `D:\AI-Knowledge-Base\exports\image_gallery.html`
- **Repaired**: `D:\AI-Knowledge-Base\Repaired\`

## Image Repair — PRODUCTION READY (Feb 11-12, 2026)

### Dual-Engine Repair: Gemini SDK + Grok Edits Endpoint

Two engines available, both produce near-surgical edits preserving composition, pose, outfit, and background while fixing defects. Auto mode tries Gemini first, falls back to Grok.

### Animal-Aware Prompting (Feb 12, 2026)
- **Problem**: Grok was converting animal paws/claws to human hands during finger/hand repairs
- **Solution**: `_detect_animal_character()` detects species from `character_details` DB field
- Uses `species:` field first, then word-boundary regex for animal keywords
- Adds `CRITICAL` instruction to repair prompt: "keep paws as paws, do NOT convert to human hands"
- Gemini prompt also adds "All animal features: paws, claws, fur texture, snout, ears, tail" to DO NOT CHANGE list
- **23 animal characters detected** in current defect set (rabbits, hamsters, squirrels, owls, cats, frogs)

### Color Anchoring (Feb 12, 2026)
- `_extract_color_details()` extracts hair/eye/fur/skin colors from `character_details`
- Adds explicit "Preserve these exact colors" instruction to repair prompt
- Prevents hair/eye color drift during repair

### Dimension Restoration (Feb 12, 2026)
- **Problem**: Grok returns images at ~1232x832 when originals were 2624x1792 (78% pixel loss)
- **Solution**: `_restore_dimensions()` runs after successful repair
- Uses local **UltraSharp ESRGAN** (4x) via spandrel for best quality (~4s/image on GPU)
- Falls back to Lanczos resize if model not available
- Automatically selects 2x or 4x scale based on needed magnification
- Only activates when repaired image is <90% of original pixel area

#### Engine 1: Gemini SDK (Google `google-genai` package)
- **Endpoint**: `client.models.generate_content()` with `response_modalities=["TEXT", "IMAGE"]`
- **Model**: `gemini-2.5-flash-image`
- **Quality**: Near-surgical, ~7s/image single-turn
- **Requires**: `GOOGLE_API_KEY` env var (Tier 1 recommended, free tier rate-limited)
- **Implementation**: `_repair_with_gemini_sdk()` primary, `_repair_with_gemini_rest()` fallback
- **Note**: Gemini Tier 1 key may still hit rate limits on image generation model specifically

#### Engine 2: Grok `/v1/images/edits` REST endpoint (NEW Feb 11, 2026)
- **Endpoint**: `POST https://api.x.ai/v1/images/edits` (dedicated editing endpoint)
- **Model**: `grok-imagine-image`
- **Quality**: Near-surgical, ~7s/image, comparable to Gemini SDK
- **Requires**: `XAI_API_KEY` env var
- **Cost**: ~$0.07/image (flat per-image billing)
- **No rate limiting** observed in batch of 104 images
- **Image format**: Must use data URI (`data:image/jpeg;base64,...`), not raw base64
- Uses `httpx` directly — no `xai_sdk` dependency needed

#### What Does NOT Work for Repair:
- **OpenRouter**: Strips thought signatures, always regenerates. Do NOT use.
- **Free tier Google API key**: RESOURCE_EXHAUSTED for image generation models
- **Grok SDK `client.image.sample()`**: Routes to generation endpoint, ignores input image. Do NOT use.
- **Grok REST generation endpoint**: Same problem — generates from prompt, ignores input image

### Batch Repair Results (Feb 11, 2026)
- **104 images processed** in ~25 minutes using Grok engine
- **100 fixed** (96%) — all anatomy/finger/hand defects repaired perfectly
- **4 partial** — all text/garbled text defects (Grok replaces text content rather than removing)
- **0 failed** — no errors or crashes
- **~15s/image average** (7s Grok API + 5s verification + overhead)
- All anatomy repairs: `verdict=pass, faithfulness=identical, score=8`
- Text repairs: `verdict=fail, faithfulness=similar` — text content changes but composition preserved

### Repair Limitations
- **Text defects** (garbled text on armor/books/screens) are hard to fix — model replaces text with different text rather than cleaning it. Verifier correctly flags as `similar` not `identical`.
- **Face defects** may need more careful prompting
- Gemini Tier 1 key may rate-limit on image gen model even though general API works fine

### API Keys
- **Google AI Studio (Tier 1)**: `AIzaSyB9os...O5fY` — "Image Repair (Tier 1)" in History 1 project
- **Google AI Studio (Free, DEPRECATED)**: `AIzaSyARKP...hJz0` — Midjourney project, rate-limited
- **xAI**: `xai-vyG0k8Z...` in `api-keys.json`
- **OpenRouter**: env var `OPENROUTER_API_KEY` (for Phase 2 classification only, NOT repair)
- All keys stored in `C:\Users\scott\.claude\api-keys.json`

### Repair Pipeline Flow
1. `get_defect_info()` — reads defects from DB (classifies first if needed)
2. `build_repair_prompt()` — engine-specific prompt (Gemini vs Grok style)
3. `repair_with_gemini()` or `repair_with_grok()` — edit image via API
4. `verify_repair()` — sends BOTH original + repaired to Gemini 2.5 Flash for comparison
5. Retry loop (up to 3 attempts) with best-effort tracking
6. `_store_repair_result()` — runs classify_image() on repaired version for proper Phase 2 data

### Implementation Details
- `repair_with_gemini()`: tries Google SDK (`_repair_with_gemini_sdk`), falls back to REST API (`_repair_with_gemini_rest`)
- `repair_with_grok()`: direct `httpx.post()` to `/v1/images/edits` with data URI, `response_format="b64_json"`
- Engine selection in `repair_image()`: only checks `GOOGLE_API_KEY` for Gemini (no OpenRouter), `XAI_API_KEY` for Grok
- Auto mode: Gemini first → Grok fallback if Gemini fails

### Test Scripts
- `test_gemini_multiturn.py` — Google SDK multi-turn vs single-turn comparison (2s between turns for Tier 1)
- `test_sdxl_inpaint.py` — SDXL local inpainting test (ready, needs free GPU)

### Test Images in Repaired Directory
- `test_gemini_multiturn.png` — Google SDK multi-turn result (**GOOD** — near-surgical)
- `test_gemini_singleturn.png` — Google SDK single-turn result (**GOOD** — near-surgical)
- `test_grok_edits_endpoint.png` — Grok `/v1/images/edits` (**GOOD** — near-surgical, same quality as Gemini)
- `test_grok_detailed.png` — Grok SDK `image.sample()` (full regeneration, NOT surgical — old method)
- `test_grok_grok-imagine-image.png` — Grok SDK (full regeneration — old method)
- `test_multiturn_or.png` — OpenRouter multi-turn result (regenerated, NOT surgical)
- `test_nanobananapro.png` — Gemini 3 Pro (worst, complete regen)

### SDXL Inpainting (Local Alternative — Still Available)
- **Model**: `diffusers/stable-diffusion-xl-1.0-inpainting-0.1` (6.6GB, cached)
- **Import**: Use `StableDiffusionXLInpaintPipeline` directly (bypasses HunyuanDiT/MT5Tokenizer conflict)
- **DO NOT use** `AutoPipelineForInpainting` — triggers transformers 5.1.0 incompatibility
- **PyTorch**: Fixed to `2.10.0+cu128` (was CPU-only from diffusers install)
- **Key params**: `strength=0.65-0.70`, `guidance_scale=10.0`, `padding_mask_crop=48`, `num_inference_steps=35`
- **Pixel-perfect**: `Image.composite(inpainted, original, mask)` preserves everything outside mask

## Code Audit (Feb 11-12, 2026)
- 5 bugs fixed: XSS in gallery (html.escape), repair schema mismatch (_store_repair_result), PIL file handle leak, Mage Spaces typos, verify fallback warning
- Grok repair rewritten: SDK `image.sample()` → REST `/v1/images/edits` endpoint
- Engine selection cleaned: removed OpenRouter references from repair path
- Animal-aware prompting: `_detect_animal_character()` + word-boundary regex species detection
- Color anchoring: `_extract_color_details()` preserves hair/eye/fur/skin colors in prompt
- Dimension restoration: `_restore_dimensions()` upscales shrunk repairs via UltraSharp ESRGAN
- `get_defect_info()` now returns `character_details` field for prompt building
- All syntax-checked, **47/47 tests passing**

## CLI Quick Reference
```bash
python image_classifier.py                           # Process Downloads
python image_classifier.py --input "D:\Midjourney 5-24-2025"  # Midjourney
python image_classifier.py --phase 1                 # Local only
python image_classifier.py --phase 2 --limit 50      # API batch
python image_classifier.py --concurrency 5           # 5 parallel API calls
python image_classifier.py --recursive               # Scan subdirs
python image_classifier.py stats                     # Show stats
python image_classifier.py search "cyberpunk"        # FTS search
python image_classifier.py top --by score_print_viability  # Best prints
python image_classifier.py defects                   # List defects
python image_classifier.py --sort                    # Copy defects to ToFix/
python image_classifier.py --report                  # HTML gallery
python image_classifier.py --reset --phase 2         # Re-classify only
python image_classifier.py repair "path/image.png"   # Repair specific image
python image_classifier.py repair --fixable           # Repair minor+moderate
python image_classifier.py repair --fixable --engine grok  # Grok only (fastest)
python image_classifier.py repair --all-defects       # Repair all defective
```

## Cost Estimates
| Dataset | Images | Phase 2 Cost | Repair Cost (Grok) | Repair Cost (Gemini) |
|---------|--------|-------------|--------------------|-----------------------|
| Downloads | 622 | $0.25 | ~$0.07/image | ~$0.02/image |
| Midjourney main | 120,588 | $48 | ~$0.07/image | ~$0.02/image |
| Upscaled | 4,606 | $1.84 | ~$0.07/image | ~$0.02/image |

## Known Model Limitations (Revisit Periodically)
- **Bird talon direction**: Neither Grok nor Gemini can reliably render zygodactyl feet (3 forward, 1 backward hallux). Both produce 4 forward-facing talons regardless of prompt specificity. Tested Feb 12, 2026 with explicit directional prompts on both engines — neither succeeded.
- **Not commercially significant**: General public does not notice talon arrangement on fantasy owl art. Only specialists (ornithologists, zoologists) would spot it.
- **Action**: `SPECIES_ANATOMY` detection rules are in place. When models improve, re-run `repair --fixable` on flagged bird images. Check after major Grok/Gemini model updates.
- **Text defects**: Models replace garbled text with different text rather than removing it. Verifier correctly flags as `similar` not `identical`.

## Testing (Feb 9-12, 2026)
- Phase 1: 10 images in 0.9s (100% success)
- Phase 2: 10 images in 16.8s via 3 concurrent (100% success, all clean)
- Repair (Gemini SDK): ~7s/image, near-surgical quality
- Repair (Grok edits): ~7s/image, near-surgical quality, no rate limits
- **Batch repair**: 104 images, 100 fixed / 4 partial (text defects) / 0 failed, ~25 min total
- Search: FTS5 working on descriptions, tags, character details
- Stats: Source/style/subject breakdowns working
- Report: HTML gallery with filters, pagination, modal viewer
