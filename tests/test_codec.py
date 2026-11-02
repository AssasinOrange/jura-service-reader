import unittest

from tools.jura_codec import (
    decode,
    decode_bcd_pin,
    encode,
    encode_byte,
    is_carrier,
    parse_rt_line,
)


class CodecTests(unittest.TestCase):
    def test_all_byte_values_round_trip(self):
        data = bytes(range(256))
        self.assertEqual(decode(encode(data)), data)

    def test_known_carriers(self):
        self.assertEqual(encode_byte(ord("T")), bytes.fromhex("DB DF DF DF"))
        self.assertTrue(all(is_carrier(value) for value in encode(b"TY:\r\n")))

    def test_rt_parser(self):
        payload = bytes(range(32))
        line = b"rt:" + payload.hex().upper().encode() + b"\r\n"
        self.assertEqual(parse_rt_line(line), payload)

    def test_rt_parser_accepts_lowercase_hex(self):
        payload = bytes(range(224, 256))
        self.assertEqual(parse_rt_line(b"rt:" + payload.hex().encode() + b"\r\n"), payload)

    def test_rt_parser_rejects_malformed_replies(self):
        valid = b"rt:" + b"00" * 32 + b"\r\n"
        invalid = [b"", b"rt:", valid[:-1], valid + b"x", valid.upper(),
                   b"rt:" + b"00" * 31 + b"\r\n",
                   b"rt:" + b"00" * 33 + b"\r\n"]
        for replacement in (b"  ", b"\t\t", b"\r\n", b"GG", b"\xff\xff"):
            invalid.append(b"rt:" + b"00" * 31 + replacement + b"\r\n")
        for line in invalid:
            with self.subTest(line=line), self.assertRaises(ValueError):
                parse_rt_line(line)

    def test_decode_rejects_partial_or_invalid_carriers(self):
        for stream in (b"\xdb", b"\xdb" * 3, b"\x00" * 4):
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                decode(stream)

    def test_packed_bcd(self):
        self.assertEqual(decode_bcd_pin(bytes.fromhex("12 34")), "1234")
        with self.assertRaises(ValueError):
            decode_bcd_pin(bytes.fromhex("1A 34"))

    def test_packed_bcd_preserves_leading_zeros(self):
        self.assertEqual(decode_bcd_pin(bytes.fromhex("00 01")), "0001")


if __name__ == "__main__":
    unittest.main()
