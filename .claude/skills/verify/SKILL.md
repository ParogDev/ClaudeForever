---
name: verify
description: Run the verify loop for one addon: luacheck + busted + stylua in Docker, then, if the game runs, ask the user to /reload, wait for the SavedVariables write and judge the selftest table and BugGrabber errors. Use when asked "verify", "test it", "does it load", or before calling addon work done. Not a substitute for writing tests.
---

# Verify

Argument: addon name (default: the one changed most recently under `AddOns/`, from `git -C AddOns/<Name> status`).

1. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\lua.ps1 all -Path AddOns\<Name>`. Red: fix first;
   never go on to the game with a red lint or a failing test. Docker not running: tell the user (start Docker
   Desktop) and stop with "not verified: Docker not running".
2. Is it in the game? `powershell -NoProfile -ExecutionPolicy Bypass -File tools\link-addons.ps1 -Status`. Not linked:
   `tools\link-addons.ps1 -Name <Name>`, then the user must restart the client (a new folder is not seen by
   `/reload`). Stop at "offline checks green; in-game check waits for a client restart".
3. Start `powershell -NoProfile -ExecutionPolicy Bypass -File tools\reload-wait.ps1 <Name> -TimeoutMinutes 20` in the
   background. Exit 3 right away means the game is not running: report "offline checks green; in-game check pending
   (game not running)". That is a valid partial result.
4. Ask the user to `/reload` (or log out) when convenient. Nothing here sends input to the game, ever; the reload is
   theirs. Do other work meanwhile; don't poll.
5. When reload-wait finishes, read its JSON:
   - exit 4: the read-back broke. Report `selftestError` / `bugGrabberError`; a null `selftest` is never a pass.
   - `selftest.version` must equal the version the code says (`ns.VERSION` in a checkout, since the `.toc` holds
     `@project-version@` until the packager replaces it). A different version means the game loaded other files.
   - `errorCount` must be 0 and `selftest.lastError` empty.
   Anything else is red: fix, rerun step 1, ask for another `/reload`.
6. Result line: `VERIFIED <Name> <version> (lint, N tests, reload at <time>, 0 errors)` or
   `NOT VERIFIED: <the link that broke>`.

BugGrabber errors are reported only when the BugGrabber and BugSack addons are installed (their Forever builds):
reload-wait reads `!BugGrabber.lua`. Without them, say "no error capture (BugGrabber not installed)".

Instance restrictions (when the change touches chat text or unit data): ask the user to run
`/console addonChatRestrictionsForced 1`, say a line, `/console addonChatRestrictionsForced 0`, then `/reload`.
`selftest.counters.secret` must be > 0 and `errorCount` 0.
