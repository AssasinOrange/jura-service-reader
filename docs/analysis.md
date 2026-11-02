# Offline capture analysis

Run these commands from the repository root with Python 3.10 or newer.
The tools use only the Python standard library and never contact the machine.

```sh
python tools/decode_capture.py "C:/path/to/capture.jura"
python tools/extract_rt.py "C:/path/to/capture.jura"
```

The decoder produces a CSV of carrier bytes and a `.summary.json` integrity
report. The RT extractor writes `capture-rt-map.bin` and
`capture-rt-replies.json` beside the original capture. The report contains
raw RT reply hex, transport checks, missing offsets and conflicting overlaps.
**All of these outputs are private evidence, even without `--show-pins`.**
The ignore rules reduce accidental commits; they do not redact file contents.

## Displaying the verified PIN fields

First verify the controller's `TY:` response separately, as described in
[protocol.md](protocol.md). The capture firmware permits either a TY query
or an RT sweep per recording, so an RT sweep does not contain an identity
response. Then, only for the verified `EF658M V15.26` controller, run:

```sh
python tools/extract_rt.py "C:/path/to/capture.jura" --show-pins --profile "EF658M V15.26"
```

`--profile` is your explicit assertion of an identity established separately;
it does not detect or prove the machine model from an RT dump. No other PIN
profile is supported. The standalone OLED reader instead verifies the identity
directly before reading the settings block.

PIN display requires a started and stopped capture, continuous frame sequence
numbers, valid CRC/framing, matching final byte counts, no queue loss or UART
errors, no conflicting overlapping reads, both PIN fields actually captured,
and valid packed BCD in both fields. Both PINs are validated before either is
printed. Refusal returns exit status 2 with an explanation on standard error.

The reconstructed map uses the verified controller's word addressing. Holes
are listed in `missing_offsets` and filled with zero bytes solely to preserve
file offsets; those zero bytes are not measurements. Holes outside the PIN
fields may remain in a valid partial address map, but a hole in either PIN
field prevents PIN display. Do not interpret maps from unknown controllers
using the verified model's addresses.

## Incomplete captures

Default extraction deliberately retains recoverable evidence, even from a
damaged recording, and returns status 0 if analysis completed. Check
`capture_integrity_ok`, `transport`, `missing_offsets` and `overlap_conflicts`
before interpreting it. A valid RT line alone does not establish capture
completeness. PIN display is refused when integrity checks fail.

Keep the original `.jura` file. Do not publish raw captures, RT hex, generated
maps, reports or screenshots containing credentials. Share a sanitised model
report or reproduce a problem with synthetic data instead; see
[CONTRIBUTING.md](../CONTRIBUTING.md).
