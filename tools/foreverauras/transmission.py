"""ForeverAuras import/export strings and the source file shape.

Export (Transmission.lua, TableToString for chat):
    "!WA:2!" .. EncodeForPrint(CompressDeflate(LibSerialize:SerializeEx(
        {errorOnUnserializableType = false}, payload)))
payload = {m = "d", d = <aura or group>, v = 1421 | 2000, s = <version>, c = {<children>}}
v is 2000 only when a child is itself a group; with 1421 the importer rebuilds
the group's controlledChildren and each child's parent from c.
"""

import os
import re

import deflate_print
import luaser
import lualit

DEFAULT_GAME_DIR = r"C:\Program Files (x86)\World of Warcraft"
FALLBACK_VERSION = "1.4.3"
FALLBACK_INTERNAL_VERSION = 91
_PREFIX = re.compile(r"^!([FW]A):(\d+)!(.+)$", re.S)


def default_fa_dir():
    base = os.environ.get("WOWF_GAME_DIR", DEFAULT_GAME_DIR)
    return os.path.join(base, "_forever_", "Interface", "AddOns", "ForeverAuras")


def addon_version(fa_dir=None):
    """`## Version:` of ForeverAuras.toc, or the fallback when the addon is not found."""
    toc = os.path.join(fa_dir or default_fa_dir(), "ForeverAuras.toc")
    try:
        with open(toc, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"##\s*Version:\s*(\S+)", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return FALLBACK_VERSION


def internal_version(fa_dir=None):
    """`local internalVersion = N` of ForeverAuras.lua, or the fallback."""
    path = os.path.join(fa_dir or default_fa_dir(), "ForeverAuras.lua")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            m = re.search(r"^local internalVersion = (\d+)", f.read(), re.M)
            if m:
                return int(m.group(1))
    except OSError:
        pass
    return FALLBACK_INTERNAL_VERSION


def children_of(src):
    c = src.get("c") or {}
    if isinstance(c, list):
        return [x for x in c if x is not None]
    array, rest = lualit.split_table(c)
    if rest:
        raise ValueError("c must be a list of child tables (found key %r)" % (rest[0][0],))
    return array


def build_payload(src, version_string):
    data = src.get("d")
    if not isinstance(data, dict):
        raise ValueError("source has no d = { ... } table")
    children = children_of(src)
    nested = any(isinstance(ch.get("controlledChildren"), (dict, list)) for ch in children)
    payload = {"m": "d", "d": data, "v": 2000 if nested else 1421, "s": version_string}
    if children:
        payload["c"] = children
    return payload


def encode_payload(payload):
    raw = luaser.serialize(payload)
    return "!WA:2!" + deflate_print.encode_for_print(deflate_print.compress_deflate(raw))


def decode_string(text):
    """Import string -> payload table. Raises ValueError naming the step that failed."""
    text = text.strip()
    m = _PREFIX.match(text)
    if not m:
        raise ValueError("not a ForeverAuras string: no !WA:N! or !FA:N! prefix")
    version = int(m.group(2))
    if version < 2:
        raise ValueError("encoding version %d uses AceSerializer; only version 2+ is supported" % version)
    packed = deflate_print.decode_for_print(m.group(3))
    if packed is None:
        raise ValueError("print decoding failed: a character outside a-zA-Z0-9()")
    try:
        raw = deflate_print.decompress_deflate(packed)
    except Exception as e:  # zlib.error
        raise ValueError("decompressing failed: %s" % e) from None
    values = luaser.deserialize(raw)
    if not values or not isinstance(values[0], dict):
        raise ValueError("deserialized data is not a table")
    return values[0]


def payload_to_src(payload):
    if payload.get("m") != "d" or not isinstance(payload.get("d"), dict):
        raise ValueError("payload is not an aura export (m=%r)" % payload.get("m"))
    src = {"d": payload["d"]}
    children = children_of(payload)
    if children:
        src["c"] = children
    return src


def write_src(src, header=None):
    lines = []
    if header:
        lines += ["-- " + h for h in header]
    lines.append("return " + lualit.dump(src, order=["d", "c"]))
    return "\n".join(lines) + "\n"


def read_src(path):
    # utf-8-sig: Windows editors and PowerShell's Set-Content add a byte-order mark.
    with open(path, encoding="utf-8-sig", errors="surrogateescape") as f:
        src = lualit.parse(f.read())
    if not isinstance(src, dict) or not isinstance(src.get("d"), dict):
        raise ValueError("%s: expected `return { d = {...}, c = {...} }`" % path)
    return src
