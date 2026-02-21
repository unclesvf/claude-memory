# Educational Content: American History & Math Courses

**Current Focus:** Audio generation for 14 courses (411 lessons)
**Hosting:** Mac mini (`~/.openclaw/workspace/courses/`)
**Status:** Active — Kokoro TTS batch running

## Courses (14 total)
early-math, speed-math, morality-ethics, reasoning-first-principles, enlightenment,
rome-republic-to-empire, colonial-founding-era, us-constitution, civil-war-reconstruction,
westward-expansion, gilded-age-wwi, american-century, 21st-century-america,
federalist-antifederalist

## TTS Pipeline (current)

| Tool | Purpose |
|------|---------|
| **Kokoro-82M** | TTS narration via DeepInfra ($0.003/lesson) |
| **Whisper** | Audio verification via DeepInfra (whisper-large-v3-turbo) |
| **14 voice presets** | Different Kokoro voices per course for variety |

### Generation Script
`~/.openclaw/workspace/tools/regenerate_audio_kokoro.py`
- 95% quality threshold with per-chunk Whisper verification
- 6 retries per failing chunk, failure logging
- Text normalization (numbers, punctuation, stage directions)
- Output: `~/.openclaw/workspace/audio-output-kokoro/`

## TTS History (failed approaches)
- **edge-tts**: Microsoft voices, free but lower quality. Used in early iterations.
- **Chatterbox** (`resemble-ai/chatterbox-turbo`): Garbled audio, 2.5% pass rate. Known bug (GitHub #385). Wasted ~$14.
- **Kokoro-82M**: Current solution. 97.8% of chunks pass 95% on first try.

## Content Creation Tools

| Tool | Purpose |
|------|---------|
| **pandoc** | Convert lesson content between formats |
| **marp-cli** | Create presentation slides from markdown |

## Image Generation Accounts
Grok Imagine (xAI), Midjourney, Higgs Field, Mage Space, SeeArt

## Quick Commands
```bash
# Generate audio for all courses
python3 tools/regenerate_audio_kokoro.py

# Single course
python3 tools/regenerate_audio_kokoro.py early-math

# Test mode (2 files)
python3 tools/regenerate_audio_kokoro.py --test

# Old edge-tts (deprecated)
edge-tts --text "In 1776..." --voice en-US-GuyNeural --write-media lesson.mp3
```
