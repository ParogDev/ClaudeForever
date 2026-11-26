---
name: tsm-settings
description: Read or change TradeSkillMaster (TSM) settings on a WoW Forever install by editing its SavedVariables file with the game closed, and show the change as a tick-box picture. Use for "change my TSM tooltip", "set TSM to X", "what is TSM set to", "edit the TSM settings file", or any gold-making task that needs a TSM option, price source, group or operation changed. Not for editing the TSM addon's own code (All Rights Reserved).
---

# TSM settings on WoW: Forever

## The working model: groups first

Load this skill whenever the prompt mentions TSM, TradeSkillMaster, the auction house, posting, sniping, flipping or gold making. Before proposing anything, think in this order:

1. **Groups are the unit of work.** TSM does nothing to an item that is in no group. Every request ("sell my leather", "stop undercutting on greens", "what should I buy") is first a question about which group the items are in, or which group has to exist.
2. **Rules are operations, and operations attach to groups.** A price rule is never set per item or globally: it is an operation (Auctioning, Shopping, Sniper, Crafting, Vendoring, Mailing, Warehousing) applied to a group and inherited by its subgroups unless one overrides it.
3. **One pricing rule, one group.** Items that should be priced, bought or restocked the same way share a group; items that need a different rule get a subgroup. The tree is designed from the rules, not from the bag layout.
4. **Claude owns the tree.** Claude creates and manages the groups, operations and settings, so the player does not maintain them by hand. New items the player starts trading get placed in a group in the same change that touches them.
5. **Global settings and tooltips come last.** They only change what is displayed or the fallback values; they are not where a strategy lives.

**Start from what is there.** Run `python -I tools/tsm/tsmdb.py profile --text` first: characters per realm and faction, class, gold, professions, existing groups and operations, custom sources, sales history and whether the desktop app's price data is present. A proposal comes after that inventory, never before.

References, read the one the task needs: `docs/tsm/README.md` (index and official URLs), `docs/tsm/strategies.md` (group trees and formulas people use), `docs/tsm/operations.md`, `docs/tsm/custom-strings.md`, `docs/tsm/savedvariables-format.md`, `docs/tsm/appdata-format.md`. Tools: `tools/tsm/tsmdb.py` (read and rewrite the file: `profile`, `groups`, `operations`, `inventory`, `accounting`, `apply`, `validate`), `tools/tsm/appdata.py` (prices and item names) and `tools/tsm/skillup.py` (cheapest way to level a profession from skill A to B: `python -I tools/tsm/skillup.py leatherworking 100 150`, details in `docs/tsm/skillup.md`). The tools are Claude's to run: run them and show the result, never hand the player a command to try.

## The player's own setup

What this player agreed to lives outside the repo, in two gitignored files:

| File | Holds |
|---|---|
| `tsm/my-setup.md` | The player's answers and choices (written by the `/setup` skill): characters and their roles, which character posts, professions being leveled, what to keep, risk appetite, agreed thresholds. Read it before proposing anything; update it in the same change when a choice changes |
| `tsm/plan.json` | The whole TSM setup as one plan, applied with `tsmdb.py apply`. It is the source of truth: change it, dry-run, apply with the game closed |

Neither file is committed: both name characters and realms. With no `tsm/plan.json` yet, start from `tsm/examples/starter-plan.json` (a small tree: Crafting mats, Gear BoE, Consumables, Vendor trash, Keep (never post), with conservative Auctioning and Vendoring operations and no items), copy it to `tsm/plan.json` and fill in the items.

When the player corrects something about TSM (a concept, a step, a preference), write it as a rule into `tsm/my-setup.md` (their preference) or into this skill or `docs/tsm/` (a fact that holds for every player) in the same session. A correction that stays only in the conversation is lost.

## How to work with the player

- **Edit the file for them.** Most players would rather restart the game than click through menus. Ask them to close the game, edit, then ask them to start it.
- **Plan the whole change and apply it once.** Do not hand over settings a few at a time.
- **Show, don't describe.** Any proposal is a tick-box picture (`mcp__visualize__show_widget`, one row per checkbox with its exact in-game label, the rows that change highlighted) or a short table (the fallback: a markdown table with a `[x]` / `[ ]` column). No paragraphs of explanation.
- **Say the scope.** TSM tooltip settings are global: every item, every character. Say so in one line.
- **Change what the words name, nothing more.** "Post everything, no limits" is the post cap, not the floors, the gates, `maxExpires` or vendoring. When the scope of a short request is unclear, ask before editing.
- **Look facts up before asking.** Game facts (deposit, cut, durations) are looked up for Forever specifically; ask the player only what cannot be found.

## Where things are

| What | Where |
|---|---|
| Settings, groups, operations, accounting | `<game>\_forever_\WTF\Account\*\SavedVariables\TradeSkillMaster.lua` (`TradeSkillMasterDB`) |
| Price data synced by the TSM desktop app | `<game>\_forever_\Interface\AddOns\TradeSkillMaster_AppHelper\AppData.lua` (read only) |
| Setting names, defaults, schema versions | `Interface\AddOns\TradeSkillMaster\LibTSMSystem\Source\AddonSettings\Schema.lua` |
| Checkbox label to setting key | `Interface\AddOns\TradeSkillMaster\App\MainUI\Settings\Tooltip.lua` (the `*_SETTINGS_INFO` tables) |
| Which tooltip line a key draws | `Interface\AddOns\TradeSkillMaster\LibTSMApp\Source\Tooltip\Internal\*.lua` |
| Backups `tsmdb.py` makes before a write | `%LOCALAPPDATA%\ClaudeForever\tsm-backups\` (`TSM_BACKUP_DIR` overrides) |

`<game>` is `C:\Program Files (x86)\World of Warcraft` unless `WOWF_GAME_DIR` says otherwise. The three `Interface\AddOns\...` rows without a prefix are under `<game>\_forever_\` too. With several `Account\*` folders, `tsmdb.py` asks for `--file`: take the one whose `TradeSkillMaster.lua` was written last and say which you took.

## The file format

`TradeSkillMasterDB` is one flat table. Each key is `scope@scopeKey@namespace@setting`:

| Prefix | Scope | Example |
|---|---|---|
| `g@ @` | global (all characters) | `["g@ @tooltipOptions@vendorSellTooltip"] = true,` |
| `p@Default@` | profile (groups, operations) | `["p@Default@userData@groups"]` |
| `r@<realm>@` | realm | `["r@<realm>@coreOptions@auctionDBAltRealm"]` |
| `f@<faction> - <realm>@` | faction and realm | crafts, mats, mail |
| `c@` / `s@` | character / sync | UI state, bag counts, professions, money |

- A setting missing from the file takes its default from `Schema.lua`.
- `_hash` is the hash of the **schema**, not of the contents: changing a value does not invalidate the file. Never touch any `_` key (`_hash`, `_version`, `_lastModifiedVersion`, `_scopeKeys`, `_syncOwner`, ...); `tsmdb.py` refuses to.
- Per-module tooltip lines live inside one table, `["g@ @tooltipOptions@moduleTooltips"]`, keyed by module (`AuctionDB`, `Accounting`, `Crafting`, ...). A two-state checkbox pair ("Market value" / "Market value and trend") is one key with the values `"noTrend"`, `"withTrend"`, `"none"`.
- Full format and TSM's load-time checks: `docs/tsm/savedvariables-format.md`.

## Changing settings

1. Read the current value (`tsmdb.py get <key>`) and the default and allowed values (`Schema.lua`, then the tooltip source for `moduleTooltips` keys). A key you cannot find in the schema is a broken link: say which file you looked in, do not guess.
2. Show the picture of what changes.
3. Put the change in `tsm/plan.json` (settings, groups, operations, items, group operations) and dry-run it: `python -I tools/tsm/tsmdb.py apply tsm/plan.json --dry-run`. Read every change line; a plan that adds validation errors is refused.
4. **The game must be closed.** The client rewrites SavedVariables on `/reload`, logout and exit, so an edit made while it runs is lost; `tsmdb.py` checks for `Wow.exe` and refuses to write under `WTF`. Ask the player to close the game; never work around the refusal.
5. Apply: `python -I tools/tsm/tsmdb.py apply tsm/plan.json`. It backs the file up first, writes a temp file, parses it back and only then replaces the original. A single value can go through `tsmdb.py set <key> <json>` the same way.
6. **Validate after.** Run `validate` (0 errors) and `apply --dry-run` again (0 changes).
7. Ask the player to start the game and say whether TSM printed an error; nothing else. Launching loads the edited file, so no `/reload` is asked for. SavedVariables are written only on reload, logout or exit: after the player's next exit or logout, run `validate`, `groups` and `apply --dry-run` (0 changes) again. A value that reverted means TSM rejected it (wrong type or not an allowed value): report it with the key. TSM wipes a DB it rejects and re-keys item strings it does not like, which is why this check is not optional.
8. Price strings are evaluated only in a real post, cancel, shopping scan or sell tab. After the player's first scan with a new operation, ask whether an "invalid price" message appeared and whether the sell list looked right before selling.

## Price scopes

The TSM app syncs two scopes, visible as the tags in `AppData.lua` (`tsmdb.py profile` lists them):

| Tooltip lines | Tag | Meaning |
|---|---|---|
| Min Buyout, Market Value, Recent, Historical, "N auctions" | `<Realm>-<Faction>` | The auction house the player posts on |
| Everything starting with "Region" | `Forever-<region>` (`Forever-US`, `Forever-EU`, ...) | Average over every auction house TSM tracks in that region |

Sale data (Region Sale Avg, Sale Rate, Avg Daily Sold) exists only at region scope. Region Market Value Avg is a price from houses the player cannot post on, and can sit far from the local market value. Players often read "region" as "where I can sell": state the mapping once, with the source, before recommending anything on it.

## Rules that hold for every setup

- **Inventory before proposal.** Read the current groups, operations, tooltips and professions (`profile`, `groups`, `operations`) before suggesting changes; a handful of tooltip tweaks is not a TSM setup.
- **Check professions before any selling, vendoring or mailing rule.** Read what each character still levels (`profile`, the crafts table, `skillup.py`) and ask about gathering professions TSM does not record, so leveling materials are held, not sold.
- **Materials stay with the crafter.** Materials a character needs for its own professions stay on that character; a bank or posting alt only gets what the crafter does not need. Hold a crafter's stock with a Mailing `keepQty` on the crafter (TSM counts the sender's bags and mails only the surplus), never with an Auctioning `keepQuantity` on the alt. Size it from `skillup.py`'s whole-path materials and recheck it when a profession's target changes.
- **Sales volume is part of every post-or-vendor decision.** Test sale rate and sold per day together with the gain over vendoring, never price alone (`docs/tsm/strategies.md` 5b).
- **A keep list is a family, not a snapshot.** When the player keeps a consumable, keep every rank and variant of it (matched by name and class in the client's item table), or the next rank gets mailed or posted the day they outgrow the first.
- **Sweep consumables for what the class uses** before mailing or posting a consumables group, and move those families into `Keep (never post)` (a group with no operation in any module).
- **"My last N purchases"** means the newest rows of `csvBuys` after the client's latest write. While the game runs the file is stale; prepare from it, then re-read after the player closes the game and before applying.
- **Make a stop readable.** When a rule stops an action (post cap 0 shows as "Posting disabled."), make the reason visible where the player looks (a custom-source tooltip line, the sell tab) and say what TSM's stock text means.
- **A Mailing operation without a target is skipped by TSM without a message.** Every new `Mail-*` operation needs its target set in the same change. Targets are character names: keep them in `tsm/plan.json`, never in a committed file.

## Limits

- Nothing sends input to the game. Posting, buying, cancelling, mailing and vendoring stay the player's clicks; Claude changes what TSM shows and how it prices.
- TSM is All Rights Reserved: read its source to learn key names and cite `file:line`, never copy it into a repo and never edit it in place.
- The SavedVariables file holds character, realm and guild names: nothing from it goes into a committed file. `tsmdb.py profile` output is for the local session only.
