"""Port of LibSerialize (MINOR 1) as shipped in ForeverAuras 1.4.3.

Lua values map to Python as: nil -> None, boolean -> bool, number -> int or
float (whole floats are written as integers, as Lua does), string -> str
(bytes that are not UTF-8 survive through 'surrogateescape'), table -> dict.
A list is accepted on the write side and written as an array. Deserialized
tables are always dicts with int keys for the array part.

Limit: a Python dict cannot hold both the key True and the key 1 (they hash
equal); Lua tables can. Aura data never does this.
"""

import math
import struct

VERSION = 1

# _EmbeddedIndex
E_STRING, E_TABLE, E_ARRAY, E_MIXED = 0, 1, 2, 3

# _ReaderIndex
NIL = 0
NUM_16_POS, NUM_16_NEG, NUM_24_POS, NUM_24_NEG = 1, 2, 3, 4
NUM_32_POS, NUM_32_NEG, NUM_64_POS, NUM_64_NEG = 5, 6, 7, 8
NUM_FLOAT, NUM_FLOATSTR_POS, NUM_FLOATSTR_NEG = 9, 10, 11
BOOL_T, BOOL_F = 12, 13
STR_8, STR_16, STR_24 = 14, 15, 16
TABLE_8, TABLE_16, TABLE_24 = 17, 18, 19
ARRAY_8, ARRAY_16, ARRAY_24 = 20, 21, 22
MIXED_8, MIXED_16, MIXED_24 = 23, 24, 25
STRINGREF_8, STRINGREF_16, STRINGREF_24 = 26, 27, 28
TABLEREF_8, TABLEREF_16, TABLEREF_24 = 29, 30, 31

_NUMBER_INDEX = {2: NUM_16_POS, 3: NUM_24_POS, 4: NUM_32_POS, 7: NUM_64_POS}


def to_bytes(s):
    return s.encode("utf-8", "surrogateescape")


def from_bytes(b):
    return b.decode("utf-8", "surrogateescape")


def _required_bytes(n):
    if n < 256:
        return 1
    if n < 65536:
        return 2
    if n < 16777216:
        return 3
    raise ValueError("Object limit exceeded")


def _required_bytes_number(n):
    if n < 256:
        return 1
    if n < 65536:
        return 2
    if n < 16777216:
        return 3
    if n < 4294967296:
        return 4
    return 7


def _int_bytes(n, required):
    if required == 7:
        return (n % (1 << 56)).to_bytes(7, "big")
    return n.to_bytes(required, "big")


def lua_tostring_number(x):
    """Lua 5.1 tostring() of a number (LUAI_NUMFFORMAT "%.14g")."""
    return "%.14g" % x


def _float_to_bytes(n):
    # IEEE big-endian, except that LibSerialize writes subnormals as signed zero.
    if math.isnan(n):
        return bytes([0xFF, 0xF8, 0, 0, 0, 0, 0, 0])
    if n != 0 and abs(n) < 2.0**-1022:
        return bytes([0x80 if n < 0 else 0, 0, 0, 0, 0, 0, 0, 0])
    return struct.pack(">d", n)


def _bytes_to_float(b):
    # Mirrors StringToFloat: exponent 0 with a mantissa is read as a normal number.
    sign = -1.0 if b[0] > 0x7F else 1.0
    expo = (b[0] % 0x80) * 0x10 + b[1] // 0x10
    mant = int.from_bytes(bytes([b[1] % 0x10]) + b[2:8], "big")
    if mant == 0 and expo == 0:
        return sign * 0.0
    if expo == 0x7FF:
        return sign * math.inf if mant == 0 else math.nan
    return sign * math.ldexp(1.0 + mant / 4503599627370496.0, expo - 0x3FF)


def _is_fractional(x):
    return isinstance(x, float) and x != math.floor(x)


def _items(tab):
    if isinstance(tab, (list, tuple)):
        return [(i + 1, v) for i, v in enumerate(tab) if v is not None]
    return [(k, v) for k, v in tab.items() if v is not None and k is not None]


class _Writer:
    def __init__(self):
        self.out = bytearray()
        self.strings = {}
        self.tables = {}
        self.keep = []  # keeps ids of written tables valid

    def byte(self, b):
        self.out.append(b)

    def int(self, n, required):
        self.out += _int_bytes(n, required)

    def write(self, obj):
        if obj is None:
            self.byte(8 * NIL)
        elif isinstance(obj, bool):
            self.byte(8 * (BOOL_T if obj else BOOL_F))
        elif isinstance(obj, (int, float)):
            self.number(obj)
        elif isinstance(obj, str):
            self.string(to_bytes(obj))
        elif isinstance(obj, bytes):
            self.string(obj)
        elif isinstance(obj, (dict, list, tuple)):
            self.table(obj)
        else:
            raise TypeError("cannot serialize %s" % type(obj).__name__)

    def number(self, num):
        if isinstance(num, float):
            if math.isinf(num) or math.isnan(num):
                raise ValueError("LibSerialize cannot write inf or nan")
            if not _is_fractional(num):
                num = int(num)
        if isinstance(num, float):
            sign, absn = (8, -num) if num < 0 else (0, num)
            s = lua_tostring_number(absn)
            if len(s) < 7 and float(s) == absn:
                self.byte(sign + 8 * NUM_FLOATSTR_POS)
                self.byte(len(s))
                self.out += s.encode("ascii")
            else:
                self.byte(8 * NUM_FLOAT)
                self.out += _float_to_bytes(num)
        elif abs(num) >= 1 << 56:
            # LibSerialize writes whole numbers in at most 7 bytes and silently wraps larger ones.
            raise ValueError("whole number %r is beyond LibSerialize's 7-byte limit" % num)
        elif -4096 < num < 4096:
            if 0 <= num < 128:
                self.byte(num * 2 + 1)
            else:
                sign = 0
                if num < 0:
                    sign, num = 8, -num
                num = num * 16 + sign + 4
                self.byte(num % 256)
                self.byte(num // 256)
        else:
            sign = 0
            if num < 0:
                sign, num = 8, -num
            required = _required_bytes_number(num)
            self.byte(sign + 8 * _NUMBER_INDEX[required])
            self.int(num, required)

    def string(self, b):
        ref = self.strings.get(b)
        if ref:
            req = _required_bytes(ref)
            self.byte(8 * (STRINGREF_8 + req - 1))
            self.int(ref, req)
            return
        n = len(b)
        if n < 16:
            self.byte(16 * n + 4 * E_STRING + 2)
        else:
            req = _required_bytes(n)
            self.byte(8 * (STR_8 + req - 1))
            self.int(n, req)
        self.out += b
        if n > 2:
            self.strings[b] = len(self.strings) + 1

    def table(self, tab):
        ref = self.tables.get(id(tab))
        if ref:
            req = _required_bytes(ref)
            self.byte(8 * (TABLEREF_8 + req - 1))
            self.int(ref, req)
            return
        self.keep.append(tab)
        self.tables[id(tab)] = len(self.tables) + 1

        items = _items(tab)
        # type() is int, not isinstance: True == 1 in Python, but [true] is no array slot in Lua.
        lookup = {k: v for k, v in items if type(k) is int}
        array_count = 0
        while (array_count + 1) in lookup:
            array_count += 1

        def is_array_key(k):
            return type(k) in (int, float) and 1 <= k <= array_count and not _is_fractional(k)

        rest = [(k, v) for k, v in items if not is_array_key(k)]
        map_count = len(rest)
        if map_count == 0:
            if array_count < 16:
                self.byte(16 * array_count + 4 * E_ARRAY + 2)
            else:
                req = _required_bytes(array_count)
                self.byte(8 * (ARRAY_8 + req - 1))
                self.int(array_count, req)
        elif array_count:
            if map_count < 5 and array_count < 5:
                combined = (map_count - 1) * 4 + array_count - 1
                self.byte(16 * combined + 4 * E_MIXED + 2)
            else:
                req = max(_required_bytes(map_count), _required_bytes(array_count))
                self.byte(8 * (MIXED_8 + req - 1))
                self.int(array_count, req)
                self.int(map_count, req)
        else:
            if map_count < 16:
                self.byte(16 * map_count + 4 * E_TABLE + 2)
            else:
                req = _required_bytes(map_count)
                self.byte(8 * (TABLE_8 + req - 1))
                self.int(map_count, req)
        for i in range(1, array_count + 1):
            self.write(lookup[i])
        for k, v in rest:
            self.write(k)
            self.write(v)


def serialize(*values):
    """LibSerialize:SerializeEx(opts, ...) -> bytes."""
    w = _Writer()
    w.byte(VERSION)
    for v in values:
        w.write(v)
    return bytes(w.out)


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.strings = []
        self.tables = []

    def take(self, n):
        if self.pos + n > len(self.data):
            raise ValueError("Reader went past end of input")
        b = self.data[self.pos : self.pos + n]
        self.pos += n
        return b

    def byte(self):
        return self.take(1)[0]

    def int(self, n):
        return int.from_bytes(self.take(n), "big")

    def read(self):
        value = self.byte()
        if value % 2 == 1:
            return (value - 1) // 2
        if value % 4 == 2:
            typ = (value - 2) // 4
            count, typ = typ // 4, typ % 4
            if typ == E_STRING:
                return self.string(count)
            if typ == E_TABLE:
                return self.table(count)
            if typ == E_ARRAY:
                return self.array(count)
            return self.mixed(count % 4 + 1, count // 4 + 1)
        if value % 8 == 4:
            packed = self.byte() * 256 + value
            if value % 16 == 12:
                return -(packed - 12) // 16
            return (packed - 4) // 16
        typ = value // 8
        return self.typed(typ)

    def typed(self, typ):
        if typ == NIL:
            return None
        if NUM_16_POS <= typ <= NUM_64_NEG:
            size = {0: 2, 1: 3, 2: 4, 3: 7}[(typ - 1) // 2]
            n = self.int(size)
            return -n if typ % 2 == 0 else n
        if typ == NUM_FLOAT:
            return _bytes_to_float(self.take(8))
        if typ in (NUM_FLOATSTR_POS, NUM_FLOATSTR_NEG):
            s = self.take(self.byte()).decode("ascii")
            x = float(s)
            if x == math.floor(x) and abs(x) < 2**63:
                x = int(x)
            return -x if typ == NUM_FLOATSTR_NEG else x
        if typ == BOOL_T:
            return True
        if typ == BOOL_F:
            return False
        if STR_8 <= typ <= STR_24:
            return self.string(self.int(typ - STR_8 + 1))
        if TABLE_8 <= typ <= TABLE_24:
            return self.table(self.int(typ - TABLE_8 + 1))
        if ARRAY_8 <= typ <= ARRAY_24:
            return self.array(self.int(typ - ARRAY_8 + 1))
        if MIXED_8 <= typ <= MIXED_24:
            n = typ - MIXED_8 + 1
            a = self.int(n)
            return self.mixed(a, self.int(n))
        if STRINGREF_8 <= typ <= STRINGREF_24:
            return self.strings[self.int(typ - STRINGREF_8 + 1) - 1]
        if TABLEREF_8 <= typ <= TABLEREF_24:
            return self.tables[self.int(typ - TABLEREF_8 + 1) - 1]
        raise ValueError("unknown type index %d" % typ)

    def string(self, n):
        s = from_bytes(self.take(n))
        if n > 2:
            self.strings.append(s)
        return s

    def _new(self):
        t = {}
        self.tables.append(t)
        return t

    def table(self, count, t=None):
        if t is None:
            t = self._new()
        for _ in range(count):
            k = self.read()
            v = self.read()
            if isinstance(k, float) and k == math.floor(k):
                k = int(k)
            if k is not None and v is not None:
                t[k] = v
        return t

    def array(self, count, t=None):
        if t is None:
            t = self._new()
        for i in range(1, count + 1):
            v = self.read()
            if v is not None:
                t[i] = v
        return t

    def mixed(self, array_count, map_count):
        t = self._new()
        self.array(array_count, t)
        self.table(map_count, t)
        return t


def deserialize(data):
    """LibSerialize:DeserializeValue(data) -> list of values."""
    r = _Reader(bytes(data))
    version = r.byte()
    if version != VERSION:
        raise ValueError("LibSerialize version byte %d, expected %d" % (version, VERSION))
    out = []
    while r.pos < len(r.data):
        out.append(r.read())
    return out
