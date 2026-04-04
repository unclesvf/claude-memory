#!/usr/bin/env python3
"""
SessionStart Hook for Claude Code
Fires when a new session begins or resumes after compaction.

If a recovery file exists from a previous PreCompact save, outputs its
contents so Claude automatically knows what was being worked on.

Only injects context when the session started due to compaction or a fresh
startup (not on /clear or resume, where context is already available).
"""
import json
import sys
import os
import time
from pathlib import Path

SESSION_DIR = Path.home() / ".claude" / "sessions"
RECOVERY_FILE = SESSION_DIR / "last_session.md"
# Max age in seconds before we consider the recovery file stale (1 hour)
MAX_AGE_SECONDS = 3600


def main():
    # Read hook input
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    source = data.get("source", "")

    # Only inject recovery context on startup or after compaction
    # "resume" already has context, "clear" means user wants a fresh start
    if source not in ("startup", "compact"):
        sys.exit(0)

    # Check if recovery file exists
    if not RECOVERY_FILE.exists():
        sys.exit(0)

    # Check if recovery file is recent enough to be useful
    try:
        age = time.time() - RECOVERY_FILE.stat().st_mtime
    except OSError:
        sys.exit(0)

    if age > MAX_AGE_SECONDS:
        sys.exit(0)

    # Read and output the recovery file
    try:
        content = RECOVERY_FILE.read_text(encoding="utf-8")
    except OSError:
        sys.exit(0)

    if not content.strip():
        sys.exit(0)

    # Output as additional context for Claude
    # Plain text to stdout gets injected into Claude's context
    output = f"[Session Recovery] Previous session state recovered:\n\n{content}"
    sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")

    # Write active session info for F9 voice daemon
    _write_voice_session_info()

    sys.exit(0)


def _write_voice_session_info():
    """Write terminal window info so F9 daemon can inject into the right window."""
    try:
        import psutil
        import win32gui
        import win32process

        # Walk up process tree to find WindowsTerminal
        p = psutil.Process(os.getpid())
        terminal_pid = None
        powershell_pid = None
        claude_pid = None
        for _ in range(10):
            p = p.parent()
            if p is None:
                break
            name = p.name().lower()
            if "node" in name and claude_pid is None:
                claude_pid = p.pid
            if "powershell" in name and powershell_pid is None:
                powershell_pid = p.pid
            if "windowsterminal" in name:
                terminal_pid = p.pid
                break

        if terminal_pid is None:
            return

        # Find the PowerShell window belonging to THIS session's PowerShell PID.
        # Windows Terminal tabs share a parent PID, so we enumerate all visible
        # windows and look for one owned by our specific PowerShell process.
        # If that fails (WT owns all tab HWNDs under its own PID), find all
        # non-admin PowerShell windows from the terminal and pick the first.
        target_hwnd = None
        target_title = None

        # First try: find window owned by our PowerShell PID directly
        if powershell_pid:
            def cb_ps(hwnd, r):
                if win32gui.IsWindowVisible(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == powershell_pid:
                        try:
                            title = win32gui.GetWindowText(hwnd)
                            r.append((hwnd, title))
                        except:
                            pass
            ps_wins = []
            win32gui.EnumWindows(cb_ps, ps_wins)
            if ps_wins:
                target_hwnd, target_title = ps_wins[0]

        # Fallback: find all terminal windows, pick non-admin PowerShell
        if target_hwnd is None:
            def cb_term(hwnd, r):
                if win32gui.IsWindowVisible(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == terminal_pid:
                        try:
                            title = win32gui.GetWindowText(hwnd)
                            if "powershell" in title.lower() and "administrator" not in title.lower():
                                r.append((hwnd, title))
                        except:
                            pass
            term_wins = []
            win32gui.EnumWindows(cb_term, term_wins)
            if term_wins:
                target_hwnd, target_title = term_wins[0]

        voice_dir = Path.home() / ".claude" / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        session_file = voice_dir / "active_session.json"
        data = {
            "terminal_pid": terminal_pid,
            "powershell_pid": powershell_pid,
            "claude_pid": claude_pid,
        }
        if target_hwnd:
            data["target_hwnd"] = target_hwnd
            data["target_title"] = target_title
        session_file.write_text(json.dumps(data, indent=2))
    except Exception:
        pass  # Never block session start


if __name__ == "__main__":
    main()
