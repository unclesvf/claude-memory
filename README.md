# claude-memory

Layered memory system for Claude Code — keyword index, topic files, and hooks that automatically surface relevant context and preserve session state across crashes.

## How It Works

1. **MEMORY.md** — Slim keyword index (~60 lines), always loaded into Claude's context. Each project gets one line with name, status, keywords, and a link to its topic file.
2. **Topic files** (`*.md`) — Full project details, loaded on demand only when keywords match.
3. **Search hook** (`hooks/memory_search.py`) — Runs on every prompt submission. Matches your message against the keyword index and injects matching topic file contents into Claude's context.
4. **PreCompact hook** (`hooks/precompact_save.py`) — Runs before context compression. Saves a session snapshot (what you were working on, files touched, recent actions) so the next session can pick up where you left off.
5. **SessionStart hook** (`hooks/session_start.py`) — Runs when a new session begins. Automatically injects the recovery snapshot from PreCompact so Claude knows what you were working on without being asked.

## Setup

### 1. Clone into your memory directory

**macOS:**
```bash
# The project path segment uses a dash prefix on macOS
MEMORY_DIR="$HOME/.claude/projects/-Users-$(whoami)/memory"
cp MEMORY.md *.md "$MEMORY_DIR/"
mkdir -p "$HOME/.claude/hooks"
cp hooks/memory_search.py "$HOME/.claude/hooks/"
chmod +x "$HOME/.claude/hooks/memory_search.py"
```

**Windows:**
```powershell
# The project path segment uses C-- prefix on Windows
$MEMORY_DIR = "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME\memory"
Copy-Item MEMORY.md, *.md -Destination $MEMORY_DIR
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\hooks"
Copy-Item hooks\memory_search.py "$env:USERPROFILE\.claude\hooks\"
```

### 2. Update the MEMORY_DIR path in the hook

Edit `~/.claude/hooks/memory_search.py` and update the `MEMORY_DIR` variable to match your system:

```python
# macOS
MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "-Users-scott", "memory")

# Windows
MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--Users-scott", "memory")
```

### 3. Configure the hook in settings.json

Add this to `~/.claude/settings.json`. The hook schema requires a nested structure — a `matcher` field and a `hooks` array inside each event entry:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.claude/hooks/memory_search.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Important:** Use the full absolute path to the script. Replace `/path/to/` with your actual home directory.

**macOS example:**
```json
"command": "python3 /Users/scott/.claude/hooks/memory_search.py"
```

**Windows example:**
```json
"command": "python3 C:\\Users\\scott\\.claude\\hooks\\memory_search.py"
```

### 4. Add the PreCompact hook (optional but recommended)

The PreCompact hook saves a session snapshot before Claude compresses context. This means after a crash, power outage, or long session that hits the context limit, the next session can read `~/.claude/sessions/last_session.md` and know exactly what you were working on.

Copy the hook:

**macOS:**
```bash
cp hooks/precompact_save.py "$HOME/.claude/hooks/"
chmod +x "$HOME/.claude/hooks/precompact_save.py"
```

**Windows:**
```powershell
Copy-Item hooks\precompact_save.py "$env:USERPROFILE\.claude\hooks\"
```

Add the PreCompact event to your `~/.claude/settings.json` alongside the UserPromptSubmit hook:

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
    ]
  }
}
```

The hook writes two files:
- `~/.claude/sessions/last_session.md` — Human-readable snapshot of what was being worked on
- `~/.claude/sessions/compaction_log.jsonl` — Append-only log of all compaction events

### 5. Add the SessionStart hook (optional, pairs with PreCompact)

The SessionStart hook automatically injects the PreCompact recovery file when a new session starts or after compaction. This means Claude will know what you were working on without you having to tell it.

Copy the hook:

**macOS:**
```bash
cp hooks/session_start.py "$HOME/.claude/hooks/"
chmod +x "$HOME/.claude/hooks/session_start.py"
```

**Windows:**
```powershell
Copy-Item hooks\session_start.py "$env:USERPROFILE\.claude\hooks\"
```

Add SessionStart to your `~/.claude/settings.json`:

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
    ]
  }
}
```

The SessionStart hook only fires on `startup` and `compact` sources — it stays silent on `/clear` (user wants a fresh start) and `resume` (context already available). Recovery files older than 1 hour are ignored.

### 6. Approve the hooks

On first launch after adding hooks, Claude Code will prompt you to review and approve them in the `/hooks` menu. This is a security measure — hooks added by editing files manually require approval before they'll run.

## Adding New Projects

Add a line to the Project Index section of `MEMORY.md`:

```markdown
**Project Name** | Status | keyword1 keyword2 keyword3 | [topic-file.md](topic-file.md)
```

Or with an importance score (1-10, default 5):

```markdown
**Project Name** | Status | 8 | keyword1 keyword2 keyword3 | [topic-file.md](topic-file.md)
```

Importance affects how strongly keyword matches rank this entry. A score of 5 is neutral, 10 doubles the keyword weight, and 1 reduces it to 20%.

Then create the corresponding topic file with full details. The hook will automatically match future prompts against the keywords and load the topic file when relevant.

## Scoring System

The search hook ranks memories using three signals:

1. **Keyword match** (0-15+) — Exact keyword match = 3 points, partial match = 2, project name match = 2
2. **Importance weight** (1-10) — Multiplier on keyword score. Default 5 = neutral (1.0x). Set per entry in MEMORY.md.
3. **Recency boost** — Files accessed in the last hour get +3, last 4 hours +2, last 24 hours +1

Formula: `final_score = keyword_score * (importance / 5) + recency_boost`

Minimum threshold to surface a topic file: **4 points**. Top 3 results are returned.

Access times are tracked in `~/.claude/memory_access_log.json` automatically.

## Common Pitfalls

- **Hook schema**: Must use nested `{matcher, hooks: [{type, command}]}` format, NOT flat `{type, command}`. The flat format will error.
- **Path separators**: macOS uses `-Users-` prefix, Windows uses `C--Users-` in the project path.
- **Hook not firing**: Check `/hooks` menu in Claude Code to approve pending hooks. Manual file edits require approval.
- **No output on short prompts**: By design — prompts under 3 characters or with no keyword matches produce no output.
