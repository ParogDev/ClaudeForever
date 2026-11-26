import contextlib
import copy
import io
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

import fa  # noqa: E402
import lint  # noqa: E402
import lualit  # noqa: E402
import savedvars  # noqa: E402
import transmission  # noqa: E402

EXAMPLE = os.path.join(HERE, "fixtures", "example_group.lua")

# The client's own layout: CRLF, a newline before each global, no indentation.
SV_TEXT = (
    "\r\nForeverAurasSaved = {\r\n"
    '["displays"] = {\r\n'
    '["Old Group"] = {\r\n["id"] = "Old Group",\r\n["regionType"] = "group",\r\n["uid"] = "oldGroupUid",\r\n'
    '["controlledChildren"] = {\r\n"Old A",\r\n"Old B",\r\n},\r\n},\r\n'
    '["Old A"] = {\r\n["id"] = "Old A",\r\n["parent"] = "Old Group",\r\n["regionType"] = "icon",\r\n},\r\n'
    '["Old B"] = {\r\n["id"] = "Old B",\r\n["parent"] = "Old Group",\r\n["regionType"] = "text",\r\n},\r\n'
    '["Loose"] = {\r\n["id"] = "Loose",\r\n["regionType"] = "icon",\r\n["uid"] = "abcDEF01234",\r\n},\r\n'
    "},\r\n"
    '["dbVersion"] = 91,\r\n'
    "}\r\n"
    "\r\nForeverAurasOther = nil\r\n"
)


def read(path, binary=False):
    if binary:
        with open(path, "rb") as f:
            return f.read()
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fa.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Transmission(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        src = transmission.read_src(EXAMPLE)
        payload = transmission.build_payload(src, "1.4.3")
        self.assertEqual(payload["v"], 1421)
        self.assertEqual(payload["m"], "d")
        text = transmission.encode_payload(payload)
        self.assertTrue(text.startswith("!WA:2!"))
        back = transmission.decode_string("  " + text + "\n")
        self.assertEqual(back["s"], "1.4.3")
        self.assertEqual(transmission.payload_to_src(back), {"d": src["d"], "c": transmission.children_of(src)})

    def test_fa_prefix_accepted(self):
        text = transmission.encode_payload({"m": "d", "d": {"id": "x"}, "v": 1421, "s": "1"})
        self.assertEqual(transmission.decode_string("!FA:2!" + text[6:])["d"], {"id": "x"})

    def test_decode_errors_name_the_step(self):
        for bad, word in [("hello", "prefix"), ("!WA:1!abc", "AceSerializer"), ("!WA:2!ab!c", "print"),
                          ("!WA:2!aaaaaaaa", "decompress")]:
            with self.assertRaises(ValueError) as cm:
                transmission.decode_string(bad)
            self.assertIn(word, str(cm.exception))

    def test_nested_groups_use_2000(self):
        src = {"d": {"id": "g"}, "c": [{"id": "sub", "controlledChildren": ["leaf"], "parent": "g"},
                                       {"id": "leaf", "parent": "sub"}]}
        self.assertEqual(transmission.build_payload(src, "x")["v"], 2000)


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.sv = os.path.join(self.dir, "ForeverAuras.lua")
        with open(self.sv, "wb") as f:
            f.write(SV_TEXT.encode())

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_encode_then_decode_files(self):
        code, _, _ = run("encode", EXAMPLE, "-o", self.path("x.txt"), "--version", "1.4.3")
        self.assertEqual(code, 0)
        code, _, _ = run("decode", self.path("x.txt"), "-o", self.path("x.lua"))
        self.assertEqual(code, 0)
        decoded = read(self.path("x.lua"))
        self.assertIn("v=1421 s=1.4.3", decoded)
        self.assertEqual(transmission.read_src(self.path("x.lua")), lualit.parse(read(EXAMPLE)))
        # decode output is stable: decoding its own re-encode gives the same text
        run("encode", self.path("x.lua"), "-o", self.path("y.txt"), "--version", "1.4.3")
        run("decode", self.path("y.txt"), "-o", self.path("y.lua"))
        self.assertEqual(read(self.path("y.lua")), decoded)

    def test_encode_fills_internal_version(self):
        with open(self.path("s.lua"), "w") as f:
            f.write('return { d = { id = "solo", regionType = "icon" } }')
        code, out, err = run("encode", self.path("s.lua"), "--fa-dir", self.dir)
        self.assertEqual(code, 0)
        self.assertIn("internalVersion", err)
        self.assertEqual(transmission.decode_string(out)["d"]["internalVersion"], 91)

    def test_pull_lists_groups(self):
        code, out, _ = run("pull", "--sv", self.sv)
        self.assertEqual(code, 0)
        self.assertIn("Old Group (2 children)", out)

    def test_pull_group(self):
        code, _, _ = run("pull", "--sv", self.sv, "--group", "Old Group", "-o", self.path("p.lua"))
        self.assertEqual(code, 0)
        src = transmission.read_src(self.path("p.lua"))
        self.assertEqual(src["d"]["id"], "Old Group")
        self.assertEqual([c["id"] for c in transmission.children_of(src)], ["Old A", "Old B"])

    def test_pull_missing_group(self):
        code, _, err = run("pull", "--sv", self.sv, "--group", "Nope")
        self.assertEqual(code, 1)
        self.assertIn("Nope", err)

    def test_install_dry_run(self):
        out_path = self.path("merged.lua")
        code, out, _ = run("install", EXAMPLE, "--sv", self.sv, "--dry-run", out_path)
        self.assertEqual(code, 0)
        self.assertEqual(read(self.sv, True), SV_TEXT.encode())  # untouched
        merged = savedvars.SvFile(out_path)
        self.assertEqual(merged.newline, "\r\n")
        displays = merged.saved()["displays"]
        group = displays["FA Example"]
        self.assertEqual(lualit.split_table(group["controlledChildren"])[0],
                         ["FA Example: Slice and Dice", "FA Example: Energy"])
        for cid in group["controlledChildren"].values():
            self.assertEqual(displays[cid]["parent"], "FA Example")
            self.assertEqual(displays[cid]["internalVersion"], 91)
            self.assertEqual(len(displays[cid]["uid"]), 11)
        # the group's uid clashed with "Loose", so it got a new one
        self.assertNotEqual(group["uid"], "abcDEF01234")
        self.assertIn("is used by another display", out)
        self.assertIn("Old Group", displays)
        self.assertIsNone(merged.get("ForeverAurasOther"))
        self.assertIn("\r\nForeverAurasOther = nil\r\n", read(out_path))
        self.assertNotIn("\n", read(out_path).replace("\r\n", "\r"))  # no bare LF anywhere

    def test_install_replaces_and_drops_removed_children(self):
        run("pull", "--sv", self.sv, "--group", "Old Group", "-o", self.path("p.lua"))
        src = transmission.read_src(self.path("p.lua"))
        src["c"] = [transmission.children_of(src)[0]]
        with open(self.path("p.lua"), "w", encoding="utf-8") as f:
            f.write(transmission.write_src(src))
        with mock.patch.object(savedvars, "game_running", return_value=False):
            code, out, _ = run("install", self.path("p.lua"), "--sv", self.sv)
        self.assertEqual(code, 0)
        self.assertIn("removed 'Old B'", out)
        backups = [n for n in os.listdir(self.dir) if ".fa-backup-" in n]
        self.assertEqual(len(backups), 1)
        self.assertEqual(read(os.path.join(self.dir, backups[0]), True), SV_TEXT.encode())
        displays = savedvars.SvFile(self.sv).saved()["displays"]
        self.assertNotIn("Old B", displays)
        self.assertEqual(displays["Old Group"]["controlledChildren"], {1: "Old A"})
        self.assertEqual(displays["Old Group"]["uid"], "oldGroupUid")

    def test_pull_install_roundtrip_is_identity(self):
        run("pull", "--sv", self.sv, "--group", "Old Group", "-o", self.path("p.lua"))
        src = transmission.read_src(self.path("p.lua"))
        sv = savedvars.SvFile(self.sv)
        before = copy.deepcopy(sv.saved())
        for aura in [before["displays"][k] for k in ("Old Group", "Old A", "Old B")]:
            aura.setdefault("internalVersion", 91)
        savedvars.merge(sv.saved(), src["d"], transmission.children_of(src), 91, random.Random(0))
        after = sv.saved()
        for k in ("Old A", "Old B"):
            self.assertEqual(len(after["displays"][k].pop("uid")), 11)
        self.assertEqual(after, before)

    def test_install_refuses_while_game_runs(self):
        with mock.patch.object(savedvars, "game_running", return_value=True):
            code, _, err = run("install", EXAMPLE, "--sv", self.sv)
        self.assertEqual(code, 2)
        self.assertIn("Wow.exe is running", err)
        self.assertEqual(read(self.sv, True), SV_TEXT.encode())


@unittest.skipUnless(os.path.isfile(os.path.join(transmission.default_fa_dir(), "Prototypes.lua")),
                     "ForeverAuras is not installed here")
class Lint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = lint.FaIndex(transmission.default_fa_dir())

    def test_index(self):
        self.assertIn("icon", self.index.region_types)
        self.assertIn("dynamicgroup", self.index.region_types)
        self.assertEqual(self.index.events.get("Power"), "unit")
        self.assertEqual(self.index.events.get("Blizzard CDM Buff"), "cdm")
        self.assertIn("secretAura", self.index.trigger_types)

    @staticmethod
    def _at_installed_version(src):
        # The fixture is written at internalVersion 91; ForeverAuras updates move that number, and a mismatch is
        # (rightly) a lint error. Lint the example as if written for the installed addon.
        iv = transmission.internal_version(transmission.default_fa_dir())
        for aura in [src["d"]] + transmission.children_of(src):
            aura["internalVersion"] = iv
        return src

    def test_example_is_clean(self):
        errors, _, notes = lint.lint(self._at_installed_version(transmission.read_src(EXAMPLE)), self.index)
        self.assertEqual(errors, [])
        self.assertTrue(any("custom code" in n for n in notes))

    def test_finds_errors(self):
        src = transmission.read_src(EXAMPLE)
        kids = transmission.children_of(src)
        kids[0]["regionType"] = "sparkle"
        kids[0]["conditions"][1]["check"]["trigger"] = 3
        kids[1]["triggers"][1]["trigger"]["event"] = "Health Points"
        kids[1]["parent"] = "Elsewhere"
        kids[1]["internalVersion"] = 80
        kids.append({"id": "FA Example", "regionType": "icon", "internalVersion": 91,
                     "triggers": {1: {"trigger": {"type": "spell"}}}})
        src["c"] = kids
        errors, _, _ = lint.lint(src, self.index)
        text = "\n".join(errors)
        for needle in ["'sparkle'", "uses trigger 3", "'Health Points' is not an event", "parent 'Elsewhere'",
                       "internalVersion is 80", "also used by d", "needs an event"]:
            self.assertIn(needle, text)

    def test_cli_exit_code(self):
        src = self._at_installed_version(transmission.read_src(EXAMPLE))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "example.lua")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(transmission.write_src(src))
            code, out, _ = run("lint", path)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
