#!/usr/bin/env python3
"""Parse a WoW SavedVariables file (plain Lua table assignments) into JSON.

    python tools/wowf_sv.py <file.lua> [--var NAME] [--path a.b.c]

The client writes `NAME = { ... }` blocks with string, number, boolean and nested table values and
keys written as `["key"]`, `[123]`, or bare identifiers. Nothing else ever appears, so this is a
small hand parser, not a Lua runtime: no code is executed, which matters because the file is
written by the game and (via chat) influenced by other players. Lua `nil` and keys in sequence
form (`{ "a", "b" }`) become JSON lists when every key is 1..n.

Used by tools\reload-wait.ps1. Stdlib only.

Exit codes: 0 ok, 2 the file does not parse (often: read while the client was still writing it),
3 --var or a --path step is absent, 4 the file cannot be read, 5 a value JSON cannot hold (inf,
nan). Codes 2-5 print one `wowf_sv: ...` line on stderr naming
the link that broke. --ascii escapes non-ASCII as \\uXXXX, so a caller that decodes stdout with
the wrong code page (PowerShell 5.1 does) cannot corrupt the JSON.
"""
import argparse
import json
import re
import sys

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<comment>--[^\n]*)
      | (?P<str>"(?:\\[\s\S]|[^"\\])*")
      | (?P<num>-?(?:0x[0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?))
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<punct>[{}\[\]=,;])
    )""",
    re.VERBOSE,
)

_ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'", "\n": "\n"}


def _unescape(s: str) -> str:
    # Lua strings are bytes: a decimal escape (\ddd) is one byte, so UTF-8 written as "\228\184\173" is 中.
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n in "0123456789":
                j = i + 1
                while j < len(s) and j < i + 4 and s[j] in "0123456789":
                    j += 1
                byte = int(s[i + 1 : j])
                if byte > 255:
                    raise ValueError(f"decimal escape \\{byte} is above 255")
                out.append(byte)
                i = j
                continue
            out += _ESC.get(n, n).encode("utf-8")
            i += 2
            continue
        out += c.encode("utf-8")
        i += 1
    return out.decode("utf-8", errors="replace")


class _Parser:
    def __init__(self, text: str):
        self.toks = []
        pos = 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m or m.end() == pos:
                if text[pos:].strip() == "":
                    break
                raise ValueError(f"unexpected text at {pos}: {text[pos:pos+30]!r}")
            pos = m.end()
            if m.group("comment"):
                continue
            kind = m.lastgroup
            self.toks.append((kind, m.group(kind)))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, kind=None, val=None):
        k, v = self.peek()
        if kind and k != kind or val is not None and v != val:
            raise ValueError(f"expected {kind or ''} {val or ''}, got {k} {v!r} at token {self.i}")
        self.i += 1
        return v

    def value(self):
        k, v = self.peek()
        if k == "str":
            self.take()
            return _unescape(v[1:-1])
        if k == "num":
            self.take()
            if re.fullmatch(r"-?0x[0-9a-fA-F]+", v):
                return int(v, 16)
            return int(v, 10) if re.fullmatch(r"-?\d+", v) else float(v)  # base 10: "007" is 7
        if k == "name":
            self.take()
            return {"true": True, "false": False, "nil": None}.get(v, v)
        if k == "punct" and v == "{":
            return self.table()
        raise ValueError(f"bad value {k} {v!r}")

    def table(self):
        self.take("punct", "{")
        items = []
        auto = 1
        while True:
            k, v = self.peek()
            if k == "punct" and v == "}":
                self.take()
                break
            if k == "punct" and v == "[":
                self.take()
                key = self.value()
                self.take("punct", "]")
                self.take("punct", "=")
                items.append((key, self.value()))
            elif k == "name" and self.i + 1 < len(self.toks) and self.toks[self.i + 1] == ("punct", "="):
                key = self.take()
                self.take()
                items.append((key, self.value()))
            else:
                items.append((auto, self.value()))
                auto += 1
            k, v = self.peek()
            if k == "punct" and v in ",;":
                self.take()
        keys = [k for k, _ in items]
        if items and all(isinstance(k, int) for k in keys) and keys == list(range(1, len(keys) + 1)):
            return [v for _, v in items]
        return {str(k): v for k, v in items}

    def file(self):
        out = {}
        while self.peek()[0] is not None:
            name = self.take("name")
            self.take("punct", "=")
            out[name] = self.value()
        return out


def parse_file(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace") as f:
        return _Parser(f.read()).file()


class Missing(LookupError):
    """--var or a --path step is absent; the message names which one and what was there instead."""


def _keys(d) -> str:
    if isinstance(d, dict):
        ks = sorted(d)
        return ", ".join(ks[:12]) + (", ..." if len(ks) > 12 else "") if ks else "(empty table)"
    if isinstance(d, list):
        return f"(a list of {len(d)})"
    return f"(a {type(d).__name__}, not a table)"


def select(data: dict, var: str = None, path: str = None):
    """Walk --var then --path; raise Missing naming the first step that is absent."""
    where = "file"
    if var:
        if var not in data:
            raise Missing(f"variable {var} not in file (top-level: {_keys(data)})")
        data, where = data[var], var
    for part in path.split(".") if path else []:
        if isinstance(data, list) and part.isdigit() and 1 <= int(part) <= len(data):
            data = data[int(part) - 1]
        elif isinstance(data, dict) and part in data:
            data = data[part]
        else:
            raise Missing(f"{where} has no {part!r} (has: {_keys(data)})")
        where = f"{where}.{part}"
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file")
    ap.add_argument("--var", help="only this top-level variable")
    ap.add_argument("--path", help="dotted path inside --var (or inside the whole file)")
    ap.add_argument("--ascii", action="store_true", help="escape non-ASCII (for callers that mis-decode UTF-8)")
    a = ap.parse_args(argv)
    # Chat text is UTF-8; the Windows console default is a code page, and -I ignores PYTHONIOENCODING.
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        data = select(parse_file(a.file), a.var, a.path)
    except OSError as e:
        print(f"wowf_sv: cannot read {a.file}: {e.strerror or e}", file=sys.stderr)
        return 4
    except (ValueError, RecursionError) as e:
        print(f"wowf_sv: does not parse (read mid-write?): {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    except Missing as e:
        print(f"wowf_sv: {e}", file=sys.stderr)
        return 3
    try:
        text = json.dumps(data, ensure_ascii=a.ascii, indent=2, allow_nan=False)
    except ValueError as e:  # inf/nan (1e999): JSON has no such number, and PowerShell would refuse it
        print(f"wowf_sv: value JSON cannot hold: {e}", file=sys.stderr)
        return 5
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
