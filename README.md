# claude-memory

Layered memory system for Claude Code — keyword index, topic files, and hooks that automatically surface relevant context, track file changes, preserve session state, and build structured memories.

**Latest: v3.0.0** — adds MemPalace semantic-search fallback, URL-keyword auto-injection, MemPalace wake-up on session start, voice-input integration, and an automine hook that pipes new memories straight into a ChromaDB palace.

## What's New in v3

- **MemPalace semantic-search fallback** — when the keyword scorer comes up dry on a prompt (best score < 6), the search hook falls back to a ChromaDB semantic search across your MemPalace drawers. Lets a vaguely-worded prompt still surface the right memory.
- **URL-keyword auto-injection** — pasted x.com URLs auto-trigger your `x-research` memory; github.com URLs trigger `github`/`repo`/`issue` keywords; reddit.com URLs trigger `reddit`/`research`. Configurable in the `URL_KEYWORD_MAP` dict in `memory_search.py`.
- **MemPalace wake-up on session start** — the SessionStart hook now also injects a compact identity + L1-essential-story primer (~800-1000 tokens) from MemPalace, cached for 1 hour. Survives compaction recovery cleanly.
- **Voice input hook** — picks up voice transcriptions from a drop-file (`voice_input.jsonl`) and injects them into Claude's context on UserPromptSubmit. Pairs with any external speech-to-text daemon (e.g. F9 hotkey, wake word).
- **MemPalace automine hook** — fires on Write/Edit of memory files. Auto-mines new/updated files into the MemPalace ChromaDB palace with rule-based wing classification (customizable). Async, never blocks.
- **All hooks now use `C--Users-yourname` template path** — every hook with a `MEMORY_DIR` constant gets templated, not just memory_search.py + subagent_start.py.

MemPalace is **optional** — if you don't have it installed, the new MemPalace bits silently skip via try/except. The core 7 hooks from v2 keep working unchanged.

[MemPalace](https://github.com/milla-jovovich/mempalace) is a separate project (not bundled here) — install it if you want the semantic-search fallback and wake-up features.

## How It Works

### Core System
1. **MEMORY.md** — Slim keyword index (~60 lines), always loaded into Claude's context. Each project gets one line with name, status, keywords, and a link to its topic file.
2. **Topic files** (`*.md`) — Full project details, loaded on demand only when keywords match.

### Hooks (9 lifecycle events)

| Hook | File | When | Purpose |
|------|------|------|---------|
| **UserPromptSubmit** | `memory_search.py` | Every prompt | Keyword match + attention decay + co-activation scoring + URL-keyword injection. Falls back to MemPalace semantic search when keyword scoring is weak. Injects HOT/WARM/COLD tiered content. |
| **UserPromptSubmit** | `voice_input.py` | Every prompt | Drains pending voice transcriptions from `~/.claude/voice/voice_input.jsonl` and injects them into the prompt context. (Optional — pair with your own STT daemon.) |
| **PreCompact** | `precompact_save.py` | Before compression | Saves session snapshot so next session can recover. |
| **SessionStart** | `session_start.py` | Session begins | Injects recovery snapshot from PreCompact + MemPalace wake-up primer (identity + essential story). |
| **Stop** | `stop_hook.py` | Claude finishes responding | Analyzes transcript for memories across 6 categories. Hash deduplication + pattern tracking. |
| **PostToolUse** | `post_tool_use.py` | After each tool call | Silently tracks file Read/Edit/Write ops. Feeds attention scores + co-activation graph. Async. |
| **PostToolUse** | `mempalace_automine.py` | After Write/Edit on memory files | Auto-mines new/updated memory files into MemPalace ChromaDB palace with rule-based wing routing. Async, 5s timeout. (Optional — requires MemPalace.) |
| **SubagentStart** | `subagent_start.py` | Subagent spawned | Injects relevant memory context into Task tool subagents. |
| **SessionEnd** | `session_end.py` | Session terminates | Writes session summary. Prunes old tracking data. Cleans up temp files. |

Bonus utility (not a hook): `telegram_memory_search.py` — same keyword scoring as `memory_search.py` but produces output formatted for an external Telegram-bot consumer.

### Memory Categories (Stop Hook)

The Stop hook classifies memories into 6 structured categories using deterministic keyword triage (zero LLM cost):

| Category | What It Captures |
|----------|-----------------|
| **session_summary** | Work resume snapshots — what happened, what's next |
| **decision** | Architectural choices with rationale (why X over Y) |
| **runbook** | Error fix procedures (symptom → fix → verification) |
| **constraint** | Known limitations, things that cannot work |
| **tech_debt** | Deferred work items with associated costs |
| **preference** | User conventions and workflow preferences |

Memories are saved as JSON files in `~/.claude/memories/<category>/`.

### Attention Scoring (Memory Search)

Inspired by [claude-cognitive](https://github.com/GMaN1911/claude-cognitive), the search hook uses 5 scoring signals:

1. **Keyword match** (0-15+) — Exact = 3, partial = 2, name = 2
2. **Importance weight** (1-10) — Multiplier per MEMORY.md entry
3. **Recency boost** — Last hour +3, 4h +2, 24h +1
4. **Attention score** (0.0–1.0) — Decays 15% per turn, boosted by file access
5. **Co-activation** — Files accessed together warm each other up

**Injection tiers:**

| Tier | Attention | Injected Content |
|------|-----------|-----------------|
| HOT | > 0.8 | Full file content |
| WARM | 0.25–0.8 | First section only |
| COLD | < 0.25 | Skipped |

**v3 fallback:** if the best keyword-scored memory has score < 6, `memory_search.py` queries MemPalace's ChromaDB collection (`mempalace_drawers`) for top-3 semantic matches above 0.25 similarity, dedup by source file. Surfaces under a `[Semantic match via MemPalace]` header so you can tell where the hit came from.

### URL-Keyword Injection (v3)

When the user prompt contains a URL, certain domains auto-inject helper keywords so the right memory file gets surfaced even without explicit terms:

| URL pattern | Injected keywords |
|-------------|-------------------|
| `x.com/`, `twitter.com/` | `x-research twitter tweet bookmarks` |
| `github.com/` | `github repo pull issue` |
| `reddit.com/` | `reddit research` |

Edit the `URL_KEYWORD_MAP` dict in `memory_search.py` to add your own domains.

### Deduplication & Pattern Tracking

- **Hash dedup**: MD5 of normalized content prevents re-inserting the same fact across sessions. Stored in `~/.claude/memory_hashes.json`.
- **Pattern threshold**: Tracks how often patterns recur. Only graduates to permanent rules after 3+ occurrences. Stored in `~/.claude/pattern_tracker.json`.

## Setup

### 1. Clone into your memory directory

**macOS:**
```bash
MEMORY_DIR="$HOME/.claude/projects/-Users-$(whoami)/memory"
cp MEMORY-TEMPLATE.md "$MEMORY_DIR/MEMORY.md"
mkdir -p "$HOME/.claude/hooks"
cp hooks/*.py "$HOME/.claude/hooks/"
chmod +x "$HOME/.claude/hooks/"*.py
```

**Windows (PowerShell):**
```powershell
$MEMORY_DIR = "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME\memory"
New-Item -ItemType Directory -Force $MEMORY_DIR | Out-Null
Copy-Item MEMORY-TEMPLATE.md "$MEMORY_DIR\MEMORY.md"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\hooks" | Out-Null
Copy-Item hooks\*.py "$env:USERPROFILE\.claude\hooks\"
```

### 2. Update the MEMORY_DIR path in every hook

The hooks ship with the placeholder path `C--Users-yourname` — replace with your actual username (or the macOS form `-Users-yourname`).

Files to update:
- `memory_search.py`
- `telegram_memory_search.py`
- `subagent_start.py`
- `precompact_save.py`
- `session_end.py`
- `mempalace_automine.py` (only if you're enabling MemPalace — see below)

```python
# macOS
MEMORY_DIR = ".../.claude/projects/-Users-yourname/memory"
# Windows
MEMORY_DIR = ".../.claude/projects/C--Users-yourname/memory"
```

### 3. (Optional) Customize the MemPalace wing rules

If you're using `mempalace_automine.py`, edit the `WING_RULES` list to map your filename prefixes/keywords to MemPalace wings. The shipped rules are placeholders for `wing_personal`, `wing_feedback`, `wing_sessions`, `wing_meta`, `wing_infrastructure`. Add your own wings for your projects.

### 4. Configure hooks in settings.json

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "python3 /path/to/.claude/hooks/memory_search.py", "timeout": 5 },
          { "type": "command", "command": "python3 /path/to/.claude/hooks/voice_input.py", "timeout": 2 }
        ]
      }
    ],
    "PreCompact": [
      { "hooks": [ { "type": "command", "command": "python3 /path/to/.claude/hooks/precompact_save.py", "timeout": 10 } ] }
    ],
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python3 /path/to/.claude/hooks/session_start.py", "timeout": 5 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "python3 /path/to/.claude/hooks/stop_hook.py", "timeout": 10 } ] }
    ],
    "PostToolUse": [
      {
        "hooks": [
          { "type": "command", "command": "python3 /path/to/.claude/hooks/post_tool_use.py", "timeout": 3, "async": true },
          { "type": "command", "command": "python3 /path/to/.claude/hooks/mempalace_automine.py", "timeout": 5, "async": true }
        ]
      }
    ],
    "SubagentStart": [
      { "hooks": [ { "type": "command", "command": "python3 /path/to/.claude/hooks/subagent_start.py", "timeout": 5 } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "python3 /path/to/.claude/hooks/session_end.py", "timeout": 10 } ] }
    ]
  }
}
```

**Important:** Replace `/path/to/` with your actual home directory path. Use `python3` on macOS, `python` on Windows.

If you're not using MemPalace, you can omit `mempalace_automine.py`. The other hooks degrade gracefully if MemPalace isn't installed — they just skip the MemPalace-specific paths via try/except.

If you don't have a voice STT daemon, omit `voice_input.py`.

### 5. Approve the hooks

On first launch after adding hooks, Claude Code will prompt you to review and approve them in the `/hooks` menu.

## Adding New Projects

Add a line to the Project Index section of `MEMORY.md`:

```markdown
**Project Name** | Status | keyword1 keyword2 keyword3 | [topic-file.md](topic-file.md)
```

Or with an importance score (1-10, default 5):

```markdown
**Project Name** | Status | 8 | keyword1 keyword2 keyword3 | [topic-file.md](topic-file.md)
```

## State Files

| File | Purpose |
|------|---------|
| `~/.claude/memory_access_log.json` | When each topic file was last accessed |
| `~/.claude/attn_state.json` | Attention scores per file (decays 15%/turn) |
| `~/.claude/coactivation_pairs.json` | Co-activation graph (files accessed together) |
| `~/.claude/memory_hashes.json` | Content hashes for deduplication |
| `~/.claude/pattern_tracker.json` | Occurrence counts for pattern graduation |
| `~/.claude/file_tracking.jsonl` | Append-only log of file operations |
| `~/.claude/sessions/last_session.md` | Recovery snapshot from PreCompact |
| `~/.claude/sessions/compaction_log.jsonl` | Compaction event log |
| `~/.claude/sessions/session_*.json` | Per-session summaries from SessionEnd |
| `~/.claude/memories/<category>/*.json` | Structured memories from Stop hook |
| `~/.claude/voice/voice_input.jsonl` | Voice STT drop-file (v3) |
| `~/.mempalace/wakeup_cache.txt` | Cached MemPalace wake-up primer (v3) |
| `~/.mempalace/palace/` | MemPalace ChromaDB persistent collection (v3) |

## Common Pitfalls

- **Hook schema**: Must use nested `{hooks: [{type, command}]}` format, NOT flat `{type, command}`.
- **Path separators**: macOS uses `-Users-` prefix, Windows uses `C--Users-` in the project path.
- **Hook not firing**: Check `/hooks` menu in Claude Code to approve pending hooks.
- **Windows encoding**: Hooks use `sys.stdout.buffer.write()` to avoid cp1252 Unicode errors.
- **Stop hook loops**: The `stop_hook_active` guard file prevents infinite re-entry. If it gets stuck, delete `~/.claude/stop_hook_active`.
- **PostToolUse is async**: Set `"async": true` in settings.json so it doesn't slow down Claude's responses.
- **MemPalace optional**: All MemPalace integration is wrapped in try/except — missing MemPalace just skips silently. No errors propagate.
- **Multiple UserPromptSubmit / PostToolUse hooks**: Both `memory_search.py` + `voice_input.py` register under UserPromptSubmit; `post_tool_use.py` + `mempalace_automine.py` under PostToolUse. The settings.json schema allows multiple hooks per event — just nest them in the same `hooks` array.

## Credits & Related Projects

External projects this system either builds on, integrates with, or borrows ideas from:

| Project | URL | Used For |
|---------|-----|----------|
| **claude-cognitive** | [github.com/GMaN1911/claude-cognitive](https://github.com/GMaN1911/claude-cognitive) | Original inspiration for the attention-scoring + co-activation approach in `memory_search.py` |
| **MemPalace** | [github.com/milla-jovovich/mempalace](https://github.com/milla-jovovich/mempalace) | Optional ChromaDB-backed semantic memory palace. v3 hooks integrate with it for semantic-search fallback (`memory_search.py`), session-start identity primer (`session_start.py`), and async automine on memory-file writes (`mempalace_automine.py`) |
| **ChromaDB** | [github.com/chroma-core/chroma](https://github.com/chroma-core/chroma) | Vector store backing MemPalace (transitive dependency) |

Want to add an external integration of your own? Open a PR — we welcome new optional hooks that follow the "graceful degrade if dependency missing" pattern that MemPalace integration uses.

## Versions

- **v3.0.0** (2026-04-24) — MemPalace semantic-search fallback, URL keyword injection, MemPalace wake-up on session start, voice-input hook, MemPalace automine hook, template-path everywhere
- **v2.0.0** (2026-04-03) — Initial public release: 7 hooks, attention scoring, hash dedup, pattern threshold
