"""Read and safely rewrite TradeSkillMaster's SavedVariables file.

Library and CLI. The format, and every TSM check this file re-implements, is
documented in docs/tsm/savedvariables-format.md (with pointers into the TSM
source). Nothing here is copied from TSM; the checks are restated from reading it.

    python -I tools/tsm/tsmdb.py --file <path> validate
    python -I tools/tsm/tsmdb.py --file <path> apply plan.json --dry-run
    python -I tools/tsm/tsmdb.py profile --text

Without --file it reads the one TradeSkillMaster.lua under
<game>\\_forever_\\WTF\\Account\\*\\SavedVariables (game folder: WOWF_GAME_DIR, else
C:\\Program Files (x86)\\World of Warcraft). Backups go to TSM_BACKUP_DIR, else
%LOCALAPPDATA%\\ClaudeForever\\tsm-backups.

Data model: a Lua table becomes a ``list`` when it holds only positional
entries, otherwise a ``dict`` (positional entries get the int keys 1..n, so a
group's ``{"#Default", ["override"] = true}`` is ``{1: "#Default", "override": True}``).
Key order is kept. Strings are ``str``; bytes that are not UTF-8 survive through
surrogateescape.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import glob
import json
import math
import os
import re
import subprocess
import sys

GLOBAL_NAME = "TradeSkillMasterDB"
KEY_SEP = "@"
SCOPE_KEY_SEP = " - "
GLOBAL_SCOPE_KEY = " "
GROUP_SEP = "`"
ROOT_GROUP = ""
DEFAULT_OPERATION = "#Default"
DEFAULT_PROFILE = "Default"
MIN_DB_VERSION = 102
ITEM_MAX_ID = 999999
SCOPES = {"global": "g", "profile": "p", "realm": "r", "factionrealm": "f", "char": "c", "sync": "s"}
SCOPE_NAMES = {v: k for k, v in SCOPES.items()}
COMMON_OPERATION_FIELDS = {"ignorePlayer": "table", "ignoreFactionrealm": "table", "relationships": "table"}
# Per module: max operations on one group, whether #Default is left off the base
# group, and the type of every field TSM registers on this client (Forever is
# not Vanilla/BC Classic, so Auctioning has no stack-size fields).
MODULES = {
    "Auctioning": {
        "max": 20,
        "exclude_default": False,
        "fields": {
            "ignoreLowDuration": "number", "postCap": "string", "keepQuantity": "string",
            "maxExpires": "string", "duration": "number", "bidPercent": "number",
            "undercut": "string", "minPrice": "string", "maxPrice": "string",
            "normalPrice": "string", "priceReset": "string", "aboveMax": "string",
            "cancelUndercut": "boolean", "cancelRepost": "boolean", "cancelRepostThreshold": "string",
        },
    },
    "Crafting": {
        "max": 1,
        "exclude_default": False,
        "fields": {"minRestock": "string", "maxRestock": "string", "minProfit": "string", "craftPriceMethod": "string"},
    },
    "Mailing": {
        "max": 50,
        "exclude_default": True,
        "fields": {
            "maxQtyEnabled": "boolean", "maxQty": "string", "target": "string",
            "restock": "boolean", "restockSources": "table", "keepQty": "string",
        },
    },
    "Shopping": {
        "max": 1,
        "exclude_default": False,
        "fields": {
            "restockQuantity": "string", "maxPrice": "string",
            "showAboveMaxPrice": "boolean", "restockSources": "table",
        },
    },
    "Sniper": {"max": 1, "exclude_default": False, "fields": {"belowPrice": "string"}},
    "Vendoring": {
        "max": 1,
        "exclude_default": True,
        "fields": {
            "sellAfterExpired": "string", "sellSoulbound": "boolean", "keepQty": "string",
            "restockQty": "string", "restockSources": "table", "enableBuy": "boolean",
            "enableSell": "boolean", "vsMarketValue": "string", "vsMaxMarketValue": "string",
            "vsDestroyValue": "string", "vsMaxDestroyValue": "string",
        },
    },
    "Warehousing": {
        "max": 12,
        "exclude_default": True,
        "fields": {
            "moveQuantity": "string", "keepBagQuantity": "string", "keepBankQuantity": "string",
            "restockQuantity": "string", "stackSize": "string", "restockKeepBankQuantity": "string",
            "restockStackSize": "string",
        },
    },
}
QUANTITY_TABLES = {"bag": "bagQuantity", "bank": "bankQuantity", "mail": "mailQuantity", "auction": "auctionQuantity"}
ACCOUNTING_KEYS = ["csvSales", "csvBuys", "csvIncome", "csvExpense", "csvExpired", "csvCancelled"]
WOW_IMAGE_RE = re.compile(r"^wow(-64|classic|classict|t|b)?\.exe$", re.IGNORECASE)


class TsmError(Exception):
    """A failure that names the link that broke (key, file, type, process)."""


# ============================================================================
# Lua subset parser
# ============================================================================

_WS_RE = re.compile(r"(?:\s+|--[^\n]*)*")
_NUM_RE = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_SIMPLE_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
                   "\\": "\\", '"': '"', "'": "'", "\n": "\n"}
_STR_CHUNK_RE = {'"': re.compile(r'[^"\\\n]*'), "'": re.compile(r"[^'\\\n]*")}


class _Parser:
    """Recursive-descent parser over latin-1 text (one char per byte)."""

    def __init__(self, text: str, source: str):
        self.text = text
        self.pos = 0
        self.source = source

    def fail(self, what: str):
        line = self.text.count("\n", 0, self.pos) + 1
        raise TsmError(f"Lua parse error in {self.source} line {line}: {what}")

    def skip(self):
        self.pos = _WS_RE.match(self.text, self.pos).end()

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expect(self, char: str):
        self.skip()
        if self.peek() != char:
            self.fail(f"expected {char!r}, found {self.text[self.pos:self.pos + 20]!r}")
        self.pos += 1

    def parse_string(self) -> str:
        quote = self.text[self.pos]
        self.pos += 1
        chunk_re = _STR_CHUNK_RE[quote]
        parts = []
        while True:
            m = chunk_re.match(self.text, self.pos)
            parts.append(m.group())
            self.pos = m.end()
            char = self.peek()
            if char == quote:
                self.pos += 1
                break
            if char != "\\":
                self.fail("unterminated string")
            esc = self.text[self.pos + 1:self.pos + 2]
            if esc.isdigit():
                m = re.compile(r"\d{1,3}").match(self.text, self.pos + 1)
                code = int(m.group())
                if code > 255:
                    self.fail(f"escape \\{m.group()} too large")
                parts.append(chr(code))
                self.pos = m.end()
            elif esc == "\r":
                parts.append("\n")
                self.pos += 3 if self.text[self.pos + 2:self.pos + 3] == "\n" else 2
            elif esc in _SIMPLE_ESCAPES:
                parts.append(_SIMPLE_ESCAPES[esc])
                self.pos += 2
            else:
                self.fail(f"unknown escape \\{esc}")
        return "".join(parts).encode("latin-1").decode("utf-8", "surrogateescape")

    def parse_value(self):
        self.skip()
        char = self.peek()
        if char == "{":
            return self.parse_table()
        if char in "\"'" and char:
            return self.parse_string()
        m = _NUM_RE.match(self.text, self.pos)
        if m:
            self.pos = m.end()
            return _to_number(m.group())
        m = _NAME_RE.match(self.text, self.pos)
        if m:
            self.pos = m.end()
            word = m.group()
            if word in ("true", "false"):
                return word == "true"
            if word in ("inf", "math.huge"):
                return math.inf
            if word == "nan":
                return math.nan
            if word == "nil":
                return None
            self.fail(f"unsupported value {word!r}")
        if self.text.startswith(("-inf", "-math.huge"), self.pos):
            self.pos = _NAME_RE.match(self.text, self.pos + 1).end()
            return -math.inf
        self.fail(f"unexpected {self.text[self.pos:self.pos + 20]!r}")

    def parse_table(self):
        self.expect("{")
        result: dict = {}
        positional = 0
        while True:
            self.skip()
            char = self.peek()
            if char == "}":
                self.pos += 1
                break
            if char == "":
                self.fail("unterminated table")
            if char == "[":
                self.pos += 1
                key = self.parse_value()
                self.expect("]")
                self.expect("=")
                value = self.parse_value()
                if isinstance(key, float) and key.is_integer():
                    key = int(key)
                if not isinstance(key, (str, int, float)) or isinstance(key, bool) \
                        or (isinstance(key, float) and math.isnan(key)):
                    self.fail("unsupported table key (only strings and numbers)")
            else:
                m = _NAME_RE.match(self.text, self.pos)
                after = _WS_RE.match(self.text, m.end()).end() if m else 0
                if m and m.group() not in ("true", "false", "nil", "inf", "nan", "math.huge") \
                        and self.text[after:after + 1] == "=" and self.text[after:after + 2] != "==":
                    key = m.group()
                    self.pos = after + 1
                    value = self.parse_value()
                else:
                    value = self.parse_value()
                    positional += 1
                    key = positional
            if value is not None:
                result[key] = value
            self.skip()
            if self.peek() in ",;":
                self.pos += 1
        if result and list(result) == list(range(1, len(result) + 1)):
            return list(result.values())
        return result


def _to_number(token: str):
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if "x" in token.lower():
        return int(token, 16)
    value = float(token)
    return value


def parse_lua_value(text: str | bytes, source: str = "<string>"):
    """Parses one Lua literal (table, string, number, boolean)."""
    if isinstance(text, str):
        text = text.encode("utf-8", "surrogateescape")
    parser = _Parser(text.decode("latin-1"), source)
    value = parser.parse_value()
    parser.skip()
    if parser.pos != len(parser.text):
        parser.fail("trailing content after value")
    return value


# ============================================================================
# Serializer (the client's SavedVariables layout)
# ============================================================================

def format_number(value) -> str:
    if isinstance(value, bool):
        raise TsmError("a boolean is not a number")
    if isinstance(value, int):
        return str(value) if abs(value) < 10 ** 16 else "%.16g" % float(value)
    if math.isnan(value):
        raise TsmError("cannot serialize NaN")
    if math.isinf(value):
        return "math.huge" if value > 0 else "-math.huge"
    return "%.16g" % value


def format_string(value: str) -> str:
    raw = value.encode("utf-8", "surrogateescape")
    out = bytearray(b'"')
    for byte in raw:
        if byte == 0x5C:
            out += b"\\\\"
        elif byte == 0x22:
            out += b'\\"'
        elif byte == 0x0A:
            out += b"\\n"
        elif byte == 0x0D:
            out += b"\\r"
        elif (byte < 0x20 and byte != 0x09) or byte == 0x7F:
            out += b"\\%03d" % byte
        else:
            out.append(byte)
    out += b'"'
    return out.decode("latin-1")


def _format_key(key) -> str:
    if isinstance(key, (int, float)) and not isinstance(key, bool):
        return f"[{format_number(key)}]"
    if isinstance(key, str):
        return f"[{format_string(key)}]"
    raise TsmError(f"unsupported table key type {type(key).__name__}")


def _write_value(out: list, value, prefix: str, depth: int, style: dict, suffix: str):
    """Appends ``prefix + value + ","`` (+ suffix) lines for one table entry."""
    indent = style["indent"] * depth
    if isinstance(value, bool):
        out.append(f"{indent}{prefix}{'true' if value else 'false'},{suffix}")
    elif isinstance(value, (int, float)):
        out.append(f"{indent}{prefix}{format_number(value)},{suffix}")
    elif isinstance(value, str):
        out.append(f"{indent}{prefix}{format_string(value)},{suffix}")
    elif isinstance(value, (dict, list, tuple)):
        out.append(f"{indent}{prefix}{{")
        _write_entries(out, value, depth + 1, style)
        out.append(f"{indent}}},{suffix}")
    elif value is None:
        raise TsmError("cannot serialize nil/None as a table value: delete the key instead")
    else:
        raise TsmError(f"unsupported value type {type(value).__name__}")


def _write_entries(out: list, table, depth: int, style: dict):
    items = enumerate(table, 1) if isinstance(table, (list, tuple)) else table.items()
    positional = 0
    for key, value in items:
        if isinstance(key, int) and not isinstance(key, bool) and key == positional + 1:
            positional += 1
            suffix = f" -- [{positional}]" if style["array_comments"] else ""
            _write_value(out, value, "", depth, style, suffix)
        else:
            _write_value(out, value, _format_key(key) + " = ", depth, style, "")


def serialize_table(name: str, table, newline: str = "\r\n", indent: str = "", array_comments: bool = False) -> str:
    """Serializes ``name = { ... }`` (latin-1 text, one char per byte, no trailing newline)."""
    out = [f"{name} = {{"]
    _write_entries(out, table, 1, {"indent": indent, "array_comments": array_comments})
    out.append("}")
    return newline.join(out)


# ============================================================================
# Database file
# ============================================================================

class Database:
    """A loaded SavedVariables file: ``data`` is the TradeSkillMasterDB table;
    ``prefix`` and ``suffix`` are the bytes around it (other globals), kept verbatim."""

    def __init__(self, path, data, prefix="", suffix="\r\n", newline="\r\n", indent="", array_comments=False):
        self.path = str(path) if path is not None else None
        self.data = data
        self.prefix = prefix
        self.suffix = suffix
        self.newline = newline
        self.indent = indent
        self.array_comments = array_comments

    def to_bytes(self) -> bytes:
        body = serialize_table(GLOBAL_NAME, self.data, self.newline, self.indent, self.array_comments)
        return (self.prefix + body + self.suffix).encode("latin-1")


def loads_db(raw: bytes, path="<bytes>") -> Database:
    text = raw.decode("latin-1")
    m = re.search(r"^" + GLOBAL_NAME + r"[ \t]*=[ \t]*(?=\{)", text, re.MULTILINE)
    if not m:
        raise TsmError(f"global {GLOBAL_NAME} not found in {path}: not a TradeSkillMaster SavedVariables file")
    parser = _Parser(text, str(path))
    parser.pos = m.end()
    data = parser.parse_table()
    if isinstance(data, list):
        data = {i: v for i, v in enumerate(data, 1)}
    body = text[m.start():parser.pos]
    newline = "\r\n" if "\r\n" in body else "\n"
    indent_match = re.search(r"\{\r?\n([ \t]*)[\[\"{\w-]", body)
    return Database(
        path, data,
        prefix=text[:m.start()], suffix=text[parser.pos:], newline=newline,
        indent=indent_match.group(1) if indent_match else "",
        array_comments=bool(re.search(r",[ \t]*-- \[\d+\]\r?\n", body)),
    )


def load_db(path) -> Database:
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise TsmError(f"cannot read SavedVariables file {path}: {exc.strerror}") from exc
    return loads_db(raw, path)


def default_live_path() -> str:
    """The live TradeSkillMaster.lua (WOWF_GAME_DIR overrides the game's parent folder)."""
    parent = os.environ.get("WOWF_GAME_DIR") or r"C:\Program Files (x86)\World of Warcraft"
    pattern = os.path.join(parent, "_forever_", "WTF", "Account", "*", "SavedVariables", "TradeSkillMaster.lua")
    found = sorted(glob.glob(pattern))
    if not found:
        raise TsmError(f"no live file matches {pattern}: TSM has never saved here, or WOWF_GAME_DIR is wrong")
    if len(found) > 1:
        raise TsmError(f"{len(found)} accounts match {pattern}: pass --file to pick one")
    return found[0]


def is_under_wtf(path) -> bool:
    parts = os.path.normpath(os.path.abspath(path)).replace("/", os.sep).split(os.sep)
    return any(part.lower() == "wtf" for part in parts[:-1])


def wow_running() -> bool:
    """True when a WoW client process exists. Raises when the check itself cannot run."""
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise TsmError(f"cannot run tasklist to check for Wow.exe ({exc}): refusing to touch a WTF file") from exc
    if result.returncode != 0:
        raise TsmError(f"tasklist exited {result.returncode}: cannot tell whether Wow.exe runs, refusing to write")
    for line in result.stdout.splitlines():
        image = line.split(",")[0].strip().strip('"')
        if WOW_IMAGE_RE.match(image):
            return True
    return False


def backup_dir() -> str:
    override = os.environ.get("TSM_BACKUP_DIR")
    if override:
        return override
    local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(local, "ClaudeForever", "tsm-backups")


def save_db(path, db: Database, backup: bool | None = None) -> dict:
    """Writes ``db`` to ``path``. Under a WTF folder it refuses while WoW runs and
    backs the old file up first. Always: temp file, re-parse, then atomic replace.
    Returns ``{"path", "backup", "bytes"}``."""
    path = str(path)
    under_wtf = is_under_wtf(path)
    if under_wtf and wow_running():
        raise TsmError(
            f"Wow.exe is running: refusing to write {path} (the client overwrites SavedVariables "
            "on /reload, logout and exit, so the change would be lost). Close the game first.")
    db.data = canonical(db.data)
    if not isinstance(db.data, dict):
        raise TsmError(f"{GLOBAL_NAME} must be a keyed table, not an array: refusing to write {path}")
    payload = db.to_bytes()
    backup_path = None
    if (under_wtf if backup is None else backup) and os.path.exists(path):
        folder = backup_dir()
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = os.path.join(folder, f"TradeSkillMaster-{stamp}.lua")
        with open(path, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())
    temp_path = f"{path}.tsmdb-tmp-{os.getpid()}"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        written = load_db(temp_path)
        if written.data != db.data or written.prefix != db.prefix or written.suffix != db.suffix:
            raise TsmError(f"re-parse of {temp_path} differs from the data that was meant to be written; {path} untouched")
        os.replace(temp_path, path)
    except OSError as exc:
        raise TsmError(f"cannot write {path}: {exc.strerror}") from exc
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    with open(path, "rb") as handle:
        if handle.read() != payload:
            raise TsmError(f"{path} does not hold the bytes just written (backup: {backup_path})")
    db.path = path
    return {"path": path, "backup": backup_path, "bytes": len(payload)}


# ============================================================================
# Settings
# ============================================================================

def lua_type(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (dict, list, tuple)):
        return "table"
    if value is None:
        return "nil"
    return type(value).__name__


def make_key(scope: str, scope_key: str | None, namespace: str, key: str) -> str:
    letter = SCOPES.get(scope, scope)
    if letter not in SCOPE_NAMES:
        raise TsmError(f"unknown scope {scope!r}: expected one of {', '.join(SCOPES)} or {', '.join(SCOPE_NAMES)}")
    if letter == "g":
        scope_key = GLOBAL_SCOPE_KEY
    elif not scope_key:
        raise TsmError(f"scope {SCOPE_NAMES[letter]} needs a scope key (profile, realm, character...)")
    return KEY_SEP.join((letter, scope_key, namespace, key))


def split_key(db_key: str):
    """``(scope letter, scope key, namespace, key)`` or None for a metadata/invalid key."""
    m = re.fullmatch(r"(.)@(.+)@([^@]+)@([^@]+)", db_key, re.DOTALL)
    return m.groups() if m and m.group(1) in SCOPE_NAMES else None


def _expand_key(db_key: str) -> str:
    parts = db_key.split(KEY_SEP)
    if len(parts) == 3 and parts[0] == "g":
        return KEY_SEP.join(("g", GLOBAL_SCOPE_KEY, parts[1], parts[2]))
    return db_key


def get_key(db: Database, db_key: str):
    db_key = _expand_key(db_key)
    if db_key not in db.data:
        parts = split_key(db_key)
        hint = ""
        if parts and parts[0] != "g":
            known = _scope_keys(db).get(SCOPE_NAMES[parts[0]], [])
            if parts[1] not in known:
                hint = f" (scope key {parts[1]!r} is not in _scopeKeys.{SCOPE_NAMES[parts[0]]}: {known})"
        raise TsmError(f"key not found: {db_key!r} in {db.path}{hint}")
    return db.data[db_key]


def set_key(db: Database, db_key: str, value):
    """Sets an existing setting; the new value must have the Lua type of the old one."""
    db_key = _expand_key(db_key)
    if db_key.startswith("_"):
        raise TsmError(f"refusing to set metadata key {db_key!r}: TSM owns every _-prefixed key")
    old = get_key(db, db_key)
    if lua_type(value) != lua_type(old):
        raise TsmError(
            f"type mismatch for {db_key!r} in {db.path}: expected {lua_type(old)}, got {lua_type(value)} ({value!r})")
    db.data[db_key] = value
    return old


def get(db: Database, scope: str, scope_key: str | None, namespace: str, key: str):
    return get_key(db, make_key(scope, scope_key, namespace, key))


def set(db: Database, scope: str, scope_key: str | None, namespace: str, key: str, value):  # noqa: A001
    return set_key(db, make_key(scope, scope_key, namespace, key), value)


def _scope_keys(db: Database) -> dict:
    scope_keys = db.data.get("_scopeKeys")
    if not isinstance(scope_keys, dict):
        return {}
    return {k: _array_part(v) for k, v in scope_keys.items() if isinstance(v, (dict, list))}


# ============================================================================
# Tables with an array part
# ============================================================================

def _array_part(table) -> list:
    if isinstance(table, (list, tuple)):
        return list(table)
    result = []
    while isinstance(table, dict) and len(result) + 1 in table:
        result.append(table[len(result) + 1])
    return result


def _ops_table(names, override: bool):
    table: dict = {i: name for i, name in enumerate(names, 1)}
    if override:
        table["override"] = True
    return canonical(table)


def canonical(value):
    """The shape the parser gives: a table with only the keys 1..n is a list,
    an empty table is ``{}``. Lets hand-built data compare equal to a re-parse."""
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value] if value else {}
    if isinstance(value, dict):
        if value and all(isinstance(k, int) and not isinstance(k, bool) for k in value) \
                and sorted(value) == list(range(1, len(value) + 1)) and list(value) == sorted(value):
            return [canonical(value[i]) for i in range(1, len(value) + 1)]
        return {(int(k) if isinstance(k, float) and k.is_integer() else k): canonical(v) for k, v in value.items()}
    return value


# ============================================================================
# Groups
# ============================================================================

def _profile_table(db: Database, profile: str, key: str) -> dict:
    db_key = make_key("profile", profile, "userData", key)
    value = get_key(db, db_key)
    if isinstance(value, list):
        raise TsmError(f"{db_key!r} in {db.path} is an array, expected a keyed table")
    if not isinstance(value, dict):
        raise TsmError(f"type mismatch for {db_key!r} in {db.path}: expected table, got {lua_type(value)}")
    return value


def _groups(db, profile) -> dict:
    return _profile_table(db, profile, "groups")


def group_parent(path: str):
    if path == ROOT_GROUP:
        return None
    return path.rpartition(GROUP_SEP)[0] if GROUP_SEP in path else ROOT_GROUP


def is_child_group(path: str, parent: str) -> bool:
    return path != ROOT_GROUP if parent == ROOT_GROUP else path.startswith(parent + GROUP_SEP)


def group_sort_key(path: str) -> str:
    return path.replace(GROUP_SEP, "\x01").lower()


def check_group_path(path) -> str:
    if not isinstance(path, str):
        raise TsmError(f"group path must be a string, got {lua_type(path)}")
    if path == ROOT_GROUP:
        raise TsmError('the root group "" always exists and cannot be created or hold items')
    if any(part == "" for part in path.split(GROUP_SEP)):
        raise TsmError(f"invalid group path {path!r}: empty group name (a path is names joined by one {GROUP_SEP!r})")
    return path


def _modules_for(db: Database, profile: str) -> list:
    """Operation types to keep on every group: the built-in seven, plus any other in the file."""
    names = list(MODULES)
    for extra in operations_table(db, profile):
        if extra not in names:
            names.append(extra)
    return names


def list_groups(db: Database, profile: str = DEFAULT_PROFILE) -> list:
    groups = _groups(db, profile)
    items = _profile_table(db, profile, "items")
    counts: dict = {}
    for group in items.values():
        counts[group] = counts.get(group, 0) + 1
    result = []
    for path in sorted(groups, key=lambda p: group_sort_key(p) if isinstance(p, str) else ""):
        info = groups[path] if isinstance(groups[path], dict) else {}
        result.append({
            "path": path,
            "items": counts.get(path, 0),
            "operations": {
                module: {"names": _array_part(ops), "override": bool(isinstance(ops, dict) and ops.get("override"))}
                for module, ops in info.items() if isinstance(ops, (dict, list))
            },
        })
    return result


def create_group(db: Database, path: str, profile: str = DEFAULT_PROFILE) -> list:
    """Creates ``path`` and any missing parents; each new group inherits its
    parent's operations (no override). Returns the paths created, top down."""
    check_group_path(path)
    groups = _groups(db, profile)
    modules = _modules_for(db, profile)
    created = []
    parts = path.split(GROUP_SEP)
    for depth in range(1, len(parts) + 1):
        current = GROUP_SEP.join(parts[:depth])
        if current in groups:
            continue
        parent = groups.get(group_parent(current))
        info = {}
        for module in modules:
            inherited = _array_part(parent.get(module)) if isinstance(parent, dict) else []
            info[module] = _ops_table(inherited, False)
        groups[current] = info
        created.append(current)
    return created


def normalize_item_string(item) -> str:
    """The cheap part of TSM's item string clean-up. ``i:ID`` is the base item
    (covers every variation not grouped itself), ``i:ID::N:b1..bN`` bonus ids
    (how Forever keys an "of the Owl" green: ``i:15110::1:12718``), ``i:ID:RAND``
    the old random-suffix form, ``i:ID::iLVL`` an item-level string,
    ``p:SPECIES`` a battle pet. Bonus ids are not filtered here; TSM does that."""
    text = str(item).strip() if not isinstance(item, bool) else ""
    m = re.fullmatch(r"(?:item:|i:)?(\d+)", text)
    if m:
        if int(m.group(1)) > ITEM_MAX_ID:
            raise TsmError(f"invalid item string {item!r}: item id above {ITEM_MAX_ID}")
        return f"i:{int(m.group(1))}" if not text.startswith("i:") else text
    if re.fullmatch(r"p:\d+", text):
        return text
    if re.fullmatch(r"i:\d+:[0-9\-:i+]*", text):
        text = text.replace(":0:", "::")
        while re.search(r":0?$", text):
            text = re.sub(r":0?$", "", text)
        return text
    if re.fullmatch(r"p:[i0-9:]+", text):
        while re.search(r":0?$", text):
            text = re.sub(r":0?$", "", text)
        m = re.fullmatch(r"p:\d+:\d+:\d+", text) or re.fullmatch(r"p:\d+:i\d+", text) or re.match(r"p:\d+", text)
        return m.group()
    raise TsmError(f"invalid item string {item!r}: expected i:<id>, i:<id>:<suffix>, i:<id>::<bonus...> or p:<species>")


def assign_items(db: Database, group_path: str, item_strings, profile: str = DEFAULT_PROFILE) -> dict:
    """Puts items in an existing non-root group (an item is in one group at most,
    so an item grouped elsewhere moves). Returns added / moved / unchanged / warnings."""
    check_group_path(group_path)
    groups = _groups(db, profile)
    if group_path not in groups:
        raise TsmError(
            f"group not found: {group_path!r} in p@{profile}@userData@groups of {db.path} (create it first)")
    items = _profile_table(db, profile, "items")
    result = {"added": [], "moved": {}, "unchanged": [], "warnings": []}
    for item in item_strings:
        item_string = normalize_item_string(item)
        if item_string.count(":") > 2:
            result["warnings"].append(
                f"{item_string}: TSM re-filters bonus ids and modifiers on load and re-keys the entry if its form differs")
        previous = items.get(item_string)
        if previous == group_path:
            result["unchanged"].append(item_string)
            continue
        if previous is None:
            result["added"].append(item_string)
        else:
            result["moved"][item_string] = previous
        items[item_string] = group_path
    return result


# ============================================================================
# Operations
# ============================================================================

def operations_key(db: Database, profile: str = DEFAULT_PROFILE) -> str:
    """Where operations live: the profile, or the global table when
    ``coreOptions.globalOperations`` is on."""
    if db.data.get(make_key("global", None, "coreOptions", "globalOperations")) is True:
        return make_key("global", None, "userData", "sharedOperations")
    return make_key("profile", profile, "userData", "operations")


def operations_table(db: Database, profile: str = DEFAULT_PROFILE) -> dict:
    db_key = operations_key(db, profile)
    value = get_key(db, db_key)
    if not isinstance(value, dict):
        raise TsmError(f"type mismatch for {db_key!r} in {db.path}: expected keyed table, got {lua_type(value)}")
    return value


def list_operations(db: Database, module: str | None = None, profile: str = DEFAULT_PROFILE) -> dict:
    table = operations_table(db, profile)
    if module is not None and module not in table:
        raise TsmError(f"operation module not found: {module!r} in {operations_key(db, profile)!r} of {db.path} "
                       f"(has: {', '.join(map(str, table))})")
    groups = _groups(db, profile)
    result = {}
    for name in ([module] if module else table):
        ops = table[name] if isinstance(table[name], dict) else {}
        result[name] = {}
        for op_name, settings in ops.items():
            used_by = sorted(
                (path for path, info in groups.items()
                 if isinstance(info, dict) and op_name in _array_part(info.get(name))),
                key=group_sort_key)
            result[name][op_name] = {"settings": settings, "groups": used_by}
    return result


def check_operation_name(name) -> str:
    if not isinstance(name, str) or name == "" or name != name.strip():
        raise TsmError(f"invalid operation name {name!r}: must be a non-empty string without leading/trailing whitespace")
    return name


def create_operation(db: Database, module: str, name: str, settings: dict | None = None,
                     profile: str = DEFAULT_PROFILE, update: bool = False, exist_ok: bool = False) -> dict:
    """Creates an operation as a copy of the module's ``#Default`` in the file
    (so every field TSM expects is present), then applies ``settings`` with type
    checks. ``update=True`` changes an existing operation instead of failing;
    ``exist_ok=True`` accepts one that already has exactly these settings."""
    check_operation_name(name)
    table = operations_table(db, profile)
    where = f"{operations_key(db, profile)!r} of {db.path}"
    if module not in table or not isinstance(table[module], dict):
        raise TsmError(f"operation module not found: {module!r} in {where} (has: {', '.join(map(str, table))})")
    ops = table[module]
    existed = name in ops
    if existed and not update:
        same = isinstance(ops[name], dict) and all(
            canonical(ops[name].get(k)) == canonical(v) for k, v in (settings or {}).items())
        if exist_ok and same:
            return {"created": False, "changed": {}}
        raise TsmError(f"operation already exists: {module}/{name} in {where}"
                       + (" with different settings" if not same else "") + " (pass update to change it)")
    template = ops.get(DEFAULT_OPERATION)
    if not isinstance(template, dict):
        raise TsmError(f"template not found: {module}/{DEFAULT_OPERATION} in {where}; cannot tell which fields TSM expects")
    if existed:
        operation = ops[name]
    else:
        operation = copy.deepcopy(template)
        for common in COMMON_OPERATION_FIELDS:
            operation[common] = {}
    changed = {}
    for key, value in (settings or {}).items():
        if key not in template:
            raise TsmError(f"unknown {module} operation field {key!r} (fields: {', '.join(sorted(template))})")
        if lua_type(value) != lua_type(template[key]):
            raise TsmError(f"type mismatch for {module}/{name}.{key}: expected {lua_type(template[key])}, "
                           f"got {lua_type(value)} ({value!r})")
        if key == "relationships":
            for field, target in value.items():
                if field not in template or target not in ops or target == name:
                    raise TsmError(f"invalid relationship {module}/{name}.{field} -> {target!r}: "
                                   "the field and the target operation must exist")
        if canonical(operation.get(key)) != canonical(value):
            changed[key] = value
            operation[key] = copy.deepcopy(value)
    ops[name] = operation
    return {"created": not existed, "changed": changed}


def set_group_operations(db: Database, group_path: str, module: str, names, override: bool = True,
                         profile: str = DEFAULT_PROFILE) -> dict:
    """Sets the operations of one module on a group. ``override=False`` drops the
    override so the group (and its non-overriding children) inherit the parent's."""
    groups = _groups(db, profile)
    if group_path not in groups or not isinstance(groups[group_path], dict):
        raise TsmError(f"group not found: {group_path!r} in p@{profile}@userData@groups of {db.path}")
    table = operations_table(db, profile)
    if module not in table or not isinstance(table[module], dict):
        raise TsmError(f"operation module not found: {module!r} in {operations_key(db, profile)!r} of {db.path}")
    names = list(names)
    if group_path == ROOT_GROUP and not override:
        raise TsmError("the root group always overrides: it has no parent to inherit from")
    if override:
        for name in names:
            if name not in table[module]:
                raise TsmError(f"operation not found: {module}/{name!r} in {operations_key(db, profile)!r} of {db.path}")
        limit = MODULES.get(module, {}).get("max")
        if limit is not None and len(names) > limit:
            raise TsmError(f"too many {module} operations on {group_path!r}: {len(names)} given, TSM keeps at most {limit}")
        if len(dict.fromkeys(names)) != len(names):
            raise TsmError(f"duplicate operation in {names!r} for {module} on {group_path!r}")
    else:
        if names:
            raise TsmError("override=False inherits the parent's operations: pass no names")
        parent = groups.get(group_parent(group_path))
        names = _array_part(parent.get(module)) if isinstance(parent, dict) else []
    before = groups[group_path].get(module)
    groups[group_path][module] = _ops_table(names, override)
    inherited = []
    for child in sorted((p for p in groups if isinstance(p, str) and is_child_group(p, group_path)), key=group_sort_key):
        info = groups[child]
        if not isinstance(info, dict):
            continue
        ops = info.get(module)
        if isinstance(ops, dict) and ops.get("override"):
            continue
        parent = groups.get(group_parent(child))
        if isinstance(parent, dict):
            info[module] = _ops_table(_array_part(parent.get(module)), False)
            inherited.append(child)
    return {"before": {"names": _array_part(before), "override": bool(isinstance(before, dict) and before.get("override"))},
            "after": {"names": names, "override": override}, "inherited_by": inherited}


def remove_operation(db: Database, module: str, name: str, profile: str = DEFAULT_PROFILE) -> dict | None:
    """Deletes an operation the way TSM's ``GroupOperation.DeleteOperation`` does:
    the operation goes, every group's list for that module drops the name, and
    relationships pointing at it are cleared. Returns None when it does not exist."""
    check_operation_name(name)
    if name == DEFAULT_OPERATION:
        raise TsmError(f"refusing to remove {module}/{DEFAULT_OPERATION}: it is the template TSM copies")
    table = operations_table(db, profile)
    ops = table.get(module)
    if not isinstance(ops, dict):
        raise TsmError(f"operation module not found: {module!r} in {operations_key(db, profile)!r} of {db.path} "
                       f"(has: {', '.join(map(str, table))})")
    if name not in ops:
        return None
    del ops[name]
    dead_relationships = []
    for other, settings in ops.items():
        relationships = settings.get("relationships") if isinstance(settings, dict) else None
        if isinstance(relationships, dict):
            for field in [f for f, target in relationships.items() if target == name]:
                del relationships[field]
                dead_relationships.append(f"{other}.{field}")
    groups_changed = []
    for path, info in _groups(db, profile).items():
        group_ops = info.get(module) if isinstance(info, dict) else None
        if not isinstance(group_ops, dict):
            continue
        names = _array_part(group_ops)
        if name in names:
            info[module] = _ops_table([n for n in names if n != name], bool(group_ops.get("override")))
            groups_changed.append(path)
    return {"groups": groups_changed, "relationships": dead_relationships}


def remove_group(db: Database, path: str, profile: str = DEFAULT_PROFILE) -> dict | None:
    """Deletes a group and its subgroups the way TSM's ``GroupOperation.DeleteGroup``
    does: their items become ungrouped (a later ``assign_items`` can place them).
    Returns None when the group does not exist."""
    check_group_path(path)
    groups = _groups(db, profile)
    if path not in groups:
        return None
    removed = sorted((p for p in groups if p == path or (isinstance(p, str) and is_child_group(p, path))),
                     key=group_sort_key)
    for p in removed:
        del groups[p]
    items = _profile_table(db, profile, "items")
    removed_set = frozenset(removed)  # this module's set() is the setting writer
    ungrouped = sorted(item for item, group in items.items() if group in removed_set)
    for item in ungrouped:
        del items[item]
    return {"groups": removed, "items": ungrouped}


# ============================================================================
# Inventory and accounting (read only)
# ============================================================================

def inventory(db: Database) -> dict:
    """Bag/bank/mail/auction quantities per character (sync scope) and summed per item."""
    characters: dict = {}
    totals: dict = {}
    for db_key, value in db.data.items():
        parts = split_key(db_key) if isinstance(db_key, str) else None
        if not parts or parts[0] != "s" or parts[2] != "internalData":
            continue
        for place, table_name in QUANTITY_TABLES.items():
            if parts[3] != table_name or not isinstance(value, dict):
                continue
            for item, quantity in value.items():
                if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
                    continue
                characters.setdefault(parts[1], {}).setdefault(item, {})[place] = quantity
                total = totals.setdefault(item, {"total": 0})
                total[place] = total.get(place, 0) + quantity
                total["total"] += quantity
    return {"characters": characters, "totals": dict(sorted(totals.items()))}


def parse_csv(text: str) -> dict:
    """TSM's CSV: first line is the field list, no quoting, rows split on ``,``."""
    lines = text.split("\n") if text else []
    fields = lines[0].split(",") if lines else []
    rows, malformed = [], []
    for number, line in enumerate(lines[1:], 2):
        values = line.split(",")
        if len(values) != len(fields):
            malformed.append({"line": number, "text": line})
            continue
        rows.append({f: (int(v) if re.fullmatch(r"-?\d+", v) else v) for f, v in zip(fields, values)})
    return {"fields": fields, "rows": rows, "malformed": malformed, "empty": not rows}


def accounting(db: Database) -> dict:
    """Per realm: csvSales, csvBuys, csvIncome, csvExpense, csvExpired, csvCancelled parsed into rows."""
    result: dict = {}
    for db_key, value in db.data.items():
        parts = split_key(db_key) if isinstance(db_key, str) else None
        if parts and parts[0] == "r" and parts[2] == "internalData" and parts[3] in ACCOUNTING_KEYS:
            if not isinstance(value, str):
                raise TsmError(f"type mismatch for {db_key!r} in {db.path}: expected string, got {lua_type(value)}")
            result.setdefault(parts[1], {})[parts[3]] = parse_csv(value)
    return result


# ============================================================================
# Profile: one summary for a setup interview (read only)
# ============================================================================

COPPER_PER_GOLD = 10000
PROFILE_TOP_SOLD = 10


def _gold(copper) -> float:
    return round(copper / COPPER_PER_GOLD, 2)


def _utc_date(ts) -> str | None:
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return None
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")


def _split_sync_key(sync_key: str):
    """``"Char - Faction - Realm"`` -> (char, faction, realm), or None."""
    parts = sync_key.split(SCOPE_KEY_SEP)
    if len(parts) < 3:
        return None
    return SCOPE_KEY_SEP.join(parts[:-2]), parts[-2], parts[-1]


def _split_char_key(char_key: str):
    """``"Char - Realm"`` -> (char, realm), or None."""
    char, sep, realm = char_key.rpartition(SCOPE_KEY_SEP)
    return (char, realm) if sep and char else None


def _trade_summary(table: dict) -> dict:
    """Rows, date range, total gold and the top items by gold for a parsed csvSales/csvBuys.
    ``price`` is copper per item: TSM's ledger shows price * quantity (App/MainUI/Ledger/Transactions.lua:297)."""
    rows = table.get("rows", [])
    total = 0
    by_item: dict = {}
    times = []
    for row in rows:
        price, quantity = row.get("price"), row.get("quantity")
        if isinstance(price, int) and isinstance(quantity, int):
            copper = price * quantity
            total += copper
            entry = by_item.setdefault(row.get("itemString"),
                                       {"itemString": row.get("itemString"), "quantity": 0, "copper": 0})
            entry["quantity"] += quantity
            entry["copper"] += copper
        if isinstance(row.get("time"), int):
            times.append(row["time"])
    top = sorted(by_item.values(), key=lambda e: (-e["copper"], str(e["itemString"])))[:PROFILE_TOP_SOLD]
    for entry in top:
        entry["gold"] = _gold(entry["copper"])
    return {
        "rows": len(rows),
        "malformed": len(table.get("malformed", [])),
        "firstDate": _utc_date(min(times)) if times else None,
        "lastDate": _utc_date(max(times)) if times else None,
        "totalCopper": total,
        "totalGold": _gold(total),
        "topItems": top,
    }


def _profile_characters(db: Database, notes: list) -> tuple[list, dict]:
    scope_keys = _scope_keys(db)
    sync = scope_keys.get("sync", [])
    chars = scope_keys.get("char", [])
    if not sync and not chars:
        notes.append("_scopeKeys has no char or sync list: TSM has not logged in any character yet")
    characters: dict = {}
    for key in sync:
        split = _split_sync_key(key) if isinstance(key, str) else None
        if not split:
            notes.append(f"_scopeKeys.sync entry {key!r} is not 'Char - Faction - Realm': skipped")
            continue
        name, faction, realm = split
        characters[(name, realm)] = {"name": name, "realm": realm, "faction": faction, "syncKey": key}
    for key in chars:
        split = _split_char_key(key) if isinstance(key, str) else None
        if not split:
            notes.append(f"_scopeKeys.char entry {key!r} is not 'Char - Realm': skipped")
            continue
        if split not in characters:
            characters[split] = {"name": split[0], "realm": split[1], "faction": None, "syncKey": None}
            notes.append(f"{split[0]} - {split[1]}: no sync key, so no faction, class, money, professions or inventory")
    inv = inventory(db)["characters"]
    out = []
    for info in characters.values():
        sync_key = info.pop("syncKey")
        entry = dict(info)
        who = f"{info['name']} - {info['realm']}"
        if sync_key:
            class_key = db.data.get(make_key("sync", sync_key, "internalData", "classKey"))
            money = db.data.get(make_key("sync", sync_key, "internalData", "money"))
            entry["classKey"] = class_key if isinstance(class_key, str) else None
            entry["money"] = money if isinstance(money, int) and not isinstance(money, bool) else None
            if entry["classKey"] is None:
                notes.append(f"{who}: no classKey recorded")
            if entry["money"] is None:
                notes.append(f"{who}: no money recorded")
            profs = db.data.get(make_key("sync", sync_key, "internalData", "playerProfessions"))
            entry["professions"] = {
                str(name): {"level": p.get("level"), "maxLevel": p.get("maxLevel"), "isSecondary": p.get("isSecondary")}
                for name, p in (profs.items() if isinstance(profs, dict) else []) if isinstance(p, dict)
            }
            if not entry["professions"]:
                notes.append(f"{who}: no professions recorded (open each profession window once with TSM loaded)")
            items = inv.get(sync_key, {})
            entry["inventory"] = {
                "distinctItems": len(items),
                "totalQuantity": sum(sum(places.values()) for places in items.values()),
            }
        else:
            entry.update({"classKey": None, "money": None, "professions": {}, "inventory": None})
        out.append(entry)
    out.sort(key=lambda e: (e["realm"].lower(), str(e["faction"]), e["name"].lower()))
    realms: dict = {}
    for entry in out:
        realms.setdefault(entry["realm"], {}).setdefault(entry["faction"] or "unknown", []).append(entry["name"])
    return out, realms


def _profile_groups(db: Database, profile_name: str, notes: list) -> tuple[dict | None, dict | None]:
    group_info = None
    try:
        groups = _groups(db, profile_name)
    except TsmError as exc:
        notes.append(f"profile {profile_name!r} has no groups table ({exc}): no groups read")
    else:
        paths = [p for p in groups if isinstance(p, str) and p != ROOT_GROUP]
        group_info = {
            "profile": profile_name,
            "count": len(paths),
            "topLevel": sorted((p for p in paths if GROUP_SEP not in p), key=str.lower),
        }
        try:
            group_info["groupedItems"] = len(_profile_table(db, profile_name, "items"))
        except TsmError:
            group_info["groupedItems"] = None
    try:
        table = operations_table(db, profile_name)
        ops = {module: (len(v) if isinstance(v, dict) else 0) for module, v in table.items()}
    except TsmError as exc:
        notes.append(f"no operations table ({exc}): no operations read")
        ops = None
    return group_info, ops


def _profile_appdata(notes: list, appdata_path=None, now: float | None = None) -> dict:
    """Whether TradeSkillMaster_AppHelper's AppData.lua exists, its age and its realms/regions."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import appdata as appdata_mod
    finally:
        sys.path.pop(0)
    path = str(appdata_path or appdata_mod.default_appdata_path())
    out: dict = {"path": path, "installed": False}
    if not os.path.isfile(path):
        notes.append(f"AppHelper not installed: no market prices ({path} missing; install the TSM desktop app "
                     "and the TradeSkillMaster_AppHelper addon, then let the app sync once)")
        return out
    now = datetime.datetime.now().timestamp() if now is None else now
    out["installed"] = True
    out["fileAgeHours"] = round((now - os.path.getmtime(path)) / 3600, 1)
    try:
        data = appdata_mod.AppData.from_file(path)
    except appdata_mod.AppDataError as exc:
        notes.append(f"AppHelper's AppData.lua unreadable: {exc}")
        out["error"] = str(exc)
        return out
    out["realms"] = data.names("realm")
    out["regions"] = data.names("region")
    last = data.app_info.get("lastSync") if data.app_info else None
    has_last = isinstance(last, (int, float)) and not isinstance(last, bool)
    out["lastSyncUtc"] = (datetime.datetime.fromtimestamp(last, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                          if has_last else None)
    out["lastSyncAgeHours"] = round((now - last) / 3600, 1) if has_last else None
    if not out["realms"]:
        notes.append("AppHelper has no realm price data: only region prices (DBRegion*) are available")
    return out


def profile(path, profile_name: str = DEFAULT_PROFILE, appdata_path=None, now: float | None = None,
            missing: str | None = None) -> dict:
    """One JSON summary of a TSM install, for a setup interview. Every missing piece is a named note,
    never an exception. ``path`` None means the live file was not found (``missing`` says why)."""
    notes: list = []
    result: dict = {"file": str(path) if path else None, "notes": notes}
    db = None
    if path is None:
        notes.append(f"TSM SavedVariables not found ({missing or 'no path'}): "
                     "no characters, groups, operations or accounting read")
    else:
        try:
            db = load_db(path)
        except TsmError as exc:
            notes.append(f"TSM SavedVariables unreadable: {exc}")
    if db is not None:
        result["characters"], result["realms"] = _profile_characters(db, notes)
        result["profiles"] = [p for p in _scope_keys(db).get("profile", []) if isinstance(p, str)]
        if not result["profiles"]:
            notes.append("_scopeKeys has no profile list")
        elif profile_name not in result["profiles"]:
            notes.append(f"profile {profile_name!r} is not in _scopeKeys.profile {result['profiles']}")
        result["groups"], result["operations"] = _profile_groups(db, profile_name, notes)
        sources = db.data.get(make_key("global", None, "userData", "customPriceSources"))
        result["customPriceSources"] = sorted(map(str, sources)) if isinstance(sources, dict) else []
        try:
            books = accounting(db)
        except TsmError as exc:
            notes.append(f"accounting unreadable: {exc}")
            books = {}
        if not books:
            notes.append("no accounting data (csvSales/csvBuys): TSM has recorded no sales or buys yet")
        result["accounting"] = {
            realm: {kind: _trade_summary(tables.get(key, {})) for kind, key in (("sales", "csvSales"), ("buys", "csvBuys"))}
            for realm, tables in sorted(books.items())
        }
    result["appHelper"] = _profile_appdata(notes, appdata_path, now)
    return result


def render_profile(d: dict) -> str:
    lines = [f"TSM file: {d['file'] or 'not found'}"]
    for realm, factions in (d.get("realms") or {}).items():
        for faction, names in factions.items():
            lines.append(f"{realm} ({faction}): {', '.join(names)}")
    for c in d.get("characters") or []:
        profs = ", ".join(f"{n} {p['level']}/{p['maxLevel']}" for n, p in c["professions"].items()) or "no professions"
        money = f"{_gold(c['money'])}g" if c["money"] is not None else "money ?"
        items = c["inventory"]["totalQuantity"] if c["inventory"] else "?"
        lines.append(f"  {c['name']}: {c['classKey'] or 'class ?'}, {money}, {profs}, {items} items")
    if d.get("groups"):
        g = d["groups"]
        lines.append(f"groups ({g['profile']}): {g['count']}, top level: {', '.join(g['topLevel']) or 'none'}")
    if d.get("operations") is not None:
        lines.append("operations: " + ", ".join(f"{m} {n}" for m, n in d["operations"].items()))
    if "customPriceSources" in d:
        lines.append(f"custom price sources: {', '.join(d['customPriceSources']) or 'none'}")
    for realm, books in (d.get("accounting") or {}).items():
        s, b = books["sales"], books["buys"]
        lines.append(f"accounting {realm}: {s['rows']} sales ({s['totalGold']}g), {b['rows']} buys ({b['totalGold']}g), "
                     f"{s['firstDate'] or b['firstDate'] or '?'} to {s['lastDate'] or b['lastDate'] or '?'}")
    app = d["appHelper"]
    if app["installed"]:
        lines.append(f"AppHelper: realms {', '.join(app.get('realms') or []) or 'none'}, regions "
                     f"{', '.join(app.get('regions') or []) or 'none'}, file {app['fileAgeHours']} h old")
    else:
        lines.append("AppHelper: not installed")
    lines += [f"note: {n}" for n in d["notes"]]
    return "\n".join(lines)


# ============================================================================
# Validation
# ============================================================================

def _is_string_array(value) -> bool:
    if isinstance(value, list):
        return all(isinstance(v, str) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(value) and isinstance(v, str)
                   for k, v in value.items())
    return False


def validate(db: Database) -> dict:
    """Re-implements TSM's load-time checks. ``errors`` make TSM wipe the DB,
    drop data or raise a Lua error; ``warnings`` are things it silently rewrites."""
    errors, warnings = [], []
    data = db.data

    # --- the checks that wipe the whole DB ---
    if 1 in data:
        errors.append("WIPE: the table has an array part (a positional entry or key [1])")
    version = data.get("_version")
    if lua_type(version) != "number":
        errors.append(f"WIPE: _version is {lua_type(version)}, expected number")
    elif version < MIN_DB_VERSION:
        errors.append(f"WIPE: _version {version} is below the minimum {MIN_DB_VERSION}")
    if lua_type(data.get("_hash")) != "number":
        errors.append(f"WIPE: _hash is {lua_type(data.get('_hash'))}, expected number")
    if "_lastModifiedVersion" in data and not isinstance(data["_lastModifiedVersion"], (dict, list)):
        errors.append("WIPE: _lastModifiedVersion is present but not a table")
    scope_keys = data.get("_scopeKeys")
    if not isinstance(scope_keys, dict):
        errors.append(f"WIPE: _scopeKeys is {lua_type(scope_keys)}, expected keyed table")
        scope_keys = {}
    for scope_name, keys in scope_keys.items():
        if scope_name not in SCOPES:
            errors.append(f"WIPE: _scopeKeys has unknown scope {scope_name!r}")
        elif not isinstance(keys, (dict, list)):
            errors.append(f"LUA ERROR: _scopeKeys.{scope_name} is {lua_type(keys)}, expected table")
        elif not _is_string_array(keys):
            errors.append(f"WIPE: _scopeKeys.{scope_name} is not a gapless array of strings")
    current_profile = data.get("_currentProfile")
    if not isinstance(current_profile, (dict, list)):
        errors.append(f"WIPE: _currentProfile is {lua_type(current_profile)}, expected table")
    elif isinstance(current_profile, list) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in current_profile.items()):
        errors.append("WIPE: _currentProfile must map character strings to profile-name strings")
    sync_owner, sync_account = data.get("_syncOwner"), data.get("_syncAccountKey")
    if sync_owner is not None:
        if not isinstance(sync_owner, dict) or not isinstance(sync_account, dict):
            errors.append("LUA ERROR: _syncOwner / _syncAccountKey must both be keyed tables")
        else:
            for sync_key, owner in sync_owner.items():
                factionrealm = sync_key.partition(SCOPE_KEY_SEP)[2] if isinstance(sync_key, str) else ""
                if sync_account.get(factionrealm) != owner:
                    warnings.append(
                        f"_syncOwner[{sync_key!r}] is not this account's key for {factionrealm!r}: "
                        "logging into that character on this account WIPES the DB (fine for a synced other account)")
    notes = [
        f"_hash {data.get('_hash')!r} / _version {version!r} cannot be checked offline: TSM wipes the DB when "
        "_version equals the schema version and _hash differs from the schema hash, so never edit them"]

    # --- setting keys ---
    known = {name: _array_part(keys) if isinstance(keys, (dict, list)) else [] for name, keys in scope_keys.items()}
    for db_key in data:
        if not isinstance(db_key, str):
            if db_key != 1:
                warnings.append(f"non-string top-level key {db_key!r}")
            continue
        if db_key.startswith("_"):
            continue
        parts = split_key(db_key)
        if not parts:
            warnings.append(f"key {db_key!r} is not <scope>@<scopeKey>@<namespace>@<key>: removed on the next schema version change")
        elif parts[0] == "g":
            if parts[1] != GLOBAL_SCOPE_KEY:
                warnings.append(f"global key {db_key!r} does not use the scope key ' ': TSM never reads it")
        elif parts[1] not in known.get(SCOPE_NAMES[parts[0]], []):
            warnings.append(
                f"key {db_key!r}: scope key {parts[1]!r} is not in _scopeKeys.{SCOPE_NAMES[parts[0]]}; "
                "TSM never reads it and resets it if that scope key is ever registered")
    if isinstance(current_profile, dict):
        for character, profile in current_profile.items():
            if profile not in known.get("profile", []):
                warnings.append(f"_currentProfile[{character!r}] = {profile!r} is not in _scopeKeys.profile: created empty on login")

    # --- operations, groups, items per profile ---
    global_ops = data.get(make_key("global", None, "coreOptions", "globalOperations")) is True
    for profile in known.get("profile", []):
        _validate_profile(db, profile, global_ops, errors, warnings)
    return {"ok": not errors, "errors": errors, "warnings": warnings, "notes": notes}


def _validate_profile(db, profile, global_ops, errors, warnings):
    data = db.data
    tag = f"profile {profile!r}"
    ops_key = make_key("global", None, "userData", "sharedOperations") if global_ops \
        else make_key("profile", profile, "userData", "operations")
    operations = data.get(ops_key)
    if not isinstance(operations, dict):
        if operations not in (None, []):
            errors.append(f"{tag}: {ops_key!r} is {lua_type(operations)}, expected keyed table")
        operations = {}
    for module, ops in operations.items():
        if module not in MODULES:
            warnings.append(f"{tag}: operations has unknown module {module!r} (TSM leaves it, groups cannot use it)")
            continue
        if not isinstance(ops, dict):
            if ops != []:
                errors.append(f"LUA ERROR: {tag}: operations.{module} is not a keyed table")
            continue
        expected = dict(MODULES[module]["fields"], **COMMON_OPERATION_FIELDS)
        for name, settings in ops.items():
            label = f"{tag}: operation {module}/{name!r}"
            if not isinstance(name, str) or name == "" or name != name.strip():
                errors.append(f"{label}: invalid name, TSM removes the operation")
                continue
            if not isinstance(settings, (dict, list)):
                errors.append(f"LUA ERROR: {label} is {lua_type(settings)}, expected table")
                continue
            settings = settings if isinstance(settings, dict) else {}
            for field, kind in expected.items():
                if field not in settings:
                    if kind != "boolean":
                        warnings.append(f"{label}: missing field {field!r}, TSM resets it to the default")
                elif lua_type(settings[field]) != kind and not (kind == "string" and lua_type(settings[field]) == "number"):
                    warnings.append(f"{label}: field {field!r} is {lua_type(settings[field])}, expected {kind}; TSM resets it")
            for field in settings:
                if field not in expected:
                    warnings.append(f"{label}: unknown field {field!r}, TSM deletes it")
            relationships = settings.get("relationships")
            if isinstance(relationships, dict):
                for field, target in relationships.items():
                    if target not in ops:
                        warnings.append(f"{label}: relationship {field!r} -> {target!r} points at no operation, TSM removes it")
                    elif field not in expected:
                        errors.append(f"LUA ERROR: {label}: relationship on unknown field {field!r}")
                    else:
                        seen, current = {name}, target
                        while isinstance(current, str) and current in ops:
                            if current in seen:
                                warnings.append(f"{label}: circular relationship on {field!r}, TSM removes it")
                                break
                            seen.add(current)
                            rel = ops[current].get("relationships") if isinstance(ops[current], dict) else None
                            current = rel.get(field) if isinstance(rel, dict) else None

    groups_key = make_key("profile", profile, "userData", "groups")
    groups = data.get(groups_key)
    if not isinstance(groups, dict):
        if groups not in (None, []):
            errors.append(f"{tag}: {groups_key!r} is {lua_type(groups)}, expected keyed table")
        groups = {}
    if ROOT_GROUP not in groups:
        warnings.append(f'{tag}: no root group "": TSM creates it and forces override on every top-level group')
    for path, info in groups.items():
        label = f"{tag}: group {path!r}"
        if not isinstance(info, dict):
            if info != []:
                errors.append(f"LUA ERROR: {label} is {lua_type(info)}, expected table")
            continue
        if not isinstance(path, str) or GROUP_SEP * 2 in path:
            errors.append(f"{label}: invalid path, TSM removes the group")
            continue
        parent = group_parent(path)
        if parent is not None and parent not in groups:
            errors.append(f"{label}: parent {parent!r} does not exist, TSM removes the group (and its items)")
        for module, ops in info.items():
            if module in ("ignoreItemVariations", "ignoreRandomEnchants"):
                continue
            if not isinstance(ops, (dict, list)):
                errors.append(f"LUA ERROR: {label}: {module!r} is {lua_type(ops)}, expected table")
                continue
            if module not in MODULES:
                if _array_part(ops):
                    errors.append(f"LUA ERROR: {label}: key {module!r} is not an operation module but lists operations")
                else:
                    warnings.append(f"{label}: key {module!r} is not an operation module, TSM removes it")
                continue
            names = _array_part(ops)
            override = isinstance(ops, dict) and ops.get("override")
            if isinstance(ops, dict):
                for key in ops:
                    if key != "override" and not (isinstance(key, int) and 1 <= key <= len(names)):
                        warnings.append(f"{label}: {module} has invalid key {key!r}, TSM removes it")
                if "override" in ops and ops["override"] is not True:
                    warnings.append(f"{label}: {module}.override is {ops['override']!r}, TSM normalises it to true/nil")
            for name in names:
                if not isinstance(name, str) or name == "":
                    warnings.append(f"{label}: {module} lists a non-string or empty operation, TSM removes it")
                elif name not in operations.get(module, {}):
                    errors.append(f"{label}: {module} operation {name!r} does not exist, TSM removes it from the group")
            if len(names) > MODULES[module]["max"]:
                warnings.append(f"{label}: {len(names)} {module} operations, TSM keeps the first {MODULES[module]['max']}")
            if path == ROOT_GROUP and not override:
                warnings.append(f"{label}: {module} has no override on the root group, TSM sets it")
            parent_info = groups.get(parent) if parent is not None else None
            if path != ROOT_GROUP and not override and isinstance(parent_info, dict) \
                    and names != _array_part(parent_info.get(module)):
                warnings.append(f"{label}: {module} has no override but differs from its parent; TSM overwrites it with the parent's list")
        for module in MODULES:
            if module not in info:
                warnings.append(f"{label}: no {module} entry, TSM adds an empty one")

    items_key = make_key("profile", profile, "userData", "items")
    items = data.get(items_key)
    if not isinstance(items, dict):
        if items not in (None, []):
            errors.append(f"{tag}: {items_key!r} is {lua_type(items)}, expected keyed table")
        items = {}
    for item, group in items.items():
        label = f"{tag}: item {item!r}"
        try:
            canonical = normalize_item_string(item) if isinstance(item, str) else None
        except TsmError:
            canonical = None
        if canonical is None:
            errors.append(f"{label}: invalid item string, TSM removes it")
        elif canonical != item:
            warnings.append(f"{label}: TSM re-keys it as {canonical!r}")
        if not isinstance(group, str):
            errors.append(f"LUA ERROR: {label}: group is {lua_type(group)}, expected string")
        elif group == ROOT_GROUP or group not in groups:
            errors.append(f"{label}: group {group!r} does not exist (or is the root), TSM removes the item")


# ============================================================================
# Declarative plan
# ============================================================================

PLAN_KEYS = {"profile", "settings", "remove_operations", "remove_groups", "operations", "groups", "items",
             "group_operations"}


def apply_plan(db: Database, plan: dict) -> list:
    """Applies a plan to ``db`` in memory and returns the change lines. Order:
    settings, remove_operations, remove_groups, operations, groups, items,
    group_operations. Re-applying is a no-op (removing what is gone does nothing)."""
    if not isinstance(plan, dict):
        raise TsmError(f"plan must be a JSON object, got {lua_type(plan)}")
    unknown = sorted(k for k in plan if k not in PLAN_KEYS)
    if unknown:
        raise TsmError(f"unknown plan key(s) {unknown}: expected {sorted(PLAN_KEYS)}")
    profile = plan.get("profile", DEFAULT_PROFILE)
    changes = []
    for db_key, value in (plan.get("settings") or {}).items():
        old = set_key(db, db_key, value)
        if old != value or lua_type(old) != lua_type(value):
            changes.append(f"setting {_expand_key(db_key)}: {json.dumps(old)} -> {json.dumps(value)}")
    for section in ("remove_operations", "remove_groups"):
        if not isinstance(plan.get(section) or [], list):
            raise TsmError(f'plan "{section}" must be a list, got {lua_type(plan[section])}')
    for entry in plan.get("remove_operations") or []:
        _need(entry, "remove_operations", ("module", "name"), ())
        result = remove_operation(db, entry["module"], entry["name"], profile=profile)
        if result is not None:
            changes.append(f"operation {entry['module']}/{entry['name']}: removed"
                           + (f", dropped from {len(result['groups'])} group(s)" if result["groups"] else "")
                           + (f", cleared relationships {result['relationships']}" if result["relationships"] else ""))
    for path in plan.get("remove_groups") or []:
        result = remove_group(db, path, profile=profile)
        if result is not None:
            changes.append(f"group {path!r}: removed {len(result['groups'])} group(s), "
                           f"{len(result['items'])} item(s) ungrouped")
    for entry in plan.get("operations") or []:
        _need(entry, "operations", ("module", "name"), ("settings", "update"))
        result = create_operation(db, entry["module"], entry["name"], entry.get("settings"),
                                  profile=profile, update=bool(entry.get("update")), exist_ok=True)
        if result["created"]:
            changes.append(f"operation {entry['module']}/{entry['name']}: created"
                           + (f" with {json.dumps(result['changed'])}" if result["changed"] else " (all defaults)"))
        elif result["changed"]:
            changes.append(f"operation {entry['module']}/{entry['name']}: changed {json.dumps(result['changed'])}")
    for path in plan.get("groups") or []:
        for created in create_group(db, path, profile=profile):
            changes.append(f"group {created!r}: created")
    items_plan = plan.get("items") or {}
    if not isinstance(items_plan, dict):
        raise TsmError('plan "items" must be an object of group path -> [item strings]')
    for path, item_strings in items_plan.items():
        result = assign_items(db, path, item_strings, profile=profile)
        for item in result["added"]:
            changes.append(f"item {item}: added to {path!r}")
        for item, previous in result["moved"].items():
            changes.append(f"item {item}: moved {previous!r} -> {path!r}")
        changes.extend(f"warning: {w}" for w in result["warnings"])
    for entry in plan.get("group_operations") or []:
        _need(entry, "group_operations", ("group", "module"), ("operations", "override"))
        override = entry.get("override", True)
        result = set_group_operations(db, entry["group"], entry["module"], entry.get("operations") or [],
                                      override=override, profile=profile)
        if result["before"] != result["after"]:
            changes.append(f"group {entry['group']!r} {entry['module']}: {result['before']['names']} "
                           f"(override={result['before']['override']}) -> {result['after']['names']} (override={override})")
            changes.extend(f"group {child!r} {entry['module']}: inherits the new list" for child in result["inherited_by"])
    return changes


def _need(entry, section, required, optional):
    if not isinstance(entry, dict):
        raise TsmError(f'plan "{section}" entries must be objects, got {lua_type(entry)}')
    missing = [k for k in required if k not in entry]
    extra = [k for k in entry if k not in required and k not in optional]
    if missing or extra:
        raise TsmError(f'plan "{section}" entry {json.dumps(entry)}: missing {missing}, unknown {extra}')


# ============================================================================
# CLI
# ============================================================================

def _print_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _write(db, path, args):
    result = save_db(path, db)
    print(f"wrote {result['path']} ({result['bytes']} bytes)" + (f"; backup {result['backup']}" if result["backup"] else ""))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read and safely rewrite TradeSkillMaster's SavedVariables.")
    parser.add_argument("--file", help="TradeSkillMaster.lua to use (default: the live file under _forever_\\WTF)")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="TSM profile for groups/operations (default: Default)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("get", help="print one setting as JSON")
    p.add_argument("key", help="full key, e.g. 'g@ @userData@ungroupedItemMode' (g@ns@key also works)")
    p = sub.add_parser("set", help="set one existing setting (same Lua type as the current value)")
    p.add_argument("key")
    p.add_argument("value", help="JSON value")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("groups", help="list groups with item counts and operations")
    p = sub.add_parser("operations", help="list operations (optionally one module)")
    p.add_argument("module", nargs="?")
    p = sub.add_parser("inventory", help="bag/bank/mail/auction quantities per character and summed")
    p.add_argument("--totals", action="store_true", help="only the per-item sums")
    p = sub.add_parser("accounting", help="sales/buys/income/expense/expired/cancelled rows per realm")
    p.add_argument("--summary", action="store_true", help="row counts only")
    p = sub.add_parser("apply", help="apply a declarative plan.json")
    p.add_argument("plan")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("validate", help="run TSM's load-time checks; exit 1 on errors")
    sub.add_parser("roundtrip", help="parse, serialize, parse again; report equality and byte identity")
    p = sub.add_parser("profile", help="one JSON summary: characters, professions, groups, accounting, AppHelper")
    p.add_argument("--text", action="store_true", help="a short human summary instead of JSON")
    p.add_argument("--appdata", help="AppHelper's AppData.lua (default: the game folder; TSM_APPDATA overrides)")
    args = parser.parse_args(argv)
    if args.command == "profile":
        path, missing = args.file, None
        if not path:
            try:
                path = default_live_path()
            except TsmError as exc:
                missing = str(exc)
        result = profile(path, args.profile, args.appdata, missing=missing)
        text = render_profile(result) if args.text else json.dumps(result, indent=2, ensure_ascii=False)
        try:
            print(text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
        return 0
    try:
        path = args.file or default_live_path()
        db = load_db(path)
        if args.command == "get":
            _print_json(get_key(db, args.key))
        elif args.command == "set":
            try:
                value = json.loads(args.value)
            except json.JSONDecodeError as exc:
                raise TsmError(f"value is not JSON ({exc}): quote strings, e.g. '\"base\"'") from exc
            old = set_key(db, args.key, value)
            print(f"{_expand_key(args.key)}: {json.dumps(old)} -> {json.dumps(value)}")
            if args.dry_run:
                print("dry run: nothing written")
            else:
                _write(db, path, args)
        elif args.command == "groups":
            _print_json(list_groups(db, args.profile))
        elif args.command == "operations":
            _print_json(list_operations(db, args.module, args.profile))
        elif args.command == "inventory":
            result = inventory(db)
            _print_json(result["totals"] if args.totals else result)
        elif args.command == "accounting":
            result = accounting(db)
            if args.summary:
                result = {realm: {k: {"rows": len(v["rows"]), "malformed": len(v["malformed"]), "empty": v["empty"]}
                                  for k, v in tables.items()} for realm, tables in result.items()}
            _print_json(result)
        elif args.command == "apply":
            try:
                with open(args.plan, encoding="utf-8") as handle:
                    plan = json.load(handle)
            except OSError as exc:
                raise TsmError(f"cannot read plan {args.plan}: {exc.strerror}") from exc
            except json.JSONDecodeError as exc:
                raise TsmError(f"plan {args.plan} is not JSON: {exc}") from exc
            before = validate(db)["errors"]
            changes = apply_plan(db, plan)
            for line in changes:
                print(line)
            real = [c for c in changes if not c.startswith("warning: ")]
            print(f"{len(real)} change(s)")
            introduced = [e for e in validate(db)["errors"] if e not in before]
            for line in introduced:
                print(f"validate error: {line}")
            if introduced:
                raise TsmError("the plan introduces validation errors: nothing written")
            if args.dry_run:
                print("dry run: nothing written")
            elif real:
                _write(db, path, args)
            else:
                print("nothing to write")
        elif args.command == "validate":
            report = validate(db)
            for line in report["errors"]:
                print(f"error: {line}")
            for line in report["warnings"]:
                print(f"warning: {line}")
            for line in report["notes"]:
                print(f"note: {line}")
            print(f"{len(report['errors'])} error(s), {len(report['warnings'])} warning(s) in {path}")
            return 0 if report["ok"] else 1
        elif args.command == "roundtrip":
            with open(path, "rb") as handle:
                original = handle.read()
            again = loads_db(db.to_bytes(), path)
            equal = again.data == db.data
            print(f"parse -> serialize -> parse equal: {equal}; byte-identical to the file: {db.to_bytes() == original}")
            return 0 if equal else 1
    except TsmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
