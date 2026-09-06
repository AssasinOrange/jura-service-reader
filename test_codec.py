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

    def test_packed_bcd(self):
        self.assertEqual(decode_bcd_pin(bytes.fromhex("12 34")), "1234")
        with self.assertRaises(ValueError):
            decode_bcd_pin(bytes.fromhex("1A 34"))


if __name__ == "__main__":
    unittest.main()
