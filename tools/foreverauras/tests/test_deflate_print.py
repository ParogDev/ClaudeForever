import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import deflate_print as dp  # noqa: E402


class PrintCodec(unittest.TestCase):
    def test_known(self):
        self.assertEqual(dp.encode_for_print(b"\x00\x00\x00"), "aaaa")
        self.assertEqual(dp.encode_for_print(b"\xff\xff\xff"), "))))")
        # 0x01 0x00 0x00 -> low 6 bits first
        self.assertEqual(dp.encode_for_print(b"\x01\x00\x00"), "baaa")
        self.assertEqual(dp.encode_for_print(b"\x01"), "ba")

    def test_roundtrip_all_lengths(self):
        rng = random.Random(1)
        for n in range(0, 40):
            data = bytes(rng.randrange(256) for _ in range(n))
            enc = dp.encode_for_print(data)
            self.assertTrue(all(c in dp.ALPHABET for c in enc))
            self.assertEqual(dp.decode_for_print(enc), data, n)

    def test_whitespace_trimmed(self):
        self.assertEqual(dp.decode_for_print("  aaaa\r\n"), b"\x00\x00\x00")

    def test_invalid(self):
        self.assertIsNone(dp.decode_for_print("aa!a"))
        self.assertIsNone(dp.decode_for_print("a"))


class Deflate(unittest.TestCase):
    def test_roundtrip(self):
        data = b"ForeverAuras " * 200 + bytes(range(256))
        packed = dp.compress_deflate(data)
        self.assertLess(len(packed), len(data))
        self.assertEqual(dp.decompress_deflate(packed), data)

    def test_raw_stream_no_zlib_header(self):
        import zlib

        with self.assertRaises(zlib.error):
            zlib.decompress(dp.compress_deflate(b"x" * 100))


if __name__ == "__main__":
    unittest.main()
