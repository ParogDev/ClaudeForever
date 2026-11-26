# ClaudeForever

A [Claude Code](https://claude.com/claude-code) workspace for **World of Warcraft: Forever**. Clone it, open it in Claude
Code, type `/setup`, and Claude sets up TradeSkillMaster for you from what TSM already knows about your characters.

I built this for my own play and kept the parts that work for anyone. It does three things:

- **TSM, set up and kept up.** Claude reads your `TradeSkillMaster.lua` (characters, professions, gold, what you sold), asks
  the few questions it can't answer, then writes a group tree and operations for you. Later you just say "stop
  undercutting my greens" or "put my new herbs in a group" and it edits the file.
- **Profession leveling at your prices.** `tools/tsm/skillup.py` works out the cheapest recipe path from skill A to B using
  your TSM market data and the recipes you already know.
- **Addons, auras and macros.** Scaffold a Forever addon with lint, tests and CI; check API calls against Blizzard's Forever UI
  source instead of Classic memory; author ForeverAuras displays as files.

## What you need

- Windows, WoW: Forever installed, [Claude Code](https://claude.com/claude-code).
- Python 3.10 or newer.
- [TradeSkillMaster](https://tradeskillmaster.com/) and, for market prices, the TSM desktop app. Log in once on each character
  with TSM loaded and open each profession window once, so TSM has something to read.
- Only for writing addons: Docker Desktop and git.

## Getting started

```powershell
git clone https://github.com/ParogDev/ClaudeForever.git
```

Open the folder in Claude Code and type `/setup`. It checks your machine, tells you what is missing, then walks through the
TSM setup. When it needs to write TSM's file it asks you to close the game first; WoW overwrites the file on exit, so edits made
while it runs are lost.

If the game is not in `C:\Program Files (x86)\World of Warcraft`, set the `WOWF_GAME_DIR` environment variable to the folder
that holds `_forever_`.

## What it will and won't do

- It edits TSM's saved settings only. It never touches TSM's own code, never posts, buys, mails or vendors for you, and never
  sends input to the game. You do every click and `/reload`.
- Your character names, realms and plans stay on your PC: `tsm/my-setup.md`, `tsm/plan.json` and your `AddOns/` folders are
  gitignored.
- Every write to TSM's file makes a backup first.

## Layout

| Folder | What's in it |
|---|---|
| `.claude/skills/` | `/setup`, `tsm-settings`, `/new-addon`, `/verify`, `/forever-api`, `/release` and friends |
| `tools/tsm/` | `tsmdb.py` (read and rewrite TSM's settings), `appdata.py` (market prices), `skillup.py` (leveling planner) |
| `tools/` | Lua lint and tests in Docker, addon linking, the game-file guard |
| `docs/` | TSM reference (price sources, operations, strategies), Forever API notes, ForeverAuras, macros |
| `templates/addon/` | The new-addon template |

## Related

My addons for Forever, each in its own repo: [SkillupHelper](https://github.com/ParogDev/SkillupHelper),
[SellOrPost](https://github.com/ParogDev/SellOrPost), [FarmRoute](https://github.com/ParogDev/FarmRoute),
[PocketLog](https://github.com/ParogDev/PocketLog), [BaitAndBlade](https://github.com/ParogDev/BaitAndBlade).

## Licence

MIT, see `LICENSE`. TradeSkillMaster is not included and is not affiliated with this project. World of Warcraft is a trademark
of Blizzard Entertainment; this project is not affiliated with or endorsed by Blizzard.
