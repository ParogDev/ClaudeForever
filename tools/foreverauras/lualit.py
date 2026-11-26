"""Lua 5.1 literal parser and writers.

Reads literal data only: tables, strings (quoted with 5.1 escapes, or long
brackets), numbers (decimal, float, exponent, hex, unary minus), true, false,
nil and comments. No expressions. Tables come back as dicts (array part under
int keys 1..n); whole floats become ints, since Lua 5.1 has one number type.

Writers: dump() is the pretty, stable form used for source files (sorted keys,
array part first, multi-line strings as long brackets); dump_sv() writes the
SavedVariables layout of this client (CRLF, no indent, ["key"] = value,).
"""

import math
import re

KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function", "if", "in",
    "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while",
}
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, "\\": 92, '"': 34, "'": 39}


class LuaSyntaxError(ValueError):
    pass


def normalize_number(x):
    if isinstance(x, float) and x == math.floor(x) and abs(x) < 2**53:
        return int(x)
    return x


class _Parser:
    def __init__(self, text):
        self.s = text
        self.i = 0

    def error(self, msg):
        line = self.s.count("\n", 0, self.i) + 1
        raise LuaSyntaxError("line %d: %s" % (line, msg))

    def long_bracket_level(self, at):
        """Level of a long bracket opening at `at` ('[' '='* '['), or -1."""
        m = re.compile(r"\[(=*)\[").match(self.s, at)
        return len(m.group(1)) if m else -1

    def read_long(self, level):
        start = self.i + level + 2
        close = "]" + "=" * level + "]"
        end = self.s.find(close, start)
        if end < 0:
            self.error("unfinished long string or comment")
        self.i = end + len(close)
        body = self.s[start:end]
        # Lua skips one newline right after the opening bracket and turns every
        # newline sequence (\n, \r, \r\n, \n\r) into \n.
        out, j = [], 0
        while j < len(body):
            c = body[j]
            if c in "\r\n":
                if j + 1 < len(body) and body[j + 1] in "\r\n" and body[j + 1] != c:
                    j += 1
                out.append("\n")
            else:
                out.append(c)
            j += 1
        text = "".join(out)
        return text[1:] if text.startswith("\n") else text

    def skip(self):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c in " \t\r\n\f\v":
                self.i += 1
            elif s.startswith("--", self.i):
                self.i += 2
                level = self.long_bracket_level(self.i)
                if level >= 0:
                    self.read_long(level)
                else:
                    nl = s.find("\n", self.i)
                    self.i = len(s) if nl < 0 else nl + 1
            else:
                break

    def peek(self, tok):
        self.skip()
        return self.s.startswith(tok, self.i)

    def expect(self, tok):
        if not self.peek(tok):
            self.error("expected %r" % tok)
        self.i += len(tok)

    def name(self):
        self.skip()
        m = _NAME.match(self.s, self.i)
        if not m:
            return None
        return m.group(0)

    def value(self):
        self.skip()
        s, i = self.s, self.i
        if i >= len(s):
            self.error("unexpected end of input")
        c = s[i]
        if c == "{":
            return self.table()
        if c in "\"'":
            return self.quoted(c)
        if c == "[":
            level = self.long_bracket_level(i)
            if level < 0:
                self.error("unexpected '['")
            return self.read_long(level)
        if c == "-":
            self.i += 1
            self.skip()
            v = self.value()
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                self.error("unary minus on a non-number")
            return -v
        m = _NUMBER.match(s, i)
        if m:
            self.i = m.end()
            if _NAME.match(s, self.i):
                self.error("malformed number near %r" % s[i : self.i + 1])
            t = m.group(0)
            if t[:2] in ("0x", "0X"):
                return int(t, 16)
            if "." in t or "e" in t or "E" in t:
                return normalize_number(float(t))
            return int(t)
        word = self.name()
        if word in ("true", "false", "nil"):
            self.i += len(word)
            return {"true": True, "false": False, "nil": None}[word]
        self.error("not a literal: %r (expressions are not supported)" % s[i : i + 20])

    def quoted(self, q):
        s = self.s
        self.i += 1
        out = bytearray()
        while True:
            if self.i >= len(s):
                self.error("unfinished string")
            c = s[self.i]
            if c == q:
                self.i += 1
                break
            if c in "\r\n":
                self.error("unfinished string (newline)")
            if c == "\\":
                self.i += 1
                e = s[self.i] if self.i < len(s) else ""
                if e in _ESCAPES:
                    out.append(_ESCAPES[e])
                    self.i += 1
                elif e in "\r\n":
                    out.append(10)
                    self.i += 1
                    if self.i < len(s) and s[self.i] in "\r\n" and s[self.i] != e:
                        self.i += 1
                elif e.isdigit():
                    m = re.compile(r"\d{1,3}").match(s, self.i)
                    n = int(m.group(0))
                    if n > 255:
                        self.error("escape sequence too large")
                    out.append(n)
                    self.i = m.end()
                else:
                    self.error("invalid escape sequence \\%s" % e)
            else:
                out += c.encode("utf-8", "surrogateescape")
                self.i += 1
        return out.decode("utf-8", "surrogateescape")

    def named_field(self):
        """True when the next field is `Name = value` (looks ahead, consumes nothing)."""
        word = self.name()
        if not word or word in KEYWORDS:
            return False
        save = self.i
        self.i += len(word)
        found = self.peek("=") and not self.peek("==")
        self.i = save
        return found

    def table(self):
        self.expect("{")
        t, n = {}, 0
        while not self.peek("}"):
            if self.peek("[") and self.long_bracket_level(self.i) < 0:
                self.i += 1
                k = self.value()
                self.expect("]")
                self.expect("=")
                v = self.value()
                if k is None:
                    self.error("table index is nil")
                if v is not None:
                    t[normalize_number(k)] = v
            elif self.named_field():
                word = self.name()
                self.i += len(word)
                self.expect("=")
                v = self.value()
                if v is not None:
                    t[word] = v
            else:
                n += 1
                v = self.value()
                if v is not None:
                    t[n] = v
            if self.peek(",") or self.peek(";"):
                self.i += 1
            elif not self.peek("}"):
                self.error("expected ',' or '}'")
        self.expect("}")
        return t

    def at_end(self):
        self.skip()
        return self.i >= len(self.s)


def parse(text):
    """A literal, optionally written as `return <literal>` (a source file)."""
    p = _Parser(text)
    if p.name() == "return":
        p.i += len("return")
    v = p.value()
    if p.peek(";"):
        p.i += 1
    if not p.at_end():
        p.error("unexpected text after the literal")
    return v


def parse_assignments(text):
    """`Name = <literal>` statements (a SavedVariables file) -> list of (name, value)."""
    p = _Parser(text)
    out = []
    while not p.at_end():
        word = p.name()
        if not word or word in KEYWORDS:
            p.error("expected a global name")
        p.i += len(word)
        p.expect("=")
        out.append((word, p.value()))
        if p.peek(";"):
            p.i += 1
    return out


# ---------------------------------------------------------------- writers


def format_number(x):
    if isinstance(x, float):
        if math.isinf(x) or math.isnan(x):
            raise ValueError("inf/nan has no Lua literal")
        x = normalize_number(x)
        if isinstance(x, float):
            return repr(x)
    return str(x)


def quote(s):
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif 0xDC80 <= o <= 0xDCFF:
            out.append("\\%03d" % (o - 0xDC00))
        elif o < 32 or o == 127:
            out.append("\\%03d" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def long_string(s):
    level = 0
    while True:
        close = "]" + "=" * level + "]"
        if (s + close).find(close) == len(s):
            return "[" + "=" * level + "[\n" + s + close
        level += 1


def _string(s, pretty):
    if pretty and "\n" in s and not any(
        (ord(c) < 32 and c not in "\n\t") or 0xDC80 <= ord(c) <= 0xDCFF for c in s
    ):
        return long_string(s)
    return quote(s)


def scalar(v, pretty=False):
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "nil"
    if isinstance(v, (int, float)):
        return format_number(v)
    if isinstance(v, str):
        return _string(v, pretty)
    raise TypeError("no Lua literal for %s" % type(v).__name__)


def as_dict(t):
    if isinstance(t, (list, tuple)):
        return {i + 1: v for i, v in enumerate(t) if v is not None}
    return t


def split_table(t):
    """(array values 1..n, remaining (key, value) pairs in a stable order)."""
    t = as_dict(t)
    # type() is int, not isinstance: True == 1 in Python, but [true] is no array slot in Lua.
    ints = {k: v for k, v in t.items() if type(k) is int}
    n = 0
    while ints.get(n + 1) is not None:
        n += 1
    array = [ints[i] for i in range(1, n + 1)]

    def rank(k):
        if isinstance(k, bool):
            return (2, str(k), 0)
        if isinstance(k, (int, float)):
            return (0, "", k)
        return (1, str(k), 0)

    rest = sorted(
        ((k, v) for k, v in t.items() if v is not None and not (type(k) is int and 1 <= k <= n)),
        key=lambda kv: rank(kv[0]),
    )
    return array, rest


def _key(k, sv):
    if isinstance(k, str) and not sv and _NAME.fullmatch(k) and k not in KEYWORDS:
        return k
    return "[" + scalar(k) + "]"


def dump(value, indent="  ", level=0, order=None):
    """Pretty, stable Lua literal. `order` puts those keys first at this level."""
    if not isinstance(value, (dict, list, tuple)):
        return scalar(value, pretty=True)
    array, rest = split_table(value)
    if not array and not rest:
        return "{}"
    if order:
        rest.sort(key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order))
    if not rest and all(not isinstance(v, (dict, list, tuple)) and not (
            isinstance(v, str) and "\n" in v) for v in array):
        inline = "{" + ", ".join(scalar(v) for v in array) + "}"
        if len(inline) + len(indent) * level <= 100:
            return inline
    pad = indent * (level + 1)
    lines = ["{"]
    for v in array:
        lines.append(pad + dump(v, indent, level + 1) + ",")
    for k, v in rest:
        lines.append(pad + _key(k, False) + " = " + dump(v, indent, level + 1) + ",")
    lines.append(indent * level + "}")
    return "\n".join(lines)


def _dump_sv(value, indent, level, out):
    if not isinstance(value, (dict, list, tuple)):
        return scalar(value)
    array, rest = split_table(value)
    pad = indent * (level + 1)
    parts = ["{"]
    for v in array:
        parts.append(pad + _dump_sv(v, indent, level + 1, out) + ",")
    for k, v in rest:
        parts.append(pad + _key(k, True) + " = " + _dump_sv(v, indent, level + 1, out) + ",")
    parts.append(indent * level + "}")
    return out.join(parts)


def dump_sv(assignments, indent="", newline="\r\n"):
    """SavedVariables file text: each global preceded by a newline, as the client writes it."""
    chunks = []
    for name, value in assignments:
        chunks.append(newline + name + " = " + _dump_sv(value, indent, 0, newline) + newline)
    return "".join(chunks)
