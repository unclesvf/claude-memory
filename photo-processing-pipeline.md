# Photo Processing Pipeline - IMPLEMENTED (Feb 9, 2026)

## Status: WORKING - Tested on 3 batches (7 photos), all features verified

## Script
`C:\Users\scott\ebay-automation\photo_processor.py`

## What It Does
Replaces manual Lightroom Classic + Fotor.com workflow:
- **Gemini 2.0 Flash** (via OpenRouter) analyzes each photo: tag detection, rotation, bg type, subject bbox
- **OpenCV/Pillow** handles rotation, crop, color correction, CLAHE
- **rembg** (onnxruntime) removes white/mixed backgrounds → black
- **Calibration card** (DSC_3055.png) provides batch-wide white balance

## Key Architecture Decisions
- One Gemini Flash vision call per photo (~$0.001/image)
- For **white/mixed backgrounds**: mask tag area → rembg → auto-crop to alpha content → composite on black
- For **black backgrounds**: paint tag area black → crop using Gemini subject bbox
- rembg runs on CPU (onnxruntime-gpu installed but CUDA DLLs missing in miniconda - works fine on CPU)
- Photos filtered by date (>= Jan 15 2026) and tracker to prevent reprocessing

## CLI Usage
```bash
python photo_processor.py                        # Process all new photos, show preview
python photo_processor.py --batch KL2686         # Filter by pattern
python photo_processor.py --export               # Save final JPEGs to Processed/
python photo_processor.py --dry-run              # Preview without processing
python photo_processor.py --reset                # Clear tracker
python photo_processor.py stats                  # Show stats
python photo_processor.py --no-open              # Don't auto-open report
```

## Paths
| Purpose | Path |
|---------|------|
| Input | `D:\Photo workarea\Auctiva\Auctiva\` |
| Export | `D:\Photo workarea\Auctiva\Processed\` |
| Previews | `D:\Photo workarea\Auctiva\Preview\` |
| Tracker | `D:\Photo workarea\Auctiva\processed_photos.json` |
| Report | `D:\Photo workarea\Auctiva\preview_report.html` |

## Dependencies (installed in miniconda base env)
- opencv-python, Pillow, numpy, httpx (API calls)
- rembg + onnxruntime-gpu (bg removal)
- kb_config (logger, shared config)

## Test Results (Feb 9, 2026)
| Batch | Background | Tag | Result |
|-------|-----------|-----|--------|
| KL2686 (flute) | Black velvet | Yes (top) | Tag painted black, subject cropped |
| KL2611 (copper fitting) | White | Yes (below) | Tag masked, bg removed, auto-cropped |
| KL2606 (nail primer) | White | Yes (left, rotated) | Tag masked, bg removed, clean |

## Known Limitations
- Tag masking on black bg can leave a faint rectangular outline (different black tone from velvet)
- onnxruntime CUDA DLLs not found in miniconda → rembg falls back to CPU (still fast enough)
- Calibration card processing is basic (brightest 5% = white patch) - may need tuning for different cards
- Gemini Flash subject bbox can be imprecise for small items; rembg auto-crop compensates for white bg
