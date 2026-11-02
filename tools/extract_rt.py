#!/usr/bin/env python3
"""Extract addressed RT replies and a reconstructed map from a .jura file."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

if __package__:
    from .decode_capture import CONTACTS, WRAP, frames
    from .jura_codec import decode, is_carrier, parse_rt_line, decode_bcd_pin
else:
    from decode_capture import CONTACTS, WRAP, frames
    from jura_codec import decode, is_carrier, parse_rt_line, decode_bcd_pin

VERIFIED_PROFILE = "EF658M V15.26"
RT_COMMAND = re.compile(r"RT:[0-9A-Fa-f]{4}\r\n")


def capture_integrity_ok(health):
    counts = {"frames", "sessions", "complete_sessions"}
    return (health["sessions"] > 0
            and health["complete_sessions"] == health["sessions"]
            and all(value == 0 for key, value in health.items() if key not in counts))


def capture_replies(path: Path):
    health = dict(unframed_bytes=0, truncated_tail_bytes=0, invalid_headers=0,
                  crc_errors=0, sequence_discontinuities=0, frames=0,
                  invalid_records=0, orphan_data_frames=0, sessions=0,
                  complete_sessions=0, missing_footers=0, count_mismatches=0,
                  queue_drops=0, hardware_overrun_events=0, uart_frame_errors=0,
                  uart_error_records=0)
    replies = []
    command = None
    carriers = bytearray()
    current = None
    previous_sequence = None

    def finish():
        nonlocal command, carriers
        if command is None:
            return
        if not carriers:
            replies.append({"command": command, "error": "no reply"})
        elif not all(is_carrier(value) for value in carriers):
            replies.append({"command": command,
                            "error": "non-carrier byte in reply",
                            "carrier_count": len(carriers)})
        elif len(carriers) % 4:
            replies.append({"command": command,
                            "error": "partial carrier group",
                            "carrier_count": len(carriers)})
        else:
            line = decode(bytes(carriers))
            try:
                payload = parse_rt_line(line)
                replies.append({"command": command,
                                "reply": line.decode("ascii").rstrip("\r\n"),
                                "payload": payload})
            except ValueError as error:
                replies.append({"command": command, "error": str(error),
                                "decoded_hex": line.hex()})
        command = None
        carriers = bytearray()

    with path.open("rb") as source:
        for kind, sequence, payload in frames(source, health):
            health["frames"] += 1
            if previous_sequence is not None and sequence != (previous_sequence + 1) % WRAP:
                health["sequence_discontinuities"] += 1
            previous_sequence = sequence
            if kind == "A":
                finish()
                if current is not None:
                    health["missing_footers"] += 1
                current = [0, 0, 0]
                health["sessions"] += 1
            elif kind == "E":
                finish()
                values = struct.unpack("<13I", payload)
                if current is None:
                    health["invalid_records"] += 1
                else:
                    health["complete_sessions"] += 1
                    if any(current[i] != values[1 + i] - values[4 + i] for i in range(3)):
                        health["count_mismatches"] += 1
                    health["queue_drops"] += sum(values[4:7])
                    health["uart_frame_errors"] += sum(values[7:10])
                    health["hardware_overrun_events"] += sum(values[10:13])
                current = None
            elif kind in ("H", "Q", "U"):
                # Do not join replies across query or capture boundaries.
                finish()
            if kind == "K":
                finish()
                try:
                    text = payload[4:].decode("ascii")
                except UnicodeDecodeError:
                    text = ""
                if RT_COMMAND.fullmatch(text):
                    command = text
                else:
                    health["invalid_records"] += 1
                    replies.append({"command_hex": payload[4:].hex(),
                                    "error": "invalid RT command marker"})
            elif kind == "D":
                if current is None:
                    health["orphan_data_frames"] += 1
                for _micros, contact, flags, value in struct.iter_unpack("<IBBB", payload):
                    if contact not in CONTACTS or flags & ~0x1C:
                        health["invalid_records"] += 1
                        continue
                    if current is not None:
                        current[CONTACTS.index(contact)] += 1
                    if flags:
                        health["uart_error_records"] += 1
                    if contact == 1 and command is not None:
                        if flags:
                            replies.append({"command": command,
                                            "error": f"UART flags 0x{flags:02X}"})
                            command = None
                            carriers = bytearray()
                            continue
                        carriers.append(value)
    finish()
    if current is not None:
        health["missing_footers"] += 1
    return replies, health


def reconstruct(replies):
    byte_map = {}
    conflicts = []
    for reply in replies:
        if "payload" not in reply:
            continue
        text = reply["command"]
        if not RT_COMMAND.fullmatch(text):
            continue
        address = int(text[3:7], 16) * 2  # word addressing, verified EF658M
        for offset, value in enumerate(reply["payload"]):
            location = address + offset
            previous = byte_map.get(location)
            if previous is not None and previous != value:
                conflicts.append({"offset": location, "first": previous,
                                  "later": value, "command": text})
            byte_map[location] = value
    if not byte_map:
        return b"", [], conflicts
    missing = [location for location in range(max(byte_map) + 1)
               if location not in byte_map]
    data = bytes(byte_map.get(location, 0) for location in range(max(byte_map) + 1))
    return data, missing, conflicts


def verified_pins(data, missing, conflicts, health, profile):
    if profile != VERIFIED_PROFILE:
        raise ValueError("the verified controller profile must be selected explicitly")
    if not capture_integrity_ok(health):
        raise ValueError("capture integrity checks failed; PINs were not displayed")
    if conflicts:
        raise ValueError("overlapping RT replies conflict; PINs were not displayed")
    required = {0x3C4, 0x3C5, 0x3C8, 0x3C9}
    if len(data) < 0x3CA or required.intersection(missing):
        raise ValueError("verified profile PIN bytes are absent from the capture")
    # Validate both fields before printing either one.
    clean_pin = decode_bcd_pin(data[0x3C4:0x3C6])
    main_pin = decode_bcd_pin(data[0x3C8:0x3CA])
    return clean_pin, main_pin


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--show-pins", action="store_true",
                        help="show verified EF658M V15.26 profile fields")
    parser.add_argument("--profile", choices=[VERIFIED_PROFILE],
                        help="assert the controller identity verified separately with TY:")
    args = parser.parse_args(argv)
    if args.show_pins and args.profile is None:
        parser.error("--show-pins requires --profile 'EF658M V15.26'; verify TY: first")
    replies, health = capture_replies(args.capture)
    data, missing, conflicts = reconstruct(replies)

    stem = args.capture.with_suffix("")
    binary_path = stem.with_name(stem.name + "-rt-map.bin")
    report_path = stem.with_name(stem.name + "-rt-replies.json")
    binary_path.write_bytes(data)

    # These are private analysis outputs: reply text still contains raw settings.
    report_replies = [{key: value for key, value in reply.items() if key != "payload"}
                      for reply in replies]
    report = {"capture": args.capture.name, "transport": health,
              "capture_integrity_ok": capture_integrity_ok(health),
              "profile_assertion": args.profile,
              "reply_count": len(replies), "map_bytes": len(data),
              "missing_offsets": missing, "overlap_conflicts": conflicts,
              "replies": report_replies}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    valid = sum("payload" in reply for reply in replies)
    print(f"Valid RT replies: {valid}/{len(replies)}")
    print(f"Reconstructed map: {binary_path} ({len(data)} bytes)")
    print(f"Report: {report_path}")
    if not report["capture_integrity_ok"]:
        print("Warning: capture integrity checks failed; outputs are partial evidence only")
    if missing:
        print(f"Missing mapped offsets: {len(missing)}")
    if conflicts:
        print(f"Overlap conflicts: {len(conflicts)}")
    if args.show_pins:
        try:
            clean_pin, main_pin = verified_pins(data, missing, conflicts, health, args.profile)
        except ValueError as error:
            print(f"Cannot show PINs: {error}", file=sys.stderr)
            return 2
        print("Cleaning PIN:", clean_pin)
        print("Main PIN:", main_pin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
