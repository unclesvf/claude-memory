# claude-mem v9.1.1 Security Audit (Feb 10, 2026)

## Plugin Info
- **Location:** `C:\Users\scott\.claude\plugins\cache\thedotmack\claude-mem\9.1.1\`
- **Author:** thedotmack (github.com/thedotmack/claude-mem)
- **Enabled in:** `C:\Users\scott\.claude\settings.json` → `"claude-mem@thedotmack": true`

## Verdict: NOT MALWARE — legitimate memory system, default config is safe

## Architecture
- **Hooks:** SessionStart (3 commands), UserPromptSubmit (2), PostToolUse (2), Stop (3)
- **Worker:** Express.js HTTP server on port 37777 (localhost by default)
- **MCP Server:** Provides search, timeline, get_observations, save_memory tools
- **Database:** SQLite at `~/.claude-mem/claude-mem.db` (unencrypted)
- **LLM providers:** Claude SDK (default), Google Gemini, OpenRouter

## CRITICAL Findings
1. **Gemini API key in URL params** — `?key=...` (Google API limitation, not plugin's fault)
2. **Can bind 0.0.0.0** — Settings allow it but default is safe `127.0.0.1`

## HIGH Findings
3. **All tool I/O sent to LLM** — Every tool name/input/output/prompt goes to configured provider
4. **Shell profile injection** — Adds `claude-mem` function to PowerShell profile, .bashrc, .zshrc
5. **Auto-installs Bun + uv** — `curl|bash` / `irm|iex` pattern, runs on every session start
6. **Reads API keys** from `~/.claude-mem/.env`

## MEDIUM Findings
7. **SQLite stores all coding activity** unencrypted (tool invocations, prompts, facts, file paths)
8. **Git command execution** via `/api/branch/switch` and `/api/branch/update` endpoints
9. **Process killing** — orphan reaper kills matching PIDs
10. **Writes to CLAUDE.md** — injects `<claude-mem-context>` blocks

## GOOD
- No telemetry/analytics (no Mixpanel, Sentry, PostHog, etc.)
- CORS restrictive (localhost only)
- Admin endpoints (shutdown/restart) have localhost IP guard
- Default binding is 127.0.0.1:37777

## External URLs Contacted
| Category | URLs |
|----------|------|
| LLM APIs | `generativelanguage.googleapis.com`, `openrouter.ai/api/v1/chat/completions` |
| Install | `bun.sh/install`, `astral.sh/uv/install.sh` |
| Docs | `docs.claude-mem.ai`, `github.com/thedotmack/claude-mem` |
| Community | `discord.gg/J4wttp9vDu`, `x.com/Claude_Memory` |

## Startup Errors
Two `SessionStart:startup hook error` lines appear when Bun is being installed (41s) and worker-service tries to start before deps are ready. Self-resolving — UserPromptSubmit hooks succeed afterward.

## Key Files
| File | Lines | Purpose |
|------|-------|---------|
| `smart-install.js` | 487 | Installs Bun, uv, deps, shell aliases |
| `bun-runner.js` | 91 | Finds Bun binary even when not in PATH |
| `worker-service.cjs` | 1739 | Bundled Express server, main worker |
| `mcp-server.cjs` | 77 | Bundled MCP server |
| `context-generator.cjs` | 650 | Bundled context generator |
| `hooks/hooks.json` | 93 | Hook configuration |
