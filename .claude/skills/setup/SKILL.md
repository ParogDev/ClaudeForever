---
name: setup
description: First-run setup for a new ClaudeForever user. Checks the machine (game folder, Python, TSM and its AppHelper), reads what TSM already knows about their characters, professions, gold and sales, asks only the questions the data cannot answer, then writes their TSM group tree and operations with the game closed. Use for "/setup", "set me up", "get started", "set up TSM", or the first time a session sees no tsm/my-setup.md. Rerun it to redo the TSM setup from scratch.
---

# Setup

The person running this is a WoW: Forever player who cloned ClaudeForever. They may not code. Keep every message short, show
choices as buttons (AskUserQuestion), and show plans as tick-box tables. Nothing here sends input to the game: the player does
every in-game click, `/reload` and restart.

## 1. Check the machine

Run these, then show one table: what was found, what is missing, the fix for each missing piece.

| Check | How | If missing |
|---|---|---|
| Game folder | `<parent>\_forever_\Wow.exe` exists; parent is `WOWF_GAME_DIR` or `C:\Program Files (x86)\World of Warcraft` | Ask where the game is installed; tell them to set `WOWF_GAME_DIR` to the folder that holds `_forever_` (a user environment variable), then restart Claude |
| Python 3.10+ | `python --version` | `winget install Python.Python.3.12`, then restart Claude |
| TSM installed | `<game>\_forever_\Interface\AddOns\TradeSkillMaster\` exists | Install TradeSkillMaster through the TSM desktop app or CurseForge, start the game once with it enabled |
| TSM has saved | `python -I tools/tsm/tsmdb.py profile` finds a `TradeSkillMaster.lua` | Start the game, log in on each character once with TSM loaded, open each profession window once, `/reload`, then rerun |
| Market prices | `profile` reports AppHelper data | Install the TSM desktop app and let it sync; until then `dbmarket` and friends are empty and plans fall back to vendor prices |
| Docker (only for writing addons) | `docker info` | Skip unless they want to write addons; then Docker Desktop |

A missing TSM file is "not now", not a failure: the player has not logged in with TSM yet. Say exactly which step is owed.

## 2. Read before asking

Run `python -I tools/tsm/tsmdb.py profile` (JSON) and `... profile --text` (for you to quote). From it, settle without asking:

- **Characters and realms.** Every `Character - Realm` TSM has seen, with faction, class and gold.
- **Main and bank alt.** A guess: the character with the most professions and gold is the main; a level-low character on the
  same realm and faction with lots of bag and bank items is a likely bank alt. State the guess, confirm it with one question.
- **Professions.** Name, level and cap per character. Do not ask "what professions do you have".
- **What they already sell.** Accounting rows: top items sold by gold, how many sales, over what dates. A player with sales
  history has a style already; describe it back to them ("you mostly sell leather and cloth, about N gold a week").
- **Existing TSM setup.** Group count, top-level groups, operations per module, custom sources. If they already have groups,
  ask whether to keep them and add, or replace them (replace keeps a backup).
- **Prices.** Whether AppHelper data is there, how old, and for which realm.

Tell them in one short table what you learned, then ask only what is left.

## 3. Ask what the data cannot answer

One AskUserQuestion call, at most four questions, skipping any the data settled. Pick from:

1. **Goal**: make gold from crafting / flip the auction house / sell what I farm / level my professions cheaply / just keep my
   bags tidy. (Multi-select.)
2. **Time at the auction house**: a few minutes a day (post and go, longer durations, fewer cancels) / I check often (shorter
   durations, tighter undercuts, cancel and repost).
3. **Undercut style**: gentle (1 copper under, never below a safe floor) / aggressive (beat the lowest, accept thinner margins).
4. **Vendor junk automatically** (grey items and greens below a value you choose) / never vendor without asking.
5. **Main and bank alt** confirmation, when the guess in step 2 is not obvious.
6. **Professions they plan to take**, only for a character with none recorded.

## 4. Write their setup down

Write `tsm/my-setup.md` (gitignored, never commit it): the detected facts (characters, professions, sales summary, price data
age) and their answers, dated. Later sessions read it instead of asking again; the `tsm-settings` skill keeps its "Agreed
settings" there.

## 5. Build the plan

Start from `tsm/examples/starter-plan.json` and shape it from steps 2-4:

- Keep the groups that match their goal and professions: crafting mats for the professions they have, their sold items from
  accounting placed in the matching group, a vendor group only if they said yes to vendoring.
- Set Auctioning durations, undercut and cancel behaviour from questions 2 and 3; floors stay at or above vendor price.
- With a bank alt: Mailing operations that send each group to the character that sells it.
- Read `docs/tsm/strategies.md` and `docs/tsm/operations.md` for the values; never invent a setting key, look it up.

Save as `tsm/plan.json` (gitignored). Run `python -I tools/tsm/tsmdb.py apply tsm/plan.json --dry-run` and fix every error.
Then show the plan: one table per group with the operations attached and the two or three numbers that matter (min / normal /
max price, post duration, vendor rule). Ask once: apply it / change something / not now.

## 6. Apply with the game closed

1. If `Wow.exe` runs, ask them to exit the game completely (not just log out); the tool refuses to write while it runs
   because the client overwrites SavedVariables on exit.
2. `python -I tools/tsm/tsmdb.py apply tsm/plan.json` (it backs the file up first; say where the backup went).
3. `python -I tools/tsm/tsmdb.py validate`, then `groups`. Red means restore the backup and say what broke.
4. Ask them to start the game and open TSM's Groups tab. Ask one question: do the groups look right?

## 7. Offer the rest

In one line each, offer what else the workspace does, as buttons, and stop:

- Plan the cheapest way to level a profession (`tools/tsm/skillup.py`, `docs/tsm/skillup.md`).
- Write their own addon (`/new-addon`), which needs Docker for lint and tests and `tools\vendor-sync.ps1` for the API source.
- Author WeakAuras-style displays with ForeverAuras (`docs/foreverauras.md`).
- Write macros (`docs/macros/`).

## Rules

- Never write anything under `<game>\_forever_\WTF` while `Wow.exe` runs. The hook in `.claude/settings.json` denies it too.
- Never edit TSM's own addon files; TSM is All Rights Reserved. We change only its SavedVariables.
- Never put a character, realm or account name in a committed file. They live in `tsm/my-setup.md` and `tsm/plan.json`,
  both gitignored.
- A missing piece is named where it broke ("AppHelper has no data for your realm", "TSM has not seen your Tailoring"), never a
  bare "not found".
