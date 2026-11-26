# TSM operations and groups on WoW: Forever

Authority: installed TradeSkillMaster v4.15.6. Files: `LibTSMSystem\Source\Operation\*.lua` (settings, defaults, decisions),
`LibTSMApp\Source\Config\GroupOperationConfig.lua` (how each type is loaded on this client),
`LibTSMTypes\Source\{Operation,GroupOperation,Group}\` (inheritance, item lookup), `App\MainUI\Operations\*.lua` (labels).
Setting keys below are the names stored in SavedVariables. "String" = a custom string (see `custom-strings.md`).

## How this client is configured (source)

| Fact | Where | Consequence |
|---|---|---|
| Game version is `FOREVER`, neither Retail nor Vanilla Classic | `LibTSMCore\Source\Core.lua` | Mostly retail code paths |
| Auctioning loads with "default zero undercut" on, stack-size support off | `GroupOperationConfig.lua:76` | Default undercut `0c`; `stackSize`, `matchStackSize`, `stackSizeIsCap` do not exist here; `postCap` counts items, 0-50000 |
| Undercut under 1s is rewritten to `0c` on load and on edit | `AuctioningOperation.lua` (`SanitizeUndercut`, `SanitizeSettings`) | Valid undercuts: `0c` (match the lowest price) or 1s and up |
| Prices are not rounded up to whole silver | `AuctioningOperation.lua` (rounding is Retail-only) | Copper-precise posting |
| Duration labels come from the client's 12/24/48h strings | `LibTSMWoW\Source\API\AuctionHouse.lua` | `duration` 1/2/3 = 12h/24h/48h |

## Settings every operation has (`Operation\Internal\Type.lua`)

| Key | Type | Meaning |
|---|---|---|
| `ignorePlayer` | table `{ ["Name - Realm"] = true }` | Operation is skipped on these characters |
| `ignoreFactionrealm` | table | Operation is skipped on these faction-realms |
| `relationships` | table `{ settingKey = "OtherOperationName" }` | That setting's value is read from the other operation of the same type (chains are followed) |

Every type gets a `#Default` operation created once per profile.

## Auctioning (max 20 per group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/1072146-tsm-addon-auctioning-operations

| Key | Type | Default | Meaning / allowed values |
|---|---|---|---|
| `minPrice` | string (price) | `check(first(crafting,dbmarket,dbregionmarketavg),max(0.25*avg(crafting,dbmarket,dbregionmarketavg),1.5*vendorsell))` | Lowest price to post at when undercutting |
| `normalPrice` | string (price) | same shape with `2*avg(...)` and `12*vendorsell` | Price when there is no competition |
| `maxPrice` | string (price) | same shape with `5*avg(...)` and `30*vendorsell` | Highest price to post at when undercutting |
| `undercut` | string (price) | `0c` on this client | Amount below the lowest competing buyout. `0c` matches it |
| `priceReset` | enum string | `none` | When the lowest auction, less undercut, is below min: `none` = do not post; `minPrice` / `maxPrice` / `normalPrice` = post at that price; `ignore` = disregard auctions below min and undercut the next one |
| `aboveMax` | enum string | `maxPrice` | When the lowest auction, less undercut, is above max: `none` = do not post; `minPrice` / `maxPrice` / `normalPrice` = post at that price |
| `duration` | number | `2` | `1` = 12h, `2` = 24h, `3` = 48h. Legacy values 12/24/48 are converted to 1/2/3 |
| `postCap` | string (count) | `5` | Max items of this item posted by this operation, 0-50000. 0 posts nothing |
| `keepQuantity` | string (count) | `0` | Items held back in bags |
| `maxExpires` | string (count) | `0` | Stop posting once `numexpires` reaches this. 0 = off |
| `bidPercent` | number 0-1 | `1` | Bid = buyout x this, never below min price |
| `ignoreLowDuration` | number | `0` | Ignore competing auctions whose time-left code is at or below this. 0 = off; 1 = short (under 30 min), 2 = medium (to 2h), 3 = long (to 12h) per docs |
| `cancelUndercut` | bool | `true` | Cancel scan cancels undercut auctions |
| `cancelRepost` | bool | `true` | Cancel scan cancels auctions that could be reposted higher |
| `cancelRepostThreshold` | string | `1g` | Only cancel-to-repost when the gain exceeds this. `1g` is retail scale |
| `stackSize`, `matchStackSize`, `stackSizeIsCap` | - | - | Vanilla/BC Classic only. Not registered on Forever |

`minPrice`, `normalPrice`, `maxPrice` must evaluate above 0 and may not reference `auctioningopmin/normal/max`. Count fields may be 0.

Post decision (`MakePostDecision`), in order:

1. Min, max, normal or undercut invalid: item reported invalid, not posted.
2. No competing auction: post at `normalPrice`.
3. Lowest buyout less undercut is below min: follow `priceReset`.
4. You are already the lowest: match your own price.
5. Lowest buyout less undercut is above max: follow `aboveMax`.
6. Otherwise post at lowest buyout less undercut.
7. The buyout is never below `minPrice`.

Multiple Auctioning operations on a group run in list order, each with its own `postCap` and prices (source: the operation
iterator; the per-operation post UI behaviour was not tested here). `auctioningop*` sources read the first only.

## Shopping (max 1 per group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-shopping-operations

| Key | Type | Default | Meaning |
|---|---|---|---|
| `maxPrice` | string (price) | `dbmarket` | Highest per-item price to show / buy |
| `showAboveMaxPrice` | bool | `true` | Also list auctions above max. With `false`, an item whose max is invalid is skipped |
| `restockQuantity` | string (count) | `0` | Buy up to this many owned, 0-50000. 0 = no cap |
| `restockSources` | table | `{ alts=false, auctions=false, bank=false, guild=false }` | What counts as already owned |

## Sniper (max 1 per group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-sniper-operations

| Key | Type | Default | Meaning |
|---|---|---|---|
| `belowPrice` | string (price) | `max(vendorsell, ifgt(DBRegionMarketAvg, 250000g, 0.8, ... ifgt(DBRegionMarketAvg, 1000g, 0.1, 0.05)...) * DBRegionMarketAvg)` | Show auctions at or below this. Eight tiers from 250000g down to 1000g; under 1000g it is 5% of region market, floored at vendor price |

At this client's prices every item falls in the last tier, so the default sniper only finds near-vendor listings.

## Crafting (max 1 per group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/1236068-tsm-addon-crafting-operations

| Key | Type | Default | Meaning |
|---|---|---|---|
| `minRestock` | string (count) | `10` | Queue nothing unless at least this many are needed, 0-50000 |
| `maxRestock` | string (count) | `20` | Target stock. Queued = maxRestock - owned, when that is >= minRestock |
| `minProfit` | string (price) | `100g` | Required profit (craft value - crafting cost). Empty string = no profit check. Invalid for the item = not queued |
| `craftPriceMethod` | string (price) | `""` | Overrides the default craft value method for this operation. May not reference `crafting` |

`minRestock > maxRestock` is an error. Profit already includes the AH cut only because the default craft value method multiplies by 0.95.

## Vendoring (max 1 per group; no `#Default` on the base group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-vendoring-operations

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enableBuy` | bool | `true` | Buy group items from the open vendor |
| `restockQty` | string (count) | `0` | Buy up to this many owned |
| `restockSources` | table | `{ alts=false, ah=false, bank=false, guild=false, alts_ah=false, mail=false }` | What counts as owned when buying |
| `enableSell` | bool | `true` | Sell group items to the vendor |
| `keepQty` | string (count) | `0` | Keep this many |
| `sellAfterExpired` | string (count) | `20` | Sell only once `numexpires` reaches this. 0 = no expiry requirement |
| `sellSoulbound` | bool | `false` | Include soulbound items |
| `vsMarketValue` | string | `dbmarket` | The item's "market value" for the gate below |
| `vsMaxMarketValue` | string | `0c` | Do not sell when market value >= this. 0 = gate off |
| `vsDestroyValue` | string | `dbmarket` | The item's "destroy value" for the gate below (set it to `destroy` to mean that) |
| `vsMaxDestroyValue` | string | `0c` | Do not sell when destroy value >= this. 0 = gate off |

An invalid `vsMarketValue` / `vsDestroyValue` counts as 0, so an item with no price data passes the gates and is sold.

## Mailing (max 50 per group; no `#Default` on the base group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-mailing-operations

| Key | Type | Default | Meaning |
|---|---|---|---|
| `target` | string | `""` | Recipient character (`Name` or `Name-Realm`) |
| `keepQty` | string (count) | `0` | Sender keeps this many |
| `maxQtyEnabled` | bool | `false` | Turns on `maxQty` |
| `maxQty` | string (count) | `10` | Max sent per run, 1-50000 |
| `restock` | bool | `false` | Treat `maxQty` as the target's stock level: send only the shortfall |
| `restockSources` | table | `{ guild=false, bank=false }` | Which of the target's inventories count |

Several operations with different targets split one group's items between characters.

## Warehousing (max 12 per group; no `#Default` on the base group)

Docs: https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-warehousing-operations

| Key | Type | Default | Meaning |
|---|---|---|---|
| `moveQuantity` | string (count) | `0` | Move at most this many per click. 0 = all |
| `stackSize` | string (count) | `0` | Move only in multiples of this, 0-200 |
| `keepBagQuantity` | string (count) | `0` | Leave this many in bags when moving to the bank |
| `keepBankQuantity` | string (count) | `0` | Leave this many in the bank when moving to bags |
| `restockQuantity` | string (count) | `0` | "Restock bags" brings bags up to this many |
| `restockStackSize` | string (count) | `0` | Restock in multiples of this |
| `restockKeepBankQuantity` | string (count) | `0` | Leave this many in the bank when restocking |

## Groups, subgroups, inheritance (source)

| Rule | Detail |
|---|---|
| A group is a path | Parent and child names joined by a separator; the Base Group is the root path. Exact encoding: `savedvariables-format.md` |
| An item is in one group | `profile.userData.items` maps item string to one group path. An item sold and also bought as a mat carries both operation types on its one group |
| Per group, per operation type: a list plus an `override` flag | `profile.userData.groups[path][Type] = { "OpA", "OpB", override = true }` |
| Inheritance | Without `override`, a subgroup's list for that type is a copy of its parent's, re-synced when the parent changes |
| Override | With `override = true` the subgroup's own list is used for that type only; other types still inherit. Its children inherit from it |
| Top-level groups | Always `override` for every type: they never inherit from the Base Group |
| Base Group | Holds `#Default` for Auctioning, Crafting, Shopping, Sniper. Mailing, Vendoring, Warehousing start empty there |
| Max operations per group | Auctioning 20, Mailing 50, Warehousing 12, Crafting / Shopping / Sniper / Vendoring 1 |
| Skipped operations | An operation ignored for this character or faction-realm is filtered out; the next in the list becomes "first" |
| Item variants | Lookup tries the exact variant, then the item-level form, then the base item (`Group\Internal\ItemMap.lua`). Grouping the base item covers every random suffix not grouped on its own |
| Storage | Operations are per profile (`profile.userData.operations`), or one shared set (`sharedOperations`) when the `globalOperations` setting is on. Key encoding: `savedvariables-format.md` |

Docs: groups https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-groups ; variants
https://support.tradeskillmaster.com/en_US/addon/how-do-i-add-items-to-groups-while-ignoring-stats-or-item-level ; default operations
https://support.tradeskillmaster.com/en_US/addon/how-do-the-default-operations-work . The docs pages do not describe inheritance or
override; the table above is from source.

## Where docs and the installed source disagree

| Topic | Docs say | Installed source |
|---|---|---|
| Auctioning "Blacklisted players" | Listed as a Details setting | No such setting or UI in 4.15.6 |
| Auctioning undercut | Retail default 0c, Classic 1c | Forever uses 0c and rewrites anything under 1s to 0c |
| Auctioning stack size | Not documented | Exists only on Vanilla/BC Classic; absent on Forever |
| Crafting restock range | 0-2000 | 0-50000 |
| Vendoring / Warehousing quantities | "does not accept custom strings" | All are custom-string settings |
| Vendoring value gate | Sell when value is at or below max | Sell only when value is strictly below max; an invalid value counts as 0 |
| Mailing and the Base Group | "do not function on the Base Group" | 4.15 "What's New" text says Mailing, Banking UI and Vendoring group actions now support the Base Group |
| Sniper and the Base Group | Runs on it in Classic, not in Retail | Base Group carries `#Default` Sniper; which behaviour Forever gets is untested |
| Price source list | Omits `dbnumauctions`, `dbalt*`, `maxstack` | Registered |
