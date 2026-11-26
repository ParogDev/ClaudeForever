# TradeSkillMaster reference for WoW: Forever

For Claude sessions (and people) that configure TSM on WoW: Forever. Nothing here sends input to the game: TSM posting,
buying, mailing and vendoring stay the player's clicks; the tools only read and write configuration, with the game closed.

Researched 2026-11-10 against TradeSkillMaster v4.15.6 (`<game>\Interface\AddOns\TradeSkillMaster`, All Rights Reserved: summarised,
not copied). Where the knowledge base and the installed Lua disagree, the Lua wins; the list is at the end of `operations.md`.

## Files

| File | Holds |
|---|---|
| `custom-strings.md` | Syntax, every registered price source, every function, idioms, pitfalls |
| `operations.md` | Every setting key, type and default per operation type; group and inheritance rules; docs-vs-source table |
| `strategies.md` | Group design with example trees, formulas per item kind, the post-or-vendor test, fresh-launch adjustments, each labelled by evidence |
| `savedvariables-format.md` | On-disk format of `TradeSkillMasterDB`, TSM's load-time checks, the editing rules |
| `appdata-format.md` | `TradeSkillMaster_AppHelper\AppData.lua` (the desktop app's price data) and `tools/tsm/appdata.py` |
| `skillup.md` | `tools/tsm/skillup.py`: cheapest recipe per skill point at your prices, its data sources and assumptions |

## Question → where to look

| Question | Here | Official page to fetch for more |
|---|---|---|
| Which price sources exist and when are they nil | `custom-strings.md` "Price sources registered on Forever" | https://support.tradeskillmaster.com/en_US/custom-strings/which-price-sources-can-i-use-and-what-do-they-mean |
| What do sale rate / sold per day mean | `custom-strings.md` AuctionDB table | https://support.tradeskillmaster.com/en_US/custom-strings/which-value-sources-can-i-use-and-what-do-they-mean |
| How is `dbmarket` computed | `custom-strings.md` AuctionDB table, "Pitfalls" | https://support.tradeskillmaster.com/en_US/custom-strings/how-is-auctiondb-market-value-calculated |
| What does `check` / `ifgt` / `convert` do with a missing value | `custom-strings.md` "Functions" | https://support.tradeskillmaster.com/en_US/custom-strings/which-functions-can-i-use-and-what-do-they-mean |
| How do I test a string | `custom-strings.md` "Test a string in game" | https://support.tradeskillmaster.com/en_US/addon/what-are-custom-strings |
| What are the keys and defaults of an operation | `operations.md`, section per type | per-type URLs below |
| What do `priceReset`, `aboveMax`, `duration` values mean | `operations.md` "Auctioning" | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/1072146-tsm-addon-auctioning-operations |
| Why does a post scan skip an item | `operations.md` "Post decision"; `custom-strings.md` "Pitfalls" | https://support.tradeskillmaster.com/en_US/addon/why-does-my-post-scan-say-my-itemgroup-is-invalid |
| How do subgroups inherit operations | `operations.md` "Groups, subgroups, inheritance" | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-groups (does not cover inheritance) |
| How should the group tree look | `strategies.md` section 1 | - |
| How are random-suffix greens grouped | `strategies.md` 1.4; `operations.md` "Item variants" | https://support.tradeskillmaster.com/en_US/addon/how-do-i-add-items-to-groups-while-ignoring-stats-or-item-level |
| What min / normal / max for greens, mats, crafts | `strategies.md` section 2 | - |
| What sniper string at vanilla prices | `strategies.md` section 4 | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-sniper-operations |
| When to vendor instead of list | `strategies.md` section 5; `operations.md` "Vendoring" | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-vendoring-operations |
| Crafting restock and profit | `strategies.md` section 6; `operations.md` "Crafting" | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/1236068-tsm-addon-crafting-operations |
| Main and bank alt | `strategies.md` section 7, tree C | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-mailing-operations |
| What changes at a fresh launch | `strategies.md` section 8 | - |
| What is the cheapest way to level a profession | `skillup.md`; run `python -I tools/tsm/skillup.py <profession> <from> <to>` | - |
| Where do settings live on disk | `savedvariables-format.md` | https://support.tradeskillmaster.com/en_US/addon/where-are-my-tsm-settings-stored |
| What does my install hold (characters, professions, groups, sales, price data age) | `python -I tools/tsm/tsmdb.py profile --text` | - |
| What prices does the desktop app give for an item | `appdata-format.md`; `python -I tools/tsm/appdata.py item <id or name>` | - |

## Official knowledge base, by topic

Base: https://support.tradeskillmaster.com (mirror with the same paths: https://tradeskillmaster.helpjuice.com). Category
indexes list every article: `/en_US/addon`, `/en_US/custom-strings`, `/en_US/tsm-addon-documentation`,
`/en_US/tsm-desktop-application`, `/en_US/tsm-website`, `/en_US/tsm-guides`, `/en_US/api-documentation`.

"Era" column: R = written for retail, check against `operations.md` before trusting; C = has Classic notes; - = neutral.

| Topic | URL | Era |
|---|---|---|
| Groups | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-groups | - |
| Item variants in groups | https://support.tradeskillmaster.com/en_US/addon/how-do-i-add-items-to-groups-while-ignoring-stats-or-item-level | R (bonus IDs) |
| Filter items in groups / Base Group | https://support.tradeskillmaster.com/en_US/addon/how-do-i-filter-items-in-my-groups-or-the-base-group | - |
| Item missing from add-to-group | https://support.tradeskillmaster.com/en_US/addon/why-doesnt-an-item-appear-to-be-added-to-a-group | - |
| Operations, managing | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-manging-operations | - (thin) |
| `#Default` operations | https://support.tradeskillmaster.com/en_US/addon/how-do-the-default-operations-work | R (gold scale; Auctioning and Sniper "coming soon") |
| Restore default operations | https://support.tradeskillmaster.com/en_US/addon/how-do-i-restore-the-default-operations | - |
| Auctioning operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/1072146-tsm-addon-auctioning-operations | R, C (undercut; lists a blacklist setting that 4.15.6 lacks) |
| Post scan: invalid group | https://support.tradeskillmaster.com/en_US/addon/why-does-my-post-scan-say-my-itemgroup-is-invalid | - |
| Post scan: not enough in bags | https://support.tradeskillmaster.com/en_US/addon/why-does-my-post-scan-say-not-enough-items-in-bags | - |
| Post scan: posting disabled | https://support.tradeskillmaster.com/en_US/addon/why-does-my-post-scan-say-posting-disabled | - |
| Slow cancel scans | https://support.tradeskillmaster.com/en_US/addon/why-are-my-cancel-scans-very-slow | - |
| Classic scan failing or lagging | https://support.tradeskillmaster.com/en_US/addon/why-is-my-scan-failing-or-lagging-in-classic | C |
| Shopping operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-shopping-operations | - |
| Sniper operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-sniper-operations | R, C (scan method differs) |
| Crafting operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/1236068-tsm-addon-crafting-operations | R (restock range differs from source) |
| Crafting cost in min profit | https://support.tradeskillmaster.com/en_US/addon/how-do-i-reference-my-crafting-cost-in-a-minimum-profit | - |
| Crafted item not restocked | https://support.tradeskillmaster.com/en_US/addon/why-doesnt-my-crafted-item-get-restocked | - |
| Missing crafting cost / profit | https://support.tradeskillmaster.com/en_US/addon/why-am-i-missing-crafting-costs-or-profits-in-my-profession-window | - |
| Vendor mat prices wrong or missing | https://support.tradeskillmaster.com/en_US/addon/why-do-my-vendor-items-have-wrong-or-missing-material-prices | - |
| Destroying window | https://support.tradeskillmaster.com/en_US/addon/how-do-i-get-the-destroy-window-to-show-up | - |
| Destroying gets stuck | https://support.tradeskillmaster.com/en_US/addon/why-does-tsm-destroying-get-stuck-after-the-first-try | - |
| Mailing operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-mailing-operations | - (Base Group note is outdated) |
| Vendoring operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-vendoring-operations | - |
| Warehousing operations | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-warehousing-operations | - |
| Custom strings overview | https://support.tradeskillmaster.com/en_US/addon/what-are-custom-strings | - |
| Price source, value source, function, custom source (concept pages) | https://support.tradeskillmaster.com/en_US/custom-strings/what-is-a-price-source , `/what-is-a-value-source` , `/what-is-a-function` , `/what-is-a-custom-source` (same folder) | - |
| Price sources list | https://support.tradeskillmaster.com/en_US/custom-strings/which-price-sources-can-i-use-and-what-do-they-mean | - |
| Value sources list | https://support.tradeskillmaster.com/en_US/custom-strings/which-value-sources-can-i-use-and-what-do-they-mean | - |
| Functions list | https://support.tradeskillmaster.com/en_US/custom-strings/which-functions-can-i-use-and-what-do-they-mean | R (examples) |
| External sources | https://support.tradeskillmaster.com/en_US/custom-strings/which-external-sources-are-available-to-use | - |
| Market value algorithm | https://support.tradeskillmaster.com/en_US/custom-strings/how-is-auctiondb-market-value-calculated (also `/en_US/tsm-addon-documentation/auctiondb-market-value`) | - |
| Import / export | Groups page above; https://support.tradeskillmaster.com/en_US/addon/where-can-i-find-group-imports | R (public lists) |
| Desktop app setup | https://support.tradeskillmaster.com/en_US/tsm-desktop-application/how-do-i-set-up-the-tsm-desktop-application | - |
| No recent AuctionDB data | https://support.tradeskillmaster.com/en_US/addon/why-does-my-addon-keep-telling-me-no-recent-auctiondb-scan-data-found | - |
| No prices in tooltips | https://support.tradeskillmaster.com/en_US/addon/why-dont-i-see-any-pricing-in-my-item-tooltips | - |
| Settings location, backups | https://support.tradeskillmaster.com/en_US/addon/where-are-my-tsm-settings-stored ; https://support.tradeskillmaster.com/en_US/tsm-desktop-application/how-do-i-restore-a-backup-of-my-addon-settings ; https://support.tradeskillmaster.com/en_US/addon/i-lost-all-of-my-groups-and-operations-what-can-i-do | - |
| Accounting / Ledger | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-ledger ; missing data: https://support.tradeskillmaster.com/en_US/addon/why-am-i-missing-sales-or-purchase-data-on-my-items ; export times: https://support.tradeskillmaster.com/en_US/tsm-desktop-application/how-do-i-read-or-convert-the-time-in-my-accounting-export | - |
| Dashboard | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-dashboard | - |
| General and tooltip settings | https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-general-settings ; https://support.tradeskillmaster.com/en_US/tsm-addon-documentation/tsm-addon-settings-tooltip-settings | - |
| Public web API (prices outside the game) | https://support.tradeskillmaster.com/en_US/api-documentation/tsm-public-web-api | - (Forever coverage unverified) |
| Written and video guides | https://support.tradeskillmaster.com/en_US/tsm-guides/written-guides ; https://support.tradeskillmaster.com/en_US/tsm-guides/video-guides | R mostly |
| Latest addon changes, known issues | https://support.tradeskillmaster.com/en_US/addon/what-are-the-latest-addon-changes ; https://support.tradeskillmaster.com/en_US/known_issues ; installed `ChangeLog.md` | - |
| Blog | https://blog.tradeskillmaster.com | R mostly; no Forever post found |

Not all pages above were fetched; the ones summarised in these files are cited where used. The older support2 / Confluence
knowledge base was not reached.

## Installed source, by question

| Question | File under `<game>\Interface\AddOns\TradeSkillMaster` |
|---|---|
| Which AuctionDB sources are registered | `LibTSMApp\Source\Config\AuctionDBConfig.lua` |
| Other sources | `LibTSMApp\Source\Price\{Item,Operations,External}.lua`, `LibTSMApp\Source\Accounting\Accounting.lua`, `LibTSMApp\Source\Crafting\Crafting.lua`, `LibTSMApp\Source\Service\Inventory.lua` |
| Function list and argument counts | `LibTSMTypes\Source\CustomString\Internal\Types.lua` |
| Function semantics | `LibTSMTypes\Source\CustomString\Internal\CodeGen.lua`, `Optimizer.lua`, `Object.lua` |
| Operation settings and defaults | `LibTSMSystem\Source\Operation\<Type>Operation.lua` |
| How each type is loaded on this client | `LibTSMApp\Source\Config\GroupOperationConfig.lua` |
| Group inheritance | `LibTSMTypes\Source\GroupOperation\GroupOperation.lua` |
| Variant lookup | `LibTSMTypes\Source\Group\Internal\ItemMap.lua` |
| Global setting defaults | `LibTSMSystem\Source\AddonSettings\Schema.lua` |
| Client flags (`IsForever`) | `LibTSMCore\Source\Core.lua` |
