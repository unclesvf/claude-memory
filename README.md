# claude-memory

Layered memory system for Claude Code — keyword index, topic files, and 7 hooks that automatically surface relevant context, track file changes, preserve session state, and build structured memories.

## How It Works

### Core System
1. **MEMORY.md** — Slim keyword index (~60 lines), always loaded into Claude's context. Each project gets one line with name, status, keywords, and a link to its topic file.
2. **Topic files** (`*.md`) — Full project details, loaded on demand only when keywords match.

### Hooks (7 lifecycle events)

| Hook | File | When | Purpose |
|------|------|------|---------|
| **UserPromptSubmit** | `memory_search.py` | Every prompt | Keyword match + attention decay + co-activation scoring. Injects HOT/WARM/COLD tiered content. |
| **PreCompact** | `precompact_save.py` | Before compression | Saves session snapshot so next session can recover. |
| **SessionStart** | `session_start.py` | Session begins | Injects recovery snapshot from PreCompact automatically. |
| **Stop** | `stop_hook.py` | Claude finishes responding | Analyzes transcript for memories across 6 categories. Hash deduplication + pattern tracking. |
| **PostToolUse** | `post_tool_use.py` | After each tool call | Silently tracks file Read/Edit/Write ops. Feeds attention scores + co-activation graph. Async. |
| **SubagentStart** | `subagent_start.py` | Subagent spawned | Injects relevant memory context into Task tool subagents. |
| **SessionEnd** | `session_end.py` | Session terminates | Writes session summary. Prunes old tracking data. Cleans up temp files. |

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

### Attention Scoring (Memory Search v2)

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

### Deduplication & Pattern Tracking

- **Hash dedup**: MD5 of normalized content prevents re-inserting the same fact across sessions. Stored in `~/.claude/memory_hashes.json`.
- **Pattern threshold**: Tracks how often patterns recur. Only graduates to permanent rules after 3+ occurrences. Stored in `~/.claude/pattern_tracker.json`.

## Setup

### 1. Clone into your memory directory

**macOS:**
```bash
MEMORY_DIR="$HOME/.claude/projects/-Users-$(whoami)/memory"
cp MEMORY.md *.md "$MEMORY_DIR/"
mkdir -p "$HOME/.claude/hooks"
cp hooks/*.py "$HOME/.claude/hooks/"
chmod +x "$HOME/.claude/hooks/"*.py
```

**Windows:**
```powershell
$MEMORY_DIR = "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME\memory"
Copy-Item MEMORY.md, *.md -Destination $MEMORY_DIR
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\hooks"
Copy-Item hooks\*.py "$env:USERPROFILE\.claude\hooks\"
```

### 2. Update the MEMORY_DIR path in the hooks

Edit `memory_search.py` and `subagent_start.py` — update the `MEMORY_DIR` variable:

```python
# macOS
MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "-Users-yourname", "memory")

# Windows
MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-yourname", "memory")
```

### 3. Configure hooks in settings.json

Add all hooks to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/memory_search.py",
            "timeout": 5
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/precompact_save.py",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/session_start.py",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/stop_hook.py",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/post_tool_use.py",
            "timeout": 3,
            "async": true
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/subagent_start.py",
            "timeout": 5
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/session_end.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

**Important:** Replace `/path/to/` with your actual home directory path. Use `python3` on macOS, `python` on Windows.

### 4. Approve the hooks

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

## Common Pitfalls

- **Hook schema**: Must use nested `{hooks: [{type, command}]}` format, NOT flat `{type, command}`.
- **Path separators**: macOS uses `-Users-` prefix, Windows uses `C--Users-` in the project path.
- **Hook not firing**: Check `/hooks` menu in Claude Code to approve pending hooks.
- **Windows encoding**: Hooks use `sys.stdout.buffer.write()` to avoid cp1252 Unicode errors.
- **Stop hook loops**: The `stop_hook_active` guard file prevents infinite re-entry. If it gets stuck, delete `~/.claude/stop_hook_active`.
- **PostToolUse is async**: Set `"async": true` in settings.json so it doesn't slow down Claude's responses.
