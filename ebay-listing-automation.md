# eBay Listing Automation - Word Doc to Auctiva CSV

## Overview
Automate the workflow of posting estate sale items to eBay via Auctiva.com.
Client: Linda and Stan (~79 years old, expect typos and format drift in write-ups).

## Current Manual Workflow
1. Linda/Stan append items to their Word docs
2. They send photos (camera names like DSC_####)
3. Scott renames in Lightroom to lot numbers (LS####, KL####, SL####)
4. Crop to subject in Lightroom
5. Export noisy-background items → Fotor.com batch background removal → black background
6. Lightroom: brightness if needed, dehaze 8-12, clarity 8-12
7. Export batch: 1920px long side, JPEG quality 90
8. Upload images to Auctiva.com (hosts the images)
9. Create listings manually in Auctiva web forms
10. Schedule listings → posts to eBay

## Lot Number Prefixes
- **LS####** - Linda's items (e.g., LS2678)
- **KL####** - Linda's items, different estates (e.g., KL2847)
- **SL####** - Stan's items (e.g., SL2712)
- IMPORTANT: Linda sometimes transposes SL and LS. If you see SL in her doc, check for LS photos first. She does NOT post Stan's SL items (rare exceptions - ask Scott).

## Photo Naming Convention
- Individual photos: LS2346-1, LS2346-2, LS2346-3 (suffix = photo number)
- Some use letter style: SL732 - A.jpg, SL732 - B.jpg
- Photos in: `D:\Photo workarea\Auctiva\Auctiva`
- Newest photos by date = items ready to post

## Document Locations
- Stan: `C:\Users\scott\OneDrive\Documents\Stan  Linda 7-31-2025.docx`
- Linda: `C:\Users\scott\OneDrive\Documents\Linda 10-31-2025.dotx` (.dotx = Word template, needs XML parsing)
- Documents can be trimmed to recent months only if too large

## Stan's Write-Up Format (very consistent for coins)
```
SL#### [Title]
[Description paragraph - often templated for coins]
[Estate] Estate  Buy it Now  $XX.XX  Free Shipping
```
- Auction items: `+++++++++++++Auction+++++++Start $1  $X.XX Shipping`
- Multiple estates: Walker, Johnson
- Non-coin items (electronics, collectibles) have variable descriptions

## Linda's Write-Up Format
```
LS#### [Title]
[Description]
Listed in category:
    [eBay category path]
[Estate] Estate
$XX.XX F/S
```
- Sometimes includes eBay categories (helpful for automation)
- KL items mixed in with LS items
- Multiple estates: Storm, others

## Parsing Challenges
- Typos: "perfactly", "we4re", smart quotes rendering issues
- Format drift between items and over time
- LS/SL transposition in Linda's doc
- Price formats: "$5,000.00", "$9.50", "F/S" (free shipping), "$2.50 Shipping"
- Buy it Now vs Auction detection
- Estate name extraction (goes in eBay listing)

## Automation Plan (Agreed with Scott)
**Phase 1 - Word Doc Parser (FIRST PRIORITY)**
- **Architecture: Dual Parse + Reconciliation (Option D)**
  - Both **DeepSeek V3.2** AND **Kimi K2.5** parse every item independently via OpenRouter
  - Python reconciliation script compares outputs field by field
  - Items where both models AGREE → auto-approved (high confidence)
  - Items where models DISAGREE → flagged for Scott's review with both interpretations
  - Typo detections: union of both models (DeepSeek catches some, Kimi catches others)
  - **Cost: ~$0.05/month for 200 items** (negligible)
- Extract: lot number, title, description, estate, price, shipping, auction vs BIN, category
- Validate against photo directory to catch transpositions
- Flag ambiguous items for human review
- See model comparison results below

**Why Dual Parse:**
- DeepSeek V3.2 scored 97% but missed "Gold Rush" typo
- Kimi K2.5 scored 94% but caught nuances DeepSeek missed
- Price agreement between two independent models = very high confidence
- Scott only needs to closely review disagreements, not every item
- Both models run in parallel (not sequential) for speed

**Phase 2 - Photo Matching**
- Match lot numbers from parser output to photo filenames in Auctiva folder
- Identify "ready to post" (has both write-up AND photos)
- Generate "waiting for photos" to-do list

**Phase 3 - CSV Generation for Auctiva**
- Format output as CSV compatible with Auctiva's bulk import
- Listings land in Auctiva "Saved Listings" for Scott to review and schedule

**Phase 4 - Lightroom Automation (future)**
- Crop, brightness, dehaze, clarity adjustments
- Export settings: 1920px long side, JPEG 90

**Phase 5 - Background Removal (future)**
- Items with noisy backgrounds → Fotor.com batch tool → black background
- Visual assessment needed (lint, hair, objects visible = needs removal)

## Auctiva Capabilities (checked Feb 2026)
- NO public API
- CSV bulk import: uploads to Saved Listings, editable before posting
- Bulk image upload available
- eBay API is alternative for full programmatic control (more complex)

## "Redo" Requests via Email
- New photos: reshoot, need to re-upload
- New prices: can revise OR end + sell similar (preferred for search algorithm boost)
- Faulty description: revise or end + sell similar
- End + sell similar looks like new listing to eBay = better search visibility

## Model Comparison Test Results (Feb 6, 2026)

**Test script:** `C:\Users\scott\ebay-automation\parser_model_test.py`
**Full results:** `C:\Users\scott\ebay-automation\parser_model_test_results.json`

Tested 12 diverse items (coins, electronics, collectibles, auctions, quantities, typos, transpositions) across 4 models via OpenRouter.

| Model | Score | Time | Cost | Notes |
|-------|-------|------|------|-------|
| **DeepSeek V3.2** | **67/69 (97%)** | 57.8s | $0.003 | Winner - best accuracy, cheap, fast |
| Kimi K2.5 | 65/69 (94%) | 136.1s | $0.022 | Caught "Gold Rush" typo others missed; slowest |
| Gemini 2.5 Pro | 64/69 (93%) | 52.0s | $0.073 | Solid but 25x more expensive than DeepSeek |
| Qwen 3 235B | 0/0 (format issue) | 32.1s | $0.002 | Returned single object not array; needs prompt fix |

### What All Models Got Right
- Extracted correct listing price on $5,000 coin (avoided $20,000 reference price trap)
- Identified auction vs Buy it Now format (++++ markers)
- Flagged SL/LS transposition in Linda-format item
- Parsed quantities, "no best offer", estate names, category paths

### Where Models Differed
- **Kimi K2.5 only**: Caught "Good Rush" → "Gold Rush" typo in SL2706
- **DeepSeek V3.2 only**: Got KL shipping correct (others failed on ambiguous shipping)
- **Qwen 3 235B**: JSON format issue (single object vs array) — fixable with prompt tweak

### Recommendation
- **Primary: DeepSeek V3.2** (`deepseek/deepseek-chat-v3-0324`) — best overall
- **Backup: Kimi K2.5** (`moonshotai/kimi-k2.5`) — for extra nuance when needed
- Cost is negligible for all models at estate sale volumes (~100 items = pennies)

## listing_parser.py (Feb 6, 2026) - IMPLEMENTED

**File:** `C:\Users\scott\ebay-automation\listing_parser.py`
**Output:** `C:\Users\scott\ebay-automation\parsed_listings.json`

Dual-LLM parser (DeepSeek V3.2 + Kimi K2.5) with reconciliation and photo matching.
- Extracts from Stan's .docx (python-docx) and Linda's .dotx (zipfile + XML strip)
- Stan: 6,317 SL items, Linda: 4,395 KL/LS items
- Photo index: 33,111 files across 9,017 lots in `D:\Photo workarea\Auctiva\Auctiva`
- Kimi is slow (~2min for 10 items) and may hit 8000 token limit on large batches
- DeepSeek is fast (~30s for 10 items) and more reliable

### CLI Usage
```bash
python listing_parser.py                          # Last 20 from each doc
python listing_parser.py --dry-run --last 5       # Text extraction only
python listing_parser.py --doc stan --last 50     # Stan only
python listing_parser.py --start-lot SL6600       # From specific lot
python listing_parser.py --no-photos              # Skip photo scan
python listing_parser.py --batch-size 15          # Custom batch size
```

### Phase 2-3: IMPLEMENTED & TESTED (Feb 7, 2026)

**CSV Generation** (`listing_parser.py --csv`) - COMPLETE:
- Smart shipping detection: keyword-based from title+category
  - Default: USPS Ground Advantage (free)
  - Coins <$20: eBay Standard Envelope (free)
  - Books/VHS/DVD/media: Media Mail (free)
- HTML description template: `auctiva_description_template.html` with {{TITLE}}, {{DESCRIPTION}}, {{ESTATE_LINE}}, {{LOT_NUMBER}}
- Store category mapping: `ebay_store_categories.json` (general + estate-specific)
- Added StoreCategory/StoreCategory2 columns
- Condition map expanded: "new without packaging" = 1500
- Zero manual fixes needed after Auctiva upload

**Photo Assignment Automation** (`auctiva_photo_assign.py`) - COMPLETE:
- Playwright browser automation with cookie-based auth
- Searches Auctiva Image Management by SKU prefix
- Assigns images via reverse-engineered JS API (DETAILSetTemplateImage)
- CLI: `--dry-run`, `--skus`, `--scrape-fains`, `--login`, `--headless`
- Tested on 4 listings: SL732 (1 img), LS430 (11), KL2775 (4), KL2847 (2)
- Fain mapping: `fain_mapping.json` (auto-scraped from Saved Listings page)
- Cookie auth: export from Chrome via JS blob → `auctiva_cookies.json`

**Remaining future work:**
- Bulk photo upload automation (currently manual in Auctiva web UI)
- Category suggestion for Stan's items (no category paths in his write-ups)

## Category Selection
- Linda sometimes includes eBay category paths in write-ups
- Stan doesn't - category inferred from item type (coins → specific subcategory)
- Both eBay and Auctiva have search category tools
- LLM could suggest categories based on item description
