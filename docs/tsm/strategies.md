# TSM strategies for a fresh WoW: Forever launch

For designing groups and operations for a small seller: one or two characters, a crafting profession or two, selling BoE
greens and gathered materials. The examples use Leatherworking; swap in your own professions. Mechanics are in
`operations.md` and `custom-strings.md`. Your own choices go in `tsm/my-setup.md` (gitignored, written by the `/setup` skill).

Every recommendation carries a label:

- **[TSM]** documented by TSM (URL given), or read from the installed source ("source").
- **[community: URL]** common community practice, with where it was seen.
- **[inference]** reasoned here from the mechanics; not found stated anywhere. Treat as a starting value to tune.

Honest note on sourcing: searches turned up little written community material on TSM group design or Classic-era strings beyond
the official docs, and nothing reliable on Forever's economy. Most numbers below are therefore [inference]. Every string
uses only sources registered on the Forever client (`custom-strings.md`); test each one with `/tsm price` before relying on it.

## 1. Group design

Operations attach to groups, so the group tree is the design. One rule decides everything else:

> Items that share a pricing rule share a group. Split a subgroup only when one module needs a different operation. [inference,
> follows from one-group-per-item and per-type override in source]

### 1.1 What the mechanics force (source, `operations.md` "Groups")

| Mechanic | Design consequence |
|---|---|
| An item lives in exactly one group | No "sell" group and "buy" group for the same leather. One group carries its Auctioning and its Shopping operation |
| Subgroups inherit each operation type separately; `override` is per type | Put the common operation on the parent; a child overrides Auctioning only and still inherits Mailing, Vendoring, Warehousing |
| Top-level groups never inherit from the Base Group | A new top-level group has no operations until you add them. `#Default` on the Base Group does not leak into your tree |
| Crafting, Shopping, Sniper, Vendoring: 1 operation per group | Different restock or snipe rules need different (sub)groups |
| Auctioning: up to 20, run in order | Rarely needed here (no stack sizes). Use one; a second only for "1 at a high price, rest at market" |
| Mailing up to 50, Warehousing up to 12 | Several mail targets from one group are fine |
| Variant lookup: exact variant, then item-level form, then base item | Group random-suffix greens by base item; pull out a specific suffix only to price it differently |

### 1.2 How people structure the tree

| Choice | Practice | Label |
|---|---|---|
| Top level by strategy or by item class | By what you do with the items (sell farmed goods, craft, flip), then by item class underneath. The strategy decides which modules have operations at all; item class only refines prices | [inference]; TSM docs describe groups as containers for items "you want to handle in specific ways" https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-groups |
| By profession | One subtree per crafting profession under the crafting branch, split by product family when restock numbers differ | [inference] |
| Depth | 2-3 levels. Deeper only when a real override exists at that level | [inference] |
| Naming | Group = what the items are (`Leather`, `Greens 10-19`). Operation = the rule, prefixed by intent (`sell-mats`, `sell-boe`, `craft-lw`, `mail-bank`). Names are how a later session reads the tree without opening it | [inference] |
| Operations are few and shared | 2-4 Auctioning operations cover a whole tree; each is attached to several groups. Per-item differences come from the custom string (vendorsell, dbmarket scale by item), not from more operations | [TSM] defaults are built this way (one string for every item) https://support.tradeskillmaster.com/en_US/addon/how-do-the-default-operations-work ; extent is [inference] |
| Do not edit `#Default` | Leave it as the Base Group's fallback; build named operations. Restoring defaults is documented https://support.tradeskillmaster.com/en_US/addon/how-do-i-restore-the-default-operations | [inference] |
| Shared settings between operations | `relationships` links one setting (for example `minPrice`) of operation B to operation A, so a floor is defined once | [TSM] source |

### 1.3 Same group or subgroup?

| Situation | Decision |
|---|---|
| Same min/normal/max formula, same post cap, same duration | Same group |
| Same formula, different post cap or duration (slow items listed longer) | Subgroup, Auctioning override |
| Same selling rule, but only some are crafted | Subgroup with a Crafting operation (parent has none) |
| Same selling rule, different mail target or bank stock | Subgroup, Mailing / Warehousing override |
| A few items need a hand-set price | Subgroup with its own Auctioning operation using fixed values; keep it small |
| Item is both a product and a material (leather, cured hide) | One group; the crafting stock stays on the character that crafts. Crafter posts too: Auctioning `keepQuantity` or Warehousing. A separate poster (main plus bank alt): Mailing `keepQty` on the crafter, so only the surplus is mailed, never a reserve held on the poster |

### 1.4 Random-suffix greens and variants

| Fact / practice | Label |
|---|---|
| Group the base item; every suffix resolves to it unless that exact variant is grouped | [TSM] source `ItemMap.lua`; docs https://support.tradeskillmaster.com/en_US/addon/how-do-i-add-items-to-groups-while-ignoring-stats-or-item-level |
| The Base Group view has a "show ungrouped items as" choice: specific variant, item level, or base item. Use base item when adding greens | [TSM] https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-groups |
| Stamina suffixes (Eagle, Bear, Monkey) and weapons sell; most other low greens do not cover the deposit | [community: https://eu.forums.blizzard.com/en/wow/t/selling-green-boes-with-tsm-normal-pricing/117522] |
| So: base items in the general greens group; drag a specific good variant into a `Premium` subgroup when you hold one. The exact variant wins the lookup | [inference] |
| Price fallback inside the string: `first(dbmarket, dbmarket(baseitem))` | [inference]; whether AuctionDB rows are keyed per suffix on Forever is unverified |

### 1.5 Keeping groups current

| Practice | Label |
|---|---|
| Ungrouped bag items appear in the Base Group list; sweep them into groups after each play session | [TSM] https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-groups |
| An ungrouped item still gets `#Default` Auctioning from the Base Group, with retail-scaled multipliers. Either group it or do not post from the Base Group | [TSM] source |
| Import strings create an "Imported Group" you then move; 4.15.6 also imports groups sent from the TSM website through the desktop app | [TSM] groups page above; installed `ChangeLog.md` |
| Public group lists exist for retail and Classic; none for Forever was found | https://support.tradeskillmaster.com/en_US/addon/where-can-i-find-group-imports ; absence is a search result, not proof |
| This repo: generate item lists per class from game data and write them with `tools/tsm/tsmdb.py apply`, rather than by hand | [inference] |

### 1.6 Example trees

Notation: `A:` Auctioning, `S:` Shopping, `N:` Sniper, `C:` Crafting, `V:` Vendoring, `M:` Mailing, `W:` Warehousing.
`(inherits)` = no override. Operation recipes are in sections 2-7.

**Tree A: minimal, strategy-first. Recommended start.** [inference]

```
Sell                               (no items; holds shared operations)
├─ Gear                            A: sell-boe        V: vendor-duds     N: snipe-low
│  ├─ Greens                       (inherits)         base items, all suffixes
│  ├─ Premium                      A: sell-boe-high   V: (override, none)
│  │                               exact variants worth listing 48h: stamina suffixes, weapons, twink-bracket items
│  └─ Blues                        A: sell-boe-high   V: (override, none)
└─ Mats                            A: sell-mats       S: buy-mats        N: snipe-low
   ├─ Cloth                        (inherits)
   └─ Leather                      A: sell-mats-keep  (override; same prices, keepQuantity > 0 for crafting)
Craft
└─ Leatherworking                  A: sell-crafted    C: craft-lw        (no Shopping: mats live under Sell/Mats)
   ├─ Armor kits and consumables   (inherits)
   └─ Gear                         C: craft-lw-single (override: maxRestock 1)
```

Five Auctioning operations, one Vendoring, one Shopping, one Sniper, two Crafting.

**Tree B: item-class-first.** Use when prices by level band diverge enough that one string misprices. [inference]

```
Gear
├─ Armor
│  ├─ Cloth / Leather / Mail       A: sell-boe        V: vendor-duds
│  │  ├─ 1-19                      A: sell-boe-short  (override: 12h, post cap 1, maxExpires 2)
│  │  ├─ 20-39                     (inherits)
│  │  └─ 40+                       A: sell-boe-high   (override)
├─ Weapons                         A: sell-boe-high   V: (none)
└─ Twink brackets (req. 19, 29)    A: sell-boe-fixed  hand-set normal price, 48h
Trade Goods
├─ Cloth                           A: sell-mats       S: buy-mats
├─ Leather                         A: sell-mats-keep  S: buy-mats
│  └─ Hides (cure before selling)  A: (override, none)  C: craft-lw
├─ Cooking mats                    A: sell-mats
└─ First Aid                       A: sell-crafted    C: craft-bandage
Leatherworking products            A: sell-crafted    C: craft-lw
```

Costs more upkeep: every new green needs the right band. `iflt(requiredlevel, 20, ...)` inside one string can replace the bands.

**Tree C: main plus bank alt.** Tree A with logistics operations added at the top so children inherit them. [inference]

```
Sell                               M: mail-to-bank (target = bank alt, keepQty 0)   W: bank-all
├─ Gear                            A: sell-boe  V: vendor-duds  (M, W inherit)
│  └─ ...
└─ Mats                            A: sell-mats  S: buy-mats
   └─ Leather                      M: mail-to-bank-keep, mail-mats-to-main   (override, two operations)
                                   mail-to-bank-keep: target = alt, keepQty = crafting stock, ignored on the alt
                                   mail-mats-to-main: target = main, restock on, maxQty = stock level, ignored on the main
Craft
└─ Leatherworking                  C: craft-lw  A: sell-crafted  M: mail-to-bank (products to the alt)
```

The alt posts; the main farms and crafts. `ignorePlayer` per operation is what lets one profile serve both characters [TSM, source
and docs management options].

## 2. Auctioning formulas

Shape used throughout [inference, built on TSM's default shape]: a vendor-based floor inside `max()` so the field stays valid
without AuctionDB data, and house data before region data.

Forever-specific mechanics to respect [TSM, source]: undercut is `0c` or >= 1s; `cancelRepostThreshold` default `1g` is too large
for cheap items; `postCap` counts items.

### 2a. BoE gear

| Field | Greens (`sell-boe`) | Premium / blues (`sell-boe-high`) | Reasoning |
|---|---|---|---|
| `minPrice` | `max(150% vendorsell, 50% first(dbmarket, dbmarket(baseitem), dbregionmarketavg))` | `max(200% vendorsell, 60% first(dbregionsaleavg, dbmarket, dbregionmarketavg))` | Below about 1.5x vendor the deposit and cut make the vendor the better buyer [community: forum thread above, "about double vendor price"]; multiplier [inference] |
| `normalPrice` | `max(300% vendorsell, 120% first(dbregionsaleavg, dbmarket, dbmarket(baseitem), dbregionmarketavg))` | `max(500% vendorsell, 150% first(dbregionsaleavg, dbmarket, dbregionmarketavg))` | Used only when nobody else lists it. Sale average first: it is what buyers paid [inference] |
| `maxPrice` | `max(600% vendorsell, 250% first(dbmarket, dbmarket(baseitem), dbregionmarketavg))` | `max(1000% vendorsell, 400% first(dbmarket, dbregionmarketavg))` | Wide: unique items have noisy comparables [inference] |
| `priceReset` | `none` | `none` | Never chase a seller below your floor |
| `aboveMax` | `normalPrice` | `maxPrice` | A lone overpriced listing should not drag greens up |
| `undercut` | `0c` (if matching works; unverified on Forever) else `1s` | same | [TSM] source constraint |
| `duration` | `2` (24h) | `3` (48h) | Greens have low sell-through; deposits scale with duration [community: https://www.warcrafttavern.com/wow-classic/guides/gold-and-trading-guide/ on fees]; choice [inference] |
| `postCap` | `1` | `1` | One per item [community: forum thread, "1 to 3 listings"] |
| `maxExpires` | `2` | `4` | Then Vendoring takes it (section 5) |
| `cancelRepostThreshold` | `max(10s, 20% dbmarket)` | same | Scale to the item [inference] |

Optional sale-rate gate for greens [inference]: wrap min in `ifgte(first(dbregionsalerate, 0.05), 0.03, <min>)`. Items the region
sells under 3% of the time become invalid and are not posted; `first(..., 0.05)` lets items with no sale data through.

### 2b. Stackable materials (`sell-mats`)

| Field | Value | Reasoning |
|---|---|---|
| `minPrice` | `max(vendorsell / 0.95 + 1c, 60% min(dbmarket, dbregionmarketavg))` | Floor just above vendor after an assumed 5% cut [TSM idiom, https://support.tradeskillmaster.com/en_US/custom-strings/which-functions-can-i-use-and-what-do-they-mean]. The 60% term uses the lower of house and region so a falling market does not strand stock above the floor [inference] |
| `normalPrice` | `max(200% vendorsell, 110% max(dbmarket, dbregionmarketavg))` | Empty market: ask a little over the higher reference [inference] |
| `maxPrice` | `max(400% vendorsell, 200% max(dbmarket, dbregionmarketavg))` | [inference] |
| `priceReset` | `none` | Hold stock when the market is under vendor-plus; early launch dumping goes below vendor value [community: warcrafttavern guide above]. **Alternative for sellers who want stock to move**: a low min (about 20% of the lower reference) with `priceReset` `minPrice`, on the reading that a flood of cheap listings means the market dipped, not that stock should wait. Keep the vendor term in min so nothing posts below vendor value [inference] |
| `aboveMax` | `maxPrice` | |
| `duration` | `1` (12h) or `2` | Mats sell fast or get undercut; short listings cost less deposit and re-price sooner [inference] |
| `postCap` | 1-2 stacks' worth (20-40 items) | Do not show the whole stock; repost often [inference] |
| `keepQuantity` | `0`; on `sell-mats-keep` the leather a crafting session needs | |

Whether Forever lists stackables as retail-style commodities is unverified; the installed code has a commodity buy dialog branch
for Forever (`App\AuctionUI\AuctionCommodityBuyConfirmationDialog.lua`), which suggests it does.

### 2c. Crafted goods (`sell-crafted`)

| Field | Value | Reasoning |
|---|---|---|
| `minPrice` | `max(crafting * 1.10 / 0.95, 120% vendorsell)` | Never below cost plus 10% after the cut. Referencing crafting cost in prices is the documented pattern https://support.tradeskillmaster.com/en_US/addon/how-do-i-reference-my-crafting-cost-in-a-minimum-profit ; numbers [inference] |
| `normalPrice` | `max(crafting * 1.6, first(dbregionsaleavg, dbmarket))` | [inference] |
| `maxPrice` | `max(crafting * 3, 200% first(dbmarket, dbregionmarketavg))` | [inference] |
| `priceReset` | `none`; `aboveMax` `normalPrice` | Or `minPrice`, the "stock should move" alternative in 2b |
| `duration` | `2` | |
| `postCap` | `2` | Matches a small restock |

`crafting` is nil until the recipe has been scanned by opening the profession with TSM loaded; `max()` then falls back to the
vendor term, which is too low. Check `/tsm price [item] crafting` once per product [TSM, source and
https://support.tradeskillmaster.com/en_US/addon/why-am-i-missing-crafting-costs-or-profits-in-my-profession-window].

## 3. Flipping and resets

| Rule | Label |
|---|---|
| Compute profit after deposit and cut before buying; start with single items; spread across items | [community: https://www.warcrafttavern.com/wow-classic/guides/gold-and-trading-guide/] |
| Buy to flip only when sell-through is known: `dbregionsalerate` >= 0.1 and `dbregionsoldperday` not tiny | [inference] |
| Shopping `maxPrice` for flips: `50% min(dbmarket, dbregionmarketavg, dbregionsaleavg)` | [inference]; uses the lowest of three references because listing prices overstate value early |
| Do not reset (buy out a market to relist higher) in the first weeks: supply regrows daily as players level, so the wall is refilled under you | [inference] |
| Expected deposit burned before a sale is about `(1 / dbregionsalerate - 1) x deposit`; subtract it from the margin | [community: r/woweconomy weekly TSM thread, seen as a search excerpt only, exact comment not fetched] |

## 4. Sniper at low gold (`snipe-low`)

| Recommendation | Label |
|---|---|
| Replace the default: its lowest tier (5% of region market below 1000g) is the only tier that ever applies here | [TSM] source |
| `belowPrice`: `max(vendorsell, ifgt(dbmarket, 5g, 0.6, ifgt(dbmarket, 1g, 0.5, ifgt(dbmarket, 20s, 0.4, 0.3))) * min(dbmarket, dbregionmarketavg))` | [inference]; same tier shape as the default, thresholds at vanilla prices. A flat `30% dbmarket` is a community starting point (r/woweconomy weekly TSM thread, search excerpt) |
| `vendorsell` inside `max()` keeps below-vendor listings visible: resale to a vendor is the one flip with no market risk | [TSM] the default string does the same; "early prices fall below vendor value" [community: warcrafttavern guide] |
| Add a sale-rate gate for non-vendor snipes: multiply the percent by `ifgte(first(dbregionsalerate, 0), 0.05, 1, 0)` only if results are too noisy | [inference] |
| Sniper needs you at the auction house clicking; it never buys by itself | [TSM] https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-sniper-operations |

## 5. Disenchant and vendor floors (`vendor-duds`)

| Recommendation | Label |
|---|---|
| Most low greens are worth more vendored or disenchanted than listed | [community: Blizzard forum thread above] |
| Without Enchanting on any of your characters, `destroy` is information only: it tells you when to sell a green to an enchanter's price, not what you can realise | [inference] |
| Vendoring operation on the greens group: `sellAfterExpired` `2`, `vsMarketValue` `first(dbregionsaleavg, dbmarket, dbmarket(baseitem), dbregionmarketavg)`, `vsMaxMarketValue` `0c` | [inference]. With the max at 0c the rule is simply "sell after 2 failed listings"; pairs with Auctioning `maxExpires` 2 |
| Stricter variant: `sellAfterExpired` `0`, `vsMaxMarketValue` `160% vendorsell` sells anything whose market value is under 1.6x vendor straight away | [inference]. Caution [TSM, source]: an item with no price data counts as value 0 and is sold |
| Keep `Premium` and `Blues` out of the Vendoring operation (override with none) | [inference] |
| Selling to the vendor is still your click in the TSM vendor tab | [TSM] https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-vendoring-operations |

### 5b. One post-or-vendor test, used three ways

A rule that decides, per item, whether listing beats the vendor once the cut and the deposits expected to burn are
counted. It is three custom price sources [inference throughout; the sources are TSM's]:

| Source | String | Meaning |
|---|---|---|
| `saleprice` | `min(first(dbmarket, dbmarket(baseitem), dbregionmarketavg), dbregionsaleavg)` | The lower of the house price and the region's average sale price |
| `netgain` | `0.95 * saleprice - first(vendorsell, 0.001) * (1 + 0.3 * (1 / first(dbregionsalerate, 0.25) - 1))` | Copper per item gained over vendoring, after a 5% cut and the 24h deposits expected to burn before a sale |
| `post` | `netgain` when the item passes the table below, else no value | The "post it" signal |

"Per stack" means times `maxstack` (1 for gear). Starting thresholds; tune them to your server's prices:

| | Gain per stack 50s or more | 5s to 50s | Under 5s or negative |
|---|---|---|---|
| Sells often: sale rate 0.25 or more and 1 stack a day or more (region) | post | post | vendor |
| Slow, or no sale data | post | vendor | vendor |

| Where | Setting | Effect |
|---|---|---|
| Tooltip | `g@ @tooltipOptions@customPriceTooltips` = `{post = true}` | A line "Custom Source (post)" with the gain per item. No line means vendor it (or no price data) |
| Every Auctioning operation | `postCap` = `ifgte(first(post, 0.001), 1, <cap>, 0)` | Post cap 0 when the test fails. TSM reports that as "posting disabled", not as an invalid price |
| One Vendoring operation | `vsMarketValue` = `first(post, ifgt(first(saleprice, 0.001), 0.5, 0.001, 1g))`, `vsMaxMarketValue` = `1c`, `sellAfterExpired` 0 | The merchant sell tab lists an item when it has a price and fails the test. No price data at all gives 1g, so it is kept |

Vendoring treats a string TSM cannot parse as 0 and sells, so after any edit of these strings look at the sell tab's list
before pressing sell. `tools/tsm/skillup.py` values leveling products with the same test.

## 6. Crafting restock (`craft-lw`)

| Setting | Value | Reasoning |
|---|---|---|
| `minRestock` | `1` | Default 10 never queues at small scale [TSM default: https://support.tradeskillmaster.com/en_US/addon/how-do-the-default-operations-work] |
| `maxRestock` | `ifgte(first(dbregionsoldperday, 0), 1, 4, 2)`; `1` for gear | Stock follows regional sales volume [inference] |
| `minProfit` | `max(5s, 15% crafting)` | Default 100g never passes here [TSM default]; value [inference] |
| `craftPriceMethod` | `first(dbregionsaleavg, min(dbminbuyout, dbmarket)) * 0.95` | Sale average first; else the lower of live floor and market, after the cut [inference]. Default is `first(dbminbuyout, dbmarket)*0.95` [TSM, source] |
| Material cost | Leave the global default `min(dbmarket, crafting, vendorbuy, convert(dbmarket))` | Farmed leather is valued at what it would sell for, so a craft queues only when it beats selling the leather raw [TSM default; reading is inference] |

Leveling crafts made for skill-ups are not restock items: keep them out of the Crafting group and let `sell-crafted` or the vendor
clear them [inference].

## 7. Mailing and warehousing between main and bank alt

| Recommendation | Label |
|---|---|
| Put `mail-to-bank` (target = alt) on the top `Sell` group so everything inherits it; override only where stock must stay | [inference] on [TSM] inheritance |
| Return flow: a second Mailing operation with `restock` on and `maxQty` = wanted stock sends the main only the shortfall | [TSM] https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-mailing-operations |
| Use `ignorePlayer` so the to-bank operation is ignored on the alt and the to-main one on the main | [TSM] source and docs |
| Warehousing: `keepBagQuantity` for the crafting stock, `restockQuantity` + `restockStackSize` to pull posting stock out of the bank | [TSM] https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-warehousing-operations |
| A bank alt only pays off once mail trips cost more play time than they save; with one character at launch, post from the main first | [inference] |
| Mailing counts what is in the **bags** of the sending character: it mails everything above `keepQty` and nothing at or below it. Bank stock is not counted and never mailed | [TSM] source (`Mailing/Internal/Groups.lua`) |
| Sending mail and moving bank items remain the player's clicks in TSM's Mailing and Banking UI | [TSM] |

## 8. Fresh launch, ahead of the curve

Nothing reliable about Forever's economy was found (one gold-seller blog, no data). This section is general fresh-economy
reasoning, labelled. Once you have a week of your own AuctionDB and Accounting data, trust that over this section.

### Behaviours of a young economy

| Behaviour | Label |
|---|---|
| Price history is days old. `dbhistorical` equals an average of those days; `dbmarket` leans on the last 2-3 | [TSM] algorithm https://support.tradeskillmaster.com/en_US/custom-strings/how-is-auctiondb-market-value-calculated |
| Early listings are heavily undercut, sometimes below vendor value, then the market settles | [community: https://www.warcrafttavern.com/wow-classic/guides/gold-and-trading-guide/] |
| Gold is scarce, so nominal prices are low and buyers price-sensitive | [community: https://www.icy-veins.com/wotlk-classic/wrath-of-the-lich-king-fresh-start-realms-explained, about fresh realms generally] |
| Raw material supply grows as the population levels; low-level mats trend down after the first rush, higher-level ones start high and fall later | [inference] |
| Early demand concentrates on bags, profession-leveling mats, and gear at twink or dungeon brackets | [inference]; widely repeated, no source fetched that states it with data |
| Being ahead of the curve means selling into each level band's demand before most sellers reach it, and not holding stock that is about to be farmed by everyone | [inference] |
| Flips carry deflation risk: stock bought today is worth less next week | [inference] |
| Region sale data comes from few TSM users this early, so `dbregionsaleavg` and sale rates are noisy | [inference] |

### How formulas change

| Change | Label |
|---|---|
| Prefer `dbminbuyout` / `dbmarket` / `dbrecent`; leave `dbhistorical` and `dbregionhistorical` out of every string for the first month | [inference] from the algorithm windows |
| Take the lower of references on the sell side (`min(dbmarket, dbregionmarketavg)`) and when buying | [inference] |
| Floors from `vendorsell`, not from market percentages, for anything farmable | [inference]; vendor-floor shape is [TSM] default |
| Wider safety margins on buys: 50% of the lowest reference instead of the 70-80% used in mature markets | [inference] |
| Short durations (12h mats, 24h greens) and small post caps; repost at each visit so prices track the fall | [inference] |
| Gate slow items with region sale data: `ifgte(first(dbregionsalerate, 0.05), 0.03, ...)`; size restock with `dbregionsoldperday` | [inference]; sources are [TSM] |
| Use `maxExpires` 2 plus Vendoring to stop paying deposits on greens that do not sell | [inference] on [TSM] settings |
| Sell farmed mats now rather than stockpile, unless a later demand event is known | [inference]; opposite advice (hold some items as players level up) also exists [community: Wowhead Classic goldmaking guide, seen as a search excerpt] and applies to items whose buyers have not arrived yet |
| Re-tune weekly for the first month: thresholds in section 4 and multipliers in section 2 assume prices measured in silver | [inference] |
| Revisit `dbhistorical` after about 60 days, when it becomes a real baseline for reset and flip rules | [inference] |
