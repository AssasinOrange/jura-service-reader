JURA FULL CAPTURE v4 - OVERLAP CHECK AND RT MEMORY SWEEP

VERIFIED SCOPE
The documented investigation on 6 September 2026 used a Jura GIGA X8c
Professional, controller EF658M V15.26. TY identification, word-addressed RT
reads and the PIN fields were verified on that machine. Returned addresses
0400..07FF repeated 0000..03FF; this does not establish physical EEPROM size.
See ../../docs/protocol.md and ../../docs/verified-profile.md for the evidence
and confidence limits. Other controller profiles remain unverified.

RECORDING
1. Open JuraFullCapture/JuraFullCapture.ino and compile/upload for Mega 2560.
   Reproducible versions and build commands are in ../../docs/build.md.
2. Close Arduino Serial Monitor. With the rig unpowered, connect:
   Jura 1 (machine TX) -> 1k series resistor -> Mega 19 / RX1
   Jura 2 (GND) -> Mega GND
   Jura 3 (machine RX) -> 1k series resistor -> Mega 16 / TX2
   Optional capture-only monitor: Jura 4 -> 1k resistor -> Mega 15 / RX3
   Leave Mega 17 disconnected. Never connect Jura pin 4 to Mega 5V.
   Use independent USB power. This is 5V TTL, not PC RS-232.
   The photographed pin numbering is in ../../docs/wiring.md.
3. Run Start-Capture.cmd, enter the actual COM port, and wait for
   "Capture start requested". The USB link uses 500000 baud; machine UARTs
   stay at 9600 8N1. Serial Monitor cannot record this binary output.
4. With the machine awake and idle, press R once for overlapping RT:0000
   and RT:0001 reads followed by 128 reads at 0000,0010,...,07F0.
   Alternatively press T for TY identification. Only one selection is
   permitted per capture; use a separate recording for the other query.
5. Allow about 4 minutes 30 seconds for the sweep, then press Enter and wait
   for SAVED. Enter can also stop an in-progress sweep and preserve it.

The sweep sends 130 read requests, each with CR/LF and 36 carrier bytes.
Requests pause at least 1.5 seconds after transmission and wait for 100ms
reply silence plus an empty queue. Exact RT commands are recorded in K
markers. There are no arbitrary commands, memory writes or actuator calls.
Only Mega 16 transmits; it returns to input after each request.

OFFLINE ANALYSIS
From the repository root, using Python 3.10 or newer:
  python tools/decode_capture.py "C:/path/to/capture.jura"
  python tools/extract_rt.py "C:/path/to/capture.jura"

If running from this README's directory, prefix each script with ../../tools/.
See ../../docs/analysis.md for outputs, integrity checks and the explicit
verified-profile option required for PIN display. Verify TY separately first.

The .jura file is the authoritative original. CSV and summary JSON describe
transport integrity; the RT map and replies JSON contain private settings.
Keep all captures and generated outputs private, even without --show-pins.
Use sanitised observations or synthetic data in public reports.

COMPLETENESS AND LIMITS
Each received UART byte retains its contact, microsecond timestamp and error
flags. Frames include sequence numbers and CRC-16; status/footer frames retain
received counts, queue losses and hardware overruns. Wrong baud, polarity or
wiring can still produce meaningless traffic. A growing or non-empty file is
not proof of valid machine data. Missing start/footer frames, count mismatches,
CRC errors, gaps and overruns make completeness uncertain. Retain the original
for diagnosis. Use individual sessions shorter than 24 hours.

The software tests use synthetic protocol/capture data. Firmware compilation
is checked separately from the physical observations recorded in the docs.

TROUBLESHOOTING
Access denied / COM busy: close Serial Monitor and other serial terminals.
No file growth: check the selected port and uploaded capture firmware.
Missing start/footer: check for reset, USB interruption or an unfinished save.
No reply: check wiring and profile; this alone does not prove a locked port.
The launcher uses Windows PowerShell 5.1 and .NET SerialPort. Its process-local
ExecutionPolicy Bypass does not persistently change system policy. If a
managed policy blocks it, retain the error rather than changing system policy.
