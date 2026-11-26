"""Tests for tools/wowf_sv.py and the read-back half of tools/reload-wait.ps1. Stdlib only:

    python -I -m pytest tools/tests -q        (or: python -m unittest discover -s tools/tests)

The fixture is a made-up SavedVariables file (addon "MyAddon") with the shapes the client writes:
nested tables, paths with backslashes and slashes as keys, UTF-8 chat text, escapes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import wowf_sv  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "selftest_logout.lua")
SCRIPT = os.path.join(TOOLS, "wowf_sv.py")
FONT_BS = "Interface\\AddOns\\MyAddon\\Fonts\\Example-Regular.ttf"
FONT_FS = "Interface/AddOns/MyAddon/Fonts/Example-Regular.ttf"


def run_cli(*args):
    p = subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def first_json(text):
    """The JSON object reload-wait prints; Write-Host lines may follow it on stdout."""
    return json.JSONDecoder().raw_decode(text[text.index("{") :])[0]


class ParseFixture(unittest.TestCase):
    def setUp(self):
        self.db = wowf_sv.parse_file(FIXTURE)["MyAddonDB"]

    def test_selftest_present(self):
        st = self.db["selftest"]
        self.assertEqual(st["phase"], "logout")
        self.assertEqual(st["interface"], 16001)
        self.assertEqual(st["counters"], {"events": 7, "secret": 0})

    def test_path_keys_with_backslashes_and_slashes(self):
        fp = self.db["selftest"]["fontProbe"]
        self.assertEqual(fp["path"], "Fonts\\ARKai_T.ttf")
        self.assertIs(fp["tried"][FONT_BS], False)
        self.assertIs(fp["tried"][FONT_FS], False)
        self.assertEqual(fp["detail"][FONT_BS], {"call": True, "got": "nil", "ret": "false"})
        self.assertEqual(fp["detail"][FONT_FS]["ret"], "false")

    def test_chat_text_and_escapes(self):
        lines = self.db["selftest"]["lastLines"]
        self.assertIn("集合石", lines[0]["text"])
        # \" and \\ escapes, and a backslash-newline (Lua's escaped line break) inside one string
        self.assertEqual(lines[1]["text"], 'say "hi" \\ then\nnext line')

    def test_sequence_and_empty_tables(self):
        self.assertIsInstance(self.db["selftest"]["lastLines"], list)
        self.assertEqual(self.db["channels"], {})


class Escapes(unittest.TestCase):
    def test_decimal_escapes_are_bytes(self):
        data = wowf_sv._Parser('X = { "\\228\\184\\173", "a\\65b", "\\0" }').file()
        self.assertEqual(data["X"], ["中", "aAb", "\x00"])

    def test_decimal_escape_above_255_does_not_parse(self):
        with self.assertRaises(ValueError):
            wowf_sv._Parser('X = { "\\300" }').file()

    def test_numbers(self):
        data = wowf_sv._Parser("X = { 007, -0x1F, 1.5, 2e3 }").file()
        self.assertEqual(data["X"], [7, -31, 1.5, 2000.0])


class Select(unittest.TestCase):
    def setUp(self):
        self.data = wowf_sv.parse_file(FIXTURE)

    def test_walks_var_and_path(self):
        self.assertEqual(wowf_sv.select(self.data, "MyAddonDB", "selftest.phase"), "logout")
        self.assertEqual(wowf_sv.select(self.data, "MyAddonDB", "selftest.lastLines.2.sender"), "Bob")

    def test_missing_var_names_what_is_there(self):
        with self.assertRaises(wowf_sv.Missing) as cm:
            wowf_sv.select(self.data, "OtherDB")
        self.assertIn("variable OtherDB not in file", str(cm.exception))
        self.assertIn("MyAddonDB", str(cm.exception))

    def test_missing_key_names_the_step(self):
        with self.assertRaises(wowf_sv.Missing) as cm:
            wowf_sv.select(self.data, "MyAddonDB", "selftest.nope")
        self.assertIn("MyAddonDB.selftest has no 'nope'", str(cm.exception))
        self.assertIn("phase", str(cm.exception))


class Cli(unittest.TestCase):
    def test_ascii_output_is_pure_ascii_and_round_trips(self):
        code, out, err = run_cli(FIXTURE, "--var", "MyAddonDB", "--path", "selftest", "--ascii")
        self.assertEqual(code, 0, err)
        out.decode("ascii")  # a wrong console code page can no longer eat a quote
        st = json.loads(out)
        self.assertEqual(st["phase"], "logout")
        self.assertIn("集合石", st["lastLines"][0]["text"])

    def test_missing_selftest_exit_3_with_reason(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sv.lua")
            with open(p, "w", encoding="utf-8") as f:
                f.write('MyAddonDB = {\n["dbVersion"] = 1,\n}\n')
            code, out, err = run_cli(p, "--var", "MyAddonDB", "--path", "selftest")
        self.assertEqual(code, 3)
        self.assertIn("MyAddonDB has no 'selftest'", err)

    def test_unreadable_file_exit_4(self):
        code, out, err = run_cli(os.path.join(HERE, "fixtures", "no-such-file.lua"))
        self.assertEqual(code, 4)
        self.assertIn("wowf_sv: cannot read", err)
        self.assertNotIn("Traceback", err)

    def test_infinity_exit_5(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sv.lua")
            with open(p, "w", encoding="utf-8") as f:
                f.write("X = { 1e999 }\n")
            code, out, err = run_cli(p, "--var", "X")
        self.assertEqual(code, 5)
        self.assertIn("wowf_sv: value JSON cannot hold", err)

    def test_truncated_file_exit_2(self):
        with open(FIXTURE, "rb") as f:
            half = f.read()[:900]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sv.lua")
            with open(p, "wb") as f:
                f.write(half)
            code, out, err = run_cli(p, "--var", "MyAddonDB")
        self.assertEqual(code, 2)
        self.assertIn("does not parse", err)


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "reload-wait.ps1 runs on Windows PowerShell 5.1")
class ReloadWaitReadBack(unittest.TestCase):
    """The script end to end, under a code page (936) that turned the JSON invalid before --ascii."""

    def run_ps(self, file):
        cmd = (
            "[Console]::OutputEncoding = [Text.Encoding]::GetEncoding(936); "
            f"& '{os.path.join(TOOLS, 'reload-wait.ps1')}' MyAddon -File '{file}'; exit $LASTEXITCODE"
        )
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")

    def test_prints_selftest(self):
        code, out, err = self.run_ps(FIXTURE)
        self.assertEqual(code, 0, out + err)
        res = first_json(out)
        self.assertEqual(res["selftest"]["phase"], "logout")
        self.assertEqual(res["selftest"]["fontProbe"]["detail"][FONT_BS]["ret"], "false")
        self.assertNotIn("selftestError", res)

    def test_names_the_broken_link(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "MyAddon.lua")
            with open(p, "w", encoding="utf-8") as f:
                f.write('MyAddonDB = {\n["dbVersion"] = 1,\n}\n')
            code, out, err = self.run_ps(p)
        self.assertEqual(code, 4, out + err)
        res = first_json(out)
        self.assertIsNone(res["selftest"])
        self.assertIn("read-back broke", out)  # the loud line after the JSON
        self.assertIn("has no 'selftest'", res["selftestError"])


if __name__ == "__main__":
    unittest.main()
