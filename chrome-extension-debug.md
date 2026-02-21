# Chrome Extension (Claude in Chrome) Debug History

## Status: WORKING - Feb 7, 2026

## Goal
Connect Claude Code CLI to Chrome browser via the "Claude in Chrome" extension.

## What's Installed
- Chrome extension: ID `fcoeoabgfenejglbffodgkkbkcdhcgfn`, v1.0.47
- Claude Code: v2.1.34
- Extension permissions: sidePanel, storage, activeTab, scripting, debugger, tabGroups, tabs, alarms, nativeMessaging
- Node.js and cli.js both exist and work

## Architecture
1. Chrome extension calls `chrome.runtime.connectNative()` to launch a native host
2. Native host creates named pipe: `\\.\pipe\claude-mcp-browser-bridge-scott`
3. Claude Code's MCP bridge (`--claude-in-chrome-mcp`) connects to the pipe
4. Tools are exposed via MCP protocol

## Two Native Host Registrations (Registry)
- `com.anthropic.claude_browser_extension` → Claude Desktop's host (REMOVED from registry in last session)
- `com.anthropic.claude_code_browser_extension` → Claude Code's host (ACTIVE)

## Changes Made (Feb 7, 2026)
1. Renamed Desktop native host config to .bak:
   `C:\Users\scott\AppData\Roaming\Claude\ChromeNativeHost\com.anthropic.claude_browser_extension.json.bak`
2. Removed Desktop registry key:
   `HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.anthropic.claude_browser_extension`
3. Only Claude Code registry key remains:
   `HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.anthropic.claude_code_browser_extension`
   Points to: `C:\Users\scott\AppData\Roaming\Claude Code\ChromeNativeHost\com.anthropic.claude_code_browser_extension.json`
4. Killed stale native host processes blocking the named pipe

## Root Causes Found
1. **Claude Desktop conflict**: Desktop's native host config pointed to deleted app-1.1.1520 path, causing Chrome to fail before trying Claude Code's host
2. **Stale processes**: Old `--chrome-native-host` processes held the named pipe, causing EADDRINUSE when new ones tried to start
3. **Pipe conflict**: Claude Code's own MCP bridge and Chrome-launched native host both tried to create the same pipe

## Last Known State (end of session)
- Claude Desktop: NOT running (closed)
- Desktop registry key: REMOVED
- Stale processes: KILLED
- Named pipe: CONFIRMED ACTIVE (pipe test returned "PIPE IS ACTIVE")
- Chrome: Successfully launched native host (PID 486016) when extension icon clicked
- User was told to: exit Claude Code, NOT close Chrome, restart with `claude --chrome`

## Key Files
- Native host bat: `C:\Users\scott\.claude\chrome\chrome-native-host.bat`
- Native host config: `C:\Users\scott\AppData\Roaming\Claude Code\ChromeNativeHost\com.anthropic.claude_code_browser_extension.json`
- Extension service worker: `C:\Users\scott\AppData\Local\Google\Chrome\User Data\Default\Extensions\fcoeoabgfenejglbffodgkkbkcdhcgfn\1.0.47_0\assets\service-worker-*.js`

## Things NOT to Repeat
- Don't suggest reinstalling the extension (already done)
- Don't suggest restarting Chrome without reason (done 5+ times)
- Don't suggest logging into claude.ai (already confirmed)
- Don't suggest checking extension permissions (confirmed: all granted)
- Don't kill the MCP bridge process from within the active session (kills own session)
- Extension has NO "Options" menu for pairing/connecting

## Root Cause Identified (Feb 7, 2026 - Session 4)
The MCP bridge (`--claude-in-chrome-mcp`) starts at Claude Code launch time (9:51 AM).
The native host (`--chrome-native-host`) starts when Chrome extension is clicked (10:05 AM).
The MCP bridge tries to connect to the pipe, finds nothing, and DOES NOT RETRY.
The native host creates the pipe later but the bridge has already given up.

**FIX: Start order matters.**
1. Chrome must be running with extension active FIRST
2. Click extension icon to trigger native host launch (creates pipe)
3. THEN start Claude Code (MCP bridge finds the pipe and connects)

## Profile Alias Updated
Added `--chrome` to PowerShell claude alias so it's always enabled:
`function claude { & "C:\home\scott\.npm-global\claude.cmd" --dangerously-skip-permissions --chrome @args }`
File: `C:\Users\scott\OneDrive\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`

## If Still Not Working
- Check for stale node processes: `powershell.exe -NoProfile -Command 'Get-Process node | ForEach-Object { $id = $_.Id; $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$id").CommandLine; Write-Host "$id : $cmd" }'`
- Check pipe status: `powershell.exe -NoProfile -Command 'try { $pipe = [System.IO.Pipes.NamedPipeClientStream]::new(".", "claude-mcp-browser-bridge-scott", [System.IO.Pipes.PipeDirection]::InOut, [System.IO.Pipes.PipeOptions]::None); $pipe.Connect(2000); Write-Host "PIPE IS ACTIVE"; $pipe.Close() } catch { Write-Host "PIPE NOT AVAILABLE: $_" }'`
- Check registry: `powershell.exe -NoProfile -Command 'Get-ChildItem "HKCU:\Software\Google\Chrome\NativeMessagingHosts\" | ForEach-Object { $name = $_.PSChildName; $val = (Get-ItemProperty $_.PSPath)."(default)"; Write-Host "$name -> $val" }'`
- May need to file issue at https://github.com/anthropics/claude-code/issues
- Related known issue: https://github.com/anthropics/claude-code/issues/20887 (Desktop vs Code conflict)

## Startup Procedure (ALWAYS FOLLOW THIS)
1. Open Chrome, ensure Claude side panel is open (click extension icon)
2. Wait 5 seconds for native host to create pipe
3. THEN start Claude Code in terminal (`claude` — alias includes --chrome)
4. Test with "test chrome access"

**CRITICAL FOR FUTURE SESSIONS:** This is a CONFIRMED BUG in Claude Code v2.1.20+ on Windows.
- GitHub issue: https://github.com/anthropics/claude-code/issues/21371 (40+ upvotes)
- Root cause: Socket path discovery function only scans for Unix .sock files, never returns Windows named pipe path
- The "restart with correct startup order" advice DOES NOT WORK — the bug is in the code itself
- **FIX OPTIONS:**
  1. Downgrade: `npm install -g @anthropic-ai/claude-code@2.1.19`
  2. Patch cli.js: Use community patch script (saved at `.claude/patch-chrome-mcp.js`)
  3. Wait for official fix from Anthropic
- Patch must be re-applied after every Claude Code update

## If Startup Order Fix Doesn't Work
- The MCP bridge may have retry logic we're not seeing - try waiting 30 seconds after starting Claude Code, then test
- Try: start Claude Code first, THEN click extension icon, wait 10 seconds, test again
- Check Chrome's extension errors: go to chrome://extensions, click "Errors" on the Claude extension
- Check if the extension service worker is active: chrome://serviceworker-internals
- Run `claude --chrome --debug` for verbose logging
- Nuclear option: uninstall extension, restart Chrome, reinstall from chrome://extensions using ID fcoeoabgfenejglbffodgkkbkcdhcgfn
- File bug at https://github.com/anthropics/claude-code/issues with details from this file

## Session History
- ~2 weeks ago: First attempt, failed, no notes saved
- Feb 7 Session 1: Identified Desktop conflict, renamed .bak, removed registry key
- Feb 7 Session 2: Killed Claude Desktop, restarted Chrome multiple times, still failed
- Feb 7 Session 3: Started with `claude --chrome`, identified stale native host (PID 405496) blocking pipe, killed it but also killed own session
- Feb 7 Session 4: Confirmed timing issue - MCP bridge starts 14 min before native host. Updated PowerShell alias. Plan: reboot with correct startup order.
- Feb 7 Session 5: Everything verified correct (registry, manifest, native host bat, cli.js, node.js, extension v1.0.47 installed). Still failed to connect. Same root cause: Claude Code was started before extension pipe was ready. Wasted time re-verifying setup instead of immediately telling user to restart. **LESSON: Don't re-diagnose — just tell user to restart Claude Code with extension open.**
- Feb 7 Session 6: User asked to test Chrome. Failed again. Verified pipe IS ACTIVE (test_pipe.ps1 confirmed). Registry keys for native host are gone from HKCU and HKLM (may have been cleaned up or moved). Claude Code v2.1.37. Chrome running, extension clicked, pipe active — but MCP bridge in Claude Code already failed at startup and won't retry. Told user to exit and restart Claude Code without closing Chrome. **NO registry entries found** — native host may now use file-based manifest or different registration. Don't waste time checking registry next time.
- Feb 7 Session 7: **SUCCESS!** Chrome MCP fully working. Patch script (`.claude/patch-chrome-mcp.js`) fixed the Windows named pipe discovery bug. All capabilities confirmed: tab context, navigation, screenshots, page reading. First screenshot attempt on chrome://newtab failed (restricted URL) but that's normal Chrome security — navigating to example.com and screenshotting worked perfectly. User granted auto-allow for screenshot permission.

## RESOLUTION SUMMARY

**The fix that worked:** Community patch script at `C:\Users\scott\.claude\patch-chrome-mcp.js`
- Patches the socket path discovery in cli.js to support Windows named pipes
- Must be re-applied after every Claude Code update (`npm update -g @anthropic-ai/claude-code`)

**After a Claude Code update, if Chrome stops working:**
1. Re-run the patch: `node C:\Users\scott\.claude\patch-chrome-mcp.js`
2. Restart Claude Code (alias already includes `--chrome`)
3. Test with "test Chrome access"

**What NOT to do:**
- Don't waste time checking registry, manifest, or startup order — those were all fine
- Don't downgrade Claude Code — the patch works on current versions
- The bug is tracked at GitHub #21371 and may eventually be fixed upstream
