# TSM AppData.lua: the synced price data

What the TradeSkillMaster desktop app writes into `Interface\AddOns\TradeSkillMaster_AppHelper\AppData.lua`, how
the addon decodes it, and how `tools/tsm/appdata.py` reads the same file offline. Checked against TSM v4.15,
desktop app 1.0.10, Forever build 1.60.1.70888, on 2026-11-10.

Source pointers are `file:line` under `Interface\AddOns\TradeSkillMaster\`. That code is All Rights Reserved:
read it to check a claim here, never copy from it.

## Reading it

```
python -I tools/tsm/appdata.py info
python -I tools/tsm/appdata.py item 14165
python -I tools/tsm/appdata.py item "pagan britches of the owl"
python -I tools/tsm/appdata.py top --by regionSoldPerDay --class Armor --subclass Leather --quality 2 --bind boe --in-realm
python -I tools/tsm/appdata.py export --out prices.json
```

`--json` on any command prints compact JSON. Exit code 2 means a broken link, named on stderr (file missing, tag
missing, item in no data, name source unavailable). The tool only reads the game folder.

## File shape

One line per data set, each a call into the AppHelper addon:

```
select(2, ...).LoadData("<TAG>","<realm-or-region>",[[return {downloadTime=<unix>,fields={"itemString",...},data={{<key>,<v>,...},...}}]]) --<TAG,name,downloadTime[,n]>
```

- `LoadData` forwards to the global `TSM_APPHELPER_LOAD_DATA` (`TradeSkillMaster_AppHelper\TradeSkillMaster_AppHelper.lua:9-12`,
  `LibTSMService\Source\AppHelper\AppHelper.lua:108`). The third argument is a string, not a table: the addon
  keeps it as text and decodes rows lazily.
- The trailing `--<...>` comment repeats tag, name and time. Realm tags carry a fourth number (a three-digit id per
  auction house); nothing in the addon reads it, most likely the app's own id for the auction house.
- The whole file is rewritten on each sync. Lines run to 100 KB; never print one.

### Tags

| Tag | Name (example) | Scope | Fields after `itemString` | Rows (one US sample, 2026-11-10) |
|---|---|---|---|---|
| `AUCTIONDB_NON_COMMODITY_DATA` | `<Realm>-Horde` | realm | `minBuyout`, `numAuctions`, `marketValueRecent` | 4935 |
| `AUCTIONDB_NON_COMMODITY_SCAN_STAT` | `<Realm>-Horde` | realm | `marketValue` | 5619 |
| `AUCTIONDB_NON_COMMODITY_HISTORICAL` | `<Realm>-Horde` | realm | `historical` | 5320 |
| `AUCTIONDB_REGION_STAT` | `Forever-US` | region | `regionMarketValue` | 6202 |
| `AUCTIONDB_REGION_HISTORICAL` | `Forever-US` | region | `regionHistorical` | 6202 |
| `AUCTIONDB_REGION_SALE` | `Forever-US` | region | `regionSale`, `regionSoldPerDay`, `regionSalePercent` | 6202 |
| `AUCTIONDB_COMMODITY_HISTORICAL` | `Forever-US` | commodity | `historical` | 0 |
| `APP_INFO` | `Global` | app | (a Lua table: `version`, `lastSync`, `message`, `news`) | 1 |

The tag sets are in `AppHelper.lua:44-58`. `AUCTIONDB_COMMODITY_DATA` and `AUCTIONDB_COMMODITY_SCAN_STAT` exist in
the addon but were not in the sample file, and the one commodity tag that was is empty: stackables (cloth, leather,
herbs) sit in the realm tags like everything else, which fits an auction house with no region-wide commodity market.
`SHOPPING_SEARCHES` and `GROUP_IMPORTS` are other tags the addon accepts (`AppHelper.lua:159-171`); they were not
in the sample file.

### Which realm and region the addon accepts

- Realm tags must match `<realm name>-<faction>` case-insensitively on anything but Retail (`AppHelper.lua:416-426`),
  for example `<Realm>-Horde`: your own auction house. A second realm's rows are kept only if it is the configured
  alt realm (`AppHelper.lua:146-148`).
- Region and commodity tags must equal `"Forever-"..region` (`AppHelper.lua:188-190`, hardcore: `Forever-HC-`),
  hence `Forever-US`: the average over all US Forever auction houses.
- Commodity rows are loaded into the realm table (`LibTSMService\Source\AuctionDB\AuctionDB.lua:140`), which is why
  `historical` appears in both a realm and a commodity tag.

`appdata.py` reads the only realm and region present, and asks for `--realm` / `--region` when a file holds more.

## Decoding a data set

`AuctionDB.lua:189-211`:

1. Split the string at `,data={`. The part before it plus `}` is loaded as Lua for `downloadTime` and `fields`;
   `fields[1]` must be `itemString`.
2. Rows are matched with one pattern, `{"?<key>"?,<rest>}` (`AuctionDB.lua:203`). A key that is a number becomes
   `i:<id>` (`:204-206`); a quoted key is already an item string.
3. `<rest>` stays a string until the item is first asked for, then is split on `,` and each value read as
   **base 32, digits `0-9A-V`, most significant first** (`AuctionDB.lua:236-260`). Values longer than 6 digits
   are read in two halves because Lua's `tonumber(v, 32)` is 32-bit; the number is the plain base-32 value
   (`int(v, 32)` in Python).
4. **A stored 0 means "no value"**: the lookup returns nil for it (`AuctionDB.lua:231-232`). Region sale rows for
   items with no recorded sales are `{id,0,0,0}` (1682 of 6202 rows here have no `regionSale`).

A duplicate key inside one field set is an error in the addon (`AuctionDB.lua:170-172`); `appdata.py` raises too.

### Units and scaling

| Field | Price source | Unit | Stored |
|---|---|---|---|
| `minBuyout` | `DBMinBuyout` | copper per item | as is |
| `marketValueRecent` | `DBRecent` | copper | as is |
| `marketValue` | `DBMarket` | copper | as is |
| `historical` | `DBHistorical` | copper | as is |
| `numAuctions` | `DBNumAuctions` | count (the tooltip's "N auctions") | as is |
| `regionMarketValue` | `DBRegionMarketAvg` | copper | as is |
| `regionHistorical` | `DBRegionHistorical` | copper | as is |
| `regionSale` | `DBRegionSaleAvg` | copper | as is |
| `regionSalePercent` | `DBRegionSaleRate` | fraction 0..1 | **x 1000** |
| `regionSoldPerDay` | `DBRegionSoldPerDay` | items per day | **x 1000** |

The price sources are registered in `LibTSMApp\Source\Config\AuctionDBConfig.lua:38-54`. The two scaled fields go
through `RegisterNumberSource`, which divides the stored integer by 1000 (`AuctionDBConfig.lua:30-37`). The tooltip
multiplies the source by 1000 again and prints `value / 1000` with three decimals
(`LibTSMApp\Source\Tooltip\Internal\AuctionDB.lua:132`, `:137`, `:171`), so stored 174 shows as `0.174`.
`appdata.py` returns both unscaled, and names the rate `regionSaleRate` (`regionSalePercent` is accepted as an
alias; it is not a percent).

A sale rate of exactly 1.000 next to a low sold-per-day is thin data, not a sure sale: 171 items sit at 1.000.

### Item keys and the variant fallback

Nearly every key is a bare item id (6198 of 6202 region keys). The four others are level strings,
`"i:285282::i1"` and similar. A lookup (`AuctionDB.lua:213-233`):

1. converts the item string to a level string (`LibTSMTypes\Source\Item\ItemString.lua:153-172`): unchanged for
   a base string, `<base>::i<level>` when the bonus ids give an item level, else the base;
2. if that key has no row, takes the base item string, `i:<id>` (`ItemString.lua:116`, `:434-436`);
3. returns nil when neither exists, or when the value is 0.

**Random suffixes are not priced separately.** In Forever "Pagan Britches of the Owl" is the item string
`i:14165::1:12720` (base item 14165, one bonus id, 12720); there is no row for it, so every tooltip line is the
base row `i:14165`. All suffixes of a green share one price and one sale rate, whatever the stats are worth.
`appdata.py` does the same: the exact key first, then the base, and it says `via base key` when it fell back.
It does not compute level strings from bonus ids; with four level keys in the data that has not mattered.

Item ids stop at 999999 (`ItemString.lua:24`); battle pets would be `p:<species>` and do not occur in Forever data.

## Data age and update cadence

- `downloadTime` is when the app fetched that data set. The addon's "x ago" for the realm is the newest
  `downloadTime` over the DATA and SCAN_STAT tags, and for the region over the three region tags; the two
  historical tags do not count (`AuctionDB.lua:26-32`, `:181-184`).
- Observed on 2026-11-10 (UTC): realm DATA and SCAN_STAT at 22:22:39 then 23:22:40, so **hourly**; realm
  HISTORICAL, REGION_STAT and the commodity tag at 08:12:51, REGION_HISTORICAL and REGION_SALE at 08:23:50, so
  **about daily**. One day of observation: treat the cadence as a reading, not a contract.
- `APP_INFO.lastSync` is the app's last write. The addon calls the app "running" when it is under an hour old
  (`AppHelper.lua:343`), the last scan "recent" under 12 hours (`AuctionDB.lua:33`), and the status icon warns at
  12 hours and errors at 7 days (`LibTSMUI\Source\Display\AppStatusIcon.lua:23-25`).
- The addon loads AppData.lua once, at login or `/reload`; data that arrives later is rejected until then
  (`AppHelper.lua:326-328`). The file on disk can be newer than what the game shows.

## Coverage (one US sample, 2026-11-10)

6293 keys in all: 5619 with realm data, 6202 with region data, 5528 with both, 91 realm only, 674 region only,
4935 on the auction house at the last scan. "Not in realm data" means nobody listed the item on that auction
house inside the app's window, not that it cannot be sold.

## Item names and attributes

Price data has ids only. `appdata.py` joins two sources and says which one each item's attributes came from
(`attrSource`):

1. **wago.tools DB2 exports** for the newest `wowf` build (`ItemSparse`, `Item`, `ItemClass`, `ItemSubClass`,
   enUS, from `https://wago.tools/db2/<table>/csv?build=<build>&locale=enUS`), cached under
   `%LOCALAPPDATA%\ClaudeForever\tsm-cache\wago\<build>\` (`TSM_CACHE_DIR` or `--cache-dir` overrides). Gives name, quality, class and subclass, slot, required
   level, item level, bind type (`Bonding`: 0 none, 1 BoP, 2 BoE, 3 on use, 4 quest), stack size, vendor sell
   price. Downloaded once; later runs are offline (`--refresh-names` asks for a newer build, `--offline` never
   downloads).
2. **TSM's own item cache**, the `TSMItemInfoDB` global in `WTF\Account\<account>\SavedVariables\TradeSkillMaster.lua`
   (read only; the game writes it on `/reload` and logout). The export alone is not enough: Forever's
   `ItemSparse` has no row for most random-suffix greens (no "Pagan Britches"), which left 2699 of 6293 priced
   items unnamed. TSM asks the client for every item in the realm data at login (`AuctionDB.lua:146-151`), so
   its cache has them: with both sources 5653 are named, and 74 of the 4935 items on the auction house are not.

`TSMItemInfoDB.data` is `base64( deflate, raw( CBOR ) )`: one flat array, 15 values per item, in the order
`itemString, name, itemLevel, minLevel, maxStack, vendorSell, invSlotId, texture, classId, subClassId, quality,
isBOP, isCraftingReagent, expansionId, craftedQuality`, with -1 for unknown
(`LibTSMTypes\Source\Item\Internal\ItemInfoSerializer.lua:29-30`, `:99-103`, `:121-143`;
`LibTSMUtil\Source\BaseType\Encoder.lua:85-87`, `:145-146`). `versionStr` is `<db version>,<locale>,<build>`
(`LibTSMService\Source\Item\ItemInfo.lua:1102-1103`); the addon wipes the cache when it changes
(`LibTSMTypes\Source\Item\ItemInfoCache.lua:83-101`).

The cache only records "binds on pickup or not". For an item taken from it, `appdata.py` reports `bop`, or
`boe` when it is equippable and uncommon or better, else `none`: an inference, good for greens, wrong for a
bind-on-use item. The cache also holds the variants the client has seen under their own names
(`i:14165::1:12720` = "Pagan Britches of the Owl"), which is what lets a name search find a suffixed name.

Still unnamed after both: items the client has never been asked about, mostly region-only rows. Log in with TSM
enabled and `/reload` to grow the cache.
