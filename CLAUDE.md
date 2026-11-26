# ClaudeForever

A Claude Code workspace for World of Warcraft: Forever players: TSM setup and upkeep, profession leveling plans, addon
writing (Lua 5.1), ForeverAuras displays and macros. Rules here; how things work in `docs/`.

## First run

No `tsm/my-setup.md` yet means this player has not been set up: offer `/setup` before anything else. Once it exists, read it
before any TSM or profession task: it holds their characters, professions, answers and agreed settings.

## Layout and paths

- `.claude/skills/` (skills), `.claude/agents/`, `tools/` (Python and PowerShell tools), `docs/`, `templates/addon/` (new-addon
  template), `auras/` (example ForeverAuras sets), `tsm/examples/` (starter plan).
- Gitignored, the player's own: `tsm/plan.json`, `tsm/my-setup.md`, `AddOns/<Name>/` (each addon its own git repo),
  `vendor/` (read-only Blizzard UI source, `tools\vendor-sync.ps1`), `research/`.
- **Game**: `C:\Program Files (x86)\World of Warcraft\_forever_\`; `WOWF_GAME_DIR` overrides the parent folder. Addons are
  junctions from `AddOns\<Name>` into `_forever_\Interface\AddOns\<Name>` (`tools\link-addons.ps1`).

## TSM

- Load the `tsm-settings` skill for anything about TSM, the auction house, posting, sniping, vendoring or gold making.
- We change TSM only through its SavedVariables (`tools/tsm/tsmdb.py`), never its addon files (All Rights Reserved).
- Write `WTF` files only with the game fully closed; `tsmdb.py` refuses otherwise and so does the hook.
- Every change: dry run, show the player a table of what changes, apply, `validate`, then ask them to check in game.

## Forever API rules (for addon work)

- Forever runs **Mainline 12.1.x** UI code with a 1.60.1 version (`## Interface: 16001`). Modern namespaces only (`C_Item`,
  `C_Spell`, `C_AddOns`, `C_ChatInfo`, `MenuUtil`, Settings API). A Classic global you remember is gone unless
  `vendor\BlizzardInterfaceResources\Resources\GlobalAPI.lua` lists it. Ask `/forever-api` before writing a call you are
  not sure of. Never cite Classic Era docs; see `docs/forever-api.md`.
- **Secret values are active**: chat text and unit values can arrive as secrets in instances. Guard every text path with
  `issecretvalue()` and degrade.
- UTF-8: no `utf8` library; use byte patterns and `strlenutf8`. Fonts: `SetFontObject` + `SetFontHeight`, never `SetFont` on a
  FontFamily.

## Build and verify (addons)

- `tools\lua.ps1 all -Path AddOns\<Name>` = luacheck + busted + stylua in Docker. Red blocks everything.
- In game, the player `/reload`s; nothing sends input to the game, ever. `/verify <Name>` runs the loop: lint and tests, then
  waits for the reload and reads the addon's `selftest` table and BugGrabber errors. Details: `docs/verify-loop.md`.
- A new addon folder or a new file in a `.toc` needs a client restart; edits to listed files need `/reload`.
- SavedVariables are written only on `/reload`, logout and exit.

## Fail at the broken link

A failed lookup names where it broke (TSM never saved on this character, AppHelper has no data for the realm, event not
registered, secret value), never a bare "not found". Tell "broken" from "not now" (game closed, secret in an instance).

## Safety

- Never send synthetic input to the game or automate the client or Battle.net (anti-cheat).
- Never commit character, realm, account or guild names, chat text or local paths. Those stay in the gitignored files above.
- Shell edits of repo files are fine for tools; prefer Edit/Write so the diff is visible.

## Skills

`/setup` first-run setup. `tsm-settings` TSM changes. `/new-addon <Name>`, `/verify [Name]`, `/forever-api <question>`,
`/release <Name> <version>` for addon work. `/unslop` before writing anything a person reads.
