import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import lint  # noqa: E402


class CustomCodeTest(unittest.TestCase):
    def test_finds_custom_strings_with_paths(self):
        aura = {"triggers": {1: {"trigger": {"custom": "function() end", "customDuration": "function() return 1 end",
                                             "events": "function words are not code here"}}}}
        found = dict(lint.custom_code(aura))
        self.assertEqual(set(found), {"triggers.1.trigger.custom", "triggers.1.trigger.customDuration"})


class CompileRemoteTest(unittest.TestCase):
    def _run(self, stderr, returncode=1):
        result = subprocess.CompletedProcess([], returncode, b"", stderr.encode())
        return mock.patch("subprocess.run", return_value=result)

    def test_clean_compile(self):
        with self._run("", 0):
            self.assertEqual(lint.compile_remote([("A: x", "function() end")], "host"), [])

    def test_error_maps_to_owner(self):
        codes = [("A: c1", "function()\nend"), ("B: c2", "function()\n  x = = 1\nend")]
        with self._run("luac5.1: /dev/stdin:4: unexpected symbol near '='"):
            self.assertEqual(lint.compile_remote(codes, "host"),
                             ["B: c2: line 2 of its code: unexpected symbol near '='"])

    def test_unclosed_block_maps_to_opening_line(self):
        codes = [("A: c1", "function()\nend"), ("B: c2", "function()\n  if x then\nend")]
        with self._run("luac5.1: /dev/stdin:6: 'end' expected (to close 'function' at line 3) near '<eof>'"):
            self.assertEqual(lint.compile_remote(codes, "host"),
                             ["B: c2: line 1 of its code: 'end' expected (to close 'function' at line 3) near '<eof>'"])

    def test_local_runs_docker_without_ssh(self):
        with self._run("", 0) as run:
            self.assertEqual(lint.compile_remote([("A: x", "function() end")]), [])
        self.assertEqual(run.call_args[0][0][:2], ["docker", "run"])

    def test_host_runs_over_ssh(self):
        with self._run("", 0) as run:
            lint.compile_remote([("A: x", "function() end")], "builder")
        self.assertEqual(run.call_args[0][0][:2], ["ssh", "builder"])

    def test_missing_docker_is_named(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("docker")):
            with self.assertRaises(OSError) as cm:
                lint.compile_remote([("A: x", "function() end")])
        self.assertIn("is Docker installed", str(cm.exception))

    def test_broken_link_is_named(self):
        with self._run("ssh: connect to host host port 22: Connection refused", 255):
            with self.assertRaises(OSError):
                lint.compile_remote([("A: x", "function() end")], "host")


if __name__ == "__main__":
    unittest.main()
