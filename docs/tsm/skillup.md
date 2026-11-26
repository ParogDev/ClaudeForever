# Cheapest profession leveling: `tools/tsm/skillup.py`

TSM shows what each recipe costs to craft. It does not know skill-up chances, so it cannot say which recipe to craft at each
skill point. This tool does: for every skill level from A to B it picks the recipe with the lowest expected cost per skill
point, at your own auction house prices.

    python -I tools/tsm/skillup.py leatherworking 100 150
    python -I tools/tsm/skillup.py cooking                 # from TSM's recorded skill to 300 (or TSM's cap if higher)
    python -I tools/tsm/skillup.py cooking --luck 95       # crafts and materials for a p95 run (default p90)
    python -I tools/tsm/skillup.py "first aid" 150 225 --json
    python -I tools/tsm/skillup.py leatherworking 100 150 --vendor-products   # no auction sales counted
    python -I tools/tsm/skillup.py leatherworking --chance flat     # the addon's colour-band guess instead of the formula
    python -I tools/tsm/skillup.py leatherworking --no-stock        # ignore bags and bank
    python -I tools/tsm/skillup.py leatherworking --level 30        # a trainer rank needing a higher level stops the plan

Output: one row per stretch of skill, with the recipe, its yellow/green/grey thresholds, crafts (p90), materials to buy
and, after `| stock`, those taken from bags and bank, what the products return (sold or vendored), net cost and where the
recipe comes from. A `*` marks a row whose recipe the other chance model would change. Then the total, the trainer
ranks to visit, the whole-path materials (need, stock, buy, reserve) and the spares no row uses.

## Data and where it comes from

| What | Source | Notes |
|---|---|---|
| Recipes, reagents, product and count | wago.tools DB2 export of the Forever client (`wowf`): SkillLineAbility, SpellReagents, SpellEffect (effect 24), SpellName | Downloaded once into `%LOCALAPPDATA%\ClaudeForever\tsm-cache\wago\<build>\` (`TSM_CACHE_DIR` or `--cache-dir` overrides), next to appdata.py's tables. Later runs are offline; `--offline` never downloads, `--build` picks a build |
| Yellow and grey thresholds | SkillLineAbility `TrivialSkillLineRankLow` (yellow) and `TrivialSkillLineRankHigh` (grey); green is halfway | Real data, filled for 591 of 592 Leatherworking recipes in build 1.60.1.70888. Forever retuned them: Deviate Scale Cloak is 95/125 here, 120/150 in Classic Era 1.15.9 |
| Skill needed to learn | The recipe item's `RequiredSkillRank` (ItemSparse), joined through ItemXItemEffect and ItemEffect (trigger 6, learn) | `MinSkillLineRank` is 1 for every recipe in the export, so it is ignored. Trainer recipes have no learn rank in client data |
| Recipes known, current skill and cap | TSM SavedVariables, read only: `f@<faction - realm>@internalData@crafts` (spell ids per player) and `s@...@internalData@playerProfessions` | TSM records a profession's recipes only after its window was opened with TSM loaded |
| Stock | TSM SavedVariables: `s@<char>@internalData@bagQuantity` and `bankQuantity` of the planned character | Mail and auctions are not counted, as in the addon. `--no-stock` ignores it |
| Trainer ranks, recipes seen at a trainer (optional) | SkillupHelper SavedVariables (`SkillupHelperDB.ranks`, `trainerSeen`), read only; `SKILLUP_SAVED_VARS` or `--addon-saved-vars` overrides the newest `WTF\Account\*\SavedVariables\SkillupHelper.lua` | Written by the addon at a profession trainer. Missing file: a note, no ranks, no recipe unchecked |
| Material prices | AppData.lua: `DBMarket`, then `DBMinBuyout`, then the region market value | Vendor reagents (thread, dye, salt, spices, water, vials, and any TSM group named `Vendor-bought`) at ItemSparse `BuyPrice` per item |
| Product value | The post-or-vendor test of `strategies.md` 5b: `saleprice`, `netgain`, post at 5s / 50s a stack | Sold only up to `--sell-days` (default 2) days of the region's sales; the rest is vendored |

## How a recipe is chosen

- Chance per craft: 1 below yellow, 0 at grey, `(grey - skill) / (grey - yellow)` in between.
- Expected crafts for a point: `1 / (chance * NumSkillUps)`.
- Cost per point: net cost per craft (materials minus what the product returns) times expected crafts.
- Crafts to buy for a row: `ceil(mean + z*sd)` of the crafts the row takes (`craft_spread`, a sum of geometric draws,
  as the addon's `P.craftSpread`), z for p90 by default (`--luck 50|75|80|90|95|99`). The crafts column, materials and
  the shopping list use it; the expected crafts and the costs stay at the mean.
- A recipe that pays for itself counts as free. Among free recipes the fewest crafts win, then the larger profit. Dividing a
  profit by a small chance would otherwise favour crafting dozens of low-chance items for one point.
- Intermediates (Cured Light Hide, Heavy Leather) are crafted only when that saves at least 20% over buying them; the
  row then says "(craft N ...)" after the materials. Crafting 410 Light Leather from scraps to save a few copper is not
  worth the clicks.
- Under the plan, "material, whole path" lists everything the path buys next to an optional TSM leveling reserve: items
  in a group whose path ends in ``Leveling reserve`Keep N on main`` (or the older ``Hold N``) are read as a reserve of N,
  and reserve items the path does not use are listed too. With no such groups the reserve column shows `-`; the need,
  stock and buy columns do not depend on it.
- Recipe items from the auction house are bought when the total, including the recipe price, drops.
- The market absorbs only so many of one product, so the plan is repriced with each recipe's planned craft count until the
  choice settles.

## Assumptions (not confirmed for Forever)

| Assumption | Effect when wrong |
|---|---|
| Skill-up chance `(grey - skill) / (grey - yellow)`, the formula players worked out from the vanilla client | Crafts per point in yellow and green are off; orange and grey are not affected |
| Trainer recipes are learnable from their yellow threshold | Orange crafts of trainer recipes are left out, so the plan can be a little dearer than needed |
| Trainer fees and recipe items bought from a vendor are not counted | Totals are low by those fees; a vendor-sold recipe item may be cheaper than the AH price shown |
| A profession TSM has not recorded: trainer recipes up to the current skill are known ("probably known"), recipe items are not | A recipe item you already own shows as a purchase |
| Vendor reagent `BuyPrice` is per item | A reagent sold in lots costs less than shown |
| Two days of region sales can be sold | Profitable crafts look better than they are when your share of the region is small |

## Planner rules

The rules the SkillupHelper addon's planner follows (`Planner.lua`, "Planner rules"), and why:

1. **p90, not the mean.** Every buy step's crafts and buy counts are `ceil(mean + z*sd)` of the crafts to its target
   (`P.craftSpread`, a sum of geometric draws), z for p90 by default (`SkillupHelperDB.luck`).
2. **Earmarks are hard constraints.** A material any later step uses is never spent by a step's stock alternative,
   a from-stock "ok" or "alternative" verdict, or a replan. Only true spares (bags minus every step's use) are offered.
3. **A bought step is committed.** A saved AH trip (`SkillupHelperDB.trips[prof].commit`) forces its steps' levels to
   their recipe until each target is reached or the recipe greys; replans never shrink or switch them.
4. **Caps from the client and the trainer.** The live cap is `C_TradeSkillUI.GetProfessionInfoBySkillLineID`'s
   `maxSkillLevel`. Forever's client data has no rank table (no 75/150/225/300, no level or cost per rank), so the
   addon reads rank services at a profession trainer (`GetTrainerService*`, `GetTrainerTradeskillRankValues`) into
   `SkillupHelperDB.ranks`; unread fields are "unknown". A `trainRank` step sits between the unlock skill and the
   cap, batched with a planned `train` visit when one falls there, and never splits a craft run (`step.rankUp`).
   A level-blocked rank is a hard stop (`plan.capBlock`). A rank's cap is known only when the trainer's text names
   it; a rank read without one keeps its cap "unknown" until a trainer's text gives it. `skillup.py` plans to max(300, TSM's
   recorded cap) by default, so the addon can plan past the live cap.
5. **No one-point islands.** One point of recipe B between two runs of A becomes A unless B saves >= 10%.
6. **Shopping by place.** `plan.shopping`: one trainer, one vendor, one AH block per stretch, in travel order. The
   addon then splits and orders the blocks by city (`View.shoppingBlocks`, the town from Guide.lua's `place`):
   nearest city first, trainer, vendor, AH inside it, rows of no known town last.
7. **Where a recipe is taught.** `src = "special"` (dungeon or special NPC; curated `SPECIAL_TEACHERS` in
   `skillup.py`) is never a `train` step and is excluded by default. `SPECIAL_TEACHERS` is hand-curated: add a
   recipe there when one turns up that a special NPC teaches, or it is planned as a trainer visit. A `trainer` recipe not in
   `SkillupHelperDB.trainerSeen` (read at TRAINER_SHOW) is "not checked" and costs 10% more per point.
8. **Exclusions.** `SkillupHelperDB.exclude` (`dungeon`, `ahPatterns`, `special`, `notNow[spell]`) filters options;
   `step.others` lists up to three alternatives with their extra cost.

Rejected and removed: a "trip cost" that let a stock route win over an AH trip, and swapping a stock step in front of
a buy step. Fix the logic itself instead of patching the cost of a trip.

### The same rules in `skillup.py`

`skillup.py` applies the rules that shape a plan, with the addon's constants:

| Rule | In `skillup.py` |
|---|---|
| 1, p90 | `crafts`, the materials and the shopping list per row are `luck_crafts(craft_spread(...))` (`--luck`); costs stay at the mean |
| 2, earmarks | With stock (default): each row takes the stock it needs in plan order, then buys the rest. Only true spares (stock minus every row's p90 materials) go to the stock pass, which gives a level to a spare-using recipe when that is cheaper at salvage value and the spares cover the level's p90 crafts. Such a row takes only those spares. No stock alternatives are offered, so no earmark can be spent |
| 3, commits | Not ported: `skillup.py` has no AH trip |
| 4, caps | With ranks in the addon's SavedVariables: the plan trains them in order (`train <rank> before <cap>`) and stops at the highest rank read, or at a rank whose level is above `--level` or that a special teacher gives. With none read it plans to max(300, TSM's cap) as before |
| 5, islands | `smooth`, run inside every `plan_levels` |
| 6, 8 | Not ported (shopping by place, the addon's exclusions) |
| 7, teachers | Special-teacher recipes are never planned; a trainer recipe not in `trainerSeen` is "(not checked)" and costs 10% more per point |
| flatChance | `--chance flat` plans with it; rows the other model would change are marked `*` |

`tools/tsm/tests/test_planner_parity.py` reads `Planner.lua` from a SkillupHelper checkout named by `SKILLUP_HELPER_DIR`
(skipped when it is not set):
it compares `LUCK`, `Z_OF`, `TRIP_Z`, `ISLAND`, `INTERLEAVE_SAVING`, `UNCHECKED_PENALTY`, `BIAS`, `EFFORT`, `CRAFT_SAVING`
and `SELL_SHARE` by value, and pins a hash of each ported Lua function (`P.chance`, `P.flatChance`, `P.craftSpread`,
`costPt`, `smooth`). A change on either side fails it until the other follows; after porting a Lua change, pin the new
hash the failure prints.

Differences that stay: the stock pass gives whole levels only (the addon splits a level by fraction), and AH sales are
priced through the replan rounds instead of the addon's running count.

## In the game: SkillupHelper (optional)

The SkillupHelper addon (https://github.com/ParogDev/SkillupHelper) shows a leveling plan beside the profession window,
next to a live list of the recipes the character can craft for skill from bags and bank, and plans with the same rules
in game. `skillup.py` does not need it. When it is installed, `skillup.py` also reads its SavedVariables for the trainer
ranks and the recipes seen at a trainer (rules 4 and 7); without it those parts of the report are a note.
