"""Jura four-carrier codec and parsers used by the capture tools."""

from __future__ import annotations

import binascii


def encode_byte(value: int) -> bytes:
    if not 0 <= value <= 0xFF:
        raise ValueError("value must be one byte")
    return bytes(
        0xDB
        | (((value >> (2 * pair)) & 1) << 2)
        | (((value >> (2 * pair + 1)) & 1) << 5)
        for pair in range(4)
    )


def encode(data: bytes) -> bytes:
    return b"".join(encode_byte(value) for value in data)


def is_carrier(value: int) -> bool:
    return 0 <= value <= 0xFF and (value & 0x5B) == 0x5B


def decode_group(group: bytes) -> int:
    if len(group) != 4:
        raise ValueError("a logical byte requires four carriers")
    if not all(is_carrier(value) for value in group):
        raise ValueError("group contains a non-carrier byte")
    decoded = 0
    for pair, value in enumerate(group):
        decoded |= ((value >> 2) & 1) << (2 * pair)
        decoded |= ((value >> 5) & 1) << (2 * pair + 1)
    return decoded


def decode(carriers: bytes) -> bytes:
    if len(carriers) % 4:
        raise ValueError("carrier stream length is not divisible by four")
    return bytes(decode_group(carriers[index : index + 4])
                 for index in range(0, len(carriers), 4))


def parse_rt_line(line: bytes) -> bytes:
    if not line.startswith(b"rt:") or not line.endswith(b"\r\n"):
        raise ValueError("not a complete rt reply")
    encoded = line[3:-2]
    if len(encoded) != 64:
        raise ValueError("expected 64 hexadecimal characters")
    try:
        # Unlike bytes.fromhex(), unhexlify rejects embedded whitespace.
        return binascii.unhexlify(encoded)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid hexadecimal RT payload") from error


def decode_bcd_pin(data: bytes) -> str:
    if len(data) != 2:
        raise ValueError("a four-digit packed-BCD PIN occupies two bytes")
    digits = []
    for value in data:
        digits.extend((value >> 4, value & 0x0F))
    if any(digit > 9 for digit in digits):
        raise ValueError("PIN field is not valid packed BCD")
    return "".join(str(digit) for digit in digits)
