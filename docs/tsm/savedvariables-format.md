# TradeSkillMaster SavedVariables format

What `WTF\Account\<account>\SavedVariables\TradeSkillMaster.lua` holds, what TSM checks when it loads the file, and what a tool may change. Read from TSM as installed on the Forever client (schema version 152). `tools/tsm/tsmdb.py` implements everything here, and `python -I tools/tsm/tsmdb.py validate` runs the checks.

Source pointers are `file:line` under `_forever_\Interface\AddOns\TradeSkillMaster\`. TSM is All Rights Reserved, so this page states facts and copies no code. Line numbers move when TSM updates. Check them again before trusting a pointer after an addon update.

## The file

The file defines two globals. `TradeSkillMasterDB` is the settings table this page covers. `TSMItemInfoDB` follows it and holds TSM's item info cache as one opaque string plus a version string. `tsmdb.py` keeps every byte outside `TradeSkillMasterDB` as it found it.

The Forever client writes the table like this:

- CRLF line endings, one blank line before the first global, no indentation at any depth.
- One entry per line, each ending in a comma. String keys are `["key"] = value,`.
- Array entries are bare values with no `-- [n]` comment. A table with both parts writes the array part first, then the keyed part.
- Strings escape `\\`, `\"`, `\n` and `\r`. Everything else is raw bytes.
- Numbers print with 16 significant digits (`152.0000610351563`), integers without a decimal point (`10000000000`).

A parse and re-serialize of the live file with `tsmdb.py` gives back the same bytes. The tool also reads the standard WoW layout (tab indentation, `-- [n]` comments) and writes back whichever layout it found.

The client rewrites the whole file on `/reload`, logout and exit, in hash order. Key order in the file means nothing and changes between saves. An edit made while the game runs is lost at the next save, which is why `tsmdb.py` refuses to write under `WTF` when a `Wow.exe` process exists.

## Key scheme

`TradeSkillMasterDB` is one flat table. Every setting is a top-level key of four parts joined by `@`:

```
<scope letter>@<scope key>@<namespace>@<setting>
```

| Scope | Letter | Scope key | Example key |
|---|---|---|---|
| global | `g` | one space | `g@ @userData@ungroupedItemMode` |
| profile | `p` | profile name | `p@Default@userData@groups` |
| realm | `r` | realm | `r@TestRealm@internalData@csvSales` |
| factionrealm | `f` | `Faction - Realm` | `f@Horde - TestRealm@internalData@crafts` |
| char | `c` | `Character - Realm` | `c@Testchar - TestRealm@internalData@auctionPrices` |
| sync | `s` | `Character - Faction - Realm` | `s@Testchar - Horde - TestRealm@internalData@bagQuantity` |

Sources: scope letters, the `@` separator, the ` - ` scope key separator, the one-space global key and the `Default` profile name are in `LibTSMTypes\Source\Settings\Internal\Types.lua:27-52`. `LibTSMTypes\Source\Settings\Internal\DB.lua:57-64` builds the current character's scope keys. Namespaces match `[A-Za-z0-9]+` (`LibTSMTypes\Source\Settings\Internal\Schema.lua:71`). A profile name is any non-empty string without `@` (`DB.lua:426-428`).

The schema lists every setting with its type, default and the version that last changed it: `LibTSMSystem\Source\AddonSettings\Schema.lua:80-365`. Types are boolean, string, number and table. `DB.lua:288-293` asserts the type on every in-game write, which is why `tsmdb.py set` refuses a value whose Lua type differs from the one in the file.

### Metadata keys

Keys that start with `_` are TSM's own (`DB.lua:23-37`). Do not edit them.

| Key | Holds |
|---|---|
| `_version` | schema version that wrote the file (152 here, minimum 102: `Schema.lua:80`) |
| `_hash` | hash of the schema's setting names, types and scalar defaults (`Settings\Internal\Schema.lua:137-145`, `:231-235`) |
| `_scopeKeys` | for `profile`, `realm`, `factionrealm`, `char`, `sync`: the array of scope keys that have settings |
| `_currentProfile` | `Character - Realm` to profile name |
| `_syncAccountKey` | `Faction - Realm` to this account's sync key (`Faction - Realm - <random number>`) |
| `_syncOwner` | `Character - Faction - Realm` to the sync key of the account that owns the character |
| `_lastModifiedVersion` | `<letter>@<namespace>@<setting>` to schema version, rebuilt on every load |

## Checks that wipe the whole DB

`SettingsDB.New` (`DB.lua:73-98`) empties the table and starts from defaults when any of these holds. The structural checks are in `private.ValidateTable` (`DB.lua:733-766`).

1. The table has an array part, meaning `#tbl > 0` (`DB.lua:734`).
2. `_version` is not a number (`:736`).
3. `_version` is below the schema's minimum version, 102 (`:738`).
4. `_hash` is not a number (`:740`).
5. `_lastModifiedVersion` exists and is not a table (`:742`).
6. `_scopeKeys` is not a table (`:744`).
7. `_scopeKeys` has a key that is not a scope name (`:747-750`).
8. A `_scopeKeys.<scope>` list is not a gapless array of strings (`:751-755`). A non-table value there raises a Lua error instead.
9. `_currentProfile` is not a table, or has a non-string key or value (`:757-764`).
10. `_version` equals the schema version and `_hash` differs from the schema's hash (`DB.lua:82-85`). A tool cannot recompute the hash without running TSM, so leave `_hash` and `_version` alone.
11. `_syncOwner` has an entry for the character logging in, and it differs from `_syncAccountKey` for that character's factionrealm (`DB.lua:86-90`). TSM treats this as a SavedVariables file copied from another account, wipes it and reports a user error.

An empty table also takes the reset path as a new install (`DB.lua:75-77`). In dev and test builds, 2 to 11 assert instead of wiping.

## What TSM rewrites on every load

- `_hash` is set to the schema hash (`DB.lua:99`).
- `_syncAccountKey` gains a key for every known factionrealm, and `_syncOwner` gains the current character (`DB.lua:108-116`).
- `_currentProfile` gains the current character with profile `Default` (`DB.lua:119`).
- A scope key seen for the first time (new character, realm, profile) is appended to `_scopeKeys`. Every setting of that scope key is then deleted and set to its default (`DB.lua:121-126`, `:768-787`). Keys written by hand for a scope key that `_scopeKeys` does not list are therefore lost the first time TSM registers it.
- Every schema setting that is `nil` for a known scope key gets its default (`DB.lua:136-144`). A tool never needs to add missing keys, and `tsmdb.py set` only changes keys that exist.
- `_lastModifiedVersion` is emptied and rebuilt (`DB.lua:196-199`).
- `p@<profile>@internalData@createdDefaultOperations` becomes `true` (`LibTSMApp\Source\Config\GroupOperationConfig.lua:72-73`).
- Operations, groups and items are sanitized as described below.

When `_version` differs from the schema version (`DB.lua:149-193`), TSM also deletes keys that do not match the four-part shape, deletes settings the schema no longer has, and resets settings whose schema entry changed since the file's version. When the versions match, TSM leaves unknown keys alone and never reads them.

## Operations

Operations live in `p@<profile>@userData@operations`. When `g@ @coreOptions@globalOperations` is `true` they live in `g@ @userData@sharedOperations` instead and the profile tables are empty (`GroupOperationConfig.lua:67-71`, `:103-121`). `tsmdb.py` follows the switch.

The table is `module -> operation name -> settings`. The modules are Auctioning, Crafting, Mailing, Shopping, Sniper, Vendoring and Warehousing (`GroupOperationConfig.lua:76-82`).

```lua
["p@Default@userData@operations"] = {
["Sniper"] = {
["#Default"] = {
["belowPrice"] = "0.5 * dbmarket",
["ignorePlayer"] = {
},
["ignoreFactionrealm"] = {
},
["relationships"] = {
},
},
},
},
```

Every operation has three common fields (`LibTSMTypes\Source\Operation\Internal\Type.lua:12-16`, `:32-37`):

- `ignorePlayer` is a set of `Character - Faction - Realm` keys with value `true`. The operation is skipped for those characters.
- `ignoreFactionrealm` is the same for `Faction - Realm` keys. Key format: `GroupOperationConfig.lua:53-55`. Lookup: `LibTSMTypes\Source\Operation\Operation.lua:465-468`.
- `relationships` maps a field name to another operation of the same module. That field's value is then copied from the target each time the operation is used (`Operation.lua:331-344`).

Fields per module. Price and quantity fields are custom strings, stored as Lua strings even when they hold a plain number (`"5"`, never `5`).

| Module | Max per group | `#Default` on the base group | Fields | Source under `LibTSMSystem\Source\Operation\` |
|---|---|---|---|---|
| Auctioning | 20 | yes | number: `ignoreLowDuration`, `duration` (1, 2 or 3), `bidPercent`. string: `postCap`, `keepQuantity`, `maxExpires`, `undercut`, `minPrice`, `maxPrice`, `normalPrice`, `cancelRepostThreshold`, `priceReset`, `aboveMax`. boolean: `cancelUndercut`, `cancelRepost` | `AuctioningOperation.lua:213-234` |
| Crafting | 1 | yes | string: `minRestock`, `maxRestock`, `minProfit`, `craftPriceMethod` | `CraftingOperation.lua:43-47` |
| Mailing | 50 | no | boolean: `maxQtyEnabled`, `restock`. string: `maxQty`, `target`, `keepQty`. table: `restockSources` (`guild`, `bank`) | `MailingOperation.lua:74-81` |
| Shopping | 1 | yes | string: `restockQuantity`, `maxPrice`. boolean: `showAboveMaxPrice`. table: `restockSources` (`alts`, `auctions`, `bank`, `guild`) | `ShoppingOperation.lua:43-47` |
| Sniper | 1 | yes | string: `belowPrice` | `SniperOperation.lua:27-28` |
| Vendoring | 1 | no | string: `sellAfterExpired`, `keepQty`, `restockQty`, `vsMarketValue`, `vsMaxMarketValue`, `vsDestroyValue`, `vsMaxDestroyValue`. boolean: `sellSoulbound`, `enableBuy`, `enableSell`. table: `restockSources` (`alts`, `ah`, `bank`, `guild`, `alts_ah`, `mail`) | `VendoringOperation.lua:73-85` |
| Warehousing | 12 | no | string: `moveQuantity`, `keepBagQuantity`, `keepBankQuantity`, `restockQuantity`, `stackSize`, `restockKeepBankQuantity`, `restockStackSize` | `WarehousingOperation.lua:73-81` |

Auctioning has three more fields (`matchStackSize`, `stackSize`, `stackSizeIsCap`) only on Vanilla and BC Classic (`AuctioningOperation.lua:230-234`, flags at `GroupOperationConfig.lua:76`). Forever does not register them, so TSM deletes them here. `priceReset` takes `none`, `ignore`, `minPrice`, `maxPrice` or `normalPrice`. `aboveMax` takes `none`, `minPrice`, `maxPrice` or `normalPrice`. Any other value raises a Lua error at post time (`AuctioningOperation.lua:479-486`, `:507-517`). `tsmdb.py` does not check those two values, nor whether a custom string parses.

`tsmdb.py create_operation` copies the module's `#Default` from the file, empties the three common fields, then applies the given settings with a type check per field. Without a `#Default` in the file it stops and says so.

### What TSM does to operations on load

`private.ValidateOperations` (`Operation.lua:486-497`) runs per module when the module registers (`Operation.lua:124-138`):

- A name that is empty, not a string, or has leading or trailing whitespace: the operation is removed (`Operation\Internal\Util.lua:25-27`).
- A field the module does not register is deleted (`Type.lua:198-200`).
- A field of the wrong type is reset to the default. A number where a string belongs is converted with `tostring` instead (`Type.lua:203-211`).
- A missing field gets its default, and a missing boolean becomes `false` (`Type.lua:217-232`).
- Auctioning rewrites `duration` 12, 24, 48 to 1, 2, 3 and an `undercut` below one silver to `"0c"` (`AuctioningOperation.lua:737-765`).
- A relationship whose target does not exist is removed (`Operation.lua:513-522`), and so is a circular one (`Operation.lua:363-372`).
- A module with no `#Default` gets one only when the module has no table at all or `createdDefaultOperations` is false (`Operation.lua:129-135`). Deleting `#Default` in game is allowed and sticks.

An operation value that is not a table raises a Lua error in the sanitize loop.

## Groups

`p@<profile>@userData@groups` maps a group path to that group's operations. A path is group names joined by a backtick, and the base group is the empty string (`LibTSMTypes\Source\Group\Internal\Path.lua:11-12`). A name is any non-empty string without a backtick (`Path.lua:40-42`). A path is invalid when it holds two backticks in a row (`Path.lua:33-35`). Parent and name come from the last backtick (`Path.lua:160-169`). The UI shows the separator as `->`.

```lua
["p@Default@userData@groups"] = {
[""] = {
["Auctioning"] = {
"#Default",
["override"] = true,
},
["Mailing"] = {
["override"] = true,
},
},
["Leather"] = {
["Auctioning"] = {
"#Default",
},
["Mailing"] = {
},
},
["Leather`Thick"] = {
["Auctioning"] = {
"TestPost",
["override"] = true,
},
["Mailing"] = {
},
},
},
```

The example shows two of the seven modules. Each group has one table per module. Its array part lists operation names in priority order. `override = true` means the group sets its own list. Without it the list is a copy of the parent's list, and TSM overwrites it from the parent on load and whenever the parent changes (`LibTSMTypes\Source\GroupOperation\GroupOperation.lua:575-585`, `:587-599`). The base group always has `override = true`.

A new group gets every module with the parent's list and no override, parents first (`GroupOperation.lua:601-626`). `tsmdb.py create_group` does the same and `set_group_operations` pushes a changed list down to children without an override.

### What TSM does to groups on load

`private.SanitizeGroups` (`GroupOperation.lua:391-498`):

- An operation name that does not exist in that module is removed from the list (`:394-400`).
- The legacy keys `ignoreItemVariations` and `ignoreRandomEnchants` are cleared (`:404-405`).
- A missing module table is added empty. The base group gets `override = true` on every module (`:409-415`).
- A list longer than the module's maximum is cut from the end (`:420-423`).
- `override` becomes `true` or absent. Any other non-array key in a module table is removed, as are non-string or empty names (`:424-439`).
- A group key that is not a module name is removed (`:441-443`). If that key holds a non-empty list, the first loop raises a Lua error before reaching this point, because it looks the name up among the operations of a module that does not exist (`:394-396` into `Operation.lua:307-309`). A non-table value raises as well.
- A group whose path is not a string or is invalid is removed (`:446-449`).
- With no base group, TSM sets override on every top-level group and creates the base group with `#Default` for Auctioning, Crafting, Shopping and Sniper (`:453-472`, exclusions at `MailingOperation.lua:75`, `VendoringOperation.lua:74`, `WarehousingOperation.lua:74`).
- A group whose parent does not exist is removed (`:481-487`). Its items go with it in the item pass.
- Every module table without an override is replaced by the parent's list, top down (`:489-494`).

## Items

`p@<profile>@userData@items` maps an item string to the path of the one group that holds it. The base group holds no items.

```lua
["p@Default@userData@items"] = {
["i:2318"] = "Leather",
["i:15110::1:12718"] = "Leather`Thick",
},
```

Item string forms (`LibTSMTypes\Source\Item\ItemString.lua:255-330`):

| Form | Meaning |
|---|---|
| `i:2318` | base item. Item ids above 999999 are invalid (`ItemString.lua:24`, `:267`) |
| `i:ID:RAND` | random-suffix id in the third field, as old clients link it |
| `i:ID::N:b1:...:bN` | N bonus ids, sorted and filtered by TSM. Modifiers may follow |
| `i:ID::iLVL` | level item string, one item level of an item |
| `p:SPECIES`, `p:SPECIES:LEVEL:QUALITY`, `p:SPECIES:iLEVEL` | battle pets |

On Forever a random-suffix green such as an "of the Owl" item is its base id plus one bonus id. The live accounting data has thirteen strings of the shape `i:15110::1:12718` and none of the `i:ID:RAND` shape. Forever keeps bonus ids and modifiers like retail does (`ItemString.lua:363`).

Lookup order when TSM asks which group an item is in (`LibTSMTypes\Source\Group\Internal\ItemMap.lua:115-135`): the exact item string, then its level item string, then its base item string. So `i:15110` in a group covers every suffix of that item, unless one specific variation is listed in a group of its own. To group all variations, add the base item.

`g@ @userData@ungroupedItemMode` (`specific`, `level` or `base`, default `specific`: `Schema.lua:258`) only controls how the Groups UI lists ungrouped items from bags, and so which string an add from that list creates (`App\MainUI\Groups\BaseGroup.lua:473-477`, `Items.lua:278-282`). It does not change lookup. An item written by a tool behaves the same in every mode.

### What TSM does to items on load

`private.SanitizeItems` (`LibTSMTypes\Source\Group\Group.lua:349-377`):

- An item string TSM cannot parse is removed.
- An item whose group is the base group or does not exist is removed.
- An item string that is valid but not in TSM's canonical form (zero fields, unsorted or unimportant bonus ids) is removed and added again under the canonical string, unless that string is already grouped (`ItemString.lua:345-349`, `:356-432`).

`tsmdb.py` does the cheap part of the clean-up (`item:ID` and bare ids become `i:ID`, zero fields and trailing colons go). It cannot filter bonus ids, since that needs TSM's bonus id tables, so it warns on every item string with bonus ids. For those, copy the string from TSM's own data instead of composing it.

## Inventory and accounting

Read-only data that the tool reports.

Quantities per character are in the sync scope: `s@<Character - Faction - Realm>@internalData@bagQuantity`, `bankQuantity`, `mailQuantity` and `auctionQuantity`, each a table of item string to count (`Schema.lua:351-363`). The same scope has `money` in copper, and `goldLog`. `g@ @internalData@warbankQuantity` and the guild vault tables in `f@...@internalData@guildVaults` exist too, and `tsmdb.py inventory` does not add them in.

Accounting is in the realm scope as CSV strings (`Schema.lua:302-315`). The first line is the field list, rows are split on `\n` and fields on `,` with no quoting (`LibTSMUtil\Source\Format\CSV.lua:24-54`, `:72-83`, `:108-122`). A row with the wrong field count stops TSM's decode.

| Key | Fields | Source under `LibTSMService\Source\Ledger\` |
|---|---|---|
| `csvSales`, `csvBuys` | `itemString,stackSize,quantity,price,otherPlayer,player,time,source` | `Transactions.lua:58` |
| `csvIncome`, `csvExpense` | `type,amount,otherPlayer,player,time` | `Money.lua:18` |
| `csvExpired`, `csvCancelled` | `itemString,stackSize,quantity,player,time` | `Auctions.lua:33` |

`price` is copper per item: TSM's ledger shows `price * quantity` as the row total (`App\MainUI\Ledger\Transactions.lua:297`) and `time` is Unix seconds. `source` is `Auction`, `Vendor` and similar. A string that is empty or holds only the header line means no records. `saveTimeSales`, `saveTimeBuys`, `saveTimeExpires` and `saveTimeCancels` are comma-separated save times that pair with rows by position (`Transactions.lua:762-771`, `Auctions.lua:221-235`).

## What is not in this file

- Auction prices (`dbmarket`, `dbminbuyout`, region values). They come from the TSM desktop app through the `TradeSkillMaster_AppHelper` addon's `AppData.lua`. See the other pages in `docs/tsm/` and `tools/tsm/appdata.py`.
- The item info cache (names, vendor prices, stack sizes). It is the second global of this file, `TSMItemInfoDB`, one opaque encoded string.
- Custom string definitions for built-in price sources. Only user-made sources are here, in `g@ @userData@customPriceSources`.
- Anything from the current session. TSM keeps live state in memory and the client writes it on `/reload`, logout and exit.

## Editing rules

1. Close the game. `tsmdb.py` checks `tasklist` and refuses to write under `WTF` while a WoW client runs.
2. Never touch a `_` key, and never add a key for a scope key that `_scopeKeys` does not list.
3. Keep each value's Lua type. Operation prices and quantities are strings.
4. Put items only in groups that exist. Give groups only operations that exist. Create parents before children.
5. Run `validate` after a change. `apply` refuses to write when the plan adds validation errors.
6. Under `WTF` the tool first copies the old file to `%LOCALAPPDATA%\ClaudeForever\tsm-backups\TradeSkillMaster-<timestamp>.lua` (`TSM_BACKUP_DIR` overrides), writes a temp file, parses it back, and only then replaces the original.

Checked in game: a tool-written file loads, TSM shows the new groups, items and operations, and the structure survives the next `/reload`. The round trip is byte-identical on an unchanged file.
