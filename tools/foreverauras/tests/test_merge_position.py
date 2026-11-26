import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import savedvars  # noqa: E402


class KeepPositionTest(unittest.TestCase):
    def test_reinstall_keeps_dragged_group_position(self):
        saved = {"displays": {"G": {"id": "G", "uid": "u0", "xOffset": 300, "yOffset": 40,
                                    "controlledChildren": {1: "A"}},
                              "A": {"id": "A", "uid": "u1", "parent": "G"}}}
        group = {"id": "G", "uid": "u0", "xOffset": 0, "yOffset": -150, "regionType": "group"}
        notes = savedvars.merge(saved, group, [{"id": "A", "uid": "u1"}], 91)
        g = saved["displays"]["G"]
        self.assertEqual((g["xOffset"], g["yOffset"]), (300, 40))
        self.assertTrue(any("kept 'G'" in n for n in notes))

    def test_first_install_uses_source_position(self):
        saved = {"displays": {}}
        savedvars.merge(saved, {"id": "G", "uid": "u0", "yOffset": -150}, [], 91)
        self.assertEqual(saved["displays"]["G"]["yOffset"], -150)


if __name__ == "__main__":
    unittest.main()
