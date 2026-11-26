#!/usr/bin/env python3
"""Read the price data the TradeSkillMaster desktop app syncs, offline.

    python -I tools/tsm/appdata.py info
    python -I tools/tsm/appdata.py item 2622
    python -I tools/tsm/appdata.py item "pagan britches of the owl"
    python -I tools/tsm/appdata.py top --by regionSaleRate --class Armor --subclass Leather --quality 2 --bind boe
    python -I tools/tsm/appdata.py export --out prices.json

The desktop app rewrites `TradeSkillMaster_AppHelper\\AppData.lua` on every sync: one `LoadData(tag, realm-or-region,
[[return {downloadTime=..,fields={..},data={{key,v,v},..}}]])` call per data set, values in base 32. This module
decodes that the way the addon does (format, scaling and source pointers: docs/tsm/appdata-format.md) and joins
it with item names and attributes from two sources: wago.tools DB2 exports of the Forever client (`wowf`), cached
under %LOCALAPPDATA%\\ClaudeForever\\tsm-cache\\wago\\<build>\\, and, for the items that export lacks (most
random-suffix greens), TSM's own item cache (`TSMItemInfoDB` in SavedVariables\\TradeSkillMaster.lua, read only).
Nothing here writes to the game folder.

Prices are copper. `regionSaleRate` (stored as regionSalePercent) and `regionSoldPerDay` are stored times 1000
and returned unscaled. A stored 0 means "no value" (the addon returns nil for it) and is left out of a row.

Add --json to any command for compact JSON. Exit code 2 = a broken link, named on stderr.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import struct
import sys
import time
import zlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_GAME_PARENT = r"C:\Program Files (x86)\World of Warcraft"
APPDATA_REL = Path("_forever_") / "Interface" / "AddOns" / "TradeSkillMaster_AppHelper" / "AppData.lua"

REALM_TAGS = ("AUCTIONDB_NON_COMMODITY_DATA", "AUCTIONDB_NON_COMMODITY_SCAN_STAT", "AUCTIONDB_NON_COMMODITY_HISTORICAL")
REGION_TAGS = ("AUCTIONDB_REGION_STAT", "AUCTIONDB_REGION_HISTORICAL", "AUCTIONDB_REGION_SALE")
COMMODITY_TAGS = ("AUCTIONDB_COMMODITY_DATA", "AUCTIONDB_COMMODITY_SCAN_STAT", "AUCTIONDB_COMMODITY_HISTORICAL")
TAG_SCOPE = {**{t: "realm" for t in REALM_TAGS}, **{t: "region" for t in REGION_TAGS}, **{t: "commodity" for t in COMMODITY_TAGS}}

REALM_FIELDS = ("minBuyout", "numAuctions", "marketValueRecent", "marketValue", "historical")
REGION_FIELDS = ("regionMarketValue", "regionHistorical", "regionSale", "regionSaleRate", "regionSoldPerDay")
PRICE_FIELDS = {"minBuyout", "marketValueRecent", "marketValue", "historical", "regionMarketValue", "regionHistorical", "regionSale"}
SCALED_FIELDS = {"regionSalePercent": "regionSaleRate", "regionSoldPerDay": "regionSoldPerDay"}  # stored name -> output name
SCALE = 1000
FIELD_ALIASES = {
    "regionsalepercent": "regionSaleRate", "salerate": "regionSaleRate", "soldperday": "regionSoldPerDay",
    "dbminbuyout": "minBuyout", "dbmarket": "marketValue", "dbrecent": "marketValueRecent", "dbhistorical": "historical",
    "dbnumauctions": "numAuctions", "dbregionmarketavg": "regionMarketValue", "dbregionhistorical": "regionHistorical",
    "dbregionsaleavg": "regionSale", "dbregionsalerate": "regionSaleRate", "dbregionsoldperday": "regionSoldPerDay",
}
ATTR_SORT_FIELDS = ("vendorSell", "requiredLevel", "itemLevel")

QUALITY_NAMES = {0: "poor", 1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary", 6: "artifact", 7: "heirloom"}
BIND_NAMES = {0: "none", 1: "bop", 2: "boe", 3: "bou", 4: "quest"}
SLOT_NAMES = {
    1: "Head", 2: "Neck", 3: "Shoulder", 4: "Shirt", 5: "Chest", 6: "Waist", 7: "Legs", 8: "Feet", 9: "Wrist", 10: "Hands",
    11: "Finger", 12: "Trinket", 13: "One-Hand", 14: "Shield", 15: "Ranged", 16: "Back", 17: "Two-Hand", 18: "Bag",
    19: "Tabard", 20: "Chest", 21: "Main Hand", 22: "Off Hand", 23: "Held In Off-hand", 24: "Ammo", 25: "Thrown",
    26: "Ranged", 28: "Relic",
}

FALLBACK_CLASSES = {0: "Consumable", 1: "Container", 2: "Weapon", 4: "Armor", 5: "Reagent", 6: "Projectile", 7: "Trade Goods",
                    9: "Recipe", 11: "Quiver", 12: "Quest", 13: "Key", 15: "Miscellaneous"}  # when the export is unavailable
FALLBACK_SUBCLASSES = {(4, 0): "Miscellaneous", (4, 1): "Cloth", (4, 2): "Leather", (4, 3): "Mail", (4, 4): "Plate", (4, 6): "Shield",
                       (7, 5): "Cloth", (7, 6): "Leather", (7, 7): "Metal & Stone", (7, 9): "Herb"}

WAGO_PRODUCT = "wowf"
WAGO_BUILDS_URL = "https://wago.tools/api/builds"
WAGO_CSV_URL = "https://wago.tools/db2/{table}/csv?build={build}&locale=enUS"
WAGO_TABLES = ("ItemSparse", "Item", "ItemClass", "ItemSubClass")
USER_AGENT = "Mozilla/5.0 (compatible; tsm-appdata/1.0)"

_CALL_RE = re.compile(r'LoadData\("([A-Z_]+)","([^"]*)",\[\[(.*?)\]\]\)[ \t]*(?:--<([^>\n]*)>)?', re.S)
_ROW_RE = re.compile(r'\{"?([^,"]+)"?,([^}]+)\}')  # the addon's own row pattern (AuctionDB.lua:203)
_SUFFIX_RE = re.compile(r"\s+of\s+(the\s+)?[\w' -]+$", re.IGNORECASE)


class AppDataError(Exception):
    """A broken link, named: which file, tag, item or name source failed and why."""


class NameSourceError(AppDataError):
    """The item name source is unavailable (no cache and no download)."""


# ---------------------------------------------------------------- decoding


def decode_b32(text: str) -> int:
    """Base 32, digits 0-9 A-V, most significant first (Lua `tonumber(v, 32)`).

    The addon splits values longer than 6 digits in two halves only because Lua's tonumber is 32-bit; the number
    is the same (AuctionDB.lua:245-250).
    """
    try:
        return int(text, 32)
    except ValueError as e:
        raise AppDataError(f"not a base-32 number: {text!r}") from e


def format_money(copper: int | None) -> str:
    """12345 -> '1g23s45c', 1303 -> '13s03c', 7 -> '7c'."""
    if copper is None:
        return "-"
    sign = "-" if copper < 0 else ""
    copper = abs(int(copper))
    g, s, c = copper // 10000, copper // 100 % 100, copper % 100
    if g:
        return f"{sign}{g}g{s:02d}s{c:02d}c"
    if s:
        return f"{sign}{s}s{c:02d}c"
    return f"{sign}{c}c"


def normalize_key(item: str | int) -> tuple[str, str]:
    """(itemString as given, base itemString). 2622, '2622', 'item:2622', 'i:2622', 'i:2622:-18', 'i:2622::i25'."""
    text = str(item).strip()
    if text.isdigit():
        text = "i:" + text
    m = re.fullmatch(r"item:(\d+)", text)
    if m:
        text = "i:" + m.group(1)
    m = re.match(r"^([ip]:\d+)(:[0-9i:+\-]*)?$", text)
    if not m:
        raise AppDataError(f"not an item id or item string: {item!r} (expected 2622, i:2622, i:2622:-18 or i:2622::i25)")
    return text.rstrip(":"), m.group(1)


@dataclass
class Block:
    tag: str
    name: str  # realm ("<Realm>-Horde") or region ("Forever-US")
    scope: str  # realm | region | commodity
    download_time: int
    fields: list[str]  # without the leading itemString
    rows: dict[str, tuple[int, ...]]
    trailer: list[str] = field(default_factory=list)  # the --<tag,name,time[,n]> comment


@dataclass
class AppData:
    blocks: list[Block]
    app_info: dict
    path: str | None = None

    # -- loading

    @classmethod
    def from_file(cls, path: str | os.PathLike | None = None) -> "AppData":
        p = Path(path) if path else default_appdata_path()
        if not p.is_file():
            raise AppDataError(
                f"AppData.lua not found at {p}: the TSM desktop app has not synced into this game folder "
                f"(or the addon TradeSkillMaster_AppHelper is not installed). Pass --appdata <path> or set WOWF_GAME_DIR."
            )
        data = cls.from_text(p.read_text(encoding="utf-8", errors="replace"), source=str(p))
        data.path = str(p)
        return data

    @classmethod
    def from_text(cls, text: str, source: str = "<text>") -> "AppData":
        blocks: list[Block] = []
        app_info: dict = {}
        for m in _CALL_RE.finditer(text):
            tag, name, body, trailer = m.group(1), m.group(2), m.group(3), m.group(4)
            if tag == "APP_INFO":
                app_info = _parse_app_info(body)
            elif tag in TAG_SCOPE:
                blocks.append(_parse_block(tag, name, body, trailer, source))
            # other tags (SHOPPING_SEARCHES, GROUP_IMPORTS) are not price data
        if not blocks and not app_info:
            raise AppDataError(f"{source}: no LoadData(...) call found; this is not a TSM AppData.lua (or the app wrote an empty file)")
        return cls(blocks, app_info)

    # -- selection

    def names(self, scope: str) -> list[str]:
        return sorted({b.name for b in self.blocks if b.scope == scope})

    def pick(self, scope: str, wanted: str | None = None) -> str | None:
        """The realm or region to read: the only one present, or the one asked for."""
        have = self.names(scope)
        if wanted:
            for n in have:
                if n.lower() == wanted.lower():
                    return n
            raise AppDataError(f"no {scope} data for {wanted!r} in AppData.lua; it holds {have or 'none'}")
        if len(have) > 1:
            raise AppDataError(f"AppData.lua holds {scope} data for {have}; say which with --{scope}")
        return have[0] if have else None

    def block(self, tag: str, name: str | None = None) -> Block:
        found = [b for b in self.blocks if b.tag == tag and (name is None or b.name == name)]
        if not found:
            have = sorted({f"{b.tag}/{b.name}" for b in self.blocks})
            raise AppDataError(f"tag {tag}{'/' + name if name else ''} is not in AppData.lua; present: {have}")
        return found[0]

    def selected(self, realm: str | None = None, region: str | None = None) -> list[Block]:
        realm_name, region_name = self.pick("realm", realm), self.pick("region", region)
        out = [b for b in self.blocks if b.scope == "realm" and b.name == realm_name]
        out += [b for b in self.blocks if b.scope == "region" and b.name == region_name]
        # commodity data is published per region and read as realm data (AuctionDB.lua:140)
        out += [b for b in self.blocks if b.scope == "commodity" and (region_name is None or b.name == region_name)]
        return out

    # -- reading

    def merged(self, realm: str | None = None, region: str | None = None) -> dict[str, dict]:
        """One row per data key: {itemString, itemId, inRealm, inRegion, <field>: value}. Zero values are left out."""
        rows: dict[str, dict] = {}
        for b in self.selected(realm, region):
            flag = "inRegion" if b.scope == "region" else "inRealm"
            for key, values in b.rows.items():
                row = rows.get(key)
                if row is None:
                    m = re.match(r"^i:(\d+)", key)
                    row = rows[key] = {"itemString": key, "itemId": int(m.group(1)) if m else None, "inRealm": False, "inRegion": False}
                row[flag] = True
                for name, value in zip(b.fields, values):
                    out_name, out_value = _unscale(name, value)
                    if out_value is not None:
                        row.setdefault(out_name, out_value)
        return rows

    def lookup(self, item: str | int, realm: str | None = None, region: str | None = None) -> dict:
        """Every field for one item from every tag, with the variant -> base fallback the addon uses.

        Returns {itemString, key (per tag), tags: {tag: {name, key, raw: {field: int}}}, values: {field: value}}.
        Raises when the item is in no tag at all.
        """
        exact, base = normalize_key(item)
        tags: dict[str, dict] = {}
        values: dict[str, float | int] = {}
        in_scope = {"realm": False, "region": False}
        selected = self.selected(realm, region)
        for b in selected:
            key = exact if exact in b.rows else base if base in b.rows else None
            if key is None:
                continue
            in_scope["region" if b.scope == "region" else "realm"] = True
            raw = dict(zip(b.fields, b.rows[key]))
            tags[b.tag] = {"name": b.name, "key": key, "downloadTime": b.download_time, "raw": raw}
            for name, value in raw.items():
                out_name, out_value = _unscale(name, value)
                if out_value is not None:
                    values.setdefault(out_name, out_value)
        if not tags:
            where = sorted({f"{b.scope} {b.name}" for b in selected}) or ["no price tags at all"]
            raise AppDataError(f"item {exact} is in no price data ({', '.join(where)}): never seen on these auction houses in the sync window")
        return {"itemString": exact, "baseItemString": base, "inRealm": in_scope["realm"], "inRegion": in_scope["region"], "tags": tags, "values": values}

    def update_times(self, realm: str | None = None, region: str | None = None) -> dict:
        """Newest downloadTime per scope, the way the addon computes its 'x ago' (AuctionDB.lua:26-32, 182-184)."""
        out = {"realm": 0, "region": 0}
        for b in self.selected(realm, region):
            if b.scope in out and b.tag != "AUCTIONDB_NON_COMMODITY_HISTORICAL":
                out[b.scope] = max(out[b.scope], b.download_time)
        return out


def _unscale(name: str, value: int):
    if value <= 0:
        return SCALED_FIELDS.get(name, name), None
    if name in SCALED_FIELDS:
        return SCALED_FIELDS[name], value / SCALE
    return name, value


def _parse_app_info(body: str) -> dict:
    info: dict = {}
    m = re.search(r'version="([^"]*)"', body)
    if m:
        info["version"] = m.group(1)
    m = re.search(r"lastSync=(\d+)", body)
    if m:
        info["lastSync"] = int(m.group(1))
    m = re.search(r'message=\{id=(\d+),msg="((?:[^"\\]|\\.)*)"', body)
    if m:
        info["message"] = {"id": int(m.group(1)), "msg": m.group(2)}
    info["news"] = [{"title": t, "timestamp": None} for t in re.findall(r'title="((?:[^"\\]|\\.)*)"', body)]
    for entry, ts in zip(info["news"], re.findall(r"timestamp=(\d+)", body)):
        entry["timestamp"] = int(ts)
    return info


def _parse_block(tag: str, name: str, body: str, trailer: str | None, source: str) -> Block:
    where = f"{source}: {tag}/{name}"
    split = body.find(",data={")
    if split < 0:
        raise AppDataError(f"{where}: no ',data={{' in the payload; the app changed its format")
    meta = body[:split]
    m = re.search(r"downloadTime=(\d+)", meta)
    f = re.search(r"fields=\{([^}]*)\}", meta)
    if not m or not f:
        raise AppDataError(f"{where}: metadata has no downloadTime/fields: {meta[:120]!r}")
    fields = re.findall(r'"([^"]+)"', f.group(1))
    if not fields or fields[0] != "itemString":
        raise AppDataError(f"{where}: first field is {fields[:1]}, expected 'itemString'")
    fields = fields[1:]
    rows: dict[str, tuple[int, ...]] = {}
    for key, rest in _ROW_RE.findall(body[split + 7:]):
        if key.isdigit():
            key = "i:" + key
        parts = rest.split(",")
        if len(parts) != len(fields):
            raise AppDataError(f"{where}: row {key} has {len(parts)} values for fields {fields}")
        if key in rows:
            raise AppDataError(f"{where}: duplicate row for {key}")
        try:
            rows[key] = tuple(int(p, 32) for p in parts)
        except ValueError as e:
            raise AppDataError(f"{where}: row {key} has a value that is not base 32: {rest!r}") from e
    return Block(tag, name, TAG_SCOPE[tag], int(m.group(1)), fields, rows, trailer.split(",") if trailer else [])


def default_appdata_path() -> Path:
    explicit = os.environ.get("TSM_APPDATA")
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("WOWF_GAME_DIR") or DEFAULT_GAME_PARENT) / APPDATA_REL


# ---------------------------------------------------------------- item names and attributes


def default_cache_dir() -> Path:
    explicit = os.environ.get("TSM_CACHE_DIR")
    if explicit:
        return Path(explicit)
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "ClaudeForever" / "tsm-cache"


def _version_key(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", version))


def _http_get(url: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
        return r.read()


def latest_build(http_get=_http_get) -> str:
    builds = json.loads(http_get(WAGO_BUILDS_URL, 60))
    rows = builds.get(WAGO_PRODUCT, []) if isinstance(builds, dict) else [b for b in builds if b.get("product") == WAGO_PRODUCT]
    rows = [b for b in rows if b.get("version")]
    if not rows:
        raise NameSourceError(f"{WAGO_BUILDS_URL}: no builds listed for product {WAGO_PRODUCT!r}")
    return max(rows, key=lambda b: (b.get("created_at") or "", _version_key(b["version"])))["version"]


def cached_builds(cache_dir: Path) -> list[str]:
    root = cache_dir / "wago"
    if not root.is_dir():
        return []
    ok = [d.name for d in root.iterdir() if d.is_dir() and all((d / f"{t}.enUS.csv").is_file() for t in WAGO_TABLES)]
    return sorted(ok, key=_version_key)


def fetch_tables(build: str, cache_dir: Path, http_get=_http_get) -> Path:
    folder = cache_dir / "wago" / build
    for table in WAGO_TABLES:
        f = folder / f"{table}.enUS.csv"
        if f.is_file() and f.stat().st_size > 0:
            continue
        url = WAGO_CSV_URL.format(table=table, build=build)
        try:
            data = http_get(url)
        except (urllib.error.URLError, OSError) as e:
            raise NameSourceError(f"item name source unavailable: {url} -> {e}; no cached copy in {folder}") from e
        if data[:200].lstrip().startswith(b"<") or b"," not in data.split(b"\n", 1)[0]:
            raise NameSourceError(f"item name source unavailable: {url} did not return a CSV (starts {data[:60]!r}); not cached")
        folder.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(f)
    return folder


def _read_csv(path: Path, needed: tuple[str, ...]) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise NameSourceError(f"item name source broken: {path} has no rows")
    missing = [c for c in needed if c not in rows[0]]
    if missing:
        raise NameSourceError(f"item name source broken: {path} lacks column(s) {missing}; header has {sorted(rows[0])[:12]}...")
    return rows


def _cbor(b: bytes, p: int = 0):
    """Minimal CBOR reader (ints, byte/text strings, arrays, maps, simple values, floats): (value, next offset)."""
    ib = b[p]
    p += 1
    major, ai = ib >> 5, ib & 31
    if ai < 24:
        n = ai
    elif ai in (24, 25, 26, 27):
        size = 1 << (ai - 24)
        n = int.from_bytes(b[p:p + size], "big")
        p += size
    elif ai == 31:
        n = None
    else:
        raise ValueError(f"CBOR additional info {ai}")
    if major == 0:
        return n, p
    if major == 1:
        return -1 - n, p
    if major in (2, 3):
        return b[p:p + n].decode("utf-8", "replace"), p + n
    if major == 4:
        out = []
        while (n is None and b[p] != 0xFF) or (n is not None and len(out) < n):
            v, p = _cbor(b, p)
            out.append(v)
        return out, p + (1 if n is None else 0)
    if major == 5:
        d = {}
        for _ in range(n):
            k, p = _cbor(b, p)
            d[k], p = _cbor(b, p)
        return d, p
    if major == 7:
        if ai in (20, 21):
            return ai == 21, p
        if ai in (22, 23):
            return None, p
        if ai in (25, 26, 27):
            return struct.unpack({25: ">e", 26: ">f", 27: ">d"}[ai], n.to_bytes(1 << (ai - 24), "big"))[0], p
    raise ValueError(f"CBOR major {major} info {ai}")


TSM_CACHE_FIELDS = ("itemString", "name", "itemLevel", "minLevel", "maxStack", "vendorSell", "invSlotId", "texture", "classId",
                    "subClassId", "quality", "isBOP", "isCraftingReagent", "expansionId", "craftedQuality")


def default_saved_vars() -> Path | None:
    """TSM's SavedVariables file: TSM_SAVED_VARS, else the newest WTF\\Account\\*\\SavedVariables\\TradeSkillMaster.lua."""
    explicit = os.environ.get("TSM_SAVED_VARS")
    if explicit:
        return Path(explicit)
    wtf = Path(os.environ.get("WOWF_GAME_DIR") or DEFAULT_GAME_PARENT) / "_forever_" / "WTF" / "Account"
    found = [p for p in wtf.glob("*/SavedVariables/TradeSkillMaster.lua") if p.is_file()] if wtf.is_dir() else []
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def read_tsm_item_cache(path: Path) -> tuple[list[dict], str]:
    """Decode the `TSMItemInfoDB` global: base64( raw deflate( CBOR flat array, 15 values per item ) ). -1 = unknown.

    Returns (rows, versionStr). The cache holds only items this client has seen (TSM queries everything in the
    realm data at login), each under its item string, random-suffix variants included.
    """
    shown = "WTF\\Account\\*\\SavedVariables\\" + Path(path).name  # the account folder name stays out of messages
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise NameSourceError(f"TSM item cache unavailable: cannot read {shown}: {e.strerror}") from e
    start = text.find("TSMItemInfoDB = {")
    m = re.search(r'\["data"\] = "([A-Za-z0-9+/=]*)"', text[start:]) if start >= 0 else None
    if not m:
        raise NameSourceError(f"TSM item cache unavailable: {shown} has no TSMItemInfoDB.data string (the addon has not saved its item cache yet)")
    version = re.search(r'\["versionStr"\] = "([^"]*)"', text[start:])
    try:
        flat, _ = _cbor(zlib.decompress(base64.b64decode(m.group(1)), -15))
    except (ValueError, IndexError, zlib.error) as e:
        raise NameSourceError(f"TSM item cache unavailable: TSMItemInfoDB.data in {shown} does not decode (base64 > deflate > CBOR): {e}") from e
    width = len(TSM_CACHE_FIELDS)
    if not isinstance(flat, list) or len(flat) % width:
        raise NameSourceError(f"TSM item cache unavailable: TSMItemInfoDB.data in {shown} is not a flat array of {width}-value records")
    rows = [dict(zip(TSM_CACHE_FIELDS, flat[i:i + width])) for i in range(0, len(flat), width)]
    return rows, version.group(1) if version else ""


@dataclass
class ItemDB:
    items: dict[int, dict]
    build: str
    source: str
    classes: dict = field(default_factory=dict)
    subclasses: dict = field(default_factory=dict)
    variants: dict[str, str] = field(default_factory=dict)  # variant item string -> its own name ('... of the Owl')
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def open(cls, cache_dir: Path | None = None, build: str | None = None, download: bool = True, refresh: bool = False,
             saved_vars: Path | None = None, tsm_cache: bool = True, http_get=_http_get) -> "ItemDB":
        """Both sources: the wago.tools export first, then TSM's own item cache for what the export lacks.

        The Forever client's ItemSparse has no row for most random-suffix greens ('Pagan Britches'), so the export
        alone names about half the priced items; TSM's cache has the rest. Either source alone still works, and
        the one that failed is kept in `warnings`. Both missing: NameSourceError.
        """
        errors = []
        try:
            db = cls.load(cache_dir, build, download, refresh, http_get)
        except NameSourceError as e:
            errors.append(str(e))
            db = cls({}, "", "")
        if tsm_cache:
            try:
                path = Path(saved_vars) if saved_vars else default_saved_vars()
                if path is None:
                    raise NameSourceError("TSM item cache unavailable: no WTF\\Account\\*\\SavedVariables\\TradeSkillMaster.lua under the game folder")
                db.merge_tsm_cache(*read_tsm_item_cache(path))
            except NameSourceError as e:
                errors.append(str(e))
        if not db.items:
            raise NameSourceError("item name source unavailable: " + "; ".join(errors))
        db.warnings = errors
        return db

    def merge_tsm_cache(self, rows: list[dict], version: str = "") -> int:
        """Add items the export lacks; keep variant names for name search. Returns how many items were added."""
        added = 0
        for r in rows:
            key, name = r["itemString"], r["name"]
            m = re.fullmatch(r"i:(\d+)", key)
            if not m:
                if name:
                    self.variants[key] = name
                continue
            item_id = int(m.group(1))
            if item_id in self.items or not name:
                continue
            known = lambda v: v if isinstance(v, int) and v >= 0 else None  # noqa: E731
            class_id, subclass_id, slot, quality = known(r["classId"]), known(r["subClassId"]), known(r["invSlotId"]), known(r["quality"])
            if r["isBOP"] == 1:
                bind = "bop"
            elif r["isBOP"] == 0:
                bind = "boe" if slot and (quality or 0) >= 2 else "none"  # the cache stores only "binds on pickup or not"
            else:
                bind = None
            self.items[item_id] = {
                "name": name,
                "quality": quality,
                "qualityName": QUALITY_NAMES.get(quality, str(quality)) if quality is not None else None,
                "classId": class_id,
                "className": self.classes.get(class_id) or FALLBACK_CLASSES.get(class_id),
                "subclassId": subclass_id,
                "subclassName": self.subclasses.get((class_id, subclass_id)) or FALLBACK_SUBCLASSES.get((class_id, subclass_id)),
                "slot": SLOT_NAMES.get(slot) if slot else None,
                "requiredLevel": known(r["minLevel"]),
                "itemLevel": known(r["itemLevel"]),
                "bind": bind,
                "stackSize": known(r["maxStack"]),
                "vendorSell": known(r["vendorSell"]),
                "attrSource": "tsm-cache",
            }
            added += 1
        note = f"TSMItemInfoDB ({version or 'no version'}): +{added} items the export lacks, {len(self.variants)} variant names; bind inferred from isBOP"
        self.source = f"{self.source} + {note}" if self.source else note
        return added

    @classmethod
    def load(cls, cache_dir: Path | None = None, build: str | None = None, download: bool = True, refresh: bool = False, http_get=_http_get) -> "ItemDB":
        """Newest cached build, offline; downloads only when nothing is cached, a build is named, or refresh is set."""
        cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        have = cached_builds(cache_dir)
        if build is None and refresh and download:
            try:
                build = latest_build(http_get)
            except (urllib.error.URLError, OSError, ValueError) as e:
                raise NameSourceError(f"item name source unavailable: {WAGO_BUILDS_URL} -> {e}") from e
        if build is None and have:
            build = have[-1]
        if build is None:
            if not download:
                raise NameSourceError(f"item name source unavailable: no wago.tools export cached under {cache_dir / 'wago'} and downloading is off (--offline)")
            try:
                build = latest_build(http_get)
            except (urllib.error.URLError, OSError, ValueError) as e:
                raise NameSourceError(f"item name source unavailable: {WAGO_BUILDS_URL} -> {e}; nothing cached under {cache_dir / 'wago'}") from e
        if build not in have:
            if not download:
                raise NameSourceError(f"item name source unavailable: build {build} is not cached under {cache_dir / 'wago'} (cached: {have or 'none'}) and downloading is off")
            fetch_tables(build, cache_dir, http_get)
        return cls.from_folder(cache_dir / "wago" / build, build)

    @classmethod
    def from_folder(cls, folder: Path, build: str | None = None) -> "ItemDB":
        folder = Path(folder)
        for t in WAGO_TABLES:
            if not (folder / f"{t}.enUS.csv").is_file():
                raise NameSourceError(f"item name source unavailable: {folder / (t + '.enUS.csv')} is missing")
        classes = {int(r["ClassID"]): r["ClassName_lang"] for r in _read_csv(folder / "ItemClass.enUS.csv", ("ClassID", "ClassName_lang"))}
        subclasses = {}
        for r in _read_csv(folder / "ItemSubClass.enUS.csv", ("ClassID", "SubClassID", "DisplayName_lang")):
            subclasses[(int(r["ClassID"]), int(r["SubClassID"]))] = r["DisplayName_lang"] or r.get("VerboseName_lang", "")
        kinds = {int(r["ID"]): (int(r["ClassID"]), int(r["SubclassID"])) for r in _read_csv(folder / "Item.enUS.csv", ("ID", "ClassID", "SubclassID"))}
        need = ("ID", "Display_lang", "OverallQualityID", "RequiredLevel", "ItemLevel", "Bonding", "Stackable", "SellPrice", "InventoryType")
        items: dict[int, dict] = {}
        for r in _read_csv(folder / "ItemSparse.enUS.csv", need):
            item_id = int(r["ID"])
            class_id, subclass_id = kinds.get(item_id, (None, None))
            quality, bonding, slot = int(r["OverallQualityID"]), int(r["Bonding"]), int(r["InventoryType"])
            items[item_id] = {
                "name": r["Display_lang"],
                "quality": quality,
                "qualityName": QUALITY_NAMES.get(quality, str(quality)),
                "classId": class_id,
                "className": classes.get(class_id),
                "subclassId": subclass_id,
                "subclassName": subclasses.get((class_id, subclass_id)),
                "slot": SLOT_NAMES.get(slot) if slot else None,
                "requiredLevel": int(r["RequiredLevel"]),
                "itemLevel": int(r["ItemLevel"]),
                "bind": BIND_NAMES.get(bonding, str(bonding)),
                "stackSize": int(r["Stackable"]),
                "vendorSell": int(r["SellPrice"]),
                "attrSource": "wago",
            }
        build = build or folder.name
        return cls(items, build, f"wago.tools DB2 export, product {WAGO_PRODUCT}, build {build}, enUS ({len(items)} items, {folder})",
                   classes, subclasses)

    def get(self, item_id: int | None) -> dict | None:
        return self.items.get(item_id) if item_id is not None else None

    def find(self, fragment: str) -> tuple[list[str], str | None]:
        """Item strings whose name matches: exact (case-insensitive) first, else substring.

        A random-suffix name ('Pagan Britches of the Owl') is no item of its own: when TSM's cache has that exact
        variant its item string is returned, otherwise the suffix is stripped and the base item returned. Either
        way the note says the prices are the base item's.
        """
        want = fragment.strip().lower()
        base_note = "TSM prices every random suffix of an item under the base item, so these are the base item's numbers"
        exact = [f"i:{i}" for i, a in sorted(self.items.items()) if a["name"].lower() == want]
        if exact:
            return exact, None
        exact = sorted(k for k, n in self.variants.items() if n.lower() == want)
        if exact:
            return exact[:1], f"'{self.variants[exact[0]]}' is the variant {exact[0]}: {base_note}"
        part = [i for i, a in self.items.items() if want in a["name"].lower()]
        if part:
            return [f"i:{i}" for i in sorted(part, key=lambda i: (len(self.items[i]["name"]), i))], None
        stripped = _SUFFIX_RE.sub("", fragment.strip())
        if stripped and stripped.lower() != want:
            keys, _ = self.find(stripped)
            if keys:
                suffix = fragment.strip()[len(stripped):].strip()
                return keys, f"'{suffix}' read as a random suffix of '{stripped}': {base_note}"
        return [], None


# ---------------------------------------------------------------- queries


def enrich(row: dict, db: ItemDB | None) -> dict:
    attrs = db.get(row.get("itemId")) if db else None
    out = dict(row)
    if attrs:
        out.update(attrs)
    elif db:
        out["name"] = None
    return out


def canonical_field(name: str) -> str:
    known = (*REALM_FIELDS, *REGION_FIELDS, *ATTR_SORT_FIELDS)
    for k in known:
        if k.lower() == name.lower():
            return k
    if name.lower() in FIELD_ALIASES:
        return FIELD_ALIASES[name.lower()]
    raise AppDataError(f"unknown field {name!r}; fields: {', '.join(known)}")


def _parse_quality(text: str | None) -> int | None:
    if text is None:
        return None
    if text.isdigit():
        return int(text)
    for k, v in QUALITY_NAMES.items():
        if v == text.lower():
            return k
    raise AppDataError(f"unknown quality {text!r}; use 0-5 or one of {', '.join(QUALITY_NAMES.values())}")


def top(data: AppData, db: ItemDB | None, by: str, *, item_class: str | None = None, subclass: str | None = None,
        quality: str | None = None, bind: str | None = None, min_level: int | None = None, max_level: int | None = None,
        min_sale_rate: float | None = None, in_realm: bool = False, ascending: bool = False, limit: int = 20,
        realm: str | None = None, region: str | None = None) -> list[dict]:
    by = canonical_field(by)
    q = _parse_quality(quality)
    if bind and bind.lower() not in BIND_NAMES.values():
        raise AppDataError(f"unknown bind type {bind!r}; use one of {', '.join(BIND_NAMES.values())}")
    needs_attrs = any(v is not None for v in (item_class, subclass, q, bind, min_level, max_level)) or by in ATTR_SORT_FIELDS
    if needs_attrs and db is None:
        raise NameSourceError("item name source unavailable: --class/--subclass/--quality/--bind/--min-level/--max-level need item attributes")
    if db is not None:
        if item_class and not any((a["className"] or "").lower() == item_class.lower() for a in db.items.values()):
            raise AppDataError(f"no item class named {item_class!r}; classes: {sorted({a['className'] for a in db.items.values() if a['className']})}")
        if subclass and not any((a["subclassName"] or "").lower() == subclass.lower() for a in db.items.values()):
            raise AppDataError(f"no item subclass named {subclass!r} (examples: Cloth, Leather, Mail, Plate, Herb, Metal & Stone)")
    out = []
    for row in data.merged(realm, region).values():
        r = enrich(row, db)
        if r.get(by) is None:
            continue
        if in_realm and not r["inRealm"]:
            continue
        if min_sale_rate is not None and (r.get("regionSaleRate") or 0) < min_sale_rate:
            continue
        if needs_attrs:
            if r.get("name") is None:
                continue
            if item_class and (r["className"] or "").lower() != item_class.lower():
                continue
            if subclass and (r["subclassName"] or "").lower() != subclass.lower():
                continue
            if q is not None and r["quality"] != q:
                continue
            if bind and r["bind"] != bind.lower():
                continue
            level = r["requiredLevel"]
            if (min_level is not None or max_level is not None) and level is None:
                continue
            if min_level is not None and level < min_level:
                continue
            if max_level is not None and level > max_level:
                continue
        out.append(r)
    out.sort(key=lambda r: (r[by], -(r["itemId"] or 0)), reverse=not ascending)
    return out[:limit] if limit and limit > 0 else out


def info(data: AppData, db: ItemDB | None = None, name_error: str | None = None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    blocks = []
    for b in data.blocks:
        blocks.append({
            "tag": b.tag, "name": b.name, "scope": b.scope, "downloadTime": b.download_time,
            "downloadTimeUtc": _iso(b.download_time), "ageHours": round((now - b.download_time) / 3600, 1),
            "rows": len(b.rows), "fields": b.fields, "trailer": b.trailer,
        })
    out: dict = {"path": data.path, "realms": data.names("realm"), "regions": data.names("region"), "blocks": blocks}
    if data.app_info:
        last = data.app_info.get("lastSync")
        out["app"] = {"version": data.app_info.get("version"), "lastSync": last, "lastSyncUtc": _iso(last) if last else None,
                      "lastSyncAgeHours": round((now - last) / 3600, 1) if last else None}
    else:
        out["app"] = None
    if len(out["realms"]) <= 1 and len(out["regions"]) <= 1:
        rows = data.merged().values()
        out["items"] = {
            "total": len(rows),
            "withRealmData": sum(1 for r in rows if r["inRealm"]),
            "withRegionData": sum(1 for r in rows if r["inRegion"]),
            "both": sum(1 for r in rows if r["inRealm"] and r["inRegion"]),
            "realmOnly": sum(1 for r in rows if r["inRealm"] and not r["inRegion"]),
            "regionOnly": sum(1 for r in rows if r["inRegion"] and not r["inRealm"]),
            "onAuctionHouseNow": sum(1 for r in rows if r.get("numAuctions")),
            "variantKeys": sum(1 for r in rows if not re.fullmatch(r"[ip]:\d+", r["itemString"])),
        }
        if db:
            out["items"]["unnamed"] = sum(1 for r in rows if db.get(r["itemId"]) is None)
        times = data.update_times()
        out["realmUpdateAgeHours"] = round((now - times["realm"]) / 3600, 1) if times["realm"] else None
        out["regionUpdateAgeHours"] = round((now - times["region"]) / 3600, 1) if times["region"] else None
    if db:
        out["names"] = {"source": db.source, "items": len(db.items), "variantNames": len(db.variants), "warning": name_error}
    else:
        out["names"] = {"source": None, "error": name_error}
    return out


def item_report(data: AppData, db: ItemDB | None, query: str, limit: int = 10, realm: str | None = None, region: str | None = None) -> dict:
    """Resolve an id, item string or name fragment and return every field from every tag for each match."""
    note = None
    try:
        keys = [normalize_key(query)[0]]
    except AppDataError:
        if db is None:
            raise NameSourceError(f"item name source unavailable: cannot look up {query!r} by name; pass an item id") from None
        keys, note = db.find(query)
        if not keys:
            raise AppDataError(f"no item named like {query!r} in the name sources ({len(db.items)} items, {len(db.variants)} variant names)") from None
    realm_name, region_name = data.pick("realm", realm), data.pick("region", region)
    matches, without_data = [], []
    for key in keys:
        item_id = int(re.match(r"^[ip]:(\d+)", key).group(1)) if key.startswith("i:") else None
        attrs = db.get(item_id) if db else None
        try:
            found = data.lookup(key, realm, region)
        except AppDataError as e:
            if len(keys) == 1:
                name = f" ({attrs['name']})" if attrs else ""
                raise AppDataError(str(e).replace(f"item {key}", f"item {key}{name}", 1)) from None
            without_data.append({"itemString": key, "name": attrs["name"] if attrs else None})
            continue
        entry = {"itemString": found["itemString"], "baseItemString": found["baseItemString"], "itemId": item_id}
        entry["attributes"] = attrs
        if db and key in db.variants:
            entry["variantName"] = db.variants[key]
        if db and attrs is None:
            entry["attributesMissing"] = f"item {item_id} is in neither name source (wago.tools export, TSM item cache)"
        entry["values"] = {k: _value_view(k, v) for k, v in found["values"].items()}
        entry["tags"] = found["tags"]
        missing = []
        if realm_name is None:
            missing.append("AppData.lua holds no realm data at all: region numbers only")
        elif not found["inRealm"]:
            missing.append(f"not in realm data ({realm_name}): no auctions of it seen on your auction house in the sync window; region numbers only")
        if not found["inRegion"]:
            missing.append(f"not in region data ({region_name}): realm numbers only")
        entry["missing"] = missing
        matches.append(entry)
    if not matches:
        raise AppDataError(f"{len(keys)} item(s) match {query!r} by name but none is in the realm ({realm_name}) or region ({region_name}) price data")
    return {"query": query, "note": note, "matchCount": len(matches), "matches": matches[:limit] if limit else matches,
            "matchesWithoutData": len(without_data)}


def export_rows(data: AppData, db: ItemDB | None, realm: str | None = None, region: str | None = None) -> list[dict]:
    rows = [enrich(r, db) for r in data.merged(realm, region).values()]
    rows.sort(key=lambda r: (r["itemId"] or 0, r["itemString"]))
    return rows


def _value_view(name: str, value):
    if name in PRICE_FIELDS:
        return {"copper": value, "text": format_money(value)}
    return value


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- text output


def _table(headers: list[str], rows: list[list[str]], right: set[int] = frozenset()) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    def line(cells):
        return "  ".join(c.rjust(w) if i in right else c.ljust(w) for i, (c, w) in enumerate(zip(cells, widths))).rstrip()
    return "\n".join([line(headers), *(line(r) for r in rows)])


def _cell(name: str, value) -> str:
    if value is None:
        return "-"
    if name in PRICE_FIELDS or name == "vendorSell":
        return format_money(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_info(d: dict) -> str:
    lines = [f"AppData: {d['path']}", f"realms: {', '.join(d['realms']) or '-'}   regions: {', '.join(d['regions']) or '-'}"]
    if d.get("app"):
        a = d["app"]
        lines.append(f"app {a['version']}, last sync {a['lastSyncUtc']} ({a['lastSyncAgeHours']} h ago)")
    else:
        lines.append("APP_INFO tag missing: the app's last sync time is unknown")
    rows = [[b["tag"], b["name"], b["downloadTimeUtc"], f"{b['ageHours']}", str(b["rows"]), ",".join(b["fields"])] for b in d["blocks"]]
    lines.append(_table(["tag", "realm/region", "downloaded (UTC)", "age h", "rows", "fields"], rows, {3, 4}))
    if "items" in d:
        i = d["items"]
        lines.append(f"items: {i['total']} keys; realm data {i['withRealmData']}, region data {i['withRegionData']}, both {i['both']}, "
                     f"realm only {i['realmOnly']}, region only {i['regionOnly']}, on the auction house now {i['onAuctionHouseNow']}, "
                     f"variant keys {i['variantKeys']}" + (f", without a name {i['unnamed']}" if "unnamed" in i else ""))
    n = d["names"]
    lines.append(f"names: {n['source']} ({n['items']} items)" if n.get("source") else f"names: unavailable ({n.get('error')})")
    return "\n".join(lines)


def render_item(d: dict) -> str:
    lines = []
    if d.get("note"):
        lines.append(f"note: {d['note']}")
    for m in d["matches"]:
        a = m.get("attributes")
        head = f"{m['itemString']}"
        if a:
            kind = " / ".join(x for x in (a["className"], a["subclassName"], a["slot"]) if x)
            head += (f"  {m.get('variantName') or a['name']}  [{a['qualityName']}, {kind}, req {a['requiredLevel']}, ilvl {a['itemLevel']}, "
                     f"{a['bind']}, stack {a['stackSize']}, vendor {format_money(a['vendorSell'])}, attrs from {a['attrSource']}]")
        elif m.get("attributesMissing"):
            head += f"  ({m['attributesMissing']})"
        lines.append(head)
        for tag, t in m["tags"].items():
            cells = []
            for name, raw in t["raw"].items():
                out_name, value = _unscale(name, raw)
                cells.append(f"{out_name}={_cell(out_name, value)}" + (f" ({raw}c)" if out_name in PRICE_FIELDS and raw else "") + (f" (raw {raw})" if name in SCALED_FIELDS else ""))
            key = "" if t["key"] == m["itemString"] else f" via base key {t['key']}"
            lines.append(f"  {tag} [{t['name']}, {_iso(t['downloadTime'])}]{key}: " + ", ".join(cells))
        for miss in m["missing"]:
            lines.append(f"  ! {miss}")
    extra = d["matchCount"] - len(d["matches"])
    if extra > 0:
        lines.append(f"... {extra} more match(es) with data; raise --limit")
    if d["matchesWithoutData"]:
        lines.append(f"({d['matchesWithoutData']} more name match(es) have no price data)")
    return "\n".join(lines)


def render_top(rows: list[dict], by: str) -> str:
    cols = ["itemId", "name", by, "minBuyout", "marketValue", "numAuctions", "regionMarketValue", "regionSale", "regionSaleRate",
            "regionSoldPerDay", "qualityName", "requiredLevel", "subclassName", "slot", "bind"]
    cols = list(dict.fromkeys(c for c in cols if c == by or c in ("itemId",) or any(r.get(c) is not None for r in rows)))
    heads = {"regionMarketValue": "regionMV", "regionSaleRate": "saleRate", "regionSoldPerDay": "sold/day", "qualityName": "quality",
             "requiredLevel": "req", "subclassName": "subclass", "numAuctions": "auctions"}
    body = [[_cell(c, r.get(c) if c != "itemId" else (r["itemId"] if r["itemString"] == f"i:{r['itemId']}" else r["itemString"])) for c in cols] for r in rows]
    right = {i for i, c in enumerate(cols) if c not in ("name", "qualityName", "subclassName", "slot", "bind")}
    return _table([heads.get(c, c) for c in cols], body, right) if rows else "no item matches"


# ---------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--appdata", help="path to AppData.lua (default: the Forever game folder; TSM_APPDATA / WOWF_GAME_DIR override)")
    common.add_argument("--realm", help="realm tag when the file holds several (e.g. MyRealm-Horde)")
    common.add_argument("--region", help="region tag when the file holds several (e.g. Forever-US)")
    common.add_argument("--cache-dir", help="name cache folder (default %%LOCALAPPDATA%%\\ClaudeForever\\tsm-cache; TSM_CACHE_DIR overrides)")
    common.add_argument("--build", help="wowf build of the wago.tools export (default: newest cached, else newest published)")
    common.add_argument("--offline", action="store_true", help="never download the name tables")
    common.add_argument("--refresh-names", action="store_true", help="ask wago.tools for the newest build and download it if new")
    common.add_argument("--saved-vars", help="TSM's SavedVariables\\TradeSkillMaster.lua for its item cache (default: newest under the game's WTF; TSM_SAVED_VARS overrides)")
    common.add_argument("--no-tsm-cache", action="store_true", help="names from the wago.tools export only")
    common.add_argument("--no-names", action="store_true", help="skip item names and attributes")
    common.add_argument("--json", action="store_true", help="compact JSON instead of text")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", parents=[common], help="tags, realm/region names, data age, row counts")
    p = sub.add_parser("item", parents=[common], help="every field for an item id, item string or name fragment")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("top", parents=[common], help="items ranked by a field, with attribute filters")
    p.add_argument("--by", required=True, help="one of: " + ", ".join((*REALM_FIELDS, *REGION_FIELDS, *ATTR_SORT_FIELDS)))
    p.add_argument("--class", dest="item_class", help="item class name, e.g. Armor, Weapon, 'Trade Goods'")
    p.add_argument("--subclass", help="item subclass name, e.g. Cloth, Leather")
    p.add_argument("--quality", help="0-5 or poor/common/uncommon/rare/epic")
    p.add_argument("--bind", help="boe, bop, bou, none, quest")
    p.add_argument("--min-level", type=int)
    p.add_argument("--max-level", type=int)
    p.add_argument("--min-sale-rate", type=float, help="region sale rate floor, 0..1")
    p.add_argument("--in-realm", action="store_true", help="only items with data on your own auction house")
    p.add_argument("--asc", action="store_true", help="lowest first")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("export", parents=[common], help="one merged row per item, with name and attributes, as JSON")
    p.add_argument("--out", required=True)
    return ap


def _load_names(a) -> tuple[ItemDB | None, str | None]:
    if a.no_names:
        return None, "skipped with --no-names"
    try:
        db = ItemDB.open(Path(a.cache_dir) if a.cache_dir else None, a.build, download=not a.offline, refresh=a.refresh_names,
                         saved_vars=Path(a.saved_vars) if a.saved_vars else None, tsm_cache=not a.no_tsm_cache)
        return db, "; ".join(db.warnings) or None
    except NameSourceError as e:
        return None, str(e)


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        data = AppData.from_file(a.appdata)
        db, name_error = _load_names(a)
        if name_error and not a.no_names:
            print(f"warning: {name_error}", file=sys.stderr)
        if a.cmd == "info":
            result = info(data, db, name_error)
            text = render_info(result)
        elif a.cmd == "item":
            result = item_report(data, db, a.query, a.limit, a.realm, a.region)
            text = render_item(result)
        elif a.cmd == "top":
            by = canonical_field(a.by)
            result = top(data, db, by, item_class=a.item_class, subclass=a.subclass, quality=a.quality, bind=a.bind,
                         min_level=a.min_level, max_level=a.max_level, min_sale_rate=a.min_sale_rate, in_realm=a.in_realm,
                         ascending=a.asc, limit=a.limit, realm=a.realm, region=a.region)
            text = render_top(result, by)
        else:
            if db is None and not a.no_names:
                raise NameSourceError(f"{name_error}; pass --no-names to export prices without names and attributes")
            rows = export_rows(data, db, a.realm, a.region)
            doc = {"source": data.path, "realm": data.pick("realm", a.realm), "region": data.pick("region", a.region),
                   "updateTimes": data.update_times(a.realm, a.region), "names": db.source if db else None,
                   "units": {"prices": "copper", "regionSaleRate": "fraction 0..1", "regionSoldPerDay": "items per day"},
                   "items": rows}
            out = Path(a.out)
            if not out.parent.is_dir():
                raise AppDataError(f"cannot write {out}: folder {out.parent} does not exist")
            out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
            result = {"out": str(out), "items": len(rows), "named": sum(1 for r in rows if r.get("name"))}
            text = f"wrote {result['items']} items ({result['named']} named) to {out}"
        if a.json:
            text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        try:
            print(text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
        return 0
    except AppDataError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
