"""Optional offline decoder: python decode_capture.py capture.jura
Writes one CSV row per captured UART byte and a JSON integrity report.
Python 3 standard library only. Not needed to record on Windows.
Does not assume the UART payload is text or apply speculative Jura decoding.
"""
import argparse
import binascii
import csv
import json
import struct
from pathlib import Path

MAGIC = b"JLG1"
CONTACTS = (1, 3, 4)
WRAP = 1 << 32


def frames(stream, health):
    buf = bytearray()
    eof = False
    while True:
        if not eof and len(buf) < 256:
            block = stream.read(65536)
            buf.extend(block)
            eof = not block
        pos = buf.find(MAGIC)
        if pos < 0:
            keep = 0 if eof else min(3, len(buf))
            discarded = len(buf) - keep
            health["unframed_bytes"] += discarded
            del buf[:discarded]
            if eof:
                return
            continue
        if pos:
            health["unframed_bytes"] += pos
            del buf[:pos]
        if len(buf) < 11:
            if eof:
                health["truncated_tail_bytes"] = len(buf)
                return
            continue
        kind, length, sequence = struct.unpack_from("<BHI", buf, 4)
        legal = (kind == ord("D") and 0 < length <= 168 and length % 7 == 0) or (
            kind in b"HATEQU" and length == 52
        ) or (kind == ord("K") and length == 13
        )
        if not legal:
            health["invalid_headers"] += 1
            del buf[0]
            continue
        size = 13 + length
        if len(buf) < size:
            if eof:
                health["truncated_tail_bytes"] = len(buf)
                return
            continue
        expected = struct.unpack_from("<H", buf, size - 2)[0]
        actual = binascii.crc_hqx(buf[4:size - 2], 0xFFFF)
        if actual != expected:
            health["crc_errors"] += 1
            del buf[0]
            continue
        payload = bytes(buf[11:size - 2])
        del buf[:size]
        yield chr(kind), sequence, payload


def decode(path):
    path = Path(path)
    health = dict(unframed_bytes=0, truncated_tail_bytes=0, invalid_headers=0,
                  crc_errors=0, sequence_discontinuities=0, frames=0,
                  invalid_records=0, orphan_data_frames=0)
    sessions = []
    queries = []
    current = None
    previous_sequence = None
    anchor = 0
    csv_path = path.with_suffix(".csv")
    with path.open("rb") as source, csv_path.open("w", newline="", encoding="utf-8") as dest:
        writer = csv.writer(dest)
        writer.writerow(("session", "mega_uptime_us", "jura_contact", "raw_hex",
                         "frame_error", "hardware_overrun", "parity_error"))
        for kind, sequence, payload in frames(source, health):
            health["frames"] += 1
            if previous_sequence is not None and sequence != (previous_sequence + 1) % WRAP:
                health["sequence_discontinuities"] += 1
            previous_sequence = sequence
            if kind == "K":
                stamp = struct.unpack_from("<I", payload)[0]
                queries.append(dict(session=current["session"] if current else 0,
                                    uptime_ms=stamp, command=payload[4:].decode("ascii")))
                continue
            if kind != "D":
                values = struct.unpack("<13I", payload)
                anchor = values[0] * 1000
                status = dict(uptime_ms=values[0], received=list(values[1:4]),
                              queue_drops=list(values[4:7]), frame_errors=list(values[7:10]),
                              hardware_overrun_events=list(values[10:13]))
                if kind == "A":
                    current = dict(session=len(sessions)+1, start=status,
                                   captured=[0, 0, 0], flagged=[0, 0, 0], footer=None,
                                   latest_status=status)
                    sessions.append(current)
                elif kind in ("Q", "U"):
                    queries.append(dict(session=current["session"] if current else 0,
                                        uptime_ms=values[0], command=("TY:\\r\\n" if kind == "Q" else "RT:0000\\r\\n")))
                elif current is not None and kind in ("T", "E"):
                    current["latest_status"] = status
                    if kind == "E":
                        current["footer"] = status
                        current = None
                continue
            if current is None:
                health["orphan_data_frames"] += 1
            for raw_us, contact, flags, data in struct.iter_unpack("<IBBB", payload):
                if contact not in CONTACTS or flags & ~0x1C:
                    health["invalid_records"] += 1
                    continue
                base = (anchor // WRAP) * WRAP
                candidates = (base + raw_us - WRAP, base + raw_us, base + raw_us + WRAP)
                timestamp = min((x for x in candidates if x >= 0), key=lambda x: abs(x-anchor))
                anchor = timestamp
                if current:
                    i = CONTACTS.index(contact)
                    current["captured"][i] += 1
                    if flags:
                        current["flagged"][i] += 1
                writer.writerow((current["session"] if current else 0, timestamp, contact,
                                 f"{data:02X}", int(bool(flags & 0x10)),
                                 int(bool(flags & 0x08)), int(bool(flags & 0x04))))
    transport_ok = all(health[k] == 0 for k in health if k != "frames") and health["frames"] > 0
    for session in sessions:
        footer = session["footer"]
        session["counts_match"] = bool(footer) and all(
            session["captured"][i] == footer["received"][i] - footer["queue_drops"][i]
            for i in range(3))
        session["no_detected_byte_loss"] = bool(transport_ok and session["counts_match"] and
            not any(footer["queue_drops"]) and not any(footer["hardware_overrun_events"]))
    report = dict(contact_order=list(CONTACTS), transport=health, sessions=sessions, queries=queries,
                  no_detected_byte_loss=bool(sessions) and all(s["no_detected_byte_loss"] for s in sessions),
                  limitation="No detected loss is not proof of correct baud/polarity or valid Jura protocol. "
                             "Timestamps are receiver ISR times, not exact wire-edge times. "
                             "Captures lacking a start or stop frame cannot be verified complete.")
    json_path = path.with_suffix(".summary.json")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, csv_path, json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    report, csv_path, json_path = decode(args.capture)
    print("CSV:", csv_path)
    print("Integrity report:", json_path)
    print("No detected byte loss:", report["no_detected_byte_loss"])
    for s in report["sessions"]:
        print("Session", s["session"], "captured contacts 1/3/4:", s["captured"],
              "flagged:", s["flagged"], "final footer:", bool(s["footer"]))
