"""LibDeflate pieces ForeverAuras uses for chat strings.

CompressDeflate is raw DEFLATE (no zlib header), so zlib with wbits=-15 reads
and writes the same streams. EncodeForPrint/DecodeForPrint are the 6-bit
printable codec ("a-zA-Z0-9()"), little-endian within each 3-byte group.
"""

import zlib

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789()"
_INDEX = {c: i for i, c in enumerate(ALPHABET)}


def compress_deflate(data, level=9):
    c = zlib.compressobj(level, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def decompress_deflate(data):
    return zlib.decompress(data, -15)


def encode_for_print(data):
    out = []
    n = len(data)
    i = 0
    while i <= n - 3:
        cache = data[i] + data[i + 1] * 256 + data[i + 2] * 65536
        i += 3
        for _ in range(4):
            out.append(ALPHABET[cache % 64])
            cache //= 64
    cache, bits = 0, 0
    while i < n:
        cache += data[i] << bits
        bits += 8
        i += 1
    while bits > 0:
        out.append(ALPHABET[cache % 64])
        cache //= 64
        bits -= 6
    return "".join(out)


def decode_for_print(text):
    """Returns bytes, or None for a string EncodeForPrint cannot produce (as LibDeflate)."""
    text = text.strip(" \t\r\n\v\f\0")
    if len(text) == 1:
        return None
    out = bytearray()
    n = len(text)
    i = 0
    try:
        while i <= n - 4:
            cache = 0
            for j in range(4):
                cache += _INDEX[text[i + j]] << (6 * j)
            i += 4
            out += bytes([cache % 256, (cache >> 8) % 256, cache >> 16])
        cache, bits = 0, 0
        while i < n:
            cache += _INDEX[text[i]] << bits
            bits += 6
            i += 1
    except KeyError:
        return None
    while bits >= 8:
        out.append(cache % 256)
        cache >>= 8
        bits -= 8
    return bytes(out)
