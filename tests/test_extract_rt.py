"""Synthetic captures only: no machine settings or recovered credentials."""

import binascii
import contextlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from tools.extract_rt import capture_replies, main, reconstruct
from tools.jura_codec import encode

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "EF658M V15.26"


def frame(kind, sequence, payload):
    body = struct.pack("<BHI", ord(kind), len(payload), sequence) + payload
    return b"JLG1" + body + struct.pack("<H", binascii.crc_hqx(body, 0xFFFF))


def status(received=0, drops=0, overruns=0, frame_errors=0):
    return struct.pack("<13I", 0, received, 0, 0, drops, 0, 0,
                       frame_errors, 0, 0, overruns, 0, 0)


def capture(address=0x01E0, payload=None, *, start=True, footer=True,
            sequence_gap=False, bad_count=False, flags=0, drops=0,
            overruns=0, contact=1, sequence_start=0, frame_errors=0):
    if payload is None:
        payload = bytearray(32)
        payload[4:6] = bytes.fromhex("00 01")
        payload[8:10] = bytes.fromhex("12 34")
    parts = []
    sequence = sequence_start
    if start:
        parts.append(frame("A", sequence, status()))
        sequence += 1
    command = f"RT:{address:04X}\r\n".encode()
    parts.append(frame("K", sequence, struct.pack("<I", 0) + command))
    sequence += 2 if sequence_gap else 1
    carriers = encode(b"rt:" + bytes(payload).hex().encode() + b"\r\n")
    records = [struct.pack("<IBBB", index * 1000, contact, flags, value)
               for index, value in enumerate(carriers)]
    for index in range(0, len(records), 24):
        parts.append(frame("D", sequence, b"".join(records[index:index + 24])))
        sequence += 1
    if footer:
        parts.append(frame("E", sequence,
                           status(len(records) + int(bad_count) + drops, drops,
                                  overruns, frame_errors)))
    return b"".join(parts)


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.jura"

    def run_cli(self, content, *options):
        self.path.write_bytes(content)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([str(self.path), *options])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_profile_capture_shows_both_pins(self):
        code, output, error = self.run_cli(capture(), "--show-pins", "--profile", PROFILE)
        self.assertEqual((code, error), (0, ""))
        self.assertIn("Cleaning PIN: 0001", output)
        self.assertIn("Main PIN: 1234", output)

    def test_profile_is_required_before_showing_pins(self):
        self.path.write_bytes(capture())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main([str(self.path), "--show-pins"])
        self.assertEqual(error.exception.code, 2)

    def test_missing_pin_bytes_never_display_zero_filled_pins(self):
        code, output, error = self.run_cli(capture(address=0x0200), "--show-pins", "--profile", PROFILE)
        self.assertEqual(code, 2)
        self.assertIn("absent", error)
        self.assertNotIn("Main PIN:", output)
        self.assertNotIn("Cleaning PIN:", output)

    def test_captured_zero_pins_remain_valid(self):
        code, output, error = self.run_cli(capture(payload=bytes(32)),
                                           "--show-pins", "--profile", PROFILE)
        self.assertEqual((code, error), (0, ""))
        self.assertIn("Cleaning PIN: 0000", output)
        self.assertIn("Main PIN: 0000", output)

    def test_one_missing_pin_field_is_refused(self):
        code, output, error = self.run_cli(capture(address=0x01E3),
                                           "--show-pins", "--profile", PROFILE)
        self.assertEqual(code, 2)
        self.assertIn("absent", error)
        self.assertNotIn("PIN:", output)

    def test_short_map_is_refused(self):
        code, output, error = self.run_cli(capture(address=0), "--show-pins", "--profile", PROFILE)
        self.assertEqual(code, 2)
        self.assertIn("absent", error)
        self.assertNotIn("PIN:", output)

    def test_invalid_bcd_does_not_print_either_pin(self):
        payload = bytearray(32)
        payload[8] = 0xFA
        code, output, error = self.run_cli(capture(payload=payload), "--show-pins", "--profile", PROFILE)
        self.assertEqual(code, 2)
        self.assertIn("BCD", error)
        self.assertNotIn("PIN:", output)

    def test_incomplete_or_damaged_captures_do_not_show_pins(self):
        cases = [capture(start=False), capture(footer=False), capture(sequence_gap=True),
                 capture(bad_count=True), capture(flags=0x10), capture(drops=1),
                 capture(overruns=1), capture(frame_errors=1), capture(contact=2), capture()[:-1],
                 b"noise" + capture()]
        corrupt = bytearray(capture())
        corrupt[30] ^= 1
        cases.append(bytes(corrupt))
        for content in cases:
            with self.subTest(content=content[:30]):
                code, output, error = self.run_cli(content, "--show-pins", "--profile", PROFILE)
                self.assertEqual(code, 2)
                self.assertNotIn("Main PIN:", output)
                self.assertNotIn("Cleaning PIN:", output)
                self.assertTrue(error)

    def test_overlapping_conflicts_refuse_pin_display(self):
        other = bytearray(32)
        other[4:6] = bytes.fromhex("00 01")
        other[8:10] = bytes.fromhex("56 78")
        code, output, error = self.run_cli(capture() + capture(payload=other, sequence_start=15),
                                           "--show-pins", "--profile", PROFILE)
        self.assertEqual(code, 2)
        self.assertIn("conflict", error)
        self.assertNotIn("PIN:", output)

    def test_report_tracks_frames_and_sequence_gaps(self):
        self.path.write_bytes(capture(sequence_gap=True))
        replies, health = capture_replies(self.path)
        self.assertEqual(len(replies), 1)
        self.assertGreater(health["frames"], 0)
        self.assertEqual(health["sequence_discontinuities"], 1)

    def test_default_extraction_preserves_raw_evidence_without_printing_pins(self):
        code, output, error = self.run_cli(capture())
        self.assertEqual((code, error), (0, ""))
        self.assertNotIn("PIN:", output)
        report = json.loads(self.path.with_name("synthetic-rt-replies.json").read_text())
        self.assertTrue(report["capture_integrity_ok"])
        self.assertIn("reply", report["replies"][0])
        self.assertTrue(self.path.with_name("synthetic-rt-map.bin").exists())

    def test_malformed_command_is_reported_without_crashing(self):
        content = frame("A", 0, status()) + frame("K", 1, struct.pack("<I", 0) + b"RT:ZZZZ\r\n")
        code, output, error = self.run_cli(content)
        self.assertEqual((code, error), (0, ""))
        self.assertIn("Valid RT replies: 0/", output)

    def test_map_records_holes_and_conflicts(self):
        data, missing, conflicts = reconstruct([
            {"command": "RT:0001\r\n", "payload": bytes(32)},
            {"command": "RT:0002\r\n", "payload": b"\x01" * 32},
        ])
        self.assertEqual(missing, [0, 1])
        self.assertEqual(len(data), 36)
        self.assertEqual(len(conflicts), 30)

    def test_module_and_script_entrypoints(self):
        for command in ([sys.executable, "-m", "tools.extract_rt", "--help"],
                        [sys.executable, "tools/extract_rt.py", "--help"]):
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
