"""Tests for tools/tsm/tsmdb.py. Run: python -I -m pytest tools/tsm/tests -q

The fixture is synthetic (invented characters and realm); nothing here comes
from a real SavedVariables file.
"""

import importlib.util
import json
import math
import pathlib
import shutil

import pytest

HERE = pathlib.Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "TradeSkillMaster.lua"

_spec = importlib.util.spec_from_file_location("tsmdb", HERE.parent / "tsmdb.py")
tsmdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tsmdb)

BS = chr(92)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "TradeSkillMaster.lua"
    shutil.copyfile(FIXTURE, path)
    return path


@pytest.fixture
def db(db_path):
    return tsmdb.load_db(db_path)


@pytest.fixture
def backups(tmp_path, monkeypatch):
    folder = tmp_path / "backups"
    monkeypatch.setenv("TSM_BACKUP_DIR", str(folder))
    return folder


def parse(text):
    return tsmdb.parse_lua_value(text)


# ---------------------------------------------------------------- parser

def test_parse_scalars():
    assert parse("{ 1, -2, 1.5, 1e3, 0x10, true, false }") == [1, -2, 1.5, 1000.0, 16, True, False]
    assert isinstance(parse("10000000000"), int)
    assert parse("math.huge") == math.inf and parse("-math.huge") == -math.inf


def test_parse_string_escapes():
    text = '"a' + BS + '"b' + BS + BS + "c" + BS + "nd" + BS + "re" + BS + "tf" + BS + '065' + BS + '10g"'
    assert parse(text) == 'a"b' + BS + "c\nd\re\tfA\ng"
    assert parse("'single " + BS + "' quote'") == "single ' quote"


def test_parse_decimal_escapes_form_utf8():
    assert parse('"' + BS + "195" + BS + '169"') == "é"
    assert parse('"é"'.encode("utf-8")) == "é"


def test_parse_invalid_utf8_bytes_survive():
    value = tsmdb.parse_lua_value(b'"a\xffb"')
    assert tsmdb.format_string(value).encode("latin-1") == b'"a\xffb"'


def test_parse_table_shapes():
    assert parse("{}") == {}
    assert parse('{"a", "b"}') == ["a", "b"]
    assert parse('{"a", ["override"] = true}') == {1: "a", "override": True}
    assert parse('{[1] = "a", [2] = "b"}') == ["a", "b"]
    assert parse('{[2] = "b"}') == {2: "b"}
    assert parse("{ name = 1, [\"k\"] = { 1, { x = 2 } } }") == {"name": 1, "k": [1, {"x": 2}]}
    assert parse("{[1.5] = 1, [-3] = 2}") == {1.5: 1, -3: 2}


def test_parse_key_order_and_comments():
    table = parse('{\n["z"] = 1, -- trailing\n-- full line\n["a"] = 2;\n"x", -- [1]\n}')
    assert list(table) == ["z", "a", 1]


def test_parse_nil_entries_are_dropped():
    assert parse("{nil, 2}") == {2: 2}
    assert parse('{["a"] = nil}') == {}


@pytest.mark.parametrize("text", ['{"a"', '"unterminated', "{[true] = 1}", "{1} trailing", "function() end", '"' + BS + 'q"'])
def test_parse_errors_name_the_line(text):
    with pytest.raises(tsmdb.TsmError, match="line 1"):
        parse(text)


# ---------------------------------------------------------------- serializer

def test_format_number_like_the_client():
    assert tsmdb.format_number(float("152.0000610351563")) == "152.0000610351563"
    assert tsmdb.format_number(1 / 3) == "0.3333333333333333"
    assert tsmdb.format_number(0.7111111283302307) == "0.7111111283302307"
    assert tsmdb.format_number(196.9) == "196.9"
    assert tsmdb.format_number(2.0) == "2"
    assert tsmdb.format_number(10000000000) == "10000000000"
    assert tsmdb.format_number(-math.inf) == "-math.huge"
    with pytest.raises(tsmdb.TsmError):
        tsmdb.format_number(math.nan)
    with pytest.raises(tsmdb.TsmError):
        tsmdb.format_number(True)


def test_format_string_escapes_round_trip():
    value = 'q" b' + BS + " n\n r\r t\t nul\x00 é |cff"
    text = tsmdb.format_string(value)
    assert "\n" not in text and "\r" not in text and "\x00" not in text
    assert BS + "000" in text and "\t" in text
    assert parse(text.encode("latin-1")) == value


def test_serialize_layout_and_mixed_tables():
    table = {"k": {1: "a", "override": True}, "arr": ["x", {"y": 1}], "e": {}, 5: "five"}
    text = tsmdb.serialize_table("T", table, newline="\n")
    assert text.split("\n") == [
        "T = {", '["k"] = {', '"a",', '["override"] = true,', "},", '["arr"] = {', '"x",', "{", '["y"] = 1,', "},",
        "},", '["e"] = {', "},", '[5] = "five",', "}"]
    assert parse(text[4:]) == table


def test_serialize_indent_and_array_comments():
    text = tsmdb.serialize_table("T", {"a": ["x", "y"]}, newline="\n", indent="\t", array_comments=True)
    assert text == 'T = {\n\t["a"] = {\n\t\t"x", -- [1]\n\t\t"y", -- [2]\n\t},\n}'


def test_serialize_rejects_none_and_objects():
    with pytest.raises(tsmdb.TsmError):
        tsmdb.serialize_table("T", {"a": None})
    with pytest.raises(tsmdb.TsmError):
        tsmdb.serialize_table("T", {"a": object()})


def test_canonical_matches_parser_shapes():
    assert tsmdb.canonical({1: "a", 2: "b"}) == ["a", "b"]
    assert tsmdb.canonical([]) == {}
    assert tsmdb.canonical({1: "a", "override": True}) == {1: "a", "override": True}
    assert tsmdb.canonical({"x": {1: {2.0: "v"}}}) == {"x": [{2: "v"}]}


# ---------------------------------------------------------------- file round trip

def test_round_trip_is_byte_identical(db_path, db):
    raw = db_path.read_bytes()
    assert db.to_bytes() == raw
    assert tsmdb.loads_db(db.to_bytes()).data == db.data


def test_round_trip_crlf_and_other_globals(tmp_path):
    raw = FIXTURE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    raw = b'OtherGlobal = "before"\r\n' + raw
    path = tmp_path / "crlf.lua"
    path.write_bytes(raw)
    loaded = tsmdb.load_db(path)
    assert loaded.newline == "\r\n"
    assert loaded.prefix.startswith('OtherGlobal = "before"')
    assert "TSMItemInfoDB" in loaded.suffix and "opaque } blob {" in loaded.suffix
    assert loaded.to_bytes() == raw


def test_round_trip_standard_wow_layout(tmp_path):
    raw = b'\nTradeSkillMasterDB = {\n\t["a"] = {\n\t\t"x", -- [1]\n\t\t{\n\t\t\t["n"] = 1,\n\t\t}, -- [2]\n\t},\n}\n'
    path = tmp_path / "std.lua"
    path.write_bytes(raw)
    loaded = tsmdb.load_db(path)
    assert loaded.data == {"a": ["x", {"n": 1}]}
    assert (loaded.indent, loaded.array_comments) == ("\t", True)
    assert loaded.to_bytes() == raw


def test_fixture_values(db):
    assert db.data["g@ @mainUIContext@frame"]["centerX"] == 152.0000610351563
    assert db.data["g@ @internalData@notes"] == 'quote " backslash ' + BS + " newline \n tab\t accent é bar |cff00ff00x|r"
    assert db.data["p@Default@userData@groups"][""]["Auctioning"] == {1: "#Default", "override": True}
    assert db.data["p@Default@userData@groups"]["Leather"]["Auctioning"] == ["#Default"]
    assert list(db.data)[:2] == ["g@ @userData@ungroupedItemMode", "g@ @coreOptions@globalOperations"]


def test_load_errors_name_the_file(tmp_path):
    with pytest.raises(tsmdb.TsmError, match="cannot read SavedVariables file"):
        tsmdb.load_db(tmp_path / "missing.lua")
    other = tmp_path / "other.lua"
    other.write_text("SomethingElse = {\n}\n")
    with pytest.raises(tsmdb.TsmError, match="TradeSkillMasterDB not found in .*other.lua"):
        tsmdb.load_db(other)


# ---------------------------------------------------------------- get / set

def test_get_and_set(db):
    assert tsmdb.get(db, "global", None, "userData", "ungroupedItemMode") == "specific"
    assert tsmdb.get(db, "s", "Testchar - Horde - TestRealm", "internalData", "money") == 123456
    assert tsmdb.get_key(db, "g@userData@ungroupedItemMode") == "specific"
    assert tsmdb.set(db, "global", None, "userData", "ungroupedItemMode", "base") == "specific"
    assert db.data["g@ @userData@ungroupedItemMode"] == "base"
    tsmdb.set_key(db, "g@ @mailingOptions@resendDelay", 2.5)
    tsmdb.set_key(db, "g@ @userData@customPriceSources", {"a": "1g"})


def test_get_missing_key_names_key_file_and_scope(db):
    with pytest.raises(tsmdb.TsmError, match=r"key not found: 'g@ @nope@nope' in .*TradeSkillMaster.lua"):
        tsmdb.get_key(db, "g@ @nope@nope")
    with pytest.raises(tsmdb.TsmError, match=r"scope key 'Nobody - TestRealm' is not in _scopeKeys.char"):
        tsmdb.get(db, "char", "Nobody - TestRealm", "internalData", "auctionPrices")
    with pytest.raises(tsmdb.TsmError, match="unknown scope"):
        tsmdb.make_key("bogus", "x", "a", "b")
    with pytest.raises(tsmdb.TsmError, match="needs a scope key"):
        tsmdb.make_key("profile", None, "a", "b")


@pytest.mark.parametrize("key,value,expected,got", [
    ("g@ @userData@ungroupedItemMode", 1, "string", "number"),
    ("g@ @tooltipOptions@vendorSellTooltip", 1, "boolean", "number"),
    ("g@ @mailingOptions@resendDelay", True, "number", "boolean"),
    ("g@ @userData@customPriceSources", "x", "table", "string"),
])
def test_set_type_mismatch(db, key, value, expected, got):
    with pytest.raises(tsmdb.TsmError, match=f"type mismatch.*expected {expected}, got {got}"):
        tsmdb.set_key(db, key, value)


def test_set_refuses_metadata(db):
    with pytest.raises(tsmdb.TsmError, match="metadata"):
        tsmdb.set_key(db, "_hash", 1)


# ---------------------------------------------------------------- groups / items

def test_list_groups(db):
    groups = tsmdb.list_groups(db)
    assert [g["path"] for g in groups] == ["", "Leather"]
    assert groups[1]["items"] == 1
    assert groups[0]["operations"]["Auctioning"] == {"names": ["#Default"], "override": True}
    assert groups[1]["operations"]["Mailing"] == {"names": [], "override": False}


def test_create_group_creates_parents_and_inherits(db):
    assert tsmdb.create_group(db, "A`B`C") == ["A", "A`B", "A`B`C"]
    groups = db.data["p@Default@userData@groups"]
    assert groups["A`B`C"]["Auctioning"] == ["#Default"]
    assert groups["A`B`C"]["Mailing"] == {}
    assert list(groups["A"]) == list(tsmdb.MODULES)
    assert tsmdb.create_group(db, "A`B") == []
    assert tsmdb.validate(db)["errors"] == []


@pytest.mark.parametrize("path", ["", "A``B", "`A", "A`", 5])
def test_create_group_rejects_bad_paths(db, path):
    with pytest.raises(tsmdb.TsmError):
        tsmdb.create_group(db, path)


def test_group_path_helpers():
    assert tsmdb.group_parent("A`B`C") == "A`B"
    assert tsmdb.group_parent("A") == ""
    assert tsmdb.group_parent("") is None
    assert tsmdb.is_child_group("A`B", "A") and not tsmdb.is_child_group("AB", "A")
    assert tsmdb.is_child_group("A", "") and not tsmdb.is_child_group("", "")


@pytest.mark.parametrize("given,expected", [
    (2318, "i:2318"), ("2318", "i:2318"), ("item:2318", "i:2318"), (" i:2318 ", "i:2318"),
    ("i:2318:0:0", "i:2318"), ("i:15234:-12", "i:15234:-12"), ("i:1234:0:2:77:88", "i:1234::2:77:88"),
    ("i:1234::i45", "i:1234::i45"), ("p:42", "p:42"), ("p:42:25:3", "p:42:25:3"), ("p:42:i25", "p:42:i25"),
    ("p:42:25:3:9:9", "p:42"),
])
def test_normalize_item_string(given, expected):
    assert tsmdb.normalize_item_string(given) == expected


@pytest.mark.parametrize("bad", ["", "x:1", "i:", "i:abc", "Light Leather", "i:1000000", True, "|cffffffff|Hitem:1|h[x]|h|r"])
def test_normalize_item_string_rejects(bad):
    with pytest.raises(tsmdb.TsmError, match="invalid item string"):
        tsmdb.normalize_item_string(bad)


def test_assign_items(db):
    result = tsmdb.assign_items(db, "Leather", ["i:2318", 2319, "i:4234", "i:1234::2:77:88"])
    assert result["added"] == ["i:2318", "i:2319", "i:1234::2:77:88"]
    assert result["unchanged"] == ["i:4234"]
    assert len(result["warnings"]) == 1 and "bonus ids" in result["warnings"][0]
    tsmdb.create_group(db, "Other")
    assert tsmdb.assign_items(db, "Other", ["i:2318"])["moved"] == {"i:2318": "Leather"}
    assert db.data["p@Default@userData@items"]["i:2318"] == "Other"


def test_assign_items_needs_an_existing_non_root_group(db):
    with pytest.raises(tsmdb.TsmError, match="group not found: 'Nope'"):
        tsmdb.assign_items(db, "Nope", ["i:1"])
    with pytest.raises(tsmdb.TsmError, match="root group"):
        tsmdb.assign_items(db, "", ["i:1"])


# ---------------------------------------------------------------- operations

def test_create_operation_fills_every_field_from_default(db):
    result = tsmdb.create_operation(db, "Auctioning", "Fast", {"postCap": "2", "duration": 3})
    assert result == {"created": True, "changed": {"postCap": "2", "duration": 3}}
    ops = db.data["p@Default@userData@operations"]["Auctioning"]
    assert set(ops["Fast"]) == set(ops["#Default"])
    assert ops["Fast"]["postCap"] == "2" and ops["#Default"]["postCap"] == "5"
    assert ops["Fast"]["minPrice"] == ops["#Default"]["minPrice"]
    assert ops["Fast"]["relationships"] == {} and ops["Fast"]["relationships"] is not ops["#Default"]["relationships"]
    assert tsmdb.validate(db)["errors"] == []


def test_create_operation_table_setting_is_copied(db):
    sources = {"guild": True, "bank": False}
    tsmdb.create_operation(db, "Mailing", "ToAlt", {"target": "Testalt", "restockSources": sources})
    stored = db.data["p@Default@userData@operations"]["Mailing"]["ToAlt"]["restockSources"]
    assert stored == sources and stored is not sources


def test_create_operation_errors(db):
    with pytest.raises(tsmdb.TsmError, match="operation module not found: 'Bogus'"):
        tsmdb.create_operation(db, "Bogus", "X")
    with pytest.raises(tsmdb.TsmError, match="unknown Auctioning operation field 'stackSize'"):
        tsmdb.create_operation(db, "Auctioning", "X", {"stackSize": "1"})
    with pytest.raises(tsmdb.TsmError, match="expected string, got number"):
        tsmdb.create_operation(db, "Auctioning", "X", {"postCap": 2})
    with pytest.raises(tsmdb.TsmError, match="invalid operation name"):
        tsmdb.create_operation(db, "Auctioning", " padded ")
    with pytest.raises(tsmdb.TsmError, match="already exists"):
        tsmdb.create_operation(db, "Auctioning", "#Default")
    del db.data["p@Default@userData@operations"]["Sniper"]["#Default"]
    with pytest.raises(tsmdb.TsmError, match="template not found: Sniper/#Default"):
        tsmdb.create_operation(db, "Sniper", "X")
    assert "X" not in db.data["p@Default@userData@operations"]["Auctioning"]


def test_create_operation_update_and_exist_ok(db):
    tsmdb.create_operation(db, "Auctioning", "Fast", {"postCap": "2"})
    assert tsmdb.create_operation(db, "Auctioning", "Fast", {"postCap": "2"}, exist_ok=True) == {"created": False, "changed": {}}
    with pytest.raises(tsmdb.TsmError, match="different settings"):
        tsmdb.create_operation(db, "Auctioning", "Fast", {"postCap": "3"}, exist_ok=True)
    assert tsmdb.create_operation(db, "Auctioning", "Fast", {"postCap": "3"}, update=True)["changed"] == {"postCap": "3"}


def test_operations_follow_global_operations_switch(db):
    db.data["g@ @coreOptions@globalOperations"] = True
    db.data["g@ @userData@sharedOperations"] = db.data.pop("p@Default@userData@operations")
    db.data["p@Default@userData@operations"] = {}
    assert tsmdb.operations_key(db) == "g@ @userData@sharedOperations"
    tsmdb.create_operation(db, "Sniper", "Cheap", {"belowPrice": "1g"})
    assert "Cheap" in db.data["g@ @userData@sharedOperations"]["Sniper"]
    assert tsmdb.validate(db)["errors"] == []


def test_list_operations(db):
    listing = tsmdb.list_operations(db, "Auctioning")
    assert list(listing) == ["Auctioning"]
    assert listing["Auctioning"]["#Default"]["groups"] == ["", "Leather"]
    assert set(tsmdb.list_operations(db)) == set(tsmdb.MODULES)
    with pytest.raises(tsmdb.TsmError, match="operation module not found"):
        tsmdb.list_operations(db, "Bogus")


def test_set_group_operations_override_and_inheritance(db):
    tsmdb.create_group(db, "Leather`Thick")
    tsmdb.create_group(db, "Leather`Own")
    tsmdb.create_operation(db, "Auctioning", "Fast")
    tsmdb.create_operation(db, "Auctioning", "Slow")
    tsmdb.set_group_operations(db, "Leather`Own", "Auctioning", ["Slow"])
    result = tsmdb.set_group_operations(db, "Leather", "Auctioning", ["Fast", "Slow"])
    groups = db.data["p@Default@userData@groups"]
    assert groups["Leather"]["Auctioning"] == {1: "Fast", 2: "Slow", "override": True}
    assert groups["Leather`Thick"]["Auctioning"] == ["Fast", "Slow"]
    assert groups["Leather`Own"]["Auctioning"] == {1: "Slow", "override": True}
    assert result["inherited_by"] == ["Leather`Thick"]
    assert result["before"] == {"names": ["#Default"], "override": False}
    tsmdb.set_group_operations(db, "Leather", "Auctioning", [], override=False)
    assert groups["Leather"]["Auctioning"] == ["#Default"]
    assert groups["Leather`Thick"]["Auctioning"] == ["#Default"]
    tsmdb.set_group_operations(db, "Leather", "Mailing", [])
    assert groups["Leather"]["Mailing"] == {"override": True}
    assert tsmdb.validate(db) ["errors"] == []


def test_set_group_operations_errors(db):
    with pytest.raises(tsmdb.TsmError, match="group not found: 'Nope'"):
        tsmdb.set_group_operations(db, "Nope", "Auctioning", [])
    with pytest.raises(tsmdb.TsmError, match="operation not found: Auctioning/'Ghost'"):
        tsmdb.set_group_operations(db, "Leather", "Auctioning", ["Ghost"])
    with pytest.raises(tsmdb.TsmError, match="operation module not found"):
        tsmdb.set_group_operations(db, "Leather", "Bogus", [])
    with pytest.raises(tsmdb.TsmError, match="too many Sniper"):
        tsmdb.create_operation(db, "Sniper", "Two")
        tsmdb.set_group_operations(db, "Leather", "Sniper", ["#Default", "Two"])
    with pytest.raises(tsmdb.TsmError, match="duplicate"):
        tsmdb.set_group_operations(db, "Leather", "Auctioning", ["#Default", "#Default"])
    with pytest.raises(tsmdb.TsmError, match="root group always overrides"):
        tsmdb.set_group_operations(db, "", "Auctioning", [], override=False)
    with pytest.raises(tsmdb.TsmError, match="pass no names"):
        tsmdb.set_group_operations(db, "Leather", "Auctioning", ["#Default"], override=False)


# ---------------------------------------------------------------- inventory / accounting

def test_inventory(db):
    result = tsmdb.inventory(db)
    assert result["totals"]["i:2318"] == {"total": 52, "bag": 45, "bank": 7}
    assert result["totals"]["i:4234"] == {"total": 3, "auction": 2, "mail": 1}
    assert result["characters"]["Testalt - Horde - TestRealm"] == {"i:2318": {"bag": 5}, "i:4234": {"mail": 1}}


def test_accounting(db):
    realm = tsmdb.accounting(db)["TestRealm"]
    assert realm["csvSales"]["rows"][1] == {
        "itemString": "i:4234", "stackSize": 1, "quantity": 1, "price": 900, "otherPlayer": "Somebuyer",
        "player": "Testchar", "time": 1794000100, "source": "Auction"}
    assert realm["csvBuys"]["empty"] and realm["csvBuys"]["fields"][0] == "itemString"
    assert realm["csvCancelled"] == {"fields": [], "rows": [], "malformed": [], "empty": True}
    assert len(realm["csvExpense"]["rows"]) == 1
    assert realm["csvExpense"]["malformed"] == [{"line": 3, "text": "broken,row"}]


# ---------------------------------------------------------------- validate

def test_validate_clean_fixture(db):
    report = tsmdb.validate(db)
    assert report["ok"] and report["errors"] == [] and report["warnings"] == []
    assert "_hash" in report["notes"][0]


def _errors(db):
    return "\n".join(tsmdb.validate(db)["errors"])


def _warnings(db):
    return "\n".join(tsmdb.validate(db)["warnings"])


@pytest.mark.parametrize("mutate,text", [
    (lambda d: d.__setitem__(1, "stray"), "WIPE: the table has an array part"),
    (lambda d: d.__setitem__("_version", "152"), "WIPE: _version is string"),
    (lambda d: d.__setitem__("_version", 101), "below the minimum 102"),
    (lambda d: d.pop("_hash"), "WIPE: _hash is nil"),
    (lambda d: d.__setitem__("_lastModifiedVersion", 5), "WIPE: _lastModifiedVersion"),
    (lambda d: d.pop("_scopeKeys"), "WIPE: _scopeKeys is nil"),
    (lambda d: d["_scopeKeys"].__setitem__("bogus", {}), "unknown scope 'bogus'"),
    (lambda d: d["_scopeKeys"].__setitem__("realm", {2: "TestRealm"}), "_scopeKeys.realm is not a gapless array"),
    (lambda d: d["_scopeKeys"].__setitem__("realm", [5]), "_scopeKeys.realm is not a gapless array"),
    (lambda d: d["_scopeKeys"].__setitem__("realm", "x"), "LUA ERROR: _scopeKeys.realm is string"),
    (lambda d: d.pop("_currentProfile"), "WIPE: _currentProfile is nil"),
    (lambda d: d["_currentProfile"].__setitem__("Testchar - TestRealm", 3), "WIPE: _currentProfile must map"),
    (lambda d: d.__setitem__("_syncAccountKey", None), "LUA ERROR: _syncOwner"),
])
def test_validate_db_checks(db, mutate, text):
    mutate(db.data)
    report = tsmdb.validate(db)
    assert not report["ok"] and text in "\n".join(report["errors"])


def test_validate_sync_owner_and_key_warnings(db):
    db.data["_syncOwner"]["Testalt - Horde - TestRealm"] = "Horde - TestRealm - 999"
    db.data["garbage"] = 1
    db.data["c@Ghost - TestRealm@internalData@auctionPrices"] = {}
    db.data["g@x@a@b"] = 1
    db.data["_currentProfile"]["Testalt - TestRealm"] = "Missing"
    text = _warnings(db)
    assert "_syncOwner['Testalt - Horde - TestRealm'] is not this account's key" in text
    assert "key 'garbage' is not <scope>" in text
    assert "scope key 'Ghost - TestRealm' is not in _scopeKeys.char" in text
    assert "global key 'g@x@a@b'" in text
    assert "'Missing' is not in _scopeKeys.profile" in text
    assert tsmdb.validate(db)["ok"]


def test_validate_groups(db):
    groups = db.data["p@Default@userData@groups"]
    groups["Orphan`Child"] = {m: {} for m in tsmdb.MODULES}
    groups["Bad``Path"] = {}
    groups["Leather"]["Auctioning"] = {1: "Ghost", "override": True}
    groups["Leather"]["Bogus"] = ["x"]
    groups["Leather"]["Empty"] = {}
    groups["Leather"]["Sniper"] = ["#Default", "#Default"]
    groups["Leather"]["Shopping"] = {1: "#Default", "override": 1, "junk": 2}
    groups["Leather"]["Crafting"] = []
    del groups["Leather"]["Mailing"]
    del groups[""]["Vendoring"]["override"]
    errors, warnings = _errors(db), _warnings(db)
    assert "group 'Orphan`Child': parent 'Orphan' does not exist" in errors
    assert "group 'Bad``Path': invalid path" in errors
    assert "Auctioning operation 'Ghost' does not exist" in errors
    assert "LUA ERROR: profile 'Default': group 'Leather': key 'Bogus'" in errors
    assert "key 'Empty' is not an operation module, TSM removes it" in warnings
    assert "2 Sniper operations, TSM keeps the first 1" in warnings
    assert "Shopping has invalid key 'junk'" in warnings and "Shopping.override is 1" in warnings
    assert "Crafting has no override but differs from its parent" in warnings
    assert "group 'Leather': no Mailing entry" in warnings
    assert "Vendoring has no override on the root group" in warnings
    del groups[""]
    assert 'no root group ""' in _warnings(db)


def test_validate_items(db):
    items = db.data["p@Default@userData@items"]
    items["i:1"] = "Nope"
    items["i:2"] = ""
    items["junk"] = "Leather"
    items["i:3:0:0"] = "Leather"
    items["i:4"] = 7
    errors = _errors(db)
    assert "item 'i:1': group 'Nope' does not exist" in errors
    assert "item 'i:2': group '' does not exist (or is the root)" in errors
    assert "item 'junk': invalid item string" in errors
    assert "LUA ERROR: profile 'Default': item 'i:4'" in errors
    assert "item 'i:3:0:0': TSM re-keys it as 'i:3'" in _warnings(db)


def test_validate_operations(db):
    ops = db.data["p@Default@userData@operations"]
    ops["Auctioning"][" bad"] = dict(ops["Auctioning"]["#Default"])
    broken = dict(ops["Auctioning"]["#Default"])
    del broken["postCap"]
    del broken["cancelUndercut"]
    broken["duration"] = "long"
    broken["keepQuantity"] = 3
    broken["extra"] = 1
    broken["relationships"] = {"minPrice": "Ghost", "maxPrice": "Loop"}
    ops["Auctioning"]["Broken"] = broken
    loop = dict(ops["Auctioning"]["#Default"])
    loop["relationships"] = {"maxPrice": "Broken"}
    ops["Auctioning"]["Loop"] = loop
    ops["Extra"] = {}
    ops["Sniper"]["Scalar"] = 5
    errors, warnings = _errors(db), _warnings(db)
    assert "operation Auctioning/' bad': invalid name" in errors
    assert "LUA ERROR: profile 'Default': operation Sniper/'Scalar' is number" in errors
    assert "Auctioning/'Broken': missing field 'postCap'" in warnings
    assert "missing field 'cancelUndercut'" not in warnings
    assert "field 'duration' is string, expected number" in warnings
    assert "field 'keepQuantity'" not in warnings
    assert "unknown field 'extra'" in warnings
    assert "relationship 'minPrice' -> 'Ghost' points at no operation" in warnings
    assert "circular relationship on 'maxPrice'" in warnings
    assert "unknown module 'Extra'" in warnings


# ---------------------------------------------------------------- apply

PLAN = {
    "profile": "Default",
    "settings": {"g@ @userData@ungroupedItemMode": "base"},
    "operations": [{"module": "Auctioning", "name": "TestPost", "settings": {"postCap": "2"}}],
    "groups": ["Test`Sub"],
    "items": {"Test`Sub": ["i:2318", "i:4234"]},
    "group_operations": [{"group": "Test`Sub", "module": "Auctioning", "operations": ["TestPost"], "override": True}],
}


def test_apply_plan_and_validate(db):
    changes = tsmdb.apply_plan(db, json.loads(json.dumps(PLAN)))
    assert changes == [
        'setting g@ @userData@ungroupedItemMode: "specific" -> "base"',
        'operation Auctioning/TestPost: created with {"postCap": "2"}',
        "group 'Test': created",
        "group 'Test`Sub': created",
        "item i:2318: added to 'Test`Sub'",
        "item i:4234: moved 'Leather' -> 'Test`Sub'",
        "group 'Test`Sub' Auctioning: ['#Default'] (override=False) -> ['TestPost'] (override=True)",
    ]
    report = tsmdb.validate(db)
    assert report["errors"] == [] and report["warnings"] == []
    assert tsmdb.apply_plan(db, json.loads(json.dumps(PLAN))) == []
    assert tsmdb.loads_db(db.to_bytes()).data == tsmdb.canonical(db.data)


def test_apply_plan_removes_operations_and_groups(db):
    tsmdb.apply_plan(db, json.loads(json.dumps(PLAN)))
    tsmdb.create_operation(db, "Auctioning", "Linked", {"relationships": {"postCap": "TestPost"}})
    removal = {
        "remove_operations": [{"module": "Auctioning", "name": "TestPost"},
                              {"module": "Auctioning", "name": "NeverExisted"}],
        "remove_groups": ["Test", "Nowhere"],
        "groups": ["Leather`Reserve"],
        "items": {"Leather`Reserve": ["i:2318"]},
    }
    changes = tsmdb.apply_plan(db, json.loads(json.dumps(removal)))
    assert changes == [
        "operation Auctioning/TestPost: removed, dropped from 1 group(s), cleared relationships ['Linked.postCap']",
        "group 'Test': removed 2 group(s), 2 item(s) ungrouped",
        "group 'Leather`Reserve': created",
        "item i:2318: added to 'Leather`Reserve'",
    ]
    groups = db.data["p@Default@userData@groups"]
    assert "Test" not in groups and "Test`Sub" not in groups
    items = db.data["p@Default@userData@items"]
    assert items.get("i:4234") is None and items["i:2318"] == "Leather`Reserve"
    ops = db.data["p@Default@userData@operations"]["Auctioning"]
    assert "TestPost" not in ops and ops["Linked"]["relationships"] == {}
    report = tsmdb.validate(db)
    assert report["errors"] == []
    assert tsmdb.apply_plan(db, json.loads(json.dumps(removal))) == []
    with pytest.raises(tsmdb.TsmError, match="refusing to remove"):
        tsmdb.apply_plan(db, {"remove_operations": [{"module": "Auctioning", "name": "#Default"}]})
    with pytest.raises(tsmdb.TsmError, match="module not found: 'Auctoning'"):
        tsmdb.apply_plan(db, {"remove_operations": [{"module": "Auctoning", "name": "X"}]})
    with pytest.raises(tsmdb.TsmError, match='"remove_groups" must be a list'):
        tsmdb.apply_plan(db, {"remove_groups": "Leather"})


def test_apply_plan_rejects_unknown_shapes(db):
    with pytest.raises(tsmdb.TsmError, match="unknown plan key"):
        tsmdb.apply_plan(db, {"group": []})
    with pytest.raises(tsmdb.TsmError, match="missing \\['name'\\]"):
        tsmdb.apply_plan(db, {"operations": [{"module": "Auctioning"}]})
    with pytest.raises(tsmdb.TsmError, match="unknown \\['ops'\\]"):
        tsmdb.apply_plan(db, {"group_operations": [{"group": "Leather", "module": "Auctioning", "ops": []}]})
    with pytest.raises(tsmdb.TsmError, match="JSON object"):
        tsmdb.apply_plan(db, [])


def _cli(path, *argv):
    return tsmdb.main(["--file", str(path), *argv])


def test_cli_apply_dry_run_then_real(db_path, tmp_path, capsys):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(PLAN), encoding="utf-8")
    before = db_path.read_bytes()
    assert _cli(db_path, "apply", str(plan_path), "--dry-run") == 0
    out = capsys.readouterr().out
    assert "7 change(s)" in out and "dry run: nothing written" in out
    assert db_path.read_bytes() == before
    assert _cli(db_path, "apply", str(plan_path)) == 0
    assert "wrote" in capsys.readouterr().out
    assert db_path.read_bytes() != before
    assert _cli(db_path, "validate") == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out
    assert _cli(db_path, "apply", str(plan_path)) == 0
    assert "nothing to write" in capsys.readouterr().out
    reloaded = tsmdb.load_db(db_path)
    assert reloaded.data["p@Default@userData@items"] == {"i:4234": "Test`Sub", "i:2318": "Test`Sub"}
    assert "TSMItemInfoDB" in reloaded.suffix


def test_cli_apply_refuses_a_plan_that_breaks_validation(db_path, tmp_path, capsys):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"settings": {"p@Default@userData@items": {"junk": "Leather"}}}), encoding="utf-8")
    before = db_path.read_bytes()
    assert _cli(db_path, "apply", str(plan_path)) == 1
    captured = capsys.readouterr()
    assert "invalid item string" in captured.out and "nothing written" in captured.err
    assert db_path.read_bytes() == before


def test_cli_get_set_and_read_commands(db_path, capsys):
    assert _cli(db_path, "get", "g@ @userData@ungroupedItemMode") == 0
    assert capsys.readouterr().out.strip() == '"specific"'
    assert _cli(db_path, "set", "g@ @userData@ungroupedItemMode", '"base"', "--dry-run") == 0
    assert tsmdb.load_db(db_path).data["g@ @userData@ungroupedItemMode"] == "specific"
    assert _cli(db_path, "set", "g@ @userData@ungroupedItemMode", '"base"') == 0
    assert tsmdb.load_db(db_path).data["g@ @userData@ungroupedItemMode"] == "base"
    capsys.readouterr()
    assert _cli(db_path, "set", "g@ @userData@ungroupedItemMode", "5") == 1
    assert "expected string, got number" in capsys.readouterr().err
    assert _cli(db_path, "set", "g@ @userData@ungroupedItemMode", "base") == 1
    assert "not JSON" in capsys.readouterr().err
    assert _cli(db_path, "get", "g@ @no@such") == 1
    assert "key not found: 'g@ @no@such'" in capsys.readouterr().err
    for command, needle in (("groups", '"Leather"'), ("operations", '"#Default"'), ("inventory", '"i:2318"'),
                            ("accounting", '"csvSales"'), ("roundtrip", "byte-identical to the file: True")):
        assert _cli(db_path, command) == 0
        assert needle in capsys.readouterr().out
    assert _cli(db_path, "accounting", "--summary") == 0
    assert json.loads(capsys.readouterr().out)["TestRealm"]["csvSales"] == {"rows": 2, "malformed": 0, "empty": False}
    assert _cli(db_path, "operations", "Sniper") == 0
    assert list(json.loads(capsys.readouterr().out)) == ["Sniper"]


def test_cli_validate_exit_code(db_path, capsys):
    db = tsmdb.load_db(db_path)
    db.data["_version"] = 1
    tsmdb.save_db(db_path, db)
    assert _cli(db_path, "validate") == 1
    assert "error: WIPE: _version 1 is below the minimum" in capsys.readouterr().out


# ---------------------------------------------------------------- save safety

def _wtf_copy(tmp_path):
    folder = tmp_path / "_forever_" / "WTF" / "Account" / "TESTACCOUNT" / "SavedVariables"
    folder.mkdir(parents=True)
    path = folder / "TradeSkillMaster.lua"
    shutil.copyfile(FIXTURE, path)
    return path


def test_save_refuses_under_wtf_while_wow_runs(tmp_path, monkeypatch, backups):
    path = _wtf_copy(tmp_path)
    before = path.read_bytes()
    db = tsmdb.load_db(path)
    db.data["g@ @userData@ungroupedItemMode"] = "base"
    monkeypatch.setattr(tsmdb, "wow_running", lambda: True)
    with pytest.raises(tsmdb.TsmError, match="Wow.exe is running: refusing to write"):
        tsmdb.save_db(path, db)
    assert path.read_bytes() == before
    assert not backups.exists()
    assert list(path.parent.iterdir()) == [path]


def test_save_under_wtf_backs_up_first(tmp_path, monkeypatch, backups):
    path = _wtf_copy(tmp_path)
    before = path.read_bytes()
    db = tsmdb.load_db(path)
    db.data["g@ @userData@ungroupedItemMode"] = "base"
    monkeypatch.setattr(tsmdb, "wow_running", lambda: False)
    result = tsmdb.save_db(path, db)
    saved = list(backups.iterdir())
    assert len(saved) == 1 and str(saved[0]) == result["backup"]
    assert saved[0].read_bytes() == before
    assert saved[0].name.startswith("TradeSkillMaster-") and saved[0].suffix == ".lua"
    assert tsmdb.load_db(path).data["g@ @userData@ungroupedItemMode"] == "base"
    assert list(path.parent.iterdir()) == [path]


def test_save_outside_wtf_skips_process_check_and_backup(db_path, db, monkeypatch, backups):
    def boom():
        raise AssertionError("process check must not run outside WTF")
    monkeypatch.setattr(tsmdb, "wow_running", boom)
    assert tsmdb.save_db(db_path, db)["backup"] is None
    assert not backups.exists()
    assert tsmdb.save_db(db_path, db, backup=True)["backup"] is not None


def test_cli_write_refused_while_wow_runs(tmp_path, monkeypatch, backups, capsys):
    path = _wtf_copy(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr(tsmdb, "wow_running", lambda: True)
    assert _cli(path, "set", "g@ @userData@ungroupedItemMode", '"base"') == 1
    assert "Wow.exe is running" in capsys.readouterr().err
    assert path.read_bytes() == before
    assert _cli(path, "get", "g@ @userData@ungroupedItemMode") == 0


def test_save_verifies_before_replacing(db_path, db, monkeypatch):
    before = db_path.read_bytes()
    real_load = tsmdb.load_db

    def corrupt_load(path):
        loaded = real_load(path)
        loaded.data["g@ @userData@ungroupedItemMode"] = "tampered"
        return loaded
    monkeypatch.setattr(tsmdb, "load_db", corrupt_load)
    with pytest.raises(tsmdb.TsmError, match="re-parse of .* differs"):
        tsmdb.save_db(db_path, db)
    assert db_path.read_bytes() == before
    assert list(db_path.parent.glob("*tsmdb-tmp*")) == []


def test_save_canonicalises_hand_built_tables(db_path, db):
    db.data["p@Default@userData@groups"]["Leather"]["Auctioning"] = {1: "#Default"}
    db.data["g@ @userData@customPriceSources"] = {"list": []}
    tsmdb.save_db(db_path, db)
    again = tsmdb.load_db(db_path)
    assert again.data["p@Default@userData@groups"]["Leather"]["Auctioning"] == ["#Default"]
    assert again.data["g@ @userData@customPriceSources"] == {"list": {}}


def test_is_under_wtf(tmp_path):
    assert tsmdb.is_under_wtf(tmp_path / "WTF" / "Account" / "x.lua")
    assert tsmdb.is_under_wtf(tmp_path / "wtf" / "x.lua")
    assert not tsmdb.is_under_wtf(tmp_path / "scratch" / "WTF.lua")


class _Completed:
    def __init__(self, stdout, returncode=0):
        self.stdout, self.returncode = stdout, returncode


def test_wow_running_reads_tasklist(monkeypatch):
    monkeypatch.setattr(tsmdb.subprocess, "run", lambda *a, **k: _Completed('"explorer.exe","1"\n"Wow.exe","2"\n'))
    assert tsmdb.wow_running() is True
    monkeypatch.setattr(tsmdb.subprocess, "run", lambda *a, **k: _Completed('"explorer.exe","1"\n"WowVoiceProxy.exe","3"\n'))
    assert tsmdb.wow_running() is False
    monkeypatch.setattr(tsmdb.subprocess, "run", lambda *a, **k: _Completed("", returncode=1))
    with pytest.raises(tsmdb.TsmError, match="tasklist exited 1"):
        tsmdb.wow_running()

    def missing(*args, **kwargs):
        raise FileNotFoundError("tasklist")
    monkeypatch.setattr(tsmdb.subprocess, "run", missing)
    with pytest.raises(tsmdb.TsmError, match="cannot run tasklist"):
        tsmdb.wow_running()


def test_default_live_path(tmp_path, monkeypatch):
    monkeypatch.setenv("WOWF_GAME_DIR", str(tmp_path))
    with pytest.raises(tsmdb.TsmError, match="no live file matches"):
        tsmdb.default_live_path()
    path = _wtf_copy(tmp_path)
    assert pathlib.Path(tsmdb.default_live_path()) == path
    second = tmp_path / "_forever_" / "WTF" / "Account" / "OTHERACCOUNT" / "SavedVariables"
    second.mkdir(parents=True)
    shutil.copyfile(FIXTURE, second / "TradeSkillMaster.lua")
    with pytest.raises(tsmdb.TsmError, match="2 accounts match"):
        tsmdb.default_live_path()


# ---------------------------------------------------------------- profile

APPDATA_FIXTURE = HERE / "fixtures" / "appdata_basic.lua"


def test_profile_summarises_the_fixture(db_path):
    result = tsmdb.profile(db_path, appdata_path=APPDATA_FIXTURE, now=1700050000)
    assert result["file"] == str(db_path)
    assert result["realms"] == {"TestRealm": {"Horde": ["Testalt", "Testchar"]}}
    char = {c["name"]: c for c in result["characters"]}
    assert char["Testchar"]["classKey"] == "ROGUE" and char["Testchar"]["money"] == 123456
    assert char["Testchar"]["professions"]["Leatherworking"] == {"level": 112, "maxLevel": 150, "isSecondary": False}
    assert char["Testchar"]["professions"]["Cooking"]["isSecondary"] is True
    # 40 + 3 in bags, 7 in the bank, 2 on the auction house
    assert char["Testchar"]["inventory"] == {"distinctItems": 3, "totalQuantity": 52}
    assert char["Testalt"]["classKey"] == "WARRIOR" and char["Testalt"]["money"] is None
    assert result["profiles"] == ["Default"]
    assert result["groups"] == {"profile": "Default", "count": 1, "topLevel": ["Leather"], "groupedItems": 1}
    assert result["operations"]["Auctioning"] == 1 and set(result["operations"]) == set(tsmdb.MODULES)
    assert result["customPriceSources"] == ["testsource"]
    sales = result["accounting"]["TestRealm"]["sales"]
    assert sales["rows"] == 2 and sales["totalCopper"] == 2 * 150 + 900
    assert [i["itemString"] for i in sales["topItems"]] == ["i:4234", "i:2318"]
    assert sales["firstDate"] == "2026-11-06"
    assert result["accounting"]["TestRealm"]["buys"]["rows"] == 0
    app = result["appHelper"]
    assert app["installed"] and app["realms"] == ["Test-Horde"] and app["regions"] == ["Test-US"]
    assert app["lastSyncAgeHours"] == pytest.approx(1.7, abs=0.1)
    assert "Testalt - TestRealm: no money recorded" in result["notes"]
    assert any("Testalt - TestRealm: no professions recorded" in n for n in result["notes"])


def test_profile_names_every_missing_piece(tmp_path):
    result = tsmdb.profile(None, appdata_path=tmp_path / "AppData.lua", missing="no live file")
    assert result["file"] is None and "characters" not in result
    assert any(n.startswith("TSM SavedVariables not found (no live file)") for n in result["notes"])
    assert any(n.startswith("AppHelper not installed: no market prices") for n in result["notes"])
    assert result["appHelper"]["installed"] is False


def test_profile_survives_a_bare_file(tmp_path):
    path = tmp_path / "TradeSkillMaster.lua"
    path.write_text('TradeSkillMasterDB = {\n["_version"] = 152,\n}\n', encoding="utf-8")
    result = tsmdb.profile(path, appdata_path=tmp_path / "none.lua")
    assert result["characters"] == [] and result["groups"] is None and result["operations"] is None
    notes = " | ".join(result["notes"])
    assert "_scopeKeys has no char or sync list" in notes
    assert "has no groups table" in notes and "no operations table" in notes
    assert "no accounting data" in notes


def test_profile_unreadable_file_is_a_note(tmp_path):
    path = tmp_path / "TradeSkillMaster.lua"
    path.write_text("not a tsm file", encoding="utf-8")
    result = tsmdb.profile(path, appdata_path=tmp_path / "none.lua")
    assert any(n.startswith("TSM SavedVariables unreadable") for n in result["notes"])


def test_cli_profile_json_and_text(db_path, monkeypatch, capsys):
    monkeypatch.setenv("TSM_APPDATA", str(APPDATA_FIXTURE))
    assert tsmdb.main(["--file", str(db_path), "profile"]) == 0
    assert json.loads(capsys.readouterr().out)["characters"][1]["name"] == "Testchar"
    assert tsmdb.main(["--file", str(db_path), "profile", "--text"]) == 0
    out = capsys.readouterr().out
    assert "TestRealm (Horde): Testalt, Testchar" in out and "Leatherworking 112/150" in out


def test_cli_profile_without_an_install(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WOWF_GAME_DIR", str(tmp_path))
    monkeypatch.delenv("TSM_APPDATA", raising=False)
    assert tsmdb.main(["profile"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["file"] is None and len(result["notes"]) == 2


# ---------------------------------------------------------------- the starter plan

STARTER_PLAN = HERE.parents[2] / "tsm" / "examples" / "starter-plan.json"


def test_starter_plan_applies_cleanly_and_is_idempotent(db):
    plan = json.loads(STARTER_PLAN.read_text(encoding="utf-8"))
    before = tsmdb.validate(db)["errors"]
    changes = tsmdb.apply_plan(db, plan)
    assert changes and not [c for c in changes if c.startswith("warning: ")]
    assert tsmdb.validate(db)["errors"] == before
    assert tsmdb.apply_plan(db, plan) == []
    paths = {g["path"] for g in tsmdb.list_groups(db)}
    assert {"Crafting mats", "Gear BoE", "Consumables", "Vendor trash", "Keep (never post)"} <= paths


def test_cli_starter_plan_dry_run(db_path, capsys):
    raw = db_path.read_bytes()
    assert tsmdb.main(["--file", str(db_path), "apply", str(STARTER_PLAN), "--dry-run"]) == 0
    assert "dry run: nothing written" in capsys.readouterr().out
    assert db_path.read_bytes() == raw
