"""Tests for tools/tsm/skillup.py with synthetic recipe tables and prices (no real data, no network).

    python -I -m pytest tools/tsm/tests/test_skillup.py -q
"""
import csv
import dataclasses
import io
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skillup as S  # noqa: E402

BUILD = "1.60.1.11111"
LEATHER, THREAD, BELT, GLOVES, PATTERN, HIDE, CURED = 10, 2320, 20, 21, 22, 30, 31

TABLES = {
    "SkillLine": [
        {"ID": "165", "DisplayName_lang": "Leatherworking", "ParentSkillLineID": "0"},
        {"ID": "2945", "DisplayName_lang": "Leatherworking", "ParentSkillLineID": "165"},
    ],
    "SpellName": [
        {"ID": "301", "Name_lang": "Cheap Belt"}, {"ID": "302", "Name_lang": "Fancy Gloves"},
        {"ID": "303", "Name_lang": "Old Thing (OLD)"}, {"ID": "304", "Name_lang": "Skin Something"},
        {"ID": "305", "Name_lang": "Cured Hide"},
    ],
    "SkillLineAbility": [
        {"SkillLine": "165", "Spell": "301", "TrivialSkillLineRankLow": "100", "TrivialSkillLineRankHigh": "120", "NumSkillUps": "1", "AcquireMethod": "0"},
        {"SkillLine": "165", "Spell": "302", "TrivialSkillLineRankLow": "130", "TrivialSkillLineRankHigh": "150", "NumSkillUps": "1", "AcquireMethod": "0"},
        {"SkillLine": "165", "Spell": "303", "TrivialSkillLineRankLow": "100", "TrivialSkillLineRankHigh": "200", "NumSkillUps": "1", "AcquireMethod": "0"},
        {"SkillLine": "165", "Spell": "304", "TrivialSkillLineRankLow": "1", "TrivialSkillLineRankHigh": "50", "NumSkillUps": "1", "AcquireMethod": "0"},
        {"SkillLine": "165", "Spell": "305", "TrivialSkillLineRankLow": "20", "TrivialSkillLineRankHigh": "40", "NumSkillUps": "1", "AcquireMethod": "1"},
    ],
    "SpellReagents": [
        {"SpellID": "301", "Reagent_0": str(LEATHER), "ReagentCount_0": "2", "Reagent_1": str(THREAD), "ReagentCount_1": "1"},
        {"SpellID": "302", "Reagent_0": str(LEATHER), "ReagentCount_0": "3"},
        {"SpellID": "303", "Reagent_0": str(LEATHER), "ReagentCount_0": "1"},
        {"SpellID": "305", "Reagent_0": str(HIDE), "ReagentCount_0": "1"},
    ],
    "SpellEffect": [
        {"SpellID": "301", "Effect": "24", "EffectItemType": str(BELT), "EffectBasePointsF": "1"},
        {"SpellID": "302", "Effect": "24", "EffectItemType": str(GLOVES), "EffectBasePointsF": "1"},
        {"SpellID": "305", "Effect": "24", "EffectItemType": str(CURED), "EffectBasePointsF": "1"},
        {"SpellID": "302", "Effect": "6", "EffectItemType": "0", "EffectBasePointsF": "0"},
    ],
    "ItemSparse": [
        {"ID": str(LEATHER), "Display_lang": "Leather", "SellPrice": "5", "BuyPrice": "20", "Stackable": "20", "RequiredSkillRank": "0"},
        {"ID": str(THREAD), "Display_lang": "Thread", "SellPrice": "2", "BuyPrice": "10", "Stackable": "20", "RequiredSkillRank": "0"},
        {"ID": str(BELT), "Display_lang": "Belt", "SellPrice": "50", "BuyPrice": "200", "Stackable": "1", "RequiredSkillRank": "0"},
        {"ID": str(GLOVES), "Display_lang": "Gloves", "SellPrice": "60", "BuyPrice": "240", "Stackable": "1", "RequiredSkillRank": "0"},
        {"ID": str(PATTERN), "Display_lang": "Pattern: Fancy Gloves", "SellPrice": "100", "BuyPrice": "400", "Stackable": "1", "RequiredSkillRank": "100"},
        {"ID": str(HIDE), "Display_lang": "Hide", "SellPrice": "1", "BuyPrice": "4", "Stackable": "20", "RequiredSkillRank": "0"},
        {"ID": str(CURED), "Display_lang": "Cured Hide", "SellPrice": "1", "BuyPrice": "4", "Stackable": "20", "RequiredSkillRank": "0"},
    ],
    "ItemEffect": [{"ID": "900", "TriggerType": "6", "SpellID": "302"}, {"ID": "901", "TriggerType": "0", "SpellID": "301"}],
    "ItemXItemEffect": [{"ID": "1", "ItemEffectID": "900", "ItemID": str(PATTERN)}, {"ID": "2", "ItemEffectID": "901", "ItemID": str(BELT)}],
}


@pytest.fixture
def rd():
    return S.RecipeData.from_tables(TABLES, BUILD)


def prices(rows=None, rd_=None, sell=True, days=2.0):
    base = {LEATHER: {"marketValue": 100}, PATTERN: {"marketValue": 500}}
    base.update(rows or {})
    return S.Prices(base, (rd_ or S.RecipeData.from_tables(TABLES)).items, set(S.VENDOR_REAGENTS), sell, days)


def known(*spells):
    return S.Character(name="Tester", level=110, max_level=150, known=set(spells))


# ---------------------------------------------------------------- chance and colours


def test_chance_follows_the_vanilla_formula():
    r = S.Recipe(1, "x", yellow=100, grey=120)
    assert [S.chance(s, r) for s in (90, 99, 100, 110, 119, 120, 130)] == [1.0, 1.0, 1.0, 0.5, 0.05, 0.0, 0.0]
    assert [S.color(s, r) for s in (99, 100, 110, 120)] == ["orange", "yellow", "green", "grey"]


def test_chance_when_yellow_equals_grey():
    r = S.Recipe(1, "x", yellow=300, grey=300)
    assert S.chance(299, r) == 1.0 and S.chance(300, r) == 0.0


# ---------------------------------------------------------------- recipe data


def test_from_tables_reads_recipes_of_the_parent_skill_line(rd):
    assert rd.skill_line("leatherworking") == 165 and rd.skill_line("165") == 165
    by_spell = {r.spell: r for r in rd.recipes[165]}
    assert sorted(by_spell) == [301, 302, 305]  # 303 is dead (OLD), 304 has no reagents
    belt = by_spell[301]
    assert belt.reagents == {LEATHER: 2, THREAD: 1} and belt.product == BELT and belt.recipe_item is None
    gloves = by_spell[302]
    assert gloves.recipe_item == PATTERN and gloves.learn_rank == 100 and gloves.product == GLOVES
    assert by_spell[305].acquire == 1


def test_unknown_profession_names_the_close_ones(rd):
    with pytest.raises(S.SkillupError, match="no profession named 'leather'.*leatherworking"):
        rd.skill_line("leather")


# ---------------------------------------------------------------- character (TSM SavedVariables)


SV = {
    "s@Alt - Horde - Realm@internalData@playerProfessions": {"Leatherworking": {"level": 60, "maxLevel": 75}},
    "s@Main - Horde - Realm@internalData@playerProfessions": {"Leatherworking": {"level": 109, "maxLevel": 150},
                                                              "Cooking": {"level": 147, "maxLevel": 150}},
    "f@Horde - Realm@internalData@crafts": {
        "c:301": {"profession": "Leatherworking", "players": {"Main": {}}},
        "c:302": {"profession": "Leatherworking", "players": {"Alt": {}}},
    },
    "p@Default@userData@items": {"i:4289": "Materials`Vendor-bought", "i:10": "Materials"},
}


def test_read_character_takes_the_highest_skill_and_its_known_recipes():
    ch = S.read_character(SV, "Leatherworking")
    assert (ch.name, ch.level, ch.max_level, ch.known) == ("Main", 109, 150, {301})
    assert ch.vendor_items == {4289}
    assert S.read_character({**SV, "p@Default@userData@items": {"i:4234": "Materials`Leveling reserve`Keep 50 on main",
                                                                  "i:2319": "Materials`Leveling reserve`Hold 40"}},
                            "Leatherworking").reserve == {4234: 50, 2319: 40}
    alt = S.read_character(SV, "leatherworking", char="alt")
    assert (alt.level, alt.known) == (60, {302})


def test_read_character_says_when_recipes_are_not_recorded():
    ch = S.read_character(SV, "Cooking")
    assert ch.level == 147 and ch.known is None and "has not recorded" in ch.note
    assert "no First Aid skill" in S.read_character(SV, "First Aid").note


def test_read_character_warns_when_recipes_belong_to_someone_else():
    sv = dict(SV)
    sv["f@Horde - Realm@internalData@crafts"] = {"c:302": {"profession": "Leatherworking", "players": {"Alt": {}}}}
    ch = S.read_character(sv, "Leatherworking")
    assert ch.name == "Main" and ch.known is None and "none for Main" in ch.note


def test_unreadable_saved_variables_is_a_note_not_a_crash(tmp_path):
    bad = tmp_path / "TradeSkillMaster.lua"
    bad.write_bytes(b"TradeSkillMasterDB = {")
    for path in (bad, tmp_path / "missing.lua"):
        ch = S.load_character(path, "Leatherworking")
        assert ch.level is None and ch.known is None and "unreadable" in ch.note
    assert "not found" in S.load_character(None, "Leatherworking").note


# ---------------------------------------------------------------- prices


def test_material_price_vendor_then_house_then_region(rd):
    p = prices({30: {"regionMarketValue": 7}}, rd)
    assert p.material(THREAD) == (10, "vendor")
    assert p.material(LEATHER) == (100, "ah")
    assert p.material(30) == (7, "region")
    assert p.material(31) == (None, "none")


def test_product_passes_or_fails_the_post_test(rd):
    fast = {BELT: {"marketValue": 2000, "regionSale": 1800, "regionSaleRate": 0.5, "regionSoldPerDay": 10}}
    vendor, sell, takes = prices(fast, rd).product(BELT)
    # 0.95 * 1800 - 50 * (1 + 0.3 * (1 / 0.5 - 1)) = 1710 - 65 = 1645 gain; +50 vendor
    assert vendor == 50 and sell == pytest.approx(1695) and takes == 20
    slow = {BELT: {"marketValue": 300, "regionSale": 300, "regionSaleRate": 0.1, "regionSoldPerDay": 0.2}}
    assert prices(slow, rd).product(BELT) == (50, None, 0.0)  # gain per stack under 50s on a slow seller
    assert prices(fast, rd, sell=False).product(BELT) == (50, None, 0.0)
    assert prices({}, rd).product(None) == (0.0, None, 0.0)


# ---------------------------------------------------------------- planning


def test_buys_the_pattern_when_that_is_cheaper(rd):
    out = S.report(rd, "Leatherworking", 110, 120, prices(rd_=rd), known(301))
    assert [r["recipe"] for r in out["rows"]] == ["Fancy Gloves"]  # orange the whole way: 10 crafts
    row = out["rows"][0]
    assert row["crafts"] == 10 and row["materials"] == {"Leather": 30} and "Pattern: Fancy Gloves" in row["source"]
    assert out["recipeCost"] == 500 and out["craftCost"] == 10 * (300 - 60) and out["total"] == 2900


def test_keeps_the_known_recipe_when_the_pattern_is_dear(rd):
    out = S.report(rd, "Leatherworking", 110, 120, prices({PATTERN: {"marketValue": 100000}}, rd), known(301))
    assert [r["recipe"] for r in out["rows"]] == ["Cheap Belt"] and out["recipeCost"] == 0
    expected = sum(20 / (120 - s) for s in range(110, 120))  # 1 / chance per level
    assert out["rows"][0]["expectedCrafts"] == pytest.approx(expected, abs=0.01)
    assert out["total"] == round(expected * (200 + 10 - 50))


# ---------------------------------------------------------------- luck (the addon's planner rule 1)


def test_craft_spread_sums_geometric_draws_per_level():
    r = S.Recipe(1, "x", yellow=100, grey=120)
    mean, var = S.craft_spread(110, 120, r)
    ps = [(120 - s) / 20 for s in range(110, 120)]
    assert mean == pytest.approx(sum(1 / p for p in ps)) and var == pytest.approx(sum((1 - p) / p ** 2 for p in ps))
    assert S.craft_spread(90, 100, r) == (10.0, 0.0)  # orange: one craft a point, no spread
    assert S.craft_spread(110.5, 111, r) == pytest.approx((0.5 / 0.5, 0.5 * 0.5 / 0.25))  # part of a level by its share
    assert S.craft_spread(118, 125, r)[0] == pytest.approx(20 / 2 + 20 / 1)  # stops where the recipe greys
    two = S.Recipe(2, "y", yellow=100, grey=120, skillups=2)
    assert S.craft_spread(110, 111, two) == (1.0, 0.0)  # chance * NumSkillUps is capped at 1


def test_plan_levels_expects_the_same_crafts_as_craft_spread():
    # NumSkillUps 2 with chance 0.8: both count one craft a point (success capped at 1), as the addon does
    two = S.Recipe(2, "y", yellow=100, grey=120, skillups=2)
    o = S.Option(two, "known", {}, 0.0)
    levels = S.plan_levels([o], 104, 108, True)
    assert [c for _, _, c in levels] == pytest.approx([1.0] * 4)
    assert sum(c for _, _, c in levels) == pytest.approx(S.craft_spread(104, 108, two)[0])


def test_luck_crafts_is_ceil_of_mean_plus_z_sd():
    mean, var = 30.2, 40.0
    assert S.luck_crafts(mean, var) == math.ceil(30.2 + 1.2816 * math.sqrt(40))  # p90 by default
    assert S.luck_crafts(mean, var, 50) == 31 and S.luck_crafts(mean, var, 99) == math.ceil(30.2 + 2.3263 * math.sqrt(40))
    assert S.luck_crafts(0.2, 0.0) == 1 and S.luck_crafts(10.0, 0.0) == 10


def test_rows_buy_for_the_luck_percentile_not_the_mean(rd):
    p = prices({PATTERN: {"marketValue": 100000}}, rd)
    out = S.report(rd, "Leatherworking", 110, 120, p, known(301))
    ps = [(120 - s) / 20 for s in range(110, 120)]
    mean, var = sum(1 / x for x in ps), sum((1 - x) / x ** 2 for x in ps)
    row = out["rows"][0]
    p90 = math.ceil(mean + 1.2816 * math.sqrt(var))
    assert row["crafts"] == p90 > math.ceil(mean) and row["expectedCrafts"] == pytest.approx(mean, abs=0.01)
    assert row["materials"] == {"Leather": 2 * p90, "Thread": p90} and out["luck"] == 90
    assert out["shopping"][0]["need"] == 2 * p90
    assert out["total"] == round(mean * (200 + 10 - 50))  # the cost stays at the mean
    assert S.report(rd, "Leatherworking", 110, 120, p, known(301), luck=50)["rows"][0]["crafts"] == math.ceil(mean)
    assert S.report(rd, "Leatherworking", 110, 120, p, known(301), luck=99)["rows"][0]["crafts"] > p90
    with pytest.raises(S.SkillupError, match="luck 85"):
        S.report(rd, "Leatherworking", 110, 120, p, known(301), luck=85)


def test_pattern_waits_for_its_skill_rank(rd):
    out = S.report(rd, "Leatherworking", 95, 105, prices(rd_=rd), known(301))
    assert {r["recipe"] for r in out["rows"]} == {"Cheap Belt"}


def test_trainer_recipes_only_from_their_yellow_threshold(rd):
    ch = known()  # knows nothing: the belt is a trainer recipe, the gloves need the pattern
    out = S.report(rd, "Leatherworking", 95, 101, prices({PATTERN: {"marketValue": 10 ** 9}}, rd), ch)
    assert out["gaps"] == ["95-100"] and out["rows"][-1]["recipe"] == "Cheap Belt" and out["rows"][-1]["source"] == "trainer"
    text = S.render(out)  # the gap row renders with every column
    assert "95-100   (nothing priced)" in text and "gaps: 95-100" in text


def test_a_free_craft_wins_on_fewest_crafts_not_on_profit_per_point(rd):
    # the belt sells at a profit, the gloves cost: a free craft beats a paid one even at 2 crafts a point
    rows = {BELT: {"marketValue": 5000, "regionSale": 5000, "regionSaleRate": 0.9, "regionSoldPerDay": 1000}}
    out = S.report(rd, "Leatherworking", 110, 112, prices(rows, rd), known(301, 302))
    assert out["rows"][0]["recipe"] == "Cheap Belt"
    # both free: fewest crafts first, so the orange gloves (1 a point) beat the green belt (2 a point)
    rows[GLOVES] = {"marketValue": 5000, "regionSale": 5000, "regionSaleRate": 0.9, "regionSoldPerDay": 1000}
    out = S.report(rd, "Leatherworking", 110, 112, prices(rows, rd), known(301, 302))
    assert out["rows"][0]["recipe"] == "Fancy Gloves" and out["total"] < 0


def test_effort_charge_stops_a_profitable_low_chance_craft_from_winning(rd):
    # the belt pays for itself at 2 crafts a point, the gloves cost 15c at 1 a point: free wins without an effort
    # charge; with 20c a craft the belt costs 40c a point and the gloves 35c
    rows = {LEATHER: {"marketValue": 25}, BELT: {"marketValue": 5000, "regionSale": 5000, "regionSaleRate": 0.9,
                                                  "regionSoldPerDay": 1000}}
    out = S.report(rd, "Leatherworking", 110, 111, prices(rows, rd), known(301, 302))
    assert out["rows"][0]["recipe"] == "Cheap Belt"
    out = S.report(rd, "Leatherworking", 110, 111, prices(rows, rd), known(301, 302), effort=20)
    assert out["rows"][0]["recipe"] == "Fancy Gloves"


def test_market_volume_caps_what_counts_as_sold(rd):
    # the belt sells high but the region takes 1 a day: two days' worth sell, the rest is vendored
    rows = {BELT: {"marketValue": 5000, "regionSale": 5000, "regionSaleRate": 0.9, "regionSoldPerDay": 1}}
    out = S.report(rd, "Leatherworking", 110, 120, prices(rows, rd), known(301))
    row = out["rows"][0]
    assert row["recipe"] == "Cheap Belt" and row["backHow"] == "sell 2, vendor rest"
    sell_each = 50 + 0.95 * 5000 - 50 * (1 + 0.3 * (1 / 0.9 - 1))
    assert row["back"] == round(2 * sell_each + (row["expectedCrafts"] - 2) * 50)


def test_reprice_drops_a_recipe_that_only_pays_when_over_sold(rd):
    # gloves look like a 45s profit each, enough to pay a 1g20s pattern, but only 1 sells: do not buy the pattern
    rows = {GLOVES: {"marketValue": 5000, "regionSale": 5000, "regionSaleRate": 0.9, "regionSoldPerDay": 0.5},
            PATTERN: {"marketValue": 12000}}
    out = S.report(rd, "Leatherworking", 110, 120, prices(rows, rd), known(301))
    assert {r["recipe"] for r in out["rows"]} == {"Cheap Belt"} and out["recipeCost"] == 0


def test_intermediate_counts_at_the_cheaper_of_buying_or_crafting(rd):
    tables = json.loads(json.dumps(TABLES))
    tables["SpellReagents"][1] = {"SpellID": "302", "Reagent_0": str(CURED), "ReagentCount_0": "2"}
    rd2 = S.RecipeData.from_tables(tables)
    p = prices({CURED: {"marketValue": 500}, HIDE: {"marketValue": 30}}, rd2)
    options, _ = S.build_options(rd2.recipes[165], p, known(301, 302, 305))
    gloves = next(o for o in options if o.recipe.spell == 302)
    assert gloves.mats == {HIDE: 2} and gloves.mat_cost == 60  # crafting 2 Cured Hide from Hide beats buying them
    assert gloves.crafted == {CURED: 2}
    # a small saving is not worth the crafting: 10% cheaper to craft -> buy the intermediate
    p = prices({CURED: {"marketValue": 33}, HIDE: {"marketValue": 30}}, rd2)
    options, _ = S.build_options(rd2.recipes[165], p, known(301, 302, 305))
    gloves = next(o for o in options if o.recipe.spell == 302)
    assert gloves.mats == {CURED: 2} and gloves.crafted == {} and gloves.mat_cost == 66


def test_whole_path_materials_next_to_the_reserve(rd):
    ch = known(301)
    ch.reserve = {LEATHER: 300, HIDE: 20, 999: 5}
    out = S.report(rd, "Leatherworking", 110, 120, prices({PATTERN: {"marketValue": 100000}}, rd), ch)
    shop = {m["item"]: (m["need"], m["reserve"]) for m in out["shopping"]}
    crafts = out["rows"][0]["crafts"]
    assert shop == {"Leather": (2 * crafts, 300), "Thread": (crafts, None)}
    assert out["reserveUnused"] == []  # Hide and item 999 are no reagent of a priced recipe here
    text = S.render(out)
    assert "material, whole path" in text and f"Leather               {2 * crafts:>4}      300" in text


def test_recipes_without_a_material_price_are_skipped(rd):
    p = S.Prices({}, rd.items, set(), True)  # no leather price at all
    out = S.report(rd, "Leatherworking", 110, 120, p, known(301))
    assert out["gaps"] == ["110-120"]
    assert {s["name"] for s in out["skipped"]} >= {"Cheap Belt", "Fancy Gloves"}
    assert all("no price for Leather" in s["why"] for s in out["skipped"] if s["name"] != "Cured Hide")


# ---------------------------------------------------------------- CLI


def _csv(rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    buf = io.StringIO()
    w = csv.DictWriter(buf, keys, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _b32(n: int) -> str:
    digits, out = "0123456789ABCDEFGHIJKLMNOPQRSTUV", ""
    while True:
        n, d = divmod(n, 32)
        out = digits[d] + out
        if not n:
            return out


def test_main_end_to_end(tmp_path, capsys, monkeypatch):
    folder = tmp_path / "cache" / "wago" / BUILD
    folder.mkdir(parents=True)
    for table, rows in TABLES.items():
        (folder / f"{table}.enUS.csv").write_text(_csv(rows), encoding="utf-8")
    appdata = tmp_path / "AppData.lua"
    appdata.write_text(
        'select(2, ...).LoadData("AUCTIONDB_NON_COMMODITY_SCAN_STAT","Test-Horde",[[return {downloadTime=1700040000,'
        f'fields={{"itemString","marketValue"}},data={{{{{LEATHER},{_b32(100)}}},{{{PATTERN},{_b32(500)}}}}}}}]])\n', encoding="utf-8")
    monkeypatch.setattr(S.A, "default_saved_vars", lambda: None)
    monkeypatch.delenv("TSM_SAVED_VARS", raising=False)
    args = ["leatherworking", "110", "120", "--appdata", str(appdata), "--cache-dir", str(tmp_path / "cache"), "--offline"]
    assert S.main(args + ["--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["total"] == 2900 and doc["rows"][0]["recipe"] == "Fancy Gloves" and doc["knownRecorded"] is False
    assert S.main(args) == 0
    text = capsys.readouterr().out
    assert "Fancy Gloves" in text and "total 29s00c" in text
    assert S.main(["leatherworking", "--appdata", str(appdata), "--cache-dir", str(tmp_path / "cache"), "--offline"]) == 2
    assert "give the skill range" in capsys.readouterr().err
    # no target: the top rank cap, as the addon plans, not TSM's recorded cap; --luck reaches the report
    assert S.main(["leatherworking", "110", "--json", "--luck", "95"] + args[3:]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["to"] == S.TOP_RANK_CAP == 300 and doc["luck"] == 95
    with pytest.raises(SystemExit):
        S.main(args + ["--luck", "85"])  # only the addon's percentiles
    assert S.build_parser().parse_args(["cooking"]).luck == S.LUCK == 90


def test_default_target_is_tsms_cap_when_above_the_top_rank(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(S, "load_character", lambda *a, **k: S.Character(name="Tester", level=110, max_level=375))
    folder = tmp_path / "cache" / "wago" / BUILD
    folder.mkdir(parents=True)
    for table, rows in TABLES.items():
        (folder / f"{table}.enUS.csv").write_text(_csv(rows), encoding="utf-8")
    appdata = tmp_path / "AppData.lua"
    appdata.write_text(
        'select(2, ...).LoadData("AUCTIONDB_NON_COMMODITY_SCAN_STAT","Test-Horde",[[return {downloadTime=1700040000,'
        f'fields={{"itemString","marketValue"}},data={{{{{LEATHER},{_b32(100)}}}}}}}]])\n', encoding="utf-8")
    args = ["leatherworking", "--appdata", str(appdata), "--cache-dir", str(tmp_path / "cache"), "--offline", "--json"]
    assert S.main(args) == 0, capsys.readouterr().err
    doc = json.loads(capsys.readouterr().out)
    assert doc["from"] == 110 and doc["to"] == 375


def test_offline_without_cache_names_the_missing_file(tmp_path, capsys):
    assert S.main(["leatherworking", "1", "2", "--cache-dir", str(tmp_path), "--build", BUILD, "--offline"]) == 2
    assert "is not cached and --offline given" in capsys.readouterr().err


# ---------------------------------------------------------------- the addon's other planner rules


def _opt(spell, net, mats=None, yellow=500, grey=600, source="known"):
    """An option orange (one craft a point) everywhere below `yellow`, net cost `net` per craft."""
    return S.Option(S.Recipe(spell, f"r{spell}", yellow, grey), source, mats or {}, float(net))


def test_flat_chance_is_the_colour_band_guess():
    r = S.Recipe(1, "x", yellow=100, grey=120)  # green from 110
    assert [S.flat_chance(s, r) for s in (99, 100, 109, 110, 119, 120)] == [1, 0.75, 0.75, 0.25, 0.25, 0]
    assert S.CHANCE_MODELS == {"formula": S.chance, "flat": S.flat_chance}
    # craft_spread and plan_levels take the model: flat yellow is 0.75 a craft
    assert S.craft_spread(100, 101, r, S.flat_chance) == pytest.approx((1 / 0.75, 0.25 / 0.75 ** 2))


def test_report_plans_with_the_flat_model_and_tags_rows_that_depend_on_the_formula(rd):
    p = prices({PATTERN: {"marketValue": 100000}}, rd)
    out = S.report(rd, "Leatherworking", 110, 120, p, known(301), chance_model="flat")
    ps = [0.25] * 10  # 110-119 is all green for 100/120
    assert out["chanceModel"] == "flat" and out["rows"][0]["crafts"] == S.luck_crafts(40, sum((1 - x) / x ** 2 for x in ps))
    assert "colour band" in out["assumptions"][0]
    assert out["rows"][0]["chanceModel"] is False  # one recipe: both models pick it
    with pytest.raises(S.SkillupError, match="chance model"):
        S.report(rd, "Leatherworking", 110, 120, p, known(301), chance_model="guess")


def test_the_two_chance_models_can_pick_different_recipes():
    # at 112: formula A 18/30 = 0.6 (16.7 a point) against B 88/100 (13.6): B. Flat: A yellow 0.75 (13.3), B 0.75 (16): A
    a, b = _opt(1, 10, yellow=100, grey=130), _opt(2, 12, yellow=100, grey=200)
    assert S.plan_levels([a, b], 112, 113, True)[0][1] is b
    assert S.plan_levels([a, b], 112, 113, True, chance_fn=S.flat_chance)[0][1] is a


def test_rule_5_turns_a_one_point_island_into_the_surrounding_recipe():
    a, b = _opt(1, 100), _opt(2, 95)  # B saves 5 on one level: under 10% of the 195 left
    levels = [(100, a, 1.0), (101, a, 1.0), (102, b, 1.0), (103, a, 1.0)]
    out = S.smooth(levels, True)
    assert [o.recipe.spell for _, o, _ in out] == [1, 1, 1, 1]
    cheap = _opt(3, 50)  # saves 50 of the 150 left: kept
    assert [o.recipe.spell for _, o, _ in S.smooth([(100, a, 1.0), (101, cheap, 1.0), (102, a, 1.0)], True)] == [1, 3, 1]
    # two points of B are not an island (ISLAND = 1)
    two = [(100, a, 1.0), (101, b, 1.0), (102, b, 1.0), (103, a, 1.0)]
    assert [o.recipe.spell for _, o, _ in S.smooth(two, True)] == [1, 2, 2, 1]
    # A gives no skill on the island level (grey there): B stays
    grey = _opt(4, 100, yellow=101, grey=102)
    out = S.smooth([(100, grey, 1.0), (102, b, 1.0), (103, grey, 1.0)], True)
    assert [o.recipe.spell for _, o, _ in out] == [4, 2, 4]


def test_plan_levels_applies_rule_5():
    # B is cheaper only at 102 (before that it is not learnable, after it greys): one point between two runs of A
    a = _opt(1, 100)
    b = S.Option(S.Recipe(2, "b", 102, 103), "recipe item", {}, 95.0)
    b.recipe.recipe_item, b.recipe.learn_rank = 99, 102
    levels = S.plan_levels([a, b], 100, 105, True)
    assert [o.recipe.spell for _, o, _ in levels] == [1] * 5


def test_unchecked_trainer_recipes_are_not_planned(rd):
    p = prices(rd_=rd)
    ch = known()  # every LW recipe is a trainer one here, except the pattern's
    opts, _ = S.build_options(rd.recipes[165], p, ch, trainer_seen={301})
    by = {o.recipe.spell: o for o in opts}
    assert by[301].unchecked is False and by[302].unchecked is False  # 302 comes from a recipe item, never unchecked
    opts, _ = S.build_options(rd.recipes[165], p, ch, trainer_seen={"cheap belt"})  # matched by lowercased name too
    assert {o.recipe.spell: o.unchecked for o in opts}[301] is False
    opts, _ = S.build_options(rd.recipes[165], p, ch, trainer_seen=set())
    belt = {o.recipe.spell: o for o in opts}[301]
    assert belt.unchecked is True
    assert not S.available(belt, 200, True)  # a shortcut in the addon, never a plan row
    assert S.available(dataclasses.replace(belt, unchecked=False), 200, True)
    assert all(not o.unchecked for o in S.build_options(rd.recipes[165], p, ch)[0])  # never read: nothing unchecked
    out = S.report(rd, "Leatherworking", 100, 105, p, ch, addon=S.AddonState(trainer_seen={165: set()}))
    assert all(not r.get("unchecked") for r in out["rows"])


ADDON_SV = b"""
SkillupHelperDB = {
\t["ranks"] = {
\t\t[165] = {
\t\t\t[225] = {["name"] = "Expert", ["cap"] = 225, ["skill"] = 125, ["level"] = 10, ["cost"] = 5000, ["where"] = "trainer"},
\t\t\t[300] = {["name"] = "Artisan", ["cap"] = 300, ["skill"] = 200, ["level"] = 35, ["where"] = "trainer"},
\t\t},
\t},
\t["trainerSeen"] = {[165] = {[301] = true, ["fancy gloves"] = true}},
}
"""


def test_addon_saved_variables_give_ranks_and_trainer_seen(tmp_path):
    f = tmp_path / "SkillupHelper.lua"
    f.write_bytes(ADDON_SV)
    st = S.load_addon_state(f)
    assert st.note is None and [r["cap"] for r in st.ranks[165]] == [225, 300]
    assert st.ranks[165][0] == {"name": "Expert", "cap": 225, "skill": 125, "level": 10, "cost": 5000, "where": "trainer"}
    assert st.trainer_seen == {165: {301, "fancy gloves"}}
    assert "not found" in S.load_addon_state(None).note
    bad = tmp_path / "bad.lua"
    bad.write_bytes(b"SkillupHelperDB = {")
    assert "unreadable" in S.load_addon_state(bad).note
    bad.write_bytes(b"Other = {}")
    assert "no SkillupHelperDB" in S.load_addon_state(bad).note


def test_cap_model_trains_ranks_and_stops_at_a_level_block():
    ranks = [{"name": "Expert", "cap": 225, "skill": 125, "level": 10, "cost": 5000, "where": "trainer"},
             {"name": "Artisan", "cap": 300, "skill": 200, "level": 35, "cost": None, "where": "trainer"}]
    m = S.cap_model(ranks, 150, 300, level=20)
    assert [u["name"] for u in m["rankUps"]] == ["Expert"] and m["rankUps"][0]["by"] == 150
    assert m["capBlock"]["name"] == "Artisan" and m["capBlock"]["by"] == 225 and m["cap"] == 225
    m = S.cap_model(ranks, 150, 300, level=40)
    assert [u["by"] for u in m["rankUps"]] == [150, 225] and m["capBlock"] is None and m["cap"] == 300
    assert S.cap_model(ranks, 150, 300)["cap"] == 300  # level unknown: no block
    special = [dict(ranks[0], where="special")]
    assert S.cap_model(special, 150, 300)["capBlock"]["reason"] == "special"
    assert S.cap_model(ranks[:1], 150, 300)["cap"] == 225  # ranks read: stop at the highest one learned
    assert S.cap_model([], 150, 300) == {"rankUps": [], "capBlock": None, "cap": 300}  # none read: skillup.py's 300


def test_report_shows_rank_ups_and_the_level_block(rd):
    p = prices({PATTERN: {"marketValue": 100000}}, rd)
    ch = S.Character(name="Tester", level=110, max_level=115, known={301})
    addon = S.AddonState(ranks={165: [{"name": "Expert", "cap": 118, "skill": 100, "level": 50, "cost": None, "where": "trainer"}]})
    out = S.report(rd, "Leatherworking", 110, 120, p, ch, addon=addon, level=20)
    assert out["to"] == 115 and out["capBlock"]["reason"] == "level" and out["rows"][-1]["to"] == 115
    assert "stop at 115: Expert (cap 118) needs level 50, you are 20" in S.render(out)
    out = S.report(rd, "Leatherworking", 110, 120, p, ch, addon=addon, level=60)
    assert out["to"] == 118 and out["rankUps"][0]["by"] == 115 and "train Expert (cap 118) before 115" in S.render(out)
    # the highest rank read stops the plan, and says so
    assert out["rankStop"] == 118 and "stop at 118: the highest rank read" in S.render(out)
    # blocked at the start: no rows for skill the character cannot gain, an error naming the rank
    with pytest.raises(S.SkillupError, match="Expert \\(cap 118\\) needs level 50"):
        S.report(rd, "Leatherworking", 115, 120, p, ch, addon=addon, level=20)
    with pytest.raises(S.SkillupError, match="highest rank read"):
        S.report(rd, "Leatherworking", 118, 120, p, ch, addon=addon, level=60)


def test_trainer_seen_keys_numeric_in_any_form():
    st = S.read_addon_state({"trainerSeen": {165.0: {301.0: True, "302": True, "Fancy Gloves": True, 303: False}}})
    assert st.trainer_seen == {165: {301, 302, "fancy gloves"}}


def test_read_character_reads_bags_and_bank_of_that_character():
    sv = {**SV, "s@Main - Horde - Realm@internalData@bagQuantity": {"i:10": 7, "i:2320": 2},
          "s@Main - Horde - Realm@internalData@bankQuantity": {"i:10": 3},
          "s@Main - Horde - Realm@internalData@mailQuantity": {"i:10": 50},
          "s@Alt - Horde - Realm@internalData@bagQuantity": {"i:10": 99}}
    assert S.read_character(sv, "Leatherworking").stock == {10: 10, 2320: 2}
    assert S.read_character(sv, "leatherworking", char="alt").stock == {10: 99}


def _belt_need(lo, hi):
    ps = [(120 - s) / 20 if s >= 100 else 1 for s in range(lo, hi)]
    return 2 * S.luck_crafts(sum(1 / x for x in ps), sum((1 - x) / x ** 2 for x in ps))


def test_rows_take_their_stock_first_and_buy_the_rest(rd):
    p = prices({PATTERN: {"marketValue": 100000}}, rd)
    need = _belt_need(110, 120)
    out = S.report(rd, "Leatherworking", 110, 120, p, known(301), stock={LEATHER: 5})
    row = out["rows"][0]
    assert row["fromStock"] == {"Leather": 5} and row["buy"]["Leather"] == need - 5 and row["stock"] == "mixed"
    assert out["shopping"][0] == {"item": "Leather", "itemId": LEATHER, "need": need, "stock": 5, "buy": need - 5,
                                  "reserve": None}
    assert "| stock 5 Leather" in S.render(out) and out["spares"] == []
    assert out["buyCost"] == (need - 5) * 100 + (need // 2) * 10  # leather at market, thread at the vendor
    out = S.report(rd, "Leatherworking", 110, 120, p, known(301), stock={LEATHER: need + 7, 999: 4})
    assert out["rows"][0]["buy"] == {"Thread": need // 2} and out["rows"][0]["stock"] == "stock"  # thread is a vendor item
    assert out["spares"] == [{"item": "Leather", "itemId": LEATHER, "spare": 7}]  # 999 is no reagent: not listed
    no = S.report(rd, "Leatherworking", 110, 120, p, known(301))
    assert no["stockUsed"] is False and no["spares"] == [] and no["rows"][0]["fromStock"] == {}


def test_earmarked_stock_is_never_given_to_a_spare_option():
    leather, hide = 10, 30
    items = {leather: {"name": "Leather", "sell": 5}, hide: {"name": "Hide", "sell": 1}}
    p = S.Prices({leather: {"marketValue": 100}, hide: {"marketValue": 120}}, items, set())
    a = _opt(1, 100, {leather: 1})
    b = _opt(2, 120, {hide: 1})  # dear at buy price, cheap at salvage (60)
    levels = S.plan_levels([a, b], 100, 105, True)
    assert all(o is a for _, o, _ in levels)
    # every Leather is earmarked for A's rows: B may not use any, and Hide is not owned
    out, alloc, spares = S.stock_pass(levels, [a, b], {leather: 5}, p, True)
    assert out == levels and alloc == {} and spares == {}
    # two spare Hides: B takes two levels (one craft each at orange, no spread), the earliest first on a tie
    out, alloc, spares = S.stock_pass(levels, [a, b], {leather: 5, hide: 2}, p, True)
    assert [o.recipe.spell for _, o, _ in out] == [2, 2, 1, 1, 1]
    assert alloc == {0: {hide: 1.0}, 1: {hide: 1.0}} and spares[hide] == pytest.approx(0) and leather not in spares
    # one Leather beyond A's need is a spare, but B does not use Leather: nothing changes for it
    out, alloc, spares = S.stock_pass(levels, [a, b], {leather: 6}, p, True)
    assert alloc == {} and spares == {leather: 1}


def test_a_spare_option_takes_a_level_only_when_spares_cover_its_bad_luck_crafts():
    hide = 30
    items = {hide: {"name": "Hide", "sell": 1}}
    p = S.Prices({hide: {"marketValue": 120}}, items, set())
    a = _opt(1, 100)
    b = S.Option(S.Recipe(2, "b", 100, 104), "known", {hide: 1}, 120.0)  # yellow: chance 1, .75, .5, .25 at 100-103
    levels = [(s, a, 1.0) for s in range(100, 104)]
    out, alloc, _ = S.stock_pass(levels, [a, b], {hide: 1}, p, True)
    # 100 needs 1 craft (chance 1); 101 needs 1.33 + spread > 1 Hide left: only level 100 is taken
    assert [o.recipe.spell for _, o, _ in out] == [2, 1, 1, 1] and sum(q for a_ in alloc.values() for q in a_.values()) <= 1
