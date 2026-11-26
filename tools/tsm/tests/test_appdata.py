"""Tests for tools/tsm/appdata.py against synthetic fixtures (no real price data, no network).

    python -I -m pytest tools/tsm/tests/test_appdata.py -q
"""
import base64
import json
import sys
import urllib.error
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import appdata as A  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BASIC = FIXTURES / "appdata_basic.lua"
BUILD = "1.60.1.11111"
NOW = 1700044000 + 3600  # one hour after the fixture's lastSync


# ---------------------------------------------------------------- helpers


def write_wago(cache: Path, build: str = BUILD) -> Path:
    folder = cache / "wago" / build
    folder.mkdir(parents=True)
    (folder / "ItemClass.enUS.csv").write_text("ID,ClassName_lang,ClassID\n1,Armor,4\n2,Trade Goods,7\n", encoding="utf-8")
    (folder / "ItemSubClass.enUS.csv").write_text(
        "DisplayName_lang,VerboseName_lang,ID,ClassID,SubClassID\nCloth,,1,4,1\nLeather,,2,4,2\nCloth,,3,7,5\n", encoding="utf-8")
    (folder / "Item.enUS.csv").write_text("ID,ClassID,SubclassID\n1001,4,1\n1002,4,2\n1003,7,5\n1004,4,2\n1005,4,2\n", encoding="utf-8")
    (folder / "ItemSparse.enUS.csv").write_text(
        "ID,Display_lang,OverallQualityID,RequiredLevel,ItemLevel,Bonding,Stackable,SellPrice,InventoryType\n"
        "1002,Test Jerkin,2,30,35,2,1,500,5\n"
        "1003,Test Cloth,1,0,10,0,20,13,0\n"
        "1005,Test Epic Tunic,4,60,66,1,1,90000,20\n", encoding="utf-8")
    return folder


def cbor(value) -> bytes:
    """Independent encoder for the test: ints, byte strings (as the client writes Lua strings) and arrays."""
    def head(major: int, n: int) -> bytes:
        if n < 24:
            return bytes([major << 5 | n])
        for ai, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
            if n < 1 << (8 * size):
                return bytes([major << 5 | ai]) + n.to_bytes(size, "big")
        raise ValueError(n)
    if isinstance(value, int):
        return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return head(2, len(raw)) + raw
    return head(4, len(value)) + b"".join(cbor(v) for v in value)


CACHE_ROWS = [
    # itemString, name, itemLevel, minLevel, maxStack, vendorSell, invSlotId, texture, classId, subClassId, quality, isBOP, reagent, expansion, craftedQuality
    ["i:1001", "Test Britches", 25, 20, 1, 1041, 7, 135614, 4, 1, 2, 0, 0, 0, -1],
    ["i:1001::1:12720", "Test Britches of the Owl", 25, 20, 1, 1041, 7, 135614, 4, 1, 2, 0, 0, 0, -1],
    ["i:1002", "Cache Name Loses", 35, 30, 1, 500, 5, 1, 4, 2, 2, 0, 0, 0, -1],
    ["i:1004", "Test Leggings", 45, 40, 1, 70000, 7, 1, 4, 2, 2, 1, 0, 0, -1],
]


def write_saved_vars(path: Path, rows=CACHE_ROWS, data: str | None = None) -> Path:
    if data is None:
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        data = base64.b64encode(comp.compress(cbor([v for r in rows for v in r])) + comp.flush()).decode()
    path.write_text('TradeSkillMasterDB = {\n["_hash"] = 1,\n}\nTSMItemInfoDB = {\n["data"] = "' + data + '",\n["versionStr"] = "20,enUS,1.60.1,11111",\n}\n',
                    encoding="utf-8")
    return path


@pytest.fixture
def data():
    return A.AppData.from_file(BASIC)


@pytest.fixture
def db(tmp_path):
    write_wago(tmp_path)
    return A.ItemDB.open(tmp_path, download=False, saved_vars=write_saved_vars(tmp_path / "TradeSkillMaster.lua"))


@pytest.fixture
def cli(tmp_path, capsys):
    write_wago(tmp_path)
    sv = write_saved_vars(tmp_path / "TradeSkillMaster.lua")

    def run(*args, appdata=BASIC, names=True):
        argv = [*args, "--appdata", str(appdata)]
        argv += ["--cache-dir", str(tmp_path), "--offline", "--saved-vars", str(sv)] if names else ["--no-names"]
        code = A.main(argv)
        out = capsys.readouterr()
        return code, out.out, out.err
    return run


# ---------------------------------------------------------------- decoding


@pytest.mark.parametrize("text,value", [("0", 0), ("V", 31), ("10", 32), ("12C", 1100), ("5E", 174), ("1E7", 1479),
                                        ("VVVVVV", 2**30 - 1), ("1000005", 2**30 + 5), ("1LCVG", 1750000)])
def test_decode_b32(text, value):
    assert A.decode_b32(text) == value


def test_decode_b32_rejects_other_digits():
    with pytest.raises(A.AppDataError, match="base-32"):
        A.decode_b32("W1")


@pytest.mark.parametrize("copper,text", [(None, "-"), (0, "0c"), (7, "7c"), (1100, "11s00c"), (1303, "13s03c"), (10000, "1g00s00c"),
                                         (1234567, "123g45s67c")])
def test_format_money(copper, text):
    assert A.format_money(copper) == text


@pytest.mark.parametrize("item,expected", [
    (2622, ("i:2622", "i:2622")), ("2622", ("i:2622", "i:2622")), ("item:2622", ("i:2622", "i:2622")),
    ("i:2622:-18", ("i:2622:-18", "i:2622")), ("i:2622::i25", ("i:2622::i25", "i:2622")),
    ("i:14165::1:12720", ("i:14165::1:12720", "i:14165")), ("p:39", ("p:39", "p:39")),
])
def test_normalize_key(item, expected):
    assert A.normalize_key(item) == expected


def test_normalize_key_rejects_names():
    with pytest.raises(A.AppDataError, match="not an item id"):
        A.normalize_key("Test Britches")


# ---------------------------------------------------------------- parsing


def test_blocks_tags_scopes_and_counts(data):
    got = {(b.tag, b.name, b.scope, len(b.rows)) for b in data.blocks}
    assert got == {
        ("AUCTIONDB_REGION_SALE", "Test-US", "region", 4), ("AUCTIONDB_REGION_HISTORICAL", "Test-US", "region", 4),
        ("AUCTIONDB_COMMODITY_HISTORICAL", "Test-US", "commodity", 0), ("AUCTIONDB_NON_COMMODITY_SCAN_STAT", "Test-Horde", "realm", 4),
        ("AUCTIONDB_NON_COMMODITY_HISTORICAL", "Test-Horde", "realm", 2), ("AUCTIONDB_NON_COMMODITY_DATA", "Test-Horde", "realm", 4),
        ("AUCTIONDB_REGION_STAT", "Test-US", "region", 4),
    }


def test_block_fields_keys_and_trailer(data):
    b = data.block("AUCTIONDB_NON_COMMODITY_DATA")
    assert b.fields == ["minBuyout", "numAuctions", "marketValueRecent"]
    assert b.download_time == 1700043600
    assert b.rows["i:1001"] == (1100, 31, 1100)
    assert "i:1004::i1" in b.rows  # a quoted key keeps its item string; a bare number becomes i:<id>
    assert b.rows["i:1005"][0] == 2**30 + 5  # 7 base-32 digits: past Lua's 32-bit tonumber, same number here
    assert b.trailer == ["AUCTIONDB_NON_COMMODITY_DATA", "Test-Horde", "1700043600", "999"]


def test_app_info(data):
    assert data.app_info["version"] == "9.9.9"
    assert data.app_info["lastSync"] == 1700044000
    assert data.app_info["news"] == [{"title": "Synthetic news", "timestamp": 1690000000}]


def test_missing_file_names_the_path(tmp_path):
    with pytest.raises(A.AppDataError, match="AppData.lua not found at .*nope.lua"):
        A.AppData.from_file(tmp_path / "nope.lua")


def test_not_an_appdata_file():
    with pytest.raises(A.AppDataError, match="no LoadData"):
        A.AppData.from_text("-- empty")


def test_missing_tag_lists_what_is_present():
    d = A.AppData.from_file(FIXTURES / "appdata_region_only.lua")
    with pytest.raises(A.AppDataError, match=r"AUCTIONDB_NON_COMMODITY_DATA is not in AppData.lua; present: \['AUCTIONDB_REGION_STAT/Test-US'\]"):
        d.block("AUCTIONDB_NON_COMMODITY_DATA")


@pytest.mark.parametrize("body,message", [
    ('return {downloadTime=1,fields={"itemString","x"}}', "no ',data={'"),
    ('return {fields={"itemString","x"},data={{1,2}}}', "no downloadTime/fields"),
    ('return {downloadTime=1,fields={"item","x"},data={{1,2}}}', "expected 'itemString'"),
    ('return {downloadTime=1,fields={"itemString","x"},data={{1,2,3}}}', "row i:1 has 2 values"),
    ('return {downloadTime=1,fields={"itemString","x"},data={{1,2},{1,3}}}', "duplicate row for i:1"),
    ('return {downloadTime=1,fields={"itemString","x"},data={{1,ZZ}}}', "not base 32"),
])
def test_malformed_block_names_the_tag(body, message):
    text = f'select(2, ...).LoadData("AUCTIONDB_REGION_STAT","Test-US",[[{body}]]) --<AUCTIONDB_REGION_STAT,Test-US,1>'
    with pytest.raises(A.AppDataError, match="AUCTIONDB_REGION_STAT/Test-US.*" + message):
        A.AppData.from_text(text)


# ---------------------------------------------------------------- lookups


def test_lookup_all_fields_unscaled(data):
    v = data.lookup(1001)["values"]
    assert v == {"minBuyout": 1100, "numAuctions": 31, "marketValueRecent": 1100, "marketValue": 1303, "historical": 1546,
                 "regionMarketValue": 1879, "regionHistorical": 1800, "regionSale": 1140, "regionSoldPerDay": 1.479,
                 "regionSaleRate": 0.174}


def test_lookup_variant_falls_back_to_base(data):
    found = data.lookup("i:1001::1:12720")
    assert found["itemString"] == "i:1001::1:12720" and found["baseItemString"] == "i:1001"
    assert {t["key"] for t in found["tags"].values()} == {"i:1001"}
    assert found["values"]["minBuyout"] == 1100


def test_lookup_exact_variant_key_wins_and_base_is_absent(data):
    assert data.lookup("i:1004::i1")["values"]["marketValue"] == 20
    with pytest.raises(A.AppDataError, match="item i:1004 is in no price data"):
        data.lookup(1004)  # only the ::i1 variant is priced; the base has no row of its own


def test_lookup_zero_means_no_value(data):
    found = data.lookup(1002)
    assert found["tags"]["AUCTIONDB_REGION_SALE"]["raw"] == {"regionSale": 0, "regionSoldPerDay": 0, "regionSalePercent": 0}
    assert found["values"] == {"regionMarketValue": 10, "regionHistorical": 11}
    assert found["inRegion"] and not found["inRealm"]


def test_lookup_realm_only(data):
    found = data.lookup(1003)
    assert found["inRealm"] and not found["inRegion"]
    assert found["values"] == {"minBuyout": 100, "numAuctions": 1, "marketValueRecent": 100, "marketValue": 100, "historical": 100}


def test_lookup_unknown_item_names_the_scopes(data):
    with pytest.raises(A.AppDataError, match=r"item i:4242 is in no price data \(commodity Test-US, realm Test-Horde, region Test-US\)"):
        data.lookup(4242)


def test_merged_rows(data):
    rows = data.merged()
    assert set(rows) == {"i:1001", "i:1002", "i:1003", "i:1004::i1", "i:1005"}
    assert rows["i:1004::i1"]["itemId"] == 1004
    assert rows["i:1002"]["inRealm"] is False and "regionSale" not in rows["i:1002"]
    assert rows["i:1005"]["regionSaleRate"] == 0.001 and rows["i:1005"]["minBuyout"] == 2**30 + 5


def test_update_times_ignore_historical(data):
    assert data.update_times() == {"realm": 1700043600, "region": 1700000000}


def test_two_realms_need_a_choice():
    d = A.AppData.from_file(FIXTURES / "appdata_two_realms.lua")
    with pytest.raises(A.AppDataError, match=r"realm data for \['Test-Alliance', 'Test-Horde'\]; say which with --realm"):
        d.merged()
    assert d.lookup(1001, realm="test-alliance")["values"]["minBuyout"] == 100
    assert d.lookup(1001, realm="Test-Horde")["values"]["minBuyout"] == 1100
    with pytest.raises(A.AppDataError, match="no realm data for 'Nope'"):
        d.lookup(1001, realm="Nope")


# ---------------------------------------------------------------- item names


def test_itemdb_merges_export_and_tsm_cache(db):
    assert db.items[1002]["name"] == "Test Jerkin" and db.items[1002]["attrSource"] == "wago"  # the export wins
    assert db.items[1002] | {} == {
        "name": "Test Jerkin", "quality": 2, "qualityName": "uncommon", "classId": 4, "className": "Armor", "subclassId": 2,
        "subclassName": "Leather", "slot": "Chest", "requiredLevel": 30, "itemLevel": 35, "bind": "boe", "stackSize": 1,
        "vendorSell": 500, "attrSource": "wago"}
    assert db.items[1001] == {
        "name": "Test Britches", "quality": 2, "qualityName": "uncommon", "classId": 4, "className": "Armor", "subclassId": 1,
        "subclassName": "Cloth", "slot": "Legs", "requiredLevel": 20, "itemLevel": 25, "bind": "boe", "stackSize": 1,
        "vendorSell": 1041, "attrSource": "tsm-cache"}
    assert db.items[1004]["bind"] == "bop"
    assert db.items[1003]["bind"] == "none" and db.items[1003]["subclassName"] == "Cloth" and db.items[1003]["slot"] is None
    assert db.items[1005]["bind"] == "bop" and db.items[1005]["qualityName"] == "epic"
    assert db.variants == {"i:1001::1:12720": "Test Britches of the Owl"}
    assert db.warnings == []
    assert "wago.tools" in db.source and "TSMItemInfoDB (20,enUS,1.60.1,11111): +2 items" in db.source


def test_itemdb_export_only_keeps_working_and_says_why(tmp_path):
    write_wago(tmp_path)
    db = A.ItemDB.open(tmp_path, download=False, saved_vars=tmp_path / "missing.lua")
    assert 1002 in db.items and 1001 not in db.items
    assert len(db.warnings) == 1 and "TSM item cache unavailable: cannot read" in db.warnings[0]


def test_itemdb_tsm_cache_only_uses_fallback_class_names(tmp_path):
    db = A.ItemDB.open(tmp_path, download=False, saved_vars=write_saved_vars(tmp_path / "TradeSkillMaster.lua"))
    assert db.items[1001]["className"] == "Armor" and db.items[1001]["subclassName"] == "Cloth"
    assert db.items[1002]["name"] == "Cache Name Loses"
    assert len(db.warnings) == 1 and "downloading is off" in db.warnings[0]


def test_itemdb_no_source_at_all(tmp_path):
    with pytest.raises(A.NameSourceError, match="item name source unavailable.*downloading is off.*TSM item cache unavailable"):
        A.ItemDB.open(tmp_path, download=False, saved_vars=tmp_path / "missing.lua")


def test_tsm_cache_broken_blob_is_named(tmp_path):
    sv = write_saved_vars(tmp_path / "TradeSkillMaster.lua", data="AAAA")
    with pytest.raises(A.NameSourceError, match="does not decode"):
        A.read_tsm_item_cache(sv)
    sv.write_text("TradeSkillMasterDB = {\n}\n", encoding="utf-8")
    with pytest.raises(A.NameSourceError, match="no TSMItemInfoDB.data"):
        A.read_tsm_item_cache(sv)


def test_tsm_cache_error_hides_the_account_folder(tmp_path):
    account = tmp_path / "WTF" / "Account" / "SECRETNAME" / "SavedVariables"
    with pytest.raises(A.NameSourceError) as e:
        A.read_tsm_item_cache(account / "TradeSkillMaster.lua")
    assert "SECRETNAME" not in str(e.value)


def test_wago_newest_cached_build_is_used_offline(tmp_path):
    write_wago(tmp_path, "1.60.1.100")
    write_wago(tmp_path, "1.60.1.99")
    assert A.cached_builds(tmp_path) == ["1.60.1.99", "1.60.1.100"]
    assert A.ItemDB.load(tmp_path, download=False).build == "1.60.1.100"


def test_wago_download_goes_to_the_cache_once(tmp_path):
    src = write_wago(tmp_path / "src")
    calls = []

    def fake_get(url, timeout=300):
        calls.append(url)
        if url == A.WAGO_BUILDS_URL:
            return json.dumps({"wowf": [{"version": "1.60.1.5", "created_at": "2026-01-01"}, {"version": BUILD, "created_at": "2026-02-01"}],
                               "wow": [{"version": "12.0.0.1", "created_at": "2027-01-01"}]}).encode()
        table = url.split("/db2/")[1].split("/")[0]
        assert f"build={BUILD}" in url and "locale=enUS" in url
        return (src / f"{table}.enUS.csv").read_bytes()

    cache = tmp_path / "cache"
    db = A.ItemDB.load(cache, http_get=fake_get)
    assert db.build == BUILD and db.items[1002]["name"] == "Test Jerkin"
    assert len(calls) == 5
    A.ItemDB.load(cache, http_get=fake_get)
    assert len(calls) == 5  # second run is offline


def test_wago_network_failure_names_the_url(tmp_path):
    def down(url, timeout=300):
        raise urllib.error.URLError("no route")
    with pytest.raises(A.NameSourceError, match="item name source unavailable: https://wago.tools/api/builds"):
        A.ItemDB.load(tmp_path, http_get=down)


def test_wago_html_instead_of_csv_is_not_cached(tmp_path):
    with pytest.raises(A.NameSourceError, match="did not return a CSV"):
        A.fetch_tables(BUILD, tmp_path, http_get=lambda url, timeout=300: b"<!DOCTYPE html><html>")
    assert A.cached_builds(tmp_path) == []


def test_wago_missing_column_is_named(tmp_path):
    folder = write_wago(tmp_path)
    (folder / "ItemSparse.enUS.csv").write_text("ID,Display_lang\n1,X\n", encoding="utf-8")
    with pytest.raises(A.NameSourceError, match=r"ItemSparse.enUS.csv lacks column\(s\) \['OverallQualityID'"):
        A.ItemDB.load(tmp_path, download=False)


def test_find_exact_then_substring_then_suffix(db):
    assert db.find("test jerkin") == (["i:1002"], None)
    keys, note = db.find("test")
    assert keys[0] == "i:1003" and set(keys) == {"i:1001", "i:1002", "i:1003", "i:1004", "i:1005"} and note is None
    keys, note = db.find("Test Britches of the Owl")
    assert keys == ["i:1001::1:12720"] and "variant i:1001::1:12720" in note
    keys, note = db.find("Test Jerkin of the Whale")
    assert keys == ["i:1002"] and "random suffix of 'Test Jerkin'" in note
    assert db.find("nothing like this") == ([], None)


# ---------------------------------------------------------------- reports


def test_info(data, db):
    d = A.info(data, db, now=NOW)
    assert d["realms"] == ["Test-Horde"] and d["regions"] == ["Test-US"]
    assert d["app"] == {"version": "9.9.9", "lastSync": 1700044000, "lastSyncUtc": "2023-11-15T10:26:40Z", "lastSyncAgeHours": 1.0}
    block = next(b for b in d["blocks"] if b["tag"] == "AUCTIONDB_NON_COMMODITY_DATA")
    assert block["rows"] == 4 and block["ageHours"] == 1.1 and block["downloadTimeUtc"] == "2023-11-15T10:20:00Z"
    assert d["items"] == {"total": 5, "withRealmData": 4, "withRegionData": 4, "both": 3, "realmOnly": 1, "regionOnly": 1,
                          "onAuctionHouseNow": 4, "variantKeys": 1, "unnamed": 0}
    assert d["realmUpdateAgeHours"] == 1.1 and d["regionUpdateAgeHours"] == 13.2


def test_item_report_by_name_with_variant_note(data, db):
    d = A.item_report(data, db, "test britches of the owl")
    m = d["matches"][0]
    assert "base item" in d["note"]
    assert m["itemString"] == "i:1001::1:12720" and m["variantName"] == "Test Britches of the Owl"
    assert m["attributes"]["name"] == "Test Britches"
    assert m["values"]["minBuyout"] == {"copper": 1100, "text": "11s00c"}
    assert m["values"]["marketValue"] == {"copper": 1303, "text": "13s03c"}
    assert m["values"]["regionSaleRate"] == 0.174 and m["values"]["regionSoldPerDay"] == 1.479
    assert m["missing"] == []


def test_item_report_region_only_says_so(data, db):
    m = A.item_report(data, db, "1002")["matches"][0]
    assert len(m["missing"]) == 1 and m["missing"][0].startswith("not in realm data (Test-Horde)")


def test_item_report_without_any_realm_data(db):
    d = A.AppData.from_file(FIXTURES / "appdata_region_only.lua")
    m = A.item_report(d, db, "1001")["matches"][0]
    assert m["missing"] == ["AppData.lua holds no realm data at all: region numbers only"]


def test_item_report_named_item_without_prices(data, db):
    with pytest.raises(A.AppDataError, match=r"item i:1004 \(Test Leggings\) is in no price data"):
        A.item_report(data, db, "1004")
    with pytest.raises(A.AppDataError, match=r"item i:1004 \(Test Leggings\) is in no price data"):
        A.item_report(data, db, "leggings")
    db.items[1006] = dict(db.items[1004], name="Other Leggings")
    with pytest.raises(A.AppDataError, match=r"2 item\(s\) match 'leggings' by name but none is in the realm \(Test-Horde\)"):
        A.item_report(data, db, "leggings")


def test_item_report_name_needs_a_name_source(data):
    with pytest.raises(A.NameSourceError, match="cannot look up 'britches' by name"):
        A.item_report(data, None, "britches")
    assert A.item_report(data, None, "1001")["matches"][0]["attributes"] is None


def test_item_report_unknown_name(data, db):
    with pytest.raises(A.AppDataError, match="no item named like 'zzz'"):
        A.item_report(data, db, "zzz")


def test_top_orders_and_filters(data, db):
    assert [r["itemId"] for r in A.top(data, db, "marketValue")] == [1005, 1001, 1003, 1004]
    assert [r["itemId"] for r in A.top(data, db, "marketValue", ascending=True, limit=2)] == [1004, 1003]
    assert [r["itemId"] for r in A.top(data, db, "regionSaleRate")] == [1004, 1001, 1005]  # 1002's 0 is "no value"
    assert [r["itemId"] for r in A.top(data, db, "regionMarketValue", item_class="armor", subclass="leather")] == [1005, 1004, 1002]
    assert [r["itemId"] for r in A.top(data, db, "regionMarketValue", item_class="Armor", quality="uncommon", bind="boe")] == [1001, 1002]
    assert [r["itemId"] for r in A.top(data, db, "regionMarketValue", quality="2", in_realm=True)] == [1001, 1004]
    assert [r["itemId"] for r in A.top(data, db, "regionMarketValue", min_level=25, max_level=45)] == [1004, 1002]
    assert [r["itemId"] for r in A.top(data, db, "regionMarketValue", min_sale_rate=0.1)] == [1001, 1004]
    assert [r["itemId"] for r in A.top(data, db, "vendorSell", limit=1)] == [1005]


def test_top_aliases_and_errors(data, db):
    assert A.canonical_field("DBRegionSaleRate") == "regionSaleRate" and A.canonical_field("regionsalepercent") == "regionSaleRate"
    with pytest.raises(A.AppDataError, match="unknown field 'price'"):
        A.top(data, db, "price")
    with pytest.raises(A.AppDataError, match="no item class named 'Armour'"):
        A.top(data, db, "marketValue", item_class="Armour")
    with pytest.raises(A.AppDataError, match="unknown quality 'shiny'"):
        A.top(data, db, "marketValue", quality="shiny")
    with pytest.raises(A.AppDataError, match="unknown bind type"):
        A.top(data, db, "marketValue", bind="soulbound")
    with pytest.raises(A.NameSourceError, match="need item attributes"):
        A.top(data, None, "marketValue", item_class="Armor")
    assert [r["itemId"] for r in A.top(data, None, "numAuctions", limit=1)] == [1001]


# ---------------------------------------------------------------- CLI


def test_cli_info_text_and_json(cli):
    code, out, err = cli("info")
    assert code == 0 and "realms: Test-Horde   regions: Test-US" in out and "AUCTIONDB_REGION_SALE" in out and err == ""
    code, out, _ = cli("info", "--json")
    assert json.loads(out)["items"]["total"] == 5 and "\n" not in out.strip()


def test_cli_item_text(cli):
    code, out, _ = cli("item", "test britches of the owl")
    assert code == 0
    assert "i:1001::1:12720  Test Britches of the Owl  [uncommon, Armor / Cloth / Legs, req 20" in out
    assert "via base key i:1001: minBuyout=11s00c (1100c), numAuctions=31" in out
    assert "regionSoldPerDay=1.479 (raw 1479), regionSaleRate=0.174 (raw 174)" in out


def test_cli_item_errors_exit_2(cli):
    code, out, err = cli("item", "4242")
    assert code == 2 and out == "" and err.startswith("error: item i:4242 is in no price data")
    code, _, err = cli("item", "britches", names=False)
    assert code == 2 and "item name source unavailable" in err


def test_cli_missing_appdata_exit_2(cli, tmp_path):
    code, _, err = cli("info", appdata=tmp_path / "gone.lua")
    assert code == 2 and "AppData.lua not found" in err


def test_cli_top_table_and_json(cli):
    code, out, _ = cli("top", "--by", "regionSaleRate", "--class", "Armor", "--quality", "2", "--bind", "boe", "--limit", "5")
    lines = out.strip().splitlines()
    assert code == 0 and lines[0].split()[:3] == ["itemId", "name", "saleRate"] and len(lines) == 2
    assert "Test Britches" in lines[1] and "0.174" in lines[1] and "11s00c" in lines[1]
    code, out, _ = cli("top", "--by", "minBuyout", "--json", "--limit", "1")
    assert json.loads(out)[0]["itemId"] == 1005
    code, out, _ = cli("top", "--by", "minBuyout", "--min-level", "61")
    assert code == 0 and out.strip() == "no item matches"


def test_cli_export(cli, tmp_path):
    out_file = tmp_path / "export.json"
    code, out, _ = cli("export", "--out", str(out_file))
    assert code == 0 and "wrote 5 items (5 named)" in out
    doc = json.loads(out_file.read_text(encoding="utf-8"))
    assert doc["realm"] == "Test-Horde" and doc["region"] == "Test-US" and doc["updateTimes"] == {"realm": 1700043600, "region": 1700000000}
    assert [r["itemString"] for r in doc["items"]] == ["i:1001", "i:1002", "i:1003", "i:1004::i1", "i:1005"]
    row = doc["items"][0]
    assert row["name"] == "Test Britches" and row["minBuyout"] == 1100 and row["regionSaleRate"] == 0.174 and row["bind"] == "boe"
    assert doc["items"][3]["name"] == "Test Leggings"  # a variant key takes the base item's attributes


def test_cli_export_without_names(cli, tmp_path):
    code, _, err = cli("export", "--out", str(tmp_path / "nodir" / "x.json"), names=False)
    assert code == 2 and "does not exist" in err
    code, out, _ = cli("export", "--out", str(tmp_path / "plain.json"), names=False)
    assert code == 0 and "(0 named)" in out
    assert "name" not in json.loads((tmp_path / "plain.json").read_text(encoding="utf-8"))["items"][0]
