import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import lualit  # noqa: E402


class Parse(unittest.TestCase):
    def test_scalars(self):
        cases = {
            "1": 1, "-1": -1, "1.5": 1.5, "-0.25": -0.25, ".5": 0.5, "1e3": 1000, "2.5e-3": 0.0025,
            "0x10": 16, "-0xFF": -255, "true": True, "false": False, "nil": None, "4.0": 4,
        }
        for text, want in cases.items():
            got = lualit.parse(text)
            self.assertEqual(got, want, text)
            self.assertIs(type(got), type(want), text)

    def test_escapes(self):
        self.assertEqual(lualit.parse(r'"a\n\"\\\065\t\0x"'), 'a\n"\\A\t\x00x')
        self.assertEqual(lualit.parse(r"'it\'s'"), "it's")
        self.assertEqual(lualit.parse('"line\\\nnext"'), "line\nnext")
        self.assertEqual(lualit.parse(r'"\0659"'), "A9")

    def test_non_utf8_escape(self):
        s = lualit.parse(r'"\255"')
        self.assertEqual(s.encode("utf-8", "surrogateescape"), b"\xff")

    def test_long_strings(self):
        self.assertEqual(lualit.parse("[[\nabc]]"), "abc")
        self.assertEqual(lualit.parse("[[abc\r\ndef]]"), "abc\ndef")
        self.assertEqual(lualit.parse("[==[a]]b]=]c]==]"), "a]]b]=]c")
        self.assertEqual(lualit.parse("[=[\n\nx]=]"), "\nx")

    def test_comments(self):
        text = "-- head\nreturn { --[[ block ]] a = 1, --[==[ x ]] ]==] b = 2 -- tail\n}"
        self.assertEqual(lualit.parse(text), {"a": 1, "b": 2})

    def test_tables(self):
        t = lualit.parse('{ 1, "two", nil, 4; x = {}, ["y z"] = true, [10] = 10, [-1] = "n", [1.5] = "f" }')
        self.assertEqual(t, {1: 1, 2: "two", 4: 4, "x": {}, "y z": True, 10: 10, -1: "n", 1.5: "f"})

    def test_keyword_values_not_keys(self):
        self.assertEqual(lualit.parse("{ true, false }"), {1: True, 2: False})

    def test_errors(self):
        for bad in ["{ a = b }", "{ 1 + 2 }", "{ a = 1", '"open', "return {} extra", "1x", "{ [nil] = 1 }"]:
            with self.assertRaises(lualit.LuaSyntaxError, msg=bad):
                lualit.parse(bad)

    def test_assignments(self):
        got = lualit.parse_assignments('\r\nA = {\r\n["k"] = 1,\r\n}\r\nB = nil\r\nC = "x"\r\n')
        self.assertEqual(got, [("A", {"k": 1}), ("B", None), ("C", "x")])


class Write(unittest.TestCase):
    SAMPLE = {
        "id": "My Aura",
        "list": {1: "a", 2: "b"},
        "code": "function()\n  return \"]]\" .. [[x]]\nend",
        "ctrl": "bell\x07 tab\t cr\r",
        "bytes": b"\xff\xfe".decode("utf-8", "surrogateescape"),
        "and": 1,
        "nested": {"deep": {1: {"x": -1.25}}},
        "holes": {1: 1, 3: 3},
        "num": {2: "two", 1.5: "f", -3: "neg"},
        "flags": {True: "t", False: "f"},
        "cjk": "汉字",
        "empty": {},
    }

    def test_pretty_roundtrip(self):
        text = lualit.dump(self.SAMPLE)
        self.assertEqual(lualit.parse(text), self.SAMPLE)
        self.assertIn('["and"] = 1', text)  # keyword key is bracketed
        self.assertIn("code = [=[\nfunction()", text)  # code with ]] in a level-1 long bracket
        self.assertIn('list = {"a", "b"}', text)

    def test_pretty_is_stable(self):
        reordered = dict(reversed(list(self.SAMPLE.items())))
        self.assertEqual(lualit.dump(reordered), lualit.dump(self.SAMPLE))

    def test_long_string_levels(self):
        for s in ["]]", "a]=]b]]", "ends with ]", "ends with ]=", "\nleading newline"]:
            self.assertEqual(lualit.parse(lualit.long_string(s)), s)

    def test_quote_roundtrip(self):
        s = "".join(chr(i) for i in range(128)) + "é" + b"\x80".decode("utf-8", "surrogateescape")
        self.assertEqual(lualit.parse(lualit.quote(s)), s)

    def test_sv_layout(self):
        text = lualit.dump_sv([("X", {"b": {1: "s", 2: 2}, "a": {}})])
        self.assertEqual(text, '\r\nX = {\r\n["a"] = {\r\n},\r\n["b"] = {\r\n"s",\r\n2,\r\n},\r\n}\r\n')

    def test_sv_roundtrip(self):
        text = lualit.dump_sv([("S", self.SAMPLE), ("T", 5)], indent="\t")
        self.assertEqual(lualit.parse_assignments(text), [("S", self.SAMPLE), ("T", 5)])


if __name__ == "__main__":
    unittest.main()
