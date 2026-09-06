# Verified protocol behaviour

## Transport

The tested port uses 9600 baud, 8 data bits, no parity, one stop bit and no
hardware flow control. One logical byte expands into four UART carrier bytes.

For carrier index `i = 0..3`:

- carrier bit 2 contains logical bit `2i`;
- carrier bit 5 contains logical bit `2i+1`;
- the remaining fixed bits produce the carrier family `DB`, `DF`, `FB`, `FF`
  in this implementation.

The receiver reverses that mapping in groups of four. Commands end in CR/LF.

## Identity exchange

```text
host -> TY:\r\n
Jura -> ty:EF658M V15.26\r\n
```

The first reply began approximately 12 ms after the final request carrier.
This exact identity also appeared on the machine's Version screen.

## RT exchange

```text
host -> RT:01E0\r\n
Jura -> rt:<64 hexadecimal characters>\r\n
```

The 64 hexadecimal characters represent 32 binary bytes. `RT:0001` matched
`RT:0000` shifted by two bytes with a 30-byte overlap, demonstrating that the
address is counted in 16-bit words on the verified controller.

The main sweep requested `0000, 0010, ... 07F0`. Data returned from
`0400..07FF` exactly repeated `0000..03FF`, giving 2048 distinct bytes. This
could be wrapping, aliasing or mirrored storage; it does not prove the size of
the physical nonvolatile memory or rule out other banks.

## Verified settings block

`RT:01E0` starts at relative byte offset `0x03C0`:

| RT payload bytes | Relative byte offset | Word address | Interpretation |
| ---: | ---: | ---: | --- |
| 4–5 | `0x03C4` | `0x01E2` | cleaning PIN, packed BCD |
| 8–9 | `0x03C8` | `0x01E4` | main programming PIN, packed BCD |

Each nibble is one decimal digit. For example, bytes `12 34` decode to the
four digits `1234`. This representation applies to the PIN fields; the drink
counters use ordinary big-endian integers.

## Timing used by the working Mega implementation

- 1 ms delay after each carrier write;
- 14 ms pause after the four carriers for one logical character;
- request/reply operations have a 3-second timeout in the OLED reader;
- long memory sweeps use a 1.5-second interval between requests.

These values favour compatibility over speed. They are working observations,
not claimed protocol minima.
