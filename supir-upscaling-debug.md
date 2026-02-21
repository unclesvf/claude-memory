# SUPIR Upscaling Pipeline - Debug State (Feb 10, 2026)

## Overview

Three-way upscaler comparison for ~120K Midjourney images:
- **UltraSharp (ESRGAN)** via spandrel — COMPLETE (~24.5s/image)
- **HAT-L (Transformer)** via spandrel — COMPLETE (~95.9s/image)
- **SUPIR-v0Q (Diffusion)** — IN PROGRESS, blocked by attention mask bug

## What Works

- **UltraSharp output**: `D:\AI-Knowledge-Base\Upscaled\4x-UltraSharp\`
- **HAT-L output**: `D:\AI-Knowledge-Base\Upscaled\4x-HAT-L\`
- **Batch upscale script**: `C:\Users\scott\ebay-automation\upscale_images.py` (spandrel, folder/DB modes, resume)
- **SUPIR model loads successfully** in ~120-180s (CLIP1 + CLIP2 + SDXL base + SUPIR-v0Q)
- **SUPIR VAE encoder/decoder works** with optimized tile sizes
- **Test images**: `D:\AI-Knowledge-Base\Upscaled\supir_input\` (5 Midjourney images, 2624x1792)

## SUPIR Environment

- **Conda env**: `supir` (Python 3.10)
- **PyTorch**: 2.10.0+cu128 (CUDA working)
- **Code**: `C:\Users\scott\SUPIR\`
- **Test script**: `C:\Users\scott\SUPIR\test_nollava.py` (bypasses LLaVA)
- **Models**: `C:\Users\scott\SUPIR\models\` (sd_xl_base_1.0_0.9vae.safetensors, SUPIR-v0Q.ckpt)

## Bugs Fixed So Far

### 1. CLIP2 Model Path Format (FIXED)
- **Error**: `RuntimeError: Pretrained value 'laion/CLIP-ViT-bigG-14-laion2B-39B-b160k' is not a known tag`
- **Root cause**: `CKPT_PTH.py` had HuggingFace model ID; `open_clip.create_model_and_transforms()` needs OpenCLIP pretrained tags
- **Fix**: Set `SDXL_CLIP2_CKPT_PTH = None` in `C:\Users\scott\SUPIR\CKPT_PTH.py`
- Falls through to YAML's `version: laion2b_s39b_b160k` (valid OpenCLIP tag)

### 2. Memory Explosion with Tiny Tiles (FIXED)
- **Problem**: `--upscale 4 --decoder_tile_size 64` → 36,162 tiny tiles, ~200GB RAM+VM, GPU idle
- **Fix**: Use `--upscale 2 --encoder_tile_size 1024 --decoder_tile_size 256` → 738 decoder tasks, proper GPU use

### 3. HuggingFace CLIP Eager Attention (APPLIED but not the real fix)
- Added `attn_implementation="eager"` to `CLIPTextModel.from_pretrained()` in `sgm/modules/encoders/modules.py`
- This only affects HuggingFace CLIP (embedder #0), NOT OpenCLIP (embedder #1 where error occurs)

## CURRENT BUG: OpenCLIP Attention Mask Shape (UNSOLVED)

### Error
```
The shape of the 2D attn_mask is torch.Size([77, 77]), but should be (1, 1).
```
All 5 images fail during diffusion sampling step (after VAE encode succeeds).

### Root Cause
PyTorch 2.10's Flash/MemEfficient SDPA backends have strict attention mask shape requirements.
OpenCLIP's text transformer creates a 2D [77,77] causal mask. Flash SDP rejects this.

### Failed Fix: Global SDPA Disable
Added to test_nollava.py:
```python
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
```
**Result**: Attention error gone, BUT VAE encoder became ~1000x slower (7s/task vs 0.007s/task).
The global disable also cripples VAE and UNet xformers attention performance.

**THIS FIX IS STILL IN test_nollava.py AND NEEDS TO BE REMOVED before next run.**

### Correct Fix Needed: Targeted SDPA Disable

The fix must ONLY disable fast SDPA during OpenCLIP text encoding, not globally.

**OpenCLIP attention mask flow** (all in `C:\Users\scott\miniconda3\envs\supir\Lib\site-packages\open_clip\transformer.py`):

1. **Mask creation** (lines 1080-1086): `build_causal_mask()` creates [77,77] additive mask (-inf upper triangle)
2. **Mask registered** (lines 1019-1022): `self.register_buffer('attn_mask', ...)`
3. **Mask sliced** (lines 1112-1135): `_embeds()` slices to `[:seq_len, :seq_len]`
4. **Mask passed** through `Transformer.forward()` → `CustomResidualAttentionBlock` → `Attention.forward()`
5. **SDPA call** (lines 190-195): `F.scaled_dot_product_attention(q, k, v, attn_mask=attn_mask)`

**Three possible targeted fixes**:

#### Option A: Context Manager in test_nollava.py
Wrap only the text encoding call with SDPA disable:
```python
# Before the batchify_sample call, temporarily disable fast SDPA
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
# Run text encoding (happens inside batchify_sample)
samples = model.batchify_sample(...)
# Re-enable after (but this won't work because text encoding happens INSIDE batchify_sample)
```
Problem: text encoding is interleaved with UNet sampling inside batchify_sample.

#### Option B: Monkey-patch OpenCLIP Attention class (RECOMMENDED)
In test_nollava.py, after model loads, patch the OpenCLIP text encoder's attention to use manual attention instead of F.scaled_dot_product_attention:
```python
# After model loads, find the OpenCLIP text encoder and set use_fsdpa = False
for embedder in model.conditioner.embedders:
    if hasattr(embedder, 'model') and hasattr(embedder.model, 'text'):
        text_transformer = embedder.model.text.transformer
        for block in text_transformer.resblocks:
            if hasattr(block, 'attn'):
                block.attn.use_fsdpa = False  # Fall back to manual bmm attention
```
The OpenCLIP Attention class (line 190) checks `self.use_fsdpa` before calling F.scaled_dot_product_attention, and has a manual fallback (lines 196-203).

#### Option C: Patch the mask shape in OpenCLIP
Modify `_embeds()` to reshape the mask to 4D [1, 1, seq_len, seq_len] before passing it through.

**Option B is simplest and safest** — no file modifications to open_clip, just flip a flag.

## Working SUPIR Command (once attention fix is applied)

```bash
cd C:/Users/scott/SUPIR && C:/Users/scott/miniconda3/envs/supir/python.exe test_nollava.py --img_dir "D:\AI-Knowledge-Base\Upscaled\supir_input" --save_dir "D:\AI-Knowledge-Base\Upscaled\4x-SUPIR" --upscale 2 --SUPIR_sign Q --use_tile_vae --encoder_tile_size 1024 --decoder_tile_size 256 --edm_steps 20 --loading_half_params --ae_dtype bf16 --diff_dtype fp16
```

## Files Modified

| File | Change |
|------|--------|
| `C:\Users\scott\SUPIR\CKPT_PTH.py` | Set `SDXL_CLIP2_CKPT_PTH = None` |
| `C:\Users\scott\SUPIR\sgm\modules\encoders\modules.py` | Added `attn_implementation="eager"` to CLIPTextModel |
| `C:\Users\scott\SUPIR\test_nollava.py` | Added global SDPA disable (NEEDS REMOVAL — replace with Option B) |
| `C:\Users\scott\SUPIR\llava\model\language_model\llava_llama.py` | try/except for config registration |

## Next Steps

1. **Remove global SDPA disable** from test_nollava.py (lines 3-5)
2. **Add Option B monkey-patch** after model loads (~line 63 in test_nollava.py)
3. **Re-run SUPIR** with the working command above
4. **Compare results** across all 3 upscalers visually
