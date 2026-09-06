#!/usr/bin/env python3
"""Extract addressed RT replies and a reconstructed map from a .jura file."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from decode_capture import frames
from jura_codec import decode, is_carrier, parse_rt_line, decode_bcd_pin


def capture_replies(path: Path):
    health = dict(unframed_bytes=0, truncated_tail_bytes=0, invalid_headers=0,
                  crc_errors=0, sequence_discontinuities=0, frames=0,
                  invalid_records=0, orphan_data_frames=0)
    replies = []
    command = None
    carriers = bytearray()

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
        for kind, _sequence, payload in frames(source, health):
            if kind == "K":
                finish()
                command = payload[4:].decode("ascii")
            elif kind == "D" and command is not None:
                for _micros, contact, flags, value in struct.iter_unpack("<IBBB", payload):
                    if contact == 1:
                        if flags:
                            replies.append({"command": command,
                                            "error": f"UART flags 0x{flags:02X}"})
                            command = None
                            carriers = bytearray()
                            break
                        carriers.append(value)
    finish()
    return replies, health


def reconstruct(replies):
    byte_map = {}
    conflicts = []
    for reply in replies:
        if "payload" not in reply:
            continue
        text = reply["command"].strip()
        if not text.startswith("RT:"):
            continue
        address = int(text[3:], 16) * 2  # word addressing, verified EF658M
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--show-pins", action="store_true",
                        help="show verified EF658M V15.26 profile fields")
    args = parser.parse_args()
    replies, health = capture_replies(args.capture)
    data, missing, conflicts = reconstruct(replies)

    stem = args.capture.with_suffix("")
    binary_path = stem.with_name(stem.name + "-rt-map.bin")
    report_path = stem.with_name(stem.name + "-rt-replies.json")
    binary_path.write_bytes(data)

    public_replies = [{key: value for key, value in reply.items() if key != "payload"}
                      for reply in replies]
    report = {"capture": args.capture.name, "transport": health,
              "reply_count": len(replies), "map_bytes": len(data),
              "missing_offsets": missing, "overlap_conflicts": conflicts,
              "replies": public_replies}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    valid = sum("payload" in reply for reply in replies)
    print(f"Valid RT replies: {valid}/{len(replies)}")
    print(f"Reconstructed map: {binary_path} ({len(data)} bytes)")
    print(f"Report: {report_path}")
    if missing:
        print(f"Missing mapped offsets: {len(missing)}")
    if conflicts:
        print(f"Overlap conflicts: {len(conflicts)}")
    if args.show_pins:
        if len(data) < 0x3CA:
            print("Verified profile block is absent")
        else:
            print("Cleaning PIN:", decode_bcd_pin(data[0x3C4:0x3C6]))
            print("Main PIN:", decode_bcd_pin(data[0x3C8:0x3CA]))


if __name__ == "__main__":
    main()
