# claude-memory

Layered memory system for Claude Code — keyword index, topic files, and a search hook that automatically surfaces relevant context.

## How It Works

1. **MEMORY.md** — Slim keyword index (~60 lines), always loaded into Claude's context. Each project gets one line with name, status, keywords, and a link to its topic file.
2. **Topic files** (`*.md`) — Full project details, loaded on demand only when keywords match.
3. **Search hook** (`hooks/memory_search.py`) — Runs on every prompt submission. Matches your message against the keyword index and injects matching topic file contents into Claude's context.

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

### 4. Approve the hook

On first launch after adding the hook, Claude Code will prompt you to review and approve it in the `/hooks` menu. This is a security measure — hooks added by editing files manually require approval before they'll run.

## Adding New Projects

Add a line to the Project Index section of `MEMORY.md`:

```markdown
**Project Name** | Status | keyword1 keyword2 keyword3 | [topic-file.md](topic-file.md)
```

Then create the corresponding topic file with full details. The hook will automatically match future prompts against the keywords and load the topic file when relevant.

## Common Pitfalls

- **Hook schema**: Must use nested `{matcher, hooks: [{type, command}]}` format, NOT flat `{type, command}`. The flat format will error.
- **Path separators**: macOS uses `-Users-` prefix, Windows uses `C--Users-` in the project path.
- **Hook not firing**: Check `/hooks` menu in Claude Code to approve pending hooks. Manual file edits require approval.
- **No output on short prompts**: By design — prompts under 3 characters or with no keyword matches produce no output.
