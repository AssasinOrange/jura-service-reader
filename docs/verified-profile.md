# Verified profile: EF658M V15.26

## Machine

- Product: Jura GIGA X8c Professional
- Main controller: `EF658M V15.26`
- Other identifiers visible in the Version menu: `EF657D V05.23`,
  `EF657R V01.01`, and the standalone value `50`
- Date of verification: 6 September 2026

The precise roles of `EF657D`, `EF657R` and `50` were not established.

## PIN recovery

The `RT:01E0` payload contains two adjacent packed-BCD fields. One matched the
already-known cleaning PIN. The second decoded to the unknown main PIN and was
accepted by the front panel, opening the machine's five-page programming menu.
The private raw capture and recovered values are deliberately omitted.

## Counter mapping

The photographed UI values matched big-endian 16-bit words at these addresses:

| Product | Lifetime word | Second-group word |
| --- | ---: | ---: |
| Espresso | `0x0280` | `0x02A0` |
| Ristretto | `0x0281` | `0x02A1` |
| Coffee | `0x0282` | `0x02A2` |
| Cappuccino | `0x0284` | `0x02A4` |
| Latte macchiato | `0x0285` | `0x02A5` |
| Café latte | `0x0288` | `0x02A8` |
| Portion milk | `0x028B` | `0x02AB` |
| Hot water | `0x028F` | `0x02AF` |

The two UI pages showed totals that were not present as direct 16- or 32-bit
values in either byte order. The total may be calculated or stored elsewhere.
The exact meaning of the second counter group has not yet been established.

## Confidence labels used by this project

- **Verified:** observed in a loss-checked capture and confirmed against the UI.
- **Inferred:** best explanation of measurements, with alternatives remaining.
- **Unknown:** deliberately left unnamed rather than guessed.

New model profiles should meet the same standard before being enabled in the
standalone reader.
