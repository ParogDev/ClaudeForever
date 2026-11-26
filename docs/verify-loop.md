# The verify loop

How an addon change is checked here, from lint to "it loaded in the game with no errors".

## Why it looks like this

There is no compiler, no bridge into the game, and no way to send it input (anti-cheat: nothing here ever types,
clicks or sends keys to the client). Data leaves the game only through SavedVariables, written on `/reload`,
logout and exit. So the loop puts almost all checking offline, where it is fast and needs nobody, and treats your
`/reload` as one checkpoint whose result is read back from disk.

## The loop

```
edit AddOns\<Name>\...
  -> tools\lua.ps1 all -Path AddOns\<Name>      luacheck + busted + stylua in Docker, a few seconds; red blocks
  -> linked?  tools\link-addons.ps1 -Status     not linked: tools\link-addons.ps1 -Name <Name>, then restart
                                                the client once (a new folder is not seen by /reload)
  -> tools\reload-wait.ps1 <Name>               in the background; waits for the next SavedVariables write
  -> you /reload in game
  -> reload-wait prints JSON: selftest table + BugGrabber errors naming the addon
  -> green: done;  red: fix, lua.ps1, /reload again
```

The `verify` skill runs this. Only the result of a reload counts: lint without a reload verified the code, not
that the game loads it.

`reload-wait` exit codes:

| Code | Meaning |
|---|---|
| 0 | Reload seen: judge `errorCount` and `selftest`. |
| 2 | Timeout (default 20 min), or the game closed before a write was seen. |
| 3 | Game not running. |
| 4 | Reload seen, but the SavedVariables read-back broke. `selftestError` / `bugGrabberError` say where: the file did not parse, or the variable or its `selftest` was absent, after 5 tries 1 s apart; `selftest` parsed to null; Python does not run. A `BugGrabberDB` still absent after the retries counts as no errors. |

`reload-wait.ps1 <Name> -File <copy.lua>` does the read-back on an existing file without waiting (no game needed).
`-Var` names the SavedVariable when it is not `<Name>DB`. Its parser, `tools\wowf_sv.py` (Python 3, standard
library only), has its own exit codes; each non-zero one prints one `wowf_sv:` line on stderr:

| Code | Meaning |
|---|---|
| 0 | OK. |
| 2 | The file does not parse. |
| 3 | The variable or a `--path` step is absent. |
| 4 | The file cannot be read. |
| 5 | A value JSON cannot hold (inf, nan). |

Known limit: PowerShell 5.1 `ConvertFrom-Json` refuses keys that differ only by case, and empty-string keys. A file
like that reports as a broken read-back (exit 4) although it is fine.

The parser never runs the Lua: the file is written by the game and can hold text other players typed.

## What the addon must give the loop

Every addon keeps `<Name>DB.selftest` (an account-wide SavedVariable), refreshed on `PLAYER_LOGIN` and on
`PLAYER_LOGOUT` (the last event before the write). `templates/addon/Core.lua` has it ready:

| Field | Meaning |
|---|---|
| `version` | `C_AddOns.GetAddOnMetadata(name, "Version")`, or the code's `ns.VERSION` while the `.toc` still says `@project-version@`. A reload that shows the new number proves the new files loaded |
| `build`, `interface`, `project` | `GetBuildInfo()` and `WOW_PROJECT_ID`, for the record |
| `phase` | `login`, `logout` or `slash`: which event wrote it |
| `loadedAt`, `savedAt` | `date("%Y-%m-%d %H:%M:%S")` |
| `counters` | whatever the addon counts: events seen, lines that were secret, items judged |
| `lastError` | the last error the addon caught itself, with where it happened (`geterrorhandler()` is not replaced) |

Add fields as the addon grows (a font probe result, the last few processed items), but never store a secret value
or other players' chat in it if the repo or a bug report might show it.

## Errors

Install the BugSack and BugGrabber addons (their Forever builds) once. BugGrabber writes `!BugGrabber.lua` on
reload; `reload-wait` reports the errors whose message or stack mentions the addon. After 100 errors in a session
the client stops dispatching them: a flood is itself the finding. `/console scriptErrors 1` shows errors on screen
as they happen.

## Offline tests

`tests/wow_mock.lua` gives busted the globals an addon file touches at load (`CreateFrame`, `C_AddOns`,
`issecretvalue`, `GetBuildInfo`, `date`, ...). Load addon files with `loadfile(path)(ADDON_NAME, ns)` so the
`local ADDON, ns = ...` header works. Test what has logic (parsing, counting, migrations, the secret guard), not
frames. A change ships with a test.

## Simulating the restrictions

`/console addonChatRestrictionsForced 1` makes chat text secret in town; `0` clears it. A test session with it on
must show raw text where the addon would analyse it, `selftest.counters.secret` above 0, and no Lua errors.

## Game folder rules

- SavedVariables (`_forever_\WTF\...`) are rewritten by the client on `/reload`, logout and exit. Editing them while
  `Wow.exe` runs loses the edit; the hook in `.claude/settings.json` (`tools\guard-game-files.ps1`) denies it.
- Your addons reach the game through junctions (`tools\link-addons.ps1`). Edit `AddOns\<Name>\...` in this
  workspace, never through `_forever_\Interface\AddOns\...`; the same hook denies that path.
- A file newly listed in a `.toc`, or a new addon folder, needs a client restart. Edits to files already listed
  need only `/reload`.
