import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import luaser  # noqa: E402


def roundtrip(v):
    return luaser.deserialize(luaser.serialize(v))[0]


class Bytes(unittest.TestCase):
    """Exact encodings, worked out by hand from LibSerialize.lua."""

    def test_embedded_7bit(self):
        self.assertEqual(luaser.serialize(5), b"\x01\x0b")

    def test_embedded_12bit_negative(self):
        self.assertEqual(luaser.serialize(-5), b"\x01\x5c\x00")

    def test_short_string(self):
        self.assertEqual(luaser.serialize("abc"), b"\x01\x32abc")

    def test_string_ref_only_above_two_bytes(self):
        self.assertEqual(luaser.serialize(["abc", "abc"]), b"\x01\x2a\x32abc\xd0\x01")
        self.assertEqual(luaser.serialize(["ab", "ab"]), b"\x01\x2a\x22ab\x22ab")

    def test_float_as_string(self):
        self.assertEqual(luaser.serialize(0.5), b"\x01\x50\x030.5")
        self.assertEqual(luaser.serialize(-0.5), b"\x01\x58\x030.5")

    def test_float_8_bytes(self):
        self.assertEqual(luaser.serialize(1 / 3)[1], 72)
        self.assertEqual(len(luaser.serialize(1 / 3)), 10)

    def test_big_ints(self):
        self.assertEqual(luaser.serialize(70000), b"\x01\x18\x01\x11\x70")
        self.assertEqual(luaser.serialize(2**40)[1], 56)
        self.assertEqual(luaser.serialize(-(2**40))[1], 64)

    def test_mixed_embedded_counts(self):
        # 1 array value, 1 map pair: combined 0 -> 0*16 + 3*4 + 2
        self.assertEqual(luaser.serialize({1: True, "k": False}), b"\x01\x0e\x60\x12k\x68")

    def test_whole_float_written_as_int(self):
        self.assertEqual(luaser.serialize(3.0), luaser.serialize(3))


class RoundTrip(unittest.TestCase):
    def test_scalars(self):
        for v in [0, 1, 127, 128, 4095, 4096, -1, -4095, -4096, 65535, 65536, 2**24, 2**32,
                  2**53, -(2**53), True, False, "", "x", "héllo", "a" * 300, "b" * 70000]:
            self.assertEqual(roundtrip(v), v, v)

    def test_floats(self):
        for v in [0.5, -2.5, 0.1, 1 / 3, -1e-300, 123456.789, 7.62939453125e-06, 2.0**55 + 0.0]:
            self.assertEqual(roundtrip(v), v, v)

    def test_unwritable_numbers_refused(self):
        # inf and whole numbers past 7 bytes are corrupted by LibSerialize itself; refuse them.
        for v in [math.inf, math.nan, 1.5e300, 2**56]:
            with self.assertRaises(ValueError, msg=v):
                luaser.serialize(v)

    def test_true_key_is_not_array_slot(self):
        self.assertEqual(roundtrip({True: "t", 2: "x"}), {True: "t", 2: "x"})
        self.assertEqual(luaser.serialize({True: "t"})[1], 16 * 1 + 4 + 2)  # map, not array

    def test_nested_and_mixed(self):
        v = {
            "id": "Aura",
            "triggers": {1: {"trigger": {"type": "aura2", "auranames": {1: "A", 2: "B"}}}, "activeTriggerMode": -10},
            "color": {1: 1, 2: 0.5, 3: 0, 4: 1},
            "holes": {1: "a", 3: "c"},
            "keys": {2.5: "frac", -1: "neg", True: "t"},
            "big": {i: i * i for i in range(1, 300)},
            "map": {"k%d" % i: i for i in range(20)},
            "mix": dict([(i, i) for i in range(1, 8)] + [("x%d" % i, i) for i in range(6)]),
        }
        self.assertEqual(roundtrip(v), v)

    def test_list_input(self):
        self.assertEqual(roundtrip([1, "two", [3]]), {1: 1, 2: "two", 3: {1: 3}})

    def test_repeated_strings(self):
        v = {i: "repeated value" for i in range(1, 400)}
        raw = luaser.serialize(v)
        self.assertLess(len(raw), 400 * 4)
        self.assertEqual(luaser.deserialize(raw)[0], v)

    def test_repeated_tables_keep_identity(self):
        shared = {"x": 1}
        out = roundtrip({"a": shared, "b": shared})
        self.assertEqual(out["a"], {"x": 1})
        self.assertIs(out["a"], out["b"])

    def test_self_reference(self):
        t = {"name": "loop"}
        t["self"] = t
        out = roundtrip(t)
        self.assertIs(out["self"], out)

    def test_many_values(self):
        self.assertEqual(luaser.deserialize(luaser.serialize(1, None, "x")), [1, None, "x"])

    def test_non_utf8_bytes(self):
        s = b"\xff\xfeok".decode("utf-8", "surrogateescape")
        self.assertEqual(roundtrip(s), s)

    def test_truncated_input(self):
        with self.assertRaises(ValueError):
            luaser.deserialize(luaser.serialize("abcdef")[:-2])


if __name__ == "__main__":
    unittest.main()
