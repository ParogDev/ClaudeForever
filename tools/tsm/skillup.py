#!/usr/bin/env python3
"""Plan the cheapest way to level a profession from one skill to another, at your auction house prices.

    python -I tools/tsm/skillup.py leatherworking 100 150
    python -I tools/tsm/skillup.py cooking            # from TSM's recorded skill to 300 (or TSM's cap if higher)
    python -I tools/tsm/skillup.py cooking --luck 95  # crafts and materials for a p95 run (default p90)
    python -I tools/tsm/skillup.py "first aid" 150 225 --json

Sources (docs/tsm/skillup.md has the details and the assumptions):
- Recipes, reagents, products and the yellow and grey thresholds: wago.tools DB2 exports of the Forever client (`wowf`):
  SkillLine, SkillLineAbility (TrivialSkillLineRankLow = yellow, TrivialSkillLineRankHigh = grey, NumSkillUps),
  SpellReagents, SpellEffect (effect 24 creates the item), SpellName, ItemSparse, ItemEffect and ItemXItemEffect (which
  recipe item teaches which spell, and the skill it needs). Cached next to appdata.py's tables.
- Prices: the TSM desktop app's AppData.lua through appdata.py. Materials at your house's market value (DBMarket, then
  DBMinBuyout, then the region market value, marked ~). Vendor-sold reagents at the vendor price.
- What you know and your current skill: TSM's SavedVariables (`internalData@crafts`, `internalData@playerProfessions`),
  read only.

Skill-up chance: 1 below yellow, 0 at grey, and (grey - skill) / (grey - yellow) in between (green starts halfway). That
is the formula players datamined from the vanilla client; it is an assumption for Forever.

Crafts and materials per row cover the 90th percentile of the crafts the row takes (--luck), not the mean, as the
SkillupHelper addon's planner buys; the costs stay at the mean.

Optional: when the SkillupHelper addon (https://github.com/ParogDev/SkillupHelper) is installed, its SavedVariables
(trainer ranks, trainers seen) are read too; without it that part of the report is a note.
Recipe tables download once from wago.tools into %LOCALAPPDATA%\\ClaudeForever\\tsm-cache\\wago\\<build>\\
(TSM_CACHE_DIR or --cache-dir override; --offline never downloads).

Exit code 2 = a broken link, named on stderr.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appdata as A  # noqa: E402

RECIPE_TABLES = ("SkillLine", "SkillLineAbility", "SpellReagents", "SpellEffect", "SpellName", "ItemSparse", "ItemEffect",
                 "ItemXItemEffect")
EFFECT_CREATE_ITEM = 24
TRIGGER_LEARN = 6  # ItemEffect.TriggerType: the item teaches SpellID
DEAD_NAME = re.compile(r"\b(OLD|DEP|DEPRECATED|TEST|UNUSED|NYI)\b|^zz", re.IGNORECASE)

# Reagents vendors sell (thread, dye, salt, spices, water, milk, vials). Used together with the items in your TSM group
# "Materials > Vendor-bought" when that is readable. Price: ItemSparse.BuyPrice per item.
VENDOR_REAGENTS = {
    2320, 2321, 4291, 8343, 14341,  # threads
    2324, 2604, 2605, 4340, 4341, 4342, 6260, 6261, 2325, 10290,  # bleach and dyes
    4289, 2678, 2692, 3713, 159, 1179, 17194, 30817,  # salt, spices, water, milk, flour
    3371, 3372, 8925, 18256,  # vials
}

# Recipes the client data calls trainer recipes but that no ordinary profession trainer teaches: a special NPC or a
# dungeon teacher. Curated by hand, keyed by lowercased recipe name (no spell ID guessed); add one only with a source.
# Goldthorn Tea: a player report places its teacher in a dungeon; the NPC is not confirmed.
SPECIAL_TEACHERS = {
    "goldthorn tea": "a special teacher in a dungeon (NPC unconfirmed)",
}


def special_teacher(name: str | None) -> str | None:
    """Who teaches a special recipe, or None for an ordinary one."""
    return SPECIAL_TEACHERS.get((name or "").strip().lower())


def recipe_source(r: "Recipe") -> str:
    """How a recipe is learned from client data plus SPECIAL_TEACHERS: item, auto, special or trainer."""
    if r.recipe_item is not None:
        return "item"
    if r.acquire == 1:
        return "auto"
    return "special" if special_teacher(r.name) else "trainer"

# The "post or vendor" test (docs/tsm/strategies.md, 5b): copper per stack.
POST_FAST_MIN = 5 * 100
POST_SLOW_MIN = 50 * 100
FAST_SALE_RATE = 0.25
DEPOSIT_SHARE = 0.3  # 24h deposit as a share of vendor price
AH_CUT = 0.95
# Craft an intermediate (Cured Light Hide, Heavy Leather) instead of buying it only when that saves this share of the buy
# price: a few copper saved is not worth crafting 410 Light Leather from 1,230 scraps.
CRAFT_SAVING = 0.2
# Copper charged per craft on top of its net cost (the SkillupHelper planner's effort charge, a setting there): a
# profitable craft is not free when it takes six crafts a point. 0 in the library functions keeps the old ranking.
DEFAULT_EFFORT = 20
DEFAULT_SELL_SHARE = 0.5  # a leftover is worth max(vendor sell, this share of the market value)
RESERVE_GROUP = re.compile(r"Leveling reserve`(?:Keep (\d+) on main|Hold (\d+))$")  # Hold N: an older name, still read


class SkillupError(A.AppDataError):
    """A broken link in the recipe data, named."""


# ---------------------------------------------------------------- recipe data


@dataclass
class Recipe:
    spell: int
    name: str
    yellow: int
    grey: int
    skillups: int = 1
    reagents: dict[int, int] = field(default_factory=dict)
    product: int | None = None
    product_count: float = 1.0
    acquire: int = 0  # SkillLineAbility.AcquireMethod: 1 = learned with the profession
    recipe_item: int | None = None
    learn_rank: int | None = None  # from the recipe item; None when no client data says

    @property
    def green(self) -> int:
        return (self.yellow + self.grey) // 2


def chance(skill: int, r: Recipe) -> float:
    """Skill-up chance at `skill` (vanilla-client formula, an assumption for Forever; the addon's P.chance)."""
    if skill < r.yellow:
        return 1.0
    if skill >= r.grey or r.grey <= r.yellow:
        return 0.0
    return (r.grey - skill) / (r.grey - r.yellow)


def flat_chance(skill: int, r: Recipe) -> float:
    """The colour-band guess (the addon's P.flatChance): 1 orange, 0.75 yellow, 0.25 green, 0 grey. The addon plans a
    second time with it and tags the steps whose recipe changes ("chance model"): those depend on the formula."""
    if skill < r.yellow:
        return 1.0
    if skill >= r.grey:
        return 0.0
    return 0.75 if skill < (r.yellow + r.grey) // 2 else 0.25


CHANCE_MODELS = {"formula": chance, "flat": flat_chance}


# Planner rule 1 of the SkillupHelper addon (Planner.lua in github.com/ParogDev/SkillupHelper, P.LUCK / P.zOf / P.craftSpread): a step
# buys for a percentile of the crafts it takes to reach its target, so a bad-luck run does not send you back to the AH.
LUCK = 90  # default percentile, the addon's P.LUCK
# The highest profession rank cap known (Artisan, 300). Forever's client data holds no rank table, so this is the classic
# top; the default target is this or TSM's recorded cap when that is higher (the addon uses the same).
TOP_RANK_CAP = 300
Z_OF = {50: 0.0, 75: 0.6745, 80: 0.8416, 90: 1.2816, 95: 1.6449, 99: 2.3263}  # the addon's Z_OF (normal approximation)
EPS = 1e-6
# Rule 5 (the addon's P.ISLAND, P.INTERLEAVE_SAVING): a run of recipe B of at most ISLAND points between two runs of
# recipe A becomes A, unless keeping B saves at least INTERLEAVE_SAVING of the cost left from there.
ISLAND = 1
INTERLEAVE_SAVING = 0.1
# Copper per point by which owned spare stock wins a near tie in the stock pass (the addon's P.BIAS).
BIAS = 10


def craft_spread(start: float, end: float, r: Recipe, chance_fn=chance) -> tuple[float, float]:
    """Crafts to go from skill `start` to `end` with r: mean and variance (the addon's P.craftSpread). Each point at
    level s takes a geometric number of crafts with success p = min(1, chance * NumSkillUps): mean 1/p, variance
    (1-p)/p^2; a part of a level counts by its share. Stops at the first level where the chance is 0."""
    mean = var = 0.0
    s = math.floor(start)
    while s < end - EPS:
        f = min(end, s + 1) - max(start, s)
        p = chance_fn(s, r) * r.skillups
        if p <= 0:
            break
        p = min(p, 1.0)
        mean += f / p
        var += f * (1 - p) / (p * p)
        s += 1
    return mean, var


def luck_crafts(mean: float, var: float, luck: int = LUCK) -> int:
    """Crafts to buy for: ceil(mean + z * sd), at least 1 (the addon's buy-step sizing, Planner.lua rule 1)."""
    return max(1, math.ceil(mean + Z_OF[luck] * math.sqrt(var) - EPS))


def color(skill: int, r: Recipe) -> str:
    if skill < r.yellow:
        return "orange"
    if skill >= r.grey:
        return "grey"
    return "yellow" if skill < r.green else "green"


def _num(text: str | None, default: float = 0) -> float:
    try:
        return float(text) if text not in (None, "") else default
    except ValueError:
        return default


@dataclass
class RecipeData:
    skill_lines: dict[str, int]  # lower-case name -> id
    recipes: dict[int, list[Recipe]]  # skill line id -> recipes
    items: dict[int, dict]  # id -> {name, sell, buy, stack}
    build: str = ""

    @classmethod
    def from_tables(cls, t: dict[str, list[dict]], build: str = "") -> "RecipeData":
        # child lines (2945 "Leatherworking", parent 165) share the name; the recipes sit on the parent
        skill_lines = {}
        for r in sorted(t["SkillLine"], key=lambda r: int(_num(r.get("ParentSkillLineID"))), reverse=True):
            if r.get("DisplayName_lang"):
                skill_lines[r["DisplayName_lang"].strip().lower()] = int(r["ID"])
        names = {int(r["ID"]): r["Name_lang"] for r in t["SpellName"]}
        items = {}
        for r in t["ItemSparse"]:
            items[int(r["ID"])] = {"name": r.get("Display_lang") or f"item {r['ID']}", "sell": int(_num(r.get("SellPrice"))),
                                   "buy": int(_num(r.get("BuyPrice"))), "stack": max(1, int(_num(r.get("Stackable"), 1))),
                                   "reqSkillRank": int(_num(r.get("RequiredSkillRank")))}
        reagents: dict[int, dict[int, int]] = {}
        for r in t["SpellReagents"]:
            mats = reagents.setdefault(int(r["SpellID"]), {})
            for i in range(8):
                item, count = int(_num(r.get(f"Reagent_{i}"))), int(_num(r.get(f"ReagentCount_{i}")))
                if item > 0 and count > 0:
                    mats[item] = mats.get(item, 0) + count
        products: dict[int, tuple[int, float]] = {}
        for r in t["SpellEffect"]:
            if int(_num(r.get("Effect"))) == EFFECT_CREATE_ITEM and int(_num(r.get("EffectItemType"))) > 0:
                products.setdefault(int(r["SpellID"]), (int(r["EffectItemType"]), max(1.0, _num(r.get("EffectBasePointsF"), 1))))
        effect_item = {int(r["ItemEffectID"]): int(r["ItemID"]) for r in t["ItemXItemEffect"]}
        teaches: dict[int, int] = {}
        for r in t["ItemEffect"]:
            if int(_num(r.get("TriggerType"))) == TRIGGER_LEARN and int(r["ID"]) in effect_item:
                teaches.setdefault(int(r["SpellID"]), effect_item[int(r["ID"])])
        recipes: dict[int, list[Recipe]] = {}
        for r in t["SkillLineAbility"]:
            spell, yellow, grey = int(r["Spell"]), int(_num(r.get("TrivialSkillLineRankLow"))), int(_num(r.get("TrivialSkillLineRankHigh")))
            if spell not in reagents or not reagents[spell] or grey <= 0:
                continue  # not a craft (no reagents) or no skill-up range
            name = names.get(spell, f"spell {spell}")
            if DEAD_NAME.search(name):
                continue
            product, count = products.get(spell, (None, 1.0))
            rec = Recipe(spell, name, yellow, grey, max(1, int(_num(r.get("NumSkillUps"), 1))), reagents[spell], product, count,
                         int(_num(r.get("AcquireMethod"))))
            item = teaches.get(spell)
            if item is not None:
                rec.recipe_item = item
                rec.learn_rank = items.get(item, {}).get("reqSkillRank") or None
            recipes.setdefault(int(r["SkillLine"]), []).append(rec)
        return cls(skill_lines, recipes, items, build)

    def skill_line(self, profession: str) -> int:
        key = profession.strip().lower()
        if key.isdigit():
            return int(key)
        if key in self.skill_lines:
            return self.skill_lines[key]
        close = sorted(n for n in self.skill_lines if key in n)
        raise SkillupError(f"no profession named {profession!r} in SkillLine" + (f"; close: {close[:6]}" if close else ""))


def default_build(cache_dir: Path, download: bool) -> str:
    root = cache_dir / "wago"
    have = [d.name for d in root.iterdir() if d.is_dir() and (d / "ItemSparse.enUS.csv").is_file()] if root.is_dir() else []
    have = [b for b in have if re.fullmatch(r"[\d.]+", b)]
    if have:
        return max(have, key=A._version_key)
    if not download:
        raise SkillupError(f"no cached wago build in {root} and --offline given")
    return A.latest_build()


def fetch_recipe_tables(build: str, cache_dir: Path, download: bool = True, http_get=A._http_get) -> dict[str, list[dict]]:
    folder = cache_dir / "wago" / build
    out = {}
    for table in RECIPE_TABLES:
        f = folder / f"{table}.enUS.csv"
        if not (f.is_file() and f.stat().st_size > 0):
            if not download:
                raise SkillupError(f"recipe data missing: {f} is not cached and --offline given")
            url = A.WAGO_CSV_URL.format(table=table, build=build)
            try:
                data = http_get(url)
            except (urllib.error.URLError, OSError) as e:
                raise SkillupError(f"recipe data unavailable: {url} -> {e}") from e
            if data[:200].lstrip().startswith(b"<") or b"," not in data.split(b"\n", 1)[0]:
                raise SkillupError(f"recipe data unavailable: {url} did not return a CSV (starts {data[:60]!r})")
            folder.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(f)
        with open(f, encoding="utf-8-sig", newline="") as fh:
            out[table] = list(csv.DictReader(fh))
        if not out[table]:
            raise SkillupError(f"recipe data broken: {f} has no rows")
    return out


# ---------------------------------------------------------------- what the character knows (TSM SavedVariables)


@dataclass
class Character:
    name: str | None = None
    level: int | None = None
    max_level: int | None = None
    known: set[int] | None = None  # None: TSM has not recorded this profession's recipes
    vendor_items: set[int] = field(default_factory=set)
    reserve: dict[int, int] = field(default_factory=dict)  # item -> N from TSM groups "Leveling reserve`Keep N on main"
    stock: dict[int, int] = field(default_factory=dict)  # item -> bags + bank of this character (TSM's inventory)
    note: str | None = None


def read_character(db_data: dict, profession: str, char: str | None = None) -> Character:
    """Skill and known recipes for `profession` from a parsed TradeSkillMaster.lua (tsmdb.Database.data)."""
    prof = profession.strip().lower()
    candidates = []
    for key, value in db_data.items():
        m = re.fullmatch(r"s@(.+) - [^-]+ - [^@]+@internalData@playerProfessions", key)
        if not m or not isinstance(value, dict):
            continue
        for pname, p in value.items():
            if isinstance(p, dict) and str(pname).lower() == prof:
                candidates.append((m.group(1), p))
    if char:
        candidates = [c for c in candidates if c[0].lower() == char.lower()]
    out = Character()
    if candidates:
        name, p = max(candidates, key=lambda c: c[1].get("level") or 0)
        out.name, out.level, out.max_level = name, p.get("level"), p.get("maxLevel")
    else:
        out.note = f"TSM has no {profession} skill recorded" + (f" for {char}" if char else "")
    other_players = 0  # crafts of this profession recorded for someone else only
    for key, value in db_data.items():
        if key.endswith("@internalData@crafts") and isinstance(value, dict):
            for craft_key, c in value.items():
                if not isinstance(c, dict) or str(c.get("profession", "")).lower() != prof:
                    continue
                if out.name and out.name not in (c.get("players") or {}):
                    other_players += 1
                    continue
                m = re.fullmatch(r"c:(\d+)", str(craft_key))
                if m:
                    out.known = (out.known or set()) | {int(m.group(1))}
        if key.endswith("@userData@items") and isinstance(value, dict):
            for item, group in value.items():
                m = re.fullmatch(r"i:(\d+)", str(item))
                if m and isinstance(group, str) and group.split("`")[-1] == "Vendor-bought":
                    out.vendor_items.add(int(m.group(1)))
                hold = RESERVE_GROUP.search(group) if m and isinstance(group, str) else None
                if hold:
                    out.reserve[int(m.group(1))] = int(hold.group(1) or hold.group(2))
    if out.name:
        # bags and bank, what the addon's planner counts as owned (`have`); mail and auctions are not at hand
        for key, value in db_data.items():
            m = re.fullmatch(r"s@(.+) - [^-]+ - [^@]+@internalData@(bagQuantity|bankQuantity)", str(key))
            if not m or m.group(1) != out.name or not isinstance(value, dict):
                continue
            for item, qty in value.items():
                im = re.fullmatch(r"i:(\d+)", str(item))
                if im and isinstance(qty, (int, float)) and not isinstance(qty, bool) and qty > 0:
                    out.stock[int(im.group(1))] = out.stock.get(int(im.group(1)), 0) + int(qty)
    if out.known is None and other_players and not out.note:
        out.note = (f"TSM lists {other_players} {profession} recipes, none for {out.name}: "
                    "treating every recipe as not known (pass --char to pick another character)")
    if out.known is None and not out.note:
        out.note = f"TSM has not recorded the {profession} recipes you know (open the profession window once with TSM loaded)"
    return out


def read_professions(db_data: dict, char: str | None = None) -> dict[str, int | None]:
    """Profession name -> recorded skill, from TSM's `playerProfessions` of every character (of `char` only when given).
    A profession on several characters keeps its highest skill, the one read_character picks."""
    out: dict[str, int | None] = {}
    for key, value in db_data.items():
        m = re.fullmatch(r"s@(.+) - [^-]+ - [^@]+@internalData@playerProfessions", str(key))
        if not m or not isinstance(value, dict) or (char and m.group(1).lower() != char.lower()):
            continue
        for pname, p in value.items():
            if isinstance(p, dict):
                level = p.get("level") if isinstance(p.get("level"), (int, float)) else None
                if str(pname) not in out or (level or 0) > (out[str(pname)] or 0):
                    out[str(pname)] = level
    return out


def load_professions(path, char: str | None = None) -> dict[str, int | None]:
    """read_professions on a SavedVariables file; raises SkillupError naming the broken link."""
    if not path:
        raise SkillupError("TSM SavedVariables not found (set TSM_SAVED_VARS or pass --saved-vars)")
    import tsmdb  # noqa: PLC0415
    try:
        found = read_professions(tsmdb.load_db(str(path)).data, char)
    except (tsmdb.TsmError, OSError, ValueError, RecursionError) as e:
        raise SkillupError(f"TSM SavedVariables unreadable ({path}): {e}") from e
    if not found:
        raise SkillupError("TSM has no professions recorded" +(f" for {char}" if char else "") + f" in {path}"
                           " (log in with TSM loaded)")
    return found


def load_character(path, profession: str, char: str | None = None) -> Character:
    """read_character on a SavedVariables file; an unreadable file is a note, not a crash."""
    if not path:
        return Character(note="TSM SavedVariables not found: no recipes known, no skill recorded")
    import tsmdb  # noqa: PLC0415
    try:
        return read_character(tsmdb.load_db(str(path)).data, profession, char)
    except (tsmdb.TsmError, OSError, ValueError, RecursionError) as e:
        return Character(note=f"TSM SavedVariables unreadable ({path}): {e}")


# ---------------------------------------------------------------- what the addon learned at the trainer


@dataclass
class AddonState:
    """SkillupHelper's SavedVariables (SkillupHelperDB), read only: ranks and trainerSeen per skill line id."""
    ranks: dict[int, list[dict]] = field(default_factory=dict)  # line -> [{name, cap, skill, level, cost, where}] by cap
    trainer_seen: dict[int, set] = field(default_factory=dict)  # line -> {spell id or lowercased recipe name}
    note: str | None = None


def _entries(t) -> list:
    """(key, value) pairs of a parsed Lua table, list or dict."""
    if isinstance(t, dict):
        return list(t.items())
    if isinstance(t, list):
        return list(enumerate(t, 1))
    return []


def read_addon_state(db: dict) -> AddonState:
    """Ranks (SkillupHelperDB.ranks[line][cap]) and trainerSeen (SkillupHelperDB.trainerSeen[line][key] = true)."""
    out = AddonState()
    for line, by_cap in _entries(db.get("ranks")):
        rows = []
        for cap, r in _entries(by_cap):
            if isinstance(r, dict) and isinstance(r.get("cap", cap), (int, float)):
                rows.append({"name": r.get("name"), "cap": int(r.get("cap", cap)), "skill": r.get("skill"),
                             "level": r.get("level"), "cost": r.get("cost"), "where": r.get("where")})
        if rows and isinstance(line, (int, float)):
            out.ranks[int(line)] = sorted(rows, key=lambda r: r["cap"])
    for line, seen in _entries(db.get("trainerSeen")):
        keys = set()
        for k, v in _entries(seen):
            if not v:
                continue
            if isinstance(k, float) and k.is_integer():
                k = int(k)
            keys.add(k if isinstance(k, int) else int(k) if str(k).isdigit() else str(k).lower())
        if keys and isinstance(line, (int, float)):
            out.trainer_seen[int(line)] = keys
    return out


def default_addon_saved_vars() -> Path | None:
    """The newest WTF\\Account\\*\\SavedVariables\\SkillupHelper.lua (SKILLUP_SAVED_VARS overrides)."""
    explicit = os.environ.get("SKILLUP_SAVED_VARS")
    if explicit:
        return Path(explicit)
    wtf = Path(os.environ.get("WOWF_GAME_DIR") or A.DEFAULT_GAME_PARENT) / "_forever_" / "WTF" / "Account"
    found = [p for p in wtf.glob("*/SavedVariables/SkillupHelper.lua") if p.is_file()] if wtf.is_dir() else []
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def load_addon_state(path) -> AddonState:
    """read_addon_state on a SkillupHelper.lua; a missing or unreadable file is a note, not a crash."""
    if not path:
        return AddonState(note="SkillupHelper SavedVariables not found: no trainer ranks read, no trainer recipe marked "
                               "\"not checked\"")
    import tsmdb  # noqa: PLC0415
    try:
        text = Path(path).read_bytes().decode("latin-1")
        m = re.search(r"^SkillupHelperDB[ \t]*=[ \t]*(?=\{)", text, re.MULTILINE)
        if not m:
            return AddonState(note=f"SkillupHelper SavedVariables ({path}) has no SkillupHelperDB table")
        parser = tsmdb._Parser(text, str(path))
        parser.pos = m.end()
        data = parser.parse_table()
        return read_addon_state(data if isinstance(data, dict) else {})
    except (tsmdb.TsmError, OSError, ValueError, RecursionError) as e:
        return AddonState(note=f"SkillupHelper SavedVariables unreadable ({path}): {e}")


def cap_model(ranks: list[dict], live_cap: int | None, end: int, level: int | None = None) -> dict:
    """The addon's capModel for a report: the ranks to train between the live cap and `end` and the first one that
    blocks (character level known and too low, or a special teacher). `by` = the cap the rank lifts."""
    ups, block, eff = [], None, live_cap
    if live_cap is None:
        return {"rankUps": ups, "capBlock": None, "cap": end}
    for rk in sorted(ranks, key=lambda r: r["cap"]):
        if eff >= end:
            break
        if rk["cap"] <= eff:
            continue
        reason = None
        if rk.get("level") and level and rk["level"] > level:
            reason = "level"
        elif rk.get("where") == "special":
            reason = "special"
        if reason:
            block = {"name": rk.get("name"), "cap": rk["cap"], "level": rk.get("level"), "have": level, "by": eff,
                     "reason": reason}
            break
        ups.append({"name": rk.get("name"), "cap": rk["cap"], "by": eff, "at": rk.get("skill"), "level": rk.get("level"),
                    "cost": rk.get("cost")})
        eff = rk["cap"]
    # with ranks read, the plan stops at the highest one reached (the addon's ctx.cap); with none read, skillup.py keeps
    # its assumption that every rank up to `end` is trainable
    return {"rankUps": ups, "capBlock": block, "cap": min(eff, end) if ranks else end}


# ---------------------------------------------------------------- prices


@dataclass
class Prices:
    rows: dict[int, dict]  # item id -> appdata merged row (base item strings only)
    items: dict[int, dict]
    vendor_items: set[int]
    sell_products: bool = True
    sell_days: float = 2.0

    def material(self, item: int) -> tuple[int | None, str]:
        """(copper per item, how). Vendor price for vendor reagents, else house market, else region market."""
        info = self.items.get(item, {})
        if item in self.vendor_items and info.get("buy"):
            return info["buy"], "vendor"
        row = self.rows.get(item, {})
        for name, how in (("marketValue", "ah"), ("minBuyout", "ah"), ("regionMarketValue", "region")):
            if row.get(name):
                return int(row[name]), how
        return None, "none"

    def product(self, item: int | None) -> tuple[float, float | None, float]:
        """(vendor copper each, auction copper each or None, how many the market takes) for one product.

        Auction value follows the post-or-vendor test (docs/tsm/strategies.md 5b: saleprice, netgain, 5s / 50s per stack): None when the
        item fails it. The market takes `sell_days` days of the region's sales; the rest is vendored.
        """
        if item is None:
            return 0.0, None, 0.0
        info = self.items.get(item, {})
        vs = float(info.get("sell", 0))
        row = self.rows.get(item, {})
        house = row.get("marketValue") or row.get("regionMarketValue")
        prices = [p for p in (house, row.get("regionSale")) if p]
        if not self.sell_products or not prices:
            return vs, None, 0.0
        sale = min(prices)
        rate = row.get("regionSaleRate")
        net = AH_CUT * sale - max(vs, 0.001) * (1 + DEPOSIT_SHARE * (1 / (rate or FAST_SALE_RATE) - 1))
        stack = info.get("stack", 1)
        per_day = row.get("regionSoldPerDay") or 0
        fast = (rate or 0) >= FAST_SALE_RATE and per_day >= stack
        if net * stack >= (POST_FAST_MIN if fast else POST_SLOW_MIN):
            return vs, vs + net, per_day * self.sell_days
        return vs, None, 0.0


# ---------------------------------------------------------------- planning


@dataclass
class Option:
    recipe: Recipe
    source: str  # known | trainer | auto | recipe item
    mats: dict[int, float]  # base materials per craft (intermediates expanded when crafting them is cheaper)
    mat_cost: float  # per craft
    vendor_each: float = 0.0  # per craft (product count included)
    sell_each: float | None = None
    market_takes: float = 0.0  # crafts' worth of product the market absorbs
    planned: float = 1.0  # crafts this option is expected to get in the plan (set by plan())
    crafted: dict[int, float] = field(default_factory=dict)  # intermediates crafted first, per craft
    unchecked: bool = False  # a trainer recipe the addon never saw a trainer teach: not planned

    def sold(self, crafts: float) -> float:
        return min(crafts, self.market_takes) if self.sell_each is not None else 0.0

    def back_total(self, crafts: float) -> float:
        n = self.sold(crafts)
        return n * (self.sell_each or 0) + (crafts - n) * self.vendor_each

    @property
    def net(self) -> float:
        """Net cost per craft at the planned number of crafts."""
        crafts = max(self.planned, 1.0)
        return self.mat_cost - self.back_total(crafts) / crafts


def _expand(item: int, qty: float, prices: Prices, crafters: dict[int, Recipe],
            depth: int) -> tuple[float, dict[int, float], dict[int, float]] | None:
    """(cost, materials to buy, intermediates to craft) for `qty` of `item`: bought, or crafted when that is clearly
    cheaper (CRAFT_SAVING) or the item has no price."""
    price, _ = prices.material(item)
    best = (price * qty, {item: qty}, {}) if price is not None else None
    r = crafters.get(item)
    if r is not None and depth > 0:
        total, mats, crafted = 0.0, {}, {item: qty}
        for sub, n in r.reagents.items():
            got = _expand(sub, qty * n / r.product_count, prices, crafters, depth - 1)
            if got is None:
                total = None
                break
            total += got[0]
            for k, v in got[1].items():
                mats[k] = mats.get(k, 0) + v
            for k, v in got[2].items():
                crafted[k] = crafted.get(k, 0) + v
        if total is not None and (best is None or total < best[0] * (1 - CRAFT_SAVING)):
            best = (total, mats, crafted)
    return best


def build_options(recipes: list[Recipe], prices: Prices, ch: Character,
                  trainer_seen: set | None = None) -> tuple[list[Option], list[dict]]:
    """Every recipe with a price, plus the skipped ones and why. `trainer_seen` (the addon's trainerSeen for this skill
    line; None = never read) marks trainer recipes no trainer was seen to teach as unchecked."""
    known = ch.known
    # recipes the character can craft without buying anything, for intermediates (Cured Light Hide, Heavy Leather)
    crafters = {}
    for r in recipes:
        if r.product and (r.spell in known if known is not None else r.recipe_item is None):
            crafters.setdefault(r.product, r)
    options, skipped = [], []
    for r in recipes:
        if known is not None and r.spell in known:
            source = "known"
        elif r.recipe_item is not None:
            source = "recipe item"
        else:
            source = recipe_source(r)
        total, mats, crafted, missing = 0.0, {}, {}, []
        for item, n in r.reagents.items():
            got = _expand(item, n, prices, {k: v for k, v in crafters.items() if v.spell != r.spell}, 2)
            if got is None:
                missing.append(prices.items.get(item, {}).get("name", f"item {item}"))
                continue
            total += got[0]
            for k, v in got[1].items():
                mats[k] = mats.get(k, 0) + v
            for k, v in got[2].items():
                crafted[k] = crafted.get(k, 0) + v
        if missing:
            skipped.append({"spell": r.spell, "name": r.name, "why": "no price for " + ", ".join(missing)})
            continue
        vendor, sell, takes = prices.product(r.product)
        n = r.product_count
        unchecked = (source == "trainer" and trainer_seen is not None and r.spell not in trainer_seen
                     and r.name.lower() not in trainer_seen)
        options.append(Option(r, source, mats, total, vendor * n, sell * n if sell is not None else None, takes / n,
                              crafted=crafted, unchecked=unchecked))
    return options, skipped


def available(o: Option, skill: int, known_recorded: bool) -> bool:
    if o.source == "known":
        return True
    if o.source == "recipe item":
        return (o.recipe.learn_rank or 0) <= skill
    if o.source == "auto":
        return True
    if o.source == "special" or o.unchecked:
        # taught by a special NPC (dungeon teacher), or a trainer recipe no trainer the addon read lists (a quest
        # reward, say): never planned, as the addon offers both only as shortcuts
        return False
    # trainer: the learn rank is server-side; assume it is no higher than the yellow threshold
    return o.recipe.yellow <= skill


def cost_pt(o: Option, s: int, effort: float = 0.0, chance_fn=chance,
            net: float | None = None) -> tuple[float, float] | None:
    """(cost per expected point, expected crafts) of o at skill s, or None when it gives no skill (the addon's costPt).
    A craft that pays for itself counts as free; `effort` is charged per craft and per intermediate crafted first.
    `net` overrides the net cost per craft (stock pass)."""
    c = chance_fn(s, o.recipe)
    if c <= 0:
        return None
    # success per craft capped at 1, as craft_spread and the addon's P.craftSpread count it
    crafts = 1 / min(1.0, c * o.recipe.skillups)
    cost = (max(o.net if net is None else net, 0.0) + effort * (1 + sum(o.crafted.values()))) * crafts
    return cost, crafts


def _level_cost(o: Option | None, s: int, effort: float, chance_fn) -> float:
    got = cost_pt(o, s, effort, chance_fn) if o is not None else None
    return got[0] if got else 0.0


def smooth(levels: list, known_recorded: bool, effort: float = 0.0, chance_fn=chance) -> list:
    """Rule 5, no one-point islands (the addon's smooth): a run of B of at most ISLAND levels between two runs of A
    becomes A, unless keeping B saves at least INTERLEAVE_SAVING of the cost left from there, or A gives no skill
    there."""
    levels = list(levels)
    changed = True
    while changed:
        changed = False
        runs: list[list] = []  # [option, first index, last index]
        for i, (_, o, _) in enumerate(levels):
            if runs and runs[-1][0] is o:
                runs[-1][2] = i
            else:
                runs.append([o, i, i])
        for r in range(1, len(runs) - 1):
            a, (b, lo, hi) = runs[r - 1][0], runs[r]
            if a is None or b is None or runs[r + 1][0] is not a or hi - lo + 1 > ISLAND:
                continue
            extra, repl = 0.0, {}
            for i in range(lo, hi + 1):
                s = levels[i][0]
                got = cost_pt(a, s, effort, chance_fn) if available(a, s, known_recorded) else None
                if got is None:
                    repl = None
                    break
                repl[i] = (s, a, got[1])
                extra += got[0] - _level_cost(b, s, effort, chance_fn)
            if repl is None:
                continue
            remaining = sum(_level_cost(o, s, effort, chance_fn) for s, o, _ in levels[lo:])
            if extra < INTERLEAVE_SAVING * remaining:
                for i, lv in repl.items():
                    levels[i] = lv
                changed = True
                break
    return levels


def plan_levels(options: list[Option], start: int, end: int, known_recorded: bool,
                effort: float = 0.0, chance_fn=chance) -> list[tuple[int, Option | None, float]]:
    """For each skill level start..end-1: (skill, cheapest option per expected point, expected crafts), then rule 5.

    `effort` is copper charged per craft (and per intermediate crafted first) on top of the net cost, the addon's
    effort charge: without it every profitable recipe ties at 0 and a low-chance one can win."""
    out = []
    for s in range(start, end):
        best, best_key = None, None
        for o in options:
            if not available(o, s, known_recorded):
                continue
            got = cost_pt(o, s, effort, chance_fn)
            if got is None:
                continue
            # among free options the fewest crafts win, then the larger profit (the addon's `better`)
            key = (got[0], got[1], o.net)
            if best_key is None or key < best_key:
                best, best_key = (o, got[1]), key
        out.append((s, best[0], best[1]) if best else (s, None, 0.0))
    return smooth(out, known_recorded, effort, chance_fn)


def _gaps(levels) -> int:
    return sum(1 for _, o, _ in levels if o is None)


def _total(levels) -> float:
    return sum(o.net * crafts for _, o, crafts in levels if o is not None)


def plan(options: list[Option], start: int, end: int, known_recorded: bool, prices: Prices, rounds: int = 4,
         effort: float = 0.0, chance_fn=chance) -> dict:
    """Cheapest plan. The market takes only so many of one product, so a recipe's net cost depends on how often the
    plan crafts it: plan, count each recipe's crafts, re-price, plan again until the choice settles."""
    for o in options:
        o.planned = 1.0
    result = _plan_once(options, start, end, known_recorded, prices, effort, chance_fn)
    for _ in range(rounds):
        counts: dict[int, float] = {}
        for _, o, crafts in result["levels"]:
            if o is not None:
                counts[id(o)] = counts.get(id(o), 0.0) + crafts
        changed = False
        for o in options:
            # only ever up: a recipe dropped for being over-sold keeps its sober price, so the plan cannot flip back
            n = counts.get(id(o), 0.0)
            if n > o.planned + 1e-6:
                o.planned, changed = n, True
        if not changed:
            break
        result = _plan_once(options, start, end, known_recorded, prices, effort, chance_fn)
    return result


def _plan_once(options: list[Option], start: int, end: int, known_recorded: bool, prices: Prices,
               effort: float = 0.0, chance_fn=chance) -> dict:
    """Cheapest plan at the current per-craft prices, buying recipe items when that lowers the total."""
    free = [o for o in options if o.source != "recipe item"]
    buyable = []
    for o in options:
        if o.source == "recipe item":
            price, how = prices.material(o.recipe.recipe_item)
            if price is not None and how != "region":
                buyable.append((o, price))
    chosen: list[tuple[Option, int]] = []
    current = plan_levels(free, start, end, known_recorded, effort, chance_fn)
    best_cost = (_gaps(current), _total(current))
    while True:
        improvement = None
        for o, price in buyable:
            if any(o is c for c, _ in chosen):
                continue
            levels = plan_levels(free + [c for c, _ in chosen] + [o], start, end, known_recorded, effort, chance_fn)
            if not any(x is o for _, x, _ in levels):
                continue
            cost = (_gaps(levels), _total(levels) + sum(p for _, p in chosen) + price)
            better = cost[0] < best_cost[0] or (cost[0] == best_cost[0] and cost[1] < best_cost[1] - 1)
            if better and (improvement is None or cost < improvement[0]):
                improvement = (cost, o, price, levels)
        if improvement is None:
            break
        best_cost, o, price, current = improvement
        chosen.append((o, price))
    return {"levels": current, "recipesBought": chosen}


def segments(levels) -> list[dict]:
    out: list[dict] = []
    for s, o, crafts in levels:
        if out and out[-1]["option"] is o:
            out[-1]["to"] = s + 1
            out[-1]["expected"] += crafts
        else:
            out.append({"from": s, "to": s + 1, "option": o, "expected": crafts})
    return out


def row_need(levels, luck: int = LUCK, chance_fn=chance) -> dict[int, float]:
    """Materials every row of `levels` buys for at the `luck` percentile: the earmarks of rule 2."""
    need: dict[int, float] = {}
    for seg in segments(levels):
        o = seg["option"]
        if o is None:
            continue
        crafts = luck_crafts(*craft_spread(seg["from"], seg["to"], o.recipe, chance_fn), luck)
        for i, q in o.mats.items():
            need[i] = need.get(i, 0) + math.ceil(q * crafts - 1e-9)
    return need


def salvage(prices: Prices, item: int) -> float:
    """What an owned spare is worth when crafted away: max(vendor sell, DEFAULT_SELL_SHARE of the market value), the
    addon's price.salvage."""
    sell = prices.items.get(item, {}).get("sell", 0)
    price, how = prices.material(item)
    return max(sell, DEFAULT_SELL_SHARE * price if price is not None and how != "vendor" else 0)


def stock_pass(levels: list, usable: list[Option], have: dict[int, int], prices: Prices, known_recorded: bool,
               effort: float = 0.0, luck: int = LUCK, chance_fn=chance) -> tuple[list, dict[int, dict[int, float]], dict]:
    """Rule 2 and the addon's pass 2: owned stock no row needs (true spares: bags and bank minus every row's p`luck`
    materials) goes to the levels where it saves most per unit, best saving first. A spare-using option takes a whole
    level only when the spares cover that level's crafts at the luck percentile, so it can never reach into an
    earmark. Returns (levels, stock allocated per level index {item: qty}, spares left)."""
    z = Z_OF[luck]
    need = row_need(levels, luck, chance_fn)
    spares = {i: q - need.get(i, 0) for i, q in have.items() if q - need.get(i, 0) > EPS}
    cands = []
    for o in usable:
        mine = [i for i in o.mats if i in spares]
        if not mine:
            continue
        mat = 0.0
        for i, n in o.mats.items():
            each = salvage(prices, i) if i in spares else prices.material(i)[0]
            if each is None:
                mat = None
                break
            mat += n * each
        if mat is None:
            continue
        net = mat - o.back_total(1.0)
        worst = max(o.mats[i] for i in mine)
        for idx, (s, cur, _) in enumerate(levels):
            if cur is o or not available(o, s, known_recorded):
                continue
            got = cost_pt(o, s, effort, chance_fn, net)
            if got is None:
                continue
            gain = (_level_cost(cur, s, effort, chance_fn) if cur is not None else 1e7) - got[0] + BIAS
            if gain > 0:
                cands.append((-(gain / got[1]) / worst, s, o.recipe.spell, idx, o, got[1]))
    cands.sort(key=lambda c: c[:3])
    out, alloc = list(levels), {}
    for _, s, _, idx, o, crafts in cands:
        if idx in alloc:
            continue
        p = 1 / crafts
        budget = crafts + z * math.sqrt((1 - p) / (p * p))  # this level's crafts at the luck percentile
        take = {i: o.mats[i] * budget for i in o.mats if i in spares}
        if all(spares[i] >= q - EPS for i, q in take.items()):
            for i, q in take.items():
                spares[i] -= q
            alloc[idx] = take
            out[idx] = (s, o, crafts)
    return out, alloc, spares


def option_row(o: Option) -> dict:
    """One priced recipe as the addon's planner sees it: per craft, product count in."""
    r = o.recipe
    return {"spell": r.spell, "name": r.name, "source": o.source, "yellow": r.yellow, "grey": r.grey, "skillups": r.skillups,
            "reagents": sorted([i, n] for i, n in r.reagents.items()), "mats": sorted([i, n] for i, n in o.mats.items()),
            "crafted": sorted([i, n] for i, n in o.crafted.items()), "matCost": round(o.mat_cost, 2),
            "vendorEach": round(o.vendor_each, 2), "sellEach": round(o.sell_each, 2) if o.sell_each is not None else None,
            "takes": round(o.market_takes, 2), "product": r.product, "productCount": r.product_count,
            "recipeItem": r.recipe_item, "learnRank": r.learn_rank, "acquire": r.acquire}


def report(rd: RecipeData, profession: str, start: int, end: int, prices: Prices, ch: Character,
           effort: float = 0.0, luck: int = LUCK, addon: AddonState | None = None, stock: dict[int, int] | None = None,
           chance_model: str = "formula", level: int | None = None) -> dict:
    """The plan as rows. `crafts`, the materials and the shopping list cover the `luck` percentile of the crafts each
    row takes (the addon's rule 1); `expectedCrafts` and the costs stay at the mean, the cost you can expect.

    The addon's other rules: rule 5 (no one-point islands) always; with `addon` (its SavedVariables) the trainer ranks
    (cap model, `level` = character level for a level-blocked rank) and trainerSeen (unchecked recipes are not planned);
    with `stock` (bags and bank) rule 2: every row takes its earmarked stock first, spares no row needs may replace a
    level (stock pass), and nothing spends an earmark. `chance_model` "flat" plans with the addon's colour guess; rows
    whose recipe would change under the other model are tagged `chanceModel`."""
    if luck not in Z_OF:
        raise SkillupError(f"luck {luck} is not one of {sorted(Z_OF)}")
    if chance_model not in CHANCE_MODELS:
        raise SkillupError(f"chance model {chance_model!r} is not one of {sorted(CHANCE_MODELS)}")
    chance_fn = CHANCE_MODELS[chance_model]
    other_fn = flat_chance if chance_model == "formula" else chance
    line = rd.skill_line(profession)
    recipes = rd.recipes.get(line, [])
    if not recipes:
        raise SkillupError(f"skill line {line} ({profession}) has no recipes with reagents and a skill-up range in build {rd.build}")
    caps = cap_model((addon.ranks.get(line) if addon else None) or [], ch.max_level, end, level)
    if caps["cap"] <= start and (caps["capBlock"] or caps["cap"] < end):
        b = caps["capBlock"]
        raise SkillupError(f"no skill to gain from {start}: " + (
            f"{b['name']} (cap {b['cap']}) " + (f"needs level {b['level']}" if b["reason"] == "level" else "is taught by a special teacher")
            if b else f"the highest rank read at a trainer caps it at {caps['cap']} (SkillupHelperDB.ranks)"))
    caps["stoppedAt"] = caps["cap"] if caps["cap"] < end and not caps["capBlock"] else None
    end = min(end, caps["cap"])
    options, skipped = build_options(recipes, prices, ch, addon.trainer_seen.get(line) if addon else None)
    known_recorded = ch.known is not None
    result = plan(options, start, end, known_recorded, prices, effort=effort, chance_fn=chance_fn)
    name = lambda i: rd.items.get(i, {}).get("name", f"item {i}")  # noqa: E731
    rows, total, gaps, need = [], 0.0, [], {}
    bought_ids = {id(o) for o, _ in result["recipesBought"]}
    usable = [o for o in options if o.source != "recipe item" or id(o) in bought_ids]
    # the other chance model's choice per level, with the same recipes: a row it changes depends on the formula
    other = {s: o for s, o, _ in plan_levels(usable, start, end, known_recorded, effort, other_fn)}
    alloc: dict[int, dict[int, float]] = {}
    have = {i: q for i, q in (stock or {}).items() if q > 0}
    if have:
        result["levels"], alloc, _ = stock_pass(result["levels"], usable, have, prices, known_recorded, effort, luck,
                                                chance_fn)
    for _, o, _ in result["levels"]:  # final counts, so the cost below matches the plan shown
        if o is not None:
            o.planned = sum(c for _, x, c in result["levels"] if x is o)
    # rows: one recipe over one contiguous range, split where the stock pass placed spares (those rows use only them)
    segs: list[dict] = []
    for idx, (s, o, crafts) in enumerate(result["levels"]):
        spare = idx in alloc
        if segs and segs[-1]["option"] is o and segs[-1]["spare"] == spare:
            segs[-1]["to"], segs[-1]["expected"] = s + 1, segs[-1]["expected"] + crafts
            for i, q in alloc.get(idx, {}).items():
                segs[-1]["alloc"][i] = segs[-1]["alloc"].get(i, 0) + q
        else:
            segs.append({"from": s, "to": s + 1, "option": o, "expected": crafts, "spare": spare,
                         "alloc": dict(alloc.get(idx, {}))})
    # rule 2: the earmarked pool (stock less what the stock pass gave away) goes to rows in plan order
    pool = dict(have)
    for a in alloc.values():
        for i, q in a.items():
            pool[i] = pool.get(i, 0) - q
    used: dict[int, int] = {i: 0 for i in have}  # stock the rows take
    buy_cost = 0.0  # what the rows' `buy` materials cost (p90 counts); the total prices every material, stock included
    for seg in segs:
        o = seg["option"]
        if o is None:
            gaps.append(f"{seg['from']}-{seg['to']}")
            rows.append({"from": seg["from"], "to": seg["to"], "recipe": None, "note": "no recipe with a price gives skill here"})
            continue
        crafts = luck_crafts(*craft_spread(seg["from"], seg["to"], o.recipe, chance_fn), luck)
        mats = {name(i): math.ceil(q * crafts - 1e-9) for i, q in sorted(o.mats.items(), key=lambda kv: -kv[1])}
        craft_first = {name(i): math.ceil(q * crafts - 1e-9) for i, q in o.crafted.items()}
        from_stock, buy = {}, {}
        for i, q in o.mats.items():
            n = math.ceil(q * crafts - 1e-9)
            need[i] = need.get(i, 0) + n
            if seg["spare"]:
                got = min(n, math.floor(seg["alloc"].get(i, 0) + 1e-9))
            else:
                got = min(n, max(0, math.floor(pool.get(i, 0) + 1e-9)))
                if got:
                    pool[i] -= got
            if got:
                from_stock[i] = got
                used[i] = used.get(i, 0) + got
            if n - got:
                buy[i] = n - got
        # the addon's labels: stock (every non-vendor reagent from stock), mixed (some), buy (none)
        stock_label = ("buy" if not from_stock else
                       "stock" if not any(i in buy for i in o.mats if i not in prices.vendor_items) else "mixed")
        net = o.net
        if seg["spare"]:  # spares count at salvage, as the stock pass priced them
            net -= sum(o.mats[i] * ((prices.material(i)[0] or 0) - salvage(prices, i)) for i in from_stock)
        cost = net * seg["expected"]
        total += cost
        share = seg["expected"] / o.planned
        sold = o.sold(o.planned) * share
        back_how = "vendor" if sold < 0.5 else ("sell" if sold >= seg["expected"] - 0.5 else f"sell {round(sold)}, vendor rest")
        r = o.recipe
        source = o.source
        # the same materials by item id, for a tool that feeds an in-game planner
        mat_items = [[i, math.ceil(q * crafts - 1e-9)] for i, q in sorted(o.mats.items(), key=lambda kv: -kv[1])]
        if o.source == "recipe item":
            price = prices.material(r.recipe_item)[0]
            source = f"buy {name(r.recipe_item)} ({A.format_money(price)}), needs {r.learn_rank or '?'}"
        elif o.source == "trainer":
            source = "trainer" + ("" if known_recorded else " (probably known)") + (" (not checked)" if o.unchecked else "")
        elif o.source == "special":
            source = f"special: {special_teacher(r.name)}"
        # a row the stock pass placed is not the chance model's doing: never tagged
        depends = not seg["spare"] and any(other.get(s) is not o for s in range(seg["from"], seg["to"]))
        buy_cost += sum(n * (prices.material(i)[0] or 0) for i, n in buy.items())
        rows.append({"from": seg["from"], "to": seg["to"], "recipe": r.name, "spell": r.spell, "source": source,
                     "stock": stock_label, "spares": seg["spare"], "fromStock": {name(i): n for i, n in from_stock.items()},
                     "buy": {name(i): n for i, n in buy.items()}, "chanceModel": depends, "unchecked": o.unchecked,
                     "colors": f"{r.yellow}/{r.green}/{r.grey}", "crafts": crafts, "expectedCrafts": round(seg["expected"], 2),
                     "materials": mats, "craftFirst": craft_first, "matCost": round(o.mat_cost * seg["expected"]),
                     "back": round(o.back_total(o.planned) * share), "backHow": back_how, "cost": round(cost),
                     "boughtRecipe": id(o) in bought_ids, "materialItems": mat_items, "product": r.product,
                     "recipeItem": r.recipe_item if o.source == "recipe item" else None,
                     "recipePrice": prices.material(r.recipe_item)[0] if o.source == "recipe item" else None,
                     "learnRank": r.learn_rank if o.source == "recipe item" else None})
    recipe_cost = sum(p for _, p in result["recipesBought"])
    reagents = {i for o in options for i in list(o.recipe.reagents) + list(o.mats)}
    return {
        "profession": profession, "skillLine": line, "from": start, "to": end, "build": rd.build,
        "character": ch.name, "tsmSkill": ch.level, "tsmCap": ch.max_level, "knownRecorded": known_recorded,
        "note": ch.note, "addonNote": addon.note if addon else None, "rows": rows, "craftCost": round(total),
        "recipeCost": recipe_cost, "total": round(total + recipe_cost),
        "gaps": gaps, "skipped": skipped, "effort": effort, "luck": luck, "chanceModel": chance_model,
        "rankUps": caps["rankUps"], "capBlock": caps["capBlock"], "rankStop": caps["stoppedAt"], "stockUsed": bool(have),
        "buyCost": round(buy_cost),
        # every priced recipe, so an exporter can build an in-game planner's input without reaching into build_options
        "options": [option_row(o) for o in options],
        # what the whole path buys, next to the TSM leveling reserve (groups "Leveling reserve`Keep N on main") and the
        # stock each item's rows take (earmarked, rule 2)
        "shopping": [{"item": name(i), "itemId": i, "need": n, "stock": used.get(i, 0), "buy": n - used.get(i, 0),
                      "reserve": ch.reserve.get(i)} for i, n in sorted(need.items(), key=lambda kv: -kv[1])],
        # true spares: owned profession materials no row uses (the only stock the addon offers for other crafts)
        "spares": [{"item": name(i), "itemId": i, "spare": have[i] - used[i]} for i in sorted(have)
                   if i in reagents and have[i] - used[i] > 0],
        "reserveUnused": [{"item": name(i), "itemId": i, "reserve": n} for i, n in sorted(ch.reserve.items())
                          if i not in need and any(i in o.recipe.reagents or i in o.crafted for o in options)],
        "assumptions": [
            ("skill-up chance (grey - skill) / (grey - yellow) between yellow and grey: vanilla-client formula, not confirmed for Forever"
             if chance_model == "formula" else
             "skill-up chance by colour band (1 orange, 0.75 yellow, 0.25 green): the addon's flat guess"),
            f"crafts and materials cover the p{luck} of the crafts a row takes (normal approximation of a sum of "
            "geometric draws); costs are at the mean",
            "trainer recipes are learnable from their yellow threshold; trainer fees are not counted",
            "products are sold when they pass the post-or-vendor test, else vendored; intermediates count at the cheaper of buying or crafting",
        ],
    }


# ---------------------------------------------------------------- text output


def _money(c) -> str:
    return A.format_money(round(c)) if c is not None else "-"


def render(d: dict) -> str:
    head = f"{d['profession'].title()} {d['from']} -> {d['to']}, crafts at p{d.get('luck', LUCK)}"
    if d["character"] and d["tsmSkill"] is not None:
        head += f"   (TSM: {d['character']} at {d['tsmSkill']}/{d['tsmCap']})"
    if d.get("chanceModel", "formula") != "formula":
        head += f", {d['chanceModel']} chance"
    lines = [head]
    for key in ("note", "addonNote"):
        if d.get(key):
            lines.append(f"note: {d[key]}")
    for up in d.get("rankUps") or []:
        lines.append(f"train {up['name'] or 'the next rank'} (cap {up['cap']}) before {up['by']}"
                     + (f", from skill {up['at']}" if up.get("at") else "") + (f", level {up['level']}" if up.get("level") else "")
                     + (f", {_money(up['cost'])}" if up.get("cost") else ""))
    if d.get("capBlock"):
        b = d["capBlock"]
        why = f"needs level {b['level']}" + (f", you are {b['have']}" if b.get("have") else "") if b["reason"] == "level" \
            else "taught by a special teacher"
        lines.append(f"stop at {b['by']}: {b['name']} (cap {b['cap']}) {why}")
    if d.get("rankStop"):
        lines.append(f"stop at {d['rankStop']}: the highest rank read at a trainer (SkillupHelperDB.ranks); "
                     "visit a trainer to read the next one")
    body = []
    for r in d["rows"]:
        if r["recipe"] is None:
            body.append([f"{r['from']}-{r['to']}", "(nothing priced)", "", "", "", "", "", ""])
            continue
        if d.get("stockUsed"):
            mats = ", ".join(f"{n} {k}" for k, n in r["buy"].items()) or "-"
            if r["fromStock"]:
                mats += " | stock " + ", ".join(f"{n} {k}" for k, n in r["fromStock"].items())
        else:
            mats = ", ".join(f"{n} {k}" for k, n in r["materials"].items())
        if r.get("chanceModel"):
            r = {**r, "recipe": r["recipe"] + " *"}
        if r["craftFirst"]:
            mats += " (craft " + ", ".join(f"{n} {k}" for k, n in r["craftFirst"].items()) + ")"
        body.append([f"{r['from']}-{r['to']}", r["recipe"], r["colors"], str(r["crafts"]), mats,
                     f"{_money(r['back'])} {r['backHow']}" if r["back"] else "-", _money(r["cost"]), r["source"]])
    lines.append(A._table(["skill", "recipe", "y/g/grey", "crafts", "buy", "back", "net", "source"], body, {3, 6}))
    lines.append(f"total {_money(d['total'])}" + (f" (crafts {_money(d['craftCost'])} + recipes {_money(d['recipeCost'])})" if d["recipeCost"] else ""))
    if d.get("stockUsed"):
        lines.append(f"materials to buy: {_money(d['buyCost'])} (p{d.get('luck', LUCK)} counts, stock taken off, before "
                     "product sales); the total is at the mean, net of sales, with every material priced, stock included")
    if any(r.get("chanceModel") for r in d["rows"]):
        lines.append("* the other chance model picks another recipe here: this row depends on the skill-up formula")
    if d["gaps"]:
        lines.append("gaps: " + ", ".join(d["gaps"]))
    if d["shopping"]:
        lines.append("")
        res = lambda m: "-" if m["reserve"] is None else str(m["reserve"])  # noqa: E731
        if d.get("stockUsed"):
            body = [[m["item"], str(m["need"]), str(m["stock"]), str(m["buy"]), res(m)] for m in d["shopping"]]
            body += [[m["item"], "0", "0", "0", str(m["reserve"])] for m in d["reserveUnused"]]
            lines.append(A._table(["material, whole path", "need", "stock", "buy", "reserve"], body, {1, 2, 3, 4}))
        else:
            body = [[m["item"], str(m["need"]), res(m)] for m in d["shopping"]]
            body += [[m["item"], "0", str(m["reserve"])] for m in d["reserveUnused"]]
            lines.append(A._table(["material, whole path", "need", "reserve"], body, {1, 2}))
    if d.get("spares"):
        lines.append("spares (no row uses them): " + ", ".join(f"{m['spare']} {m['item']}" for m in d["spares"]))
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profession", help="Leatherworking, Cooking, 'First Aid', ... or a skill line id")
    ap.add_argument("start", nargs="?", type=int, help="current skill (default: TSM's recorded skill)")
    ap.add_argument("end", nargs="?", type=int,
                    help=f"target skill (default: the top rank cap, {TOP_RANK_CAP}, or TSM's recorded cap if higher)")
    ap.add_argument("--char", help="character name when several have the profession")
    ap.add_argument("--appdata", help="path to AppData.lua (default: the Forever game folder)")
    ap.add_argument("--realm")
    ap.add_argument("--region")
    ap.add_argument("--saved-vars", help="TSM's SavedVariables\\TradeSkillMaster.lua (default: the newest under the game's WTF)")
    ap.add_argument("--cache-dir", help="wago cache folder (default %%LOCALAPPDATA%%\\ClaudeForever\\tsm-cache)")
    ap.add_argument("--build", help="wowf build (default: newest cached, else newest published)")
    ap.add_argument("--offline", action="store_true", help="never download")
    ap.add_argument("--vendor-products", action="store_true", help="count every product at vendor price (no auction sales)")
    ap.add_argument("--sell-days", type=float, default=2.0, help="days of the region's sales one product can count on (default 2)")
    ap.add_argument("--effort", type=float, default=DEFAULT_EFFORT,
                    help=f"copper charged per craft on top of its net cost, as the addon does (default {DEFAULT_EFFORT})")
    ap.add_argument("--luck", type=int, default=LUCK, choices=sorted(Z_OF),
                    help=f"percentile of crafts each row buys for, as the addon's /skillup luck (default {LUCK})")
    ap.add_argument("--chance", choices=sorted(CHANCE_MODELS), default="formula",
                    help="skill-up chance model: the vanilla formula (default) or the addon's flat colour guess")
    ap.add_argument("--no-stock", action="store_true",
                    help="ignore the character's bags and bank (TSM's inventory); by default rows take their stock first")
    ap.add_argument("--addon-saved-vars",
                    help="SkillupHelper's SavedVariables (trainer ranks, trainerSeen; default: the newest under the game's WTF)")
    ap.add_argument("--level", type=int, help="character level, for a rank that needs a higher one (the addon's capBlock)")
    ap.add_argument("--json", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        cache = Path(a.cache_dir) if a.cache_dir else A.default_cache_dir()
        build = a.build or default_build(cache, not a.offline)
        rd = RecipeData.from_tables(fetch_recipe_tables(build, cache, not a.offline), build)
        data = A.AppData.from_file(a.appdata)
        rows = {r["itemId"]: r for r in data.merged(a.realm, a.region).values() if r["itemString"] == f"i:{r['itemId']}"}
        ch = load_character(a.saved_vars or os.environ.get("TSM_SAVED_VARS") or A.default_saved_vars(), a.profession, a.char)
        start = a.start if a.start is not None else ch.level
        # default target: the top rank cap, as the addon plans, or TSM's recorded cap when higher
        end = a.end if a.end is not None else max(TOP_RANK_CAP, ch.max_level or 0)
        if start is None or end is None:
            raise SkillupError(f"give the skill range: {ch.note or 'TSM has no skill recorded'}")
        if end <= start:
            raise SkillupError(f"target {end} is not above {start}")
        prices = Prices(rows, rd.items, VENDOR_REAGENTS | ch.vendor_items, not a.vendor_products, a.sell_days)
        addon = load_addon_state(a.addon_saved_vars or default_addon_saved_vars())
        result = report(rd, a.profession, start, end, prices, ch, a.effort, a.luck, addon,
                        None if a.no_stock else ch.stock, a.chance, a.level)
        text = json.dumps(result, ensure_ascii=False, separators=(",", ":")) if a.json else render(result)
        try:
            print(text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
        return 0
    except A.AppDataError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
