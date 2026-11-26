# TSM custom strings on WoW: Forever

Authority: the installed addon, TradeSkillMaster v4.15.6 (`<game>\Interface\AddOns\TradeSkillMaster`).
Files read: `LibTSMTypes\Source\CustomString\Internal\{Types,Tokenizer,TokenProcessor,Optimizer,CodeGen,Object,Sources}.lua`,
`LibTSMApp\Source\Config\AuctionDBConfig.lua`, `LibTSMApp\Source\Price\*.lua`, `LibTSMApp\Source\Accounting\Accounting.lua`,
`LibTSMApp\Source\Crafting\Crafting.lua`, `LibTSMApp\Source\Service\Inventory.lua`.
Official docs: https://support.tradeskillmaster.com/en_US/custom-strings (category index).
"Source" below means the installed Lua; "docs" means the knowledge base.

## Test a string in game

| Command | Does |
|---|---|
| `/tsm sources` | Prints every registered source, grouped by module |
| `/tsm price <item link> <custom string>` | Validates and evaluates the string for that item |

The result is rounded to whole copper and a result of 0 prints as "did not give a value". To read a fractional value source,
scale it: `/tsm price [item] dbregionsalerate * 100g` shows a sale rate of 0.25 as 25g. (Inference from `Object.lua` rounding.)

## Syntax (source)

| Element | Rule |
|---|---|
| Case, spacing | Lower-cased and trimmed before parsing; spaces, tabs, newlines and colour codes are ignored |
| Money literal | `12g34s56c`, `5g`, `20s`, `1c`. No decimals inside a money literal (`1.5g` is an error; write `150s` or `1.5 * 1g`) |
| Plain number | A bare number is copper when used as a price (`100` = 1s), or a factor (`0.5 * dbmarket`). Exponent form `1e3` parses |
| Operators | `+ - * / ^ %`, parentheses, unary minus. Precedence: `^`, then `* / %`, then `+ -` |
| Percent | `a % b` compiles to `a / 100 * b`, so `50% dbmarket` = half of dbmarket |
| Identifier | Letters a-z only. Followed by `(` it is a function or a source with an item argument; otherwise a source |
| Item argument | `dbmarket(i:2589)`, `dbmarket(item:2589)`, pets `p:...`, or `dbmarket(baseitem)` = the item with its variant stripped. One argument only |
| Custom source name | Lower-case letters only, not a reserved word (a registered source or function name) |
| Result | Rounded to nearest copper. Negative, infinite or NaN (division by zero) = invalid. 0 = invalid for price fields, allowed for quantity fields |
| Loops | 100 nested evaluations aborts with "Loop detected" in chat and returns invalid |

Docs show item arguments as pasted links, e.g. `dbminbuyout([Item])`
(https://support.tradeskillmaster.com/en_US/custom-strings/which-functions-can-i-use-and-what-do-they-mean). The tokenizer here
accepts `i:ID` / `item:ID` / `baseitem`; the options UI converts links. When writing strings into SavedVariables use `i:ID`.

## Functions (source: `Types.FUNCTION_INFO`, `CodeGen.lua`)

"Invalid" = a source with no value for the item.

| Function | Args | Behaviour | Example |
|---|---|---|---|
| `min(a, ...)` | 1+ | Lowest valid argument; invalid ones are skipped; all invalid = invalid | `min(dbmarket, dbregionmarketavg)` |
| `max(a, ...)` | 1+ | Highest valid argument, same skipping | `max(150% vendorsell, 60% dbmarket)` |
| `avg(a, ...)` | 1+ | Mean of the valid arguments | `avg(dbmarket, dbregionmarketavg)` |
| `first(a, ...)` | 1+ | First valid argument, left to right | `first(dbminbuyout, dbmarket, dbregionmarketavg)` |
| `check(a, b[, c])` | 2-3 | Rewritten to `ifgt(a, 0, b, c)`: b when a > 0, else c | `check(dbmarket - 2 * vendorsell, dbmarket)` |
| `ifgt(a, b, c[, d])` | 3-4 | c when a > b, else d | `ifgt(dbmarket, 1g, 0.6, 0.4) * dbmarket` |
| `ifgte(a, b, c[, d])` | 3-4 | c when a >= b, else d | `ifgte(dbregionsalerate, 0.05, dbmarket)` |
| `iflt(a, b, c[, d])` | 3-4 | c when a < b, else d | `iflt(itemlevel, 20, 2 * vendorsell, dbmarket)` |
| `iflte(a, b, c[, d])` | 3-4 | c when a <= b, else d | `iflte(numexpires, 2, dbmarket, vendorsell)` |
| `ifeq(a, b, c[, d])` | 3-4 | c when a == b, else d | `ifeq(itemquality, 2, 50% dbmarket, dbmarket)` |
| `round(a[, b])` | 1-2 | Nearest multiple of b (default 1c) | `round(dbmarket, 1s)` |
| `roundup(a[, b])` | 1-2 | Up to a multiple of b | `roundup(crafting * 1.2, 5s)` |
| `rounddown(a[, b])` | 1-2 | Down to a multiple of b | `rounddown(dbminbuyout, 1s)` |
| `convert(src[, item])` | 1-2 | Cheapest way to get the item from its conversion sources (vendor trades, transforms, mill, prospect), priced with `src` | `convert(dbmarket)` |

Rules that matter:

- In `if*`/`check`, an invalid a or b makes the whole call invalid. Only the chosen branch is evaluated. With d omitted and the
  test false, the result is invalid (useful as a gate: an invalid Auctioning price stops the post).
- `convert`'s source must be a price-database source (the AuctionDB and external rows below). `crafting`, `vendorbuy`, `matprice`
  and custom sources are rejected ("not a valid argument for convert()"). The second argument must be an item (`i:ID`, `baseitem`).
- Arithmetic with an invalid operand is invalid, and that propagates up to the nearest `first/min/max/avg` argument, which then
  skips it. `first(dbmarket * 2, 5s)` is 5s when dbmarket is missing; `dbmarket * 2 + 5s` alone is invalid.
- Docs agree on all of the above
  (https://support.tradeskillmaster.com/en_US/custom-strings/which-functions-can-i-use-and-what-do-they-mean).

## Price sources registered on Forever

Keys are case-insensitive. Scope: "house" = the auction house the desktop app tags for this character (`<Realm>-<Faction>`);
"region" = across all Forever-US houses (app data region `Forever-US`, source `AppHelper.lua`); "own" = this account's data.

### AuctionDB (needs TSM desktop app data; all nil for an item the app has no row for)

| Key | Scope | Meaning | Nil when |
|---|---|---|---|
| `dbmarket` | house | Market value: outlier-trimmed listing price, weighted over today + 14 days, half-life about 2 days | Item never seen listed on this house |
| `dbminbuyout` | house | Lowest buyout at the last app snapshot (can be 30+ minutes old per docs) | No auctions at the snapshot |
| `dbrecent` | house | Market value of the latest snapshot only, no day averaging | No auctions at the snapshot |
| `dbhistorical` | house | 60-day average of dbmarket | No history; at a launch it averages only the days that exist |
| `dbnumauctions` | house | Number of auctions at the last snapshot (a count, not money) | No data |
| `dbaltmarket`, `dbaltminbuyout`, `dbaltrecent`, `dbalthistorical`, `dbaltnumauctions` | "alt realm" house | Same five for a second house. Registered on Retail and Forever only | No alt house data (which house this is on Forever: open question) |
| `dbregionmarketavg` | region | Average of dbmarket across the region's houses | Item unseen region-wide |
| `dbregionhistorical` | region | 60-day average of dbregionmarketavg | No history |
| `dbregionsaleavg` | region | Average actual sale price, from TSM users' Accounting data | No recorded sales |
| `dbregionsalerate` | region | Fraction of postings that sell (0.4 = 40%). Stored x1000, returned as a decimal | No recorded sales |
| `dbregionsoldperday` | region | Average units sold per house per day, decimal | No recorded sales |

Definitions: https://support.tradeskillmaster.com/en_US/custom-strings/which-price-sources-can-i-use-and-what-do-they-mean ,
https://support.tradeskillmaster.com/en_US/custom-strings/which-value-sources-can-i-use-and-what-do-they-mean ,
algorithm: https://support.tradeskillmaster.com/en_US/custom-strings/how-is-auctiondb-market-value-calculated .
`DBRegionMinBuyoutAvg` is retired per docs and is not registered here.

### Accounting (own; nil until this account has the matching transactions)

| Key | Meaning |
|---|---|
| `avgsell`, `minsell`, `maxsell` | Average / lowest / highest price you sold the item for |
| `avgbuy`, `minbuy`, `maxbuy` | Average / lowest / highest price you bought it for |
| `smartavgbuy` | Average over your last N buys, N = how many you hold now. Nil when you hold none |
| `numexpires` | Expired or cancelled auctions of the item since your last sale (count) |
| `salerate` | Your own sell-through fraction for the item |

### Item (game data)

| Key | Meaning | Nil when |
|---|---|---|
| `vendorsell` | What a vendor pays | Item has no vendor value (0) |
| `vendorbuy` | What a vendor charges | Not known as vendor-sold; docs say it fills in after visiting the vendor |
| `itemquality` | 0 poor, 1 common, 2 uncommon, 3 rare, 4 epic | Item info not cached |
| `itemlevel` | Item level | Item info not cached |
| `requiredlevel` | Required character level | Item info not cached |
| `maxstack` | Max stack size (in source, not in the docs list) | Item info not cached |
| `numinventory` | Total quantity TSM's inventory tracking holds for the item (which locations are counted was not read) | - |

### Crafting

| Key | Meaning | Nil when |
|---|---|---|
| `crafting` | Lowest cost to craft: sum of mat prices | No character on the account has scanned a recipe for it |
| `matprice` | Cost of a material: per-item override, else the default material cost method | Item is not a material of a known recipe |
| `destroy` | Value of disenchant / mill / prospect results, priced with the "destroy value source" setting (default `dbmarket`) | Item cannot be destroyed, or results have no price |

Forever has its own disenchant table (`LibTSMData\Destroy\Disenchant.lua`, `DATA.Forever`); mill, prospect, transform and vendor-trade
data use the Vanilla tables.

### Operations (value of the item's first operation; nil when the item's group has none or the operation's string is invalid)

| Key | Meaning |
|---|---|
| `auctioningopmin`, `auctioningopnormal`, `auctioningopmax` | Min / normal / max price of the first Auctioning operation. Rejected inside Auctioning operation fields |
| `shoppingopmax` | Shopping operation max price |
| `sniperopmax` | Sniper operation below-price |

### External (registered only when that addon is enabled)

`aucappraiser`, `aucminbuyout`, `aucmarket` (Auctioneer); `atrvalue` (Auctionator); `oerealm`, `oeregion` (Oribos Exchange);
`ahdbminbuyout`, `ahdbminbid` (AHDB). None of these addons were confirmed installed. Docs:
https://support.tradeskillmaster.com/en_US/custom-strings/which-external-sources-are-available-to-use

A string that names an unregistered key fails validation ("not a valid source"), which makes the whole operation field invalid.

## Global strings that feed sources (source: `LibTSMSystem\Source\AddonSettings\Schema.lua`)

| Setting | Default | Feeds |
|---|---|---|
| `craftingOptions.defaultMatCostMethod` | `min(dbmarket, crafting, vendorbuy, convert(dbmarket))` | `matprice`, `crafting` |
| `craftingOptions.defaultCraftPriceMethod` | `first(dbminbuyout, dbmarket)*0.95` | Crafted item value and profit. May not reference `crafting` |
| `coreOptions.destroyValueSource` | `dbmarket` | `destroy` |
| `coreOptions.groupPriceSource` | `dbmarket` | Value filter in the group item lists only |
| `shoppingOptions.pctSource` | `dbmarket` | The "% of market" column in Shopping results |

## Idioms

| Goal | String | Why |
|---|---|---|
| Vendor floor | `max(150% vendorsell, <price>)` | `max` skips an invalid `<price>`, so the field stays valid with no AuctionDB row |
| Fallback chain | `first(dbmarket, dbregionmarketavg, dbregionsaleavg)` | House price first, region when the house has no data |
| Conservative value | `min(dbmarket, dbregionmarketavg)` | Whichever is lower; skips a missing one |
| Break-even after the AH cut | `<cost> / 0.95` | Docs idiom; assumes a 5% cut (Forever's cut is unverified) |
| Sale-rate gate | `ifgte(dbregionsalerate, 0.05, <price>)` | Invalid below 5% sell-through, so nothing is posted |
| Tiered percent | `ifgt(dbmarket, 5g, 0.7, ifgt(dbmarket, 1g, 0.6, 0.5)) * dbmarket` | Same shape as the default sniper string, at this client's gold scale |
| Random-suffix fallback | `first(dbmarket, dbmarket(baseitem))` | Variant price, else the base item's |
| Round to tidy prices | `roundup(<price>, 1s)` | |
| Positive-profit test | `check(<value> - <cost>, <value>)` | Invalid when the margin is not positive |

## Pitfalls

| Pitfall | Detail |
|---|---|
| Nil propagation | One missing source in plain arithmetic invalidates the string. Wrap alternatives in `first`/`min`/`max`/`avg` |
| Invalid = no action, mostly | Auctioning reports the item as invalid and skips it. Vendoring is the exception: an invalid value string counts as 0 and passes a "max value" gate (see `operations.md`) |
| Zero | A price field that evaluates to 0 is invalid. `first(dbmarket, 0c)` does not rescue a price field |
| Thin history at launch | `dbhistorical` and `dbregionhistorical` average only the few days that exist, and lag a falling market upward. `dbmarket` itself is a 14-day weighting, so in week one it is mostly the last 2-3 days |
| Listing price is not sale price | `dbmarket` is built from listings. Only `dbregionsaleavg` reflects sales, and only at region scope |
| Stale min buyout | `dbminbuyout` is the app snapshot, not the live house. Post scans read the live house themselves |
| Value sources are fractions | `dbregionsalerate` is 0-1, not a percent. `ifgte(dbregionsalerate, 5, ...)` never passes |
| Retail-scaled defaults | `#Default` sniper tiers start at 1000g and crafting minProfit is 100g: at vanilla prices the first always picks 5% and the second never queues |
| Sub-silver undercut | On this client an Auctioning undercut under 1s is rewritten to `0c` (see `operations.md`) |
| `convert()` argument | Only database sources; `convert(crafting)` and `convert(mycustomsource)` fail validation |
| `vendorbuy` gaps | Missing until TSM has seen the vendor, so `min(..., vendorbuy)` may overprice a vendor mat |
