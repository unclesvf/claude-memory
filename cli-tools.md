# CLI Tools Inventory

**Full reference:** `C:\Users\scott\.claude\cli-tools-inventory.json`
**Printable guide:** `C:\Users\scott\Documents\CLI-Tools-Reference.pdf`
**Installed:** January 30, 2026 (45+ tools)

## By Category

| Category | Tools |
|----------|-------|
| **Terminal** | fzf, zoxide, starship, tldr, bat, fd, delta, lazygit, ripgrep, eza, glow, just |
| **Web/API** | gh, httpie, aria2, wget, yt-dlp, vercel, httpx |
| **Data** | jq, sqlite3, rclone, sqlite-utils, visidata |
| **Documents** | pandoc, wkhtmltopdf, marp-cli, calibre |
| **Audio/Video** | sox, openai-whisper (local GPU), HandBrakeCLI, gifsicle, ffmpeg, edge-tts, pyttsx3 |
| **Image/Laser** | imagemagick, inkscape, potrace |
| **Files** | 7zip, duf, ncdu |
| **Python** | ruff, black, uv |
| **AI/ML** | ollama, comfy-cli, gradio, streamlit, openai, replicate |
| **Containers** | docker |

**Note:** Starship and zoxide are configured in PowerShell profile.

## Quick Examples

```bash
fzf                              # Fuzzy find files
z projects                       # Smart directory jump
rg "def main" --type py          # Fast code search
eza -la --git                    # Pretty file listing
glow README.md                   # View markdown in terminal
just build                       # Run project tasks
vd data.csv                      # Explore data interactively
edge-tts --text "Hello" --write-media hello.mp3
potrace input.bmp -s -o output.svg  # Bitmap to vector for laser
```
