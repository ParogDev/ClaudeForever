
TradeSkillMasterDB = {
["g@ @userData@ungroupedItemMode"] = "specific",
["g@ @coreOptions@globalOperations"] = false,
["g@ @tooltipOptions@vendorSellTooltip"] = true,
["g@ @mailingOptions@resendDelay"] = 1,
["_hash"] = 1234567,
["g@ @mainUIContext@frame"] = {
["centerX"] = 152.0000610351563,
["centerY"] = 0.7111111283302307,
["width"] = 948,
["scale"] = 1,
},
["g@ @userData@sharedOperations"] = {
},
["g@ @userData@customPriceSources"] = {
["testsource"] = "dbmarket * 0.5",
},
["g@ @internalData@lastCharacter"] = "Testchar - TestRealm",
["g@ @craftingUIContext@craftsScrollingTable"] = {
["sortAscending"] = true,
["cols"] = {
{
["id"] = "queued",
["width"] = 30,
},
{
["id"] = "craftName",
["width"] = 196.9,
},
},
},
["g@ @internalData@notes"] = "quote \" backslash \\ newline \n tab	 accent é bar |cff00ff00x|r",
["_lastModifiedVersion"] = {
["g@userData@ungroupedItemMode"] = 106,
["p@userData@groups"] = 102,
},
["_scopeKeys"] = {
["char"] = {
"Testchar - TestRealm",
"Testalt - TestRealm",
},
["sync"] = {
"Testchar - Horde - TestRealm",
"Testalt - Horde - TestRealm",
},
["factionrealm"] = {
"Horde - TestRealm",
},
["profile"] = {
"Default",
},
["realm"] = {
"TestRealm",
},
},
["_version"] = 152,
["_syncAccountKey"] = {
["Horde - TestRealm"] = "Horde - TestRealm - 123456789",
},
["_currentProfile"] = {
["Testchar - TestRealm"] = "Default",
["Testalt - TestRealm"] = "Default",
},
["_syncOwner"] = {
["Testchar - Horde - TestRealm"] = "Horde - TestRealm - 123456789",
["Testalt - Horde - TestRealm"] = "Horde - TestRealm - 123456789",
},
["f@Horde - TestRealm@internalData@mailExcessGoldLimit"] = 10000000000,
["s@Testchar - Horde - TestRealm@internalData@bagQuantity"] = {
["i:2318"] = 40,
["i:2319"] = 3,
},
["s@Testchar - Horde - TestRealm@internalData@bankQuantity"] = {
["i:2318"] = 7,
},
["s@Testchar - Horde - TestRealm@internalData@mailQuantity"] = {
},
["s@Testchar - Horde - TestRealm@internalData@auctionQuantity"] = {
["i:4234"] = 2,
},
["s@Testalt - Horde - TestRealm@internalData@bagQuantity"] = {
["i:2318"] = 5,
},
["s@Testalt - Horde - TestRealm@internalData@bankQuantity"] = {
},
["s@Testalt - Horde - TestRealm@internalData@mailQuantity"] = {
["i:4234"] = 1,
},
["s@Testalt - Horde - TestRealm@internalData@auctionQuantity"] = {
},
["s@Testchar - Horde - TestRealm@internalData@money"] = 123456,
["s@Testchar - Horde - TestRealm@internalData@classKey"] = "ROGUE",
["s@Testalt - Horde - TestRealm@internalData@classKey"] = "WARRIOR",
["s@Testchar - Horde - TestRealm@internalData@playerProfessions"] = {
["Leatherworking"] = {
["maxLevel"] = 150,
["isSecondary"] = false,
["level"] = 112,
["skillId"] = 165,
},
["Cooking"] = {
["maxLevel"] = 75,
["isSecondary"] = true,
["level"] = 60,
["skillId"] = 185,
},
},
["r@TestRealm@internalData@csvSales"] = "itemString,stackSize,quantity,price,otherPlayer,player,time,source\ni:2318,1,2,150,Merchant,Testchar,1794000000,Vendor\ni:4234,1,1,900,Somebuyer,Testchar,1794000100,Auction",
["r@TestRealm@internalData@csvBuys"] = "itemString,stackSize,quantity,price,otherPlayer,player,time,source",
["r@TestRealm@internalData@csvIncome"] = "type,amount,otherPlayer,player,time",
["r@TestRealm@internalData@csvExpense"] = "type,amount,otherPlayer,player,time\nRepair Bill,1286,Merchant,Testchar,1794000200\nbroken,row",
["r@TestRealm@internalData@csvExpired"] = "itemString,stackSize,quantity,player,time",
["r@TestRealm@internalData@csvCancelled"] = "",
["p@Default@internalData@createdDefaultOperations"] = true,
["p@Default@userData@items"] = {
["i:4234"] = "Leather",
},
["p@Default@userData@groups"] = {
[""] = {
["Sniper"] = {
"#Default",
["override"] = true,
},
["Warehousing"] = {
["override"] = true,
},
["Auctioning"] = {
"#Default",
["override"] = true,
},
["Crafting"] = {
"#Default",
["override"] = true,
},
["Mailing"] = {
["override"] = true,
},
["Vendoring"] = {
["override"] = true,
},
["Shopping"] = {
"#Default",
["override"] = true,
},
},
["Leather"] = {
["Sniper"] = {
"#Default",
},
["Warehousing"] = {
},
["Auctioning"] = {
"#Default",
},
["Crafting"] = {
"#Default",
},
["Mailing"] = {
},
["Vendoring"] = {
},
["Shopping"] = {
"#Default",
},
},
},
["p@Default@userData@operations"] = {
["Mailing"] = {
["#Default"] = {
["ignoreFactionrealm"] = {
},
["restock"] = false,
["maxQtyEnabled"] = false,
["relationships"] = {
},
["keepQty"] = "0",
["target"] = "",
["ignorePlayer"] = {
},
["restockSources"] = {
["guild"] = false,
["bank"] = false,
},
["maxQty"] = "10",
},
},
["Auctioning"] = {
["#Default"] = {
["cancelRepost"] = true,
["normalPrice"] = "2 * dbmarket",
["duration"] = 2,
["keepQuantity"] = "0",
["postCap"] = "5",
["bidPercent"] = 1,
["relationships"] = {
},
["maxPrice"] = "5 * dbmarket",
["ignoreLowDuration"] = 0,
["ignoreFactionrealm"] = {
},
["cancelRepostThreshold"] = "1g",
["maxExpires"] = "0",
["priceReset"] = "none",
["undercut"] = "0c",
["aboveMax"] = "maxPrice",
["minPrice"] = "0.5 * dbmarket",
["cancelUndercut"] = true,
["ignorePlayer"] = {
},
},
},
["Crafting"] = {
["#Default"] = {
["ignoreFactionrealm"] = {
},
["minProfit"] = "100g",
["maxRestock"] = "20",
["relationships"] = {
},
["minRestock"] = "10",
["craftPriceMethod"] = "",
["ignorePlayer"] = {
},
},
},
["Shopping"] = {
["#Default"] = {
["ignoreFactionrealm"] = {
},
["maxPrice"] = "dbmarket",
["showAboveMaxPrice"] = true,
["relationships"] = {
},
["restockQuantity"] = "0",
["ignorePlayer"] = {
},
["restockSources"] = {
["alts"] = false,
["auctions"] = false,
["bank"] = false,
["guild"] = false,
},
},
},
["Sniper"] = {
["#Default"] = {
["ignoreFactionrealm"] = {
},
["belowPrice"] = "0.5 * dbmarket",
["relationships"] = {
},
["ignorePlayer"] = {
},
},
},
["Vendoring"] = {
["#Default"] = {
["ignoreFactionrealm"] = {
},
["sellAfterExpired"] = "20",
["sellSoulbound"] = false,
["keepQty"] = "0",
["restockQty"] = "0",
["restockSources"] = {
["alts"] = false,
["ah"] = false,
["bank"] = false,
["guild"] = false,
["alts_ah"] = false,
["mail"] = false,
},
["enableBuy"] = true,
["enableSell"] = true,
["vsMarketValue"] = "dbmarket",
["vsMaxMarketValue"] = "0c",
["vsDestroyValue"] = "dbmarket",
["vsMaxDestroyValue"] = "0c",
["relationships"] = {
},
["ignorePlayer"] = {
},
},
},
["Warehousing"] = {
["#Default"] = {
["ignoreFactionrealm"] = {
},
["moveQuantity"] = "0",
["keepBagQuantity"] = "0",
["keepBankQuantity"] = "0",
["restockQuantity"] = "0",
["stackSize"] = "0",
["restockKeepBankQuantity"] = "0",
["restockStackSize"] = "0",
["relationships"] = {
},
["ignorePlayer"] = {
},
},
},
},
}
TSMItemInfoDB = {
["data"] = "opaque } blob { that must = survive",
["versionStr"] = "20,enUS,1.60.1,70888",
}
