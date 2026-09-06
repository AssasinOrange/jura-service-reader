JURA FULL CAPTURE v4 - OVERLAP CHECK + RT:0000 THROUGH RT:07F0 EEPROM CAPTURE

1. Extract the ZIP; upload JuraFullCapture/JuraFullCapture.ino to Mega 2560.
2. Close Arduino Serial Monitor. With the rig unpowered, use:
   Jura 1 red   -> existing 1k -> Mega 19 (reply input)
   Jura 2 black -> Mega GND
   Jura 3 white -> existing 1k -> Mega 16 (command output)
   Jura 4 green -> existing 1k -> Mega 15
   Remove the 16-17 jumper; leave Mega 17 disconnected. It has an internal
   pull-up so the unused receiver does not float. TX18 and TX14 unused.
   Jura supply is NOT connected to Mega 5V.
3. Run Start-Capture.cmd, enter COM4. Wait for Capture start requested.
4. Boot the Jura if needed. When ready and idle, press R ONCE.
   First RT:0000 and RT:0001, then 128 RT reads: 0000,0010,...,07F0.
   Total 130 requests, each followed by CR/LF.
   Each request has 36 encoded carrier bytes; requests pause at least 1.5s
   after transmission, and wait for 100ms reply silence and an empty queue.
5. Wait 4 minutes 30 seconds; press ENTER; wait for SAVED.
6. Analyse the .jura file with ../../tools/decode_capture.py and extract_rt.py.

T still requests TY: if selected instead of R. Only ONE sweep or TY query total per
capture. Neither is automatic. Use a new capture for another query.
Each K marker records the exact RT command and uptime; Q identifies TY:.
The sweep is exactly 130 read requests. No writes or actuator calls.
The actual machine returned 32 bytes per RT request in the previous capture.
The initial overlapping reads test whether offsets count bytes or words.
The extended sweep returns 4096 payload bytes if all 128 replies match that
format, plus 64 bytes from the overlap check. These are returned byte counts,
NOT a claim of contiguous coverage or complete EEPROM size. Byte-addressed
32-byte replies would overlap at the 0x10 stride; word addressing may not.
We will establish addressing from the overlap replies before mapping data.
No PIN location is assumed. Enter can stop an in-progress sweep and save.
If replies are continuous, the idle guard may delay the sweep; the saved
command markers show exactly how far it progressed.
Keep the RT prefix unchanged; RE and TR are not substitutes.

WHAT CHANGED
- No first-32-byte limit and no intentional sampling/discarding of input data.
- Each received UART byte has a contact label, microsecond uptime timestamp
  and UART error flags. Noise and malformed frames are retained too.
- The Mega queues data, sends CRC-protected binary frames and reports queue
  losses plus hardware overrun events. The final footer verifies byte counts.
- PC recording retains the exact transport stream, even if corrupt/truncated.
- T requests TY:\r\n, encoded into 20 legacy carrier bytes. The original
  Q42 bit mapping and conservative inter-character delays are used.
- Only Mega 16 transmits, only while sending this query; it returns to input
  afterwards. No arbitrary command console, EEPROM writes or actuator calls.
- The capture records Q for TY or K with the exact RT command before each read.
  With white moved to 16, input 17 is disconnected; replies arrive on 19.
  The v2 capture confirmed TY: -> ty:EF658M V15.26 on contact 1.

SPEEDS
The three Jura receivers stay at 9600 baud / 8N1.
The laptop link is now 500000 baud and the launcher sets that automatically.
Do not use Serial Monitor for capture: output is binary and will look garbled.
The cmd launcher uses Windows PowerShell and the built-in .NET serial API.
No Python, drivers beyond the working Arduino driver, or packages are needed
for recording. The process-local ExecutionPolicy Bypass in the launcher does
not persistently change your PowerShell policy. Review the scripts if desired.

FILES AND COMPLETENESS
The .jura file is the authoritative original; notes use the laptop clock.
"Bytes saved" includes status/transport framing, not just Jura payload bytes.
If no machine bytes arrive, status frames still produce a growing file.
The program does not claim that a non-empty file is valid Jura data.
An overrun, checksum failure, missing sequence, mismatched final count or
missing footer makes completeness uncertain; the original file is retained.
Stopping defines the end of the capture: a UART byte still in flight when
receivers are disabled is outside that capture boundary.
This records UART bytes, not analogue voltage or exact edge timing. Wrong
baud/polarity, floating pins or out-of-range voltages can still cause nonsense.
PIN recovery and EEPROM access remain unconfirmed.
Use individual sessions shorter than 24 hours; longer sessions are untested.

VALIDATION
Firmware compiled and linked for ATmega2560 with Arduino AVR core 1.8.6.
Simulated firmware output and the actual decoder recovered all 256 byte
values on each of three channels. Forced queue loss and UART error flags
were reported. Decoder tests cover corruption, truncated files, missing
footers and timestamp wraps. The previous passive firmware has also produced
a clean capture on your Windows/Jura rig. TY: has worked on the machine.
The original 16-block RT sweep worked on this machine. This expanded range
has not yet been tested on it; no reply does not by itself establish a locked port.

OPTIONAL CSV CONVERSION
No need to do this yourself: send the file here and I can decode it.
If you have Python 3, run:
  python decode_capture.py "C:\path\to\Jura-....jura"
It creates a CSV with every captured byte and a JSON integrity report.
It deliberately preserves raw data rather than guessing a Jura text encoding.

TROUBLESHOOTING
Access denied / COM busy: close Serial Monitor and any other serial terminal.
No file growth: check COM selection and that this NEW firmware was uploaded.
No start/footer when decoded: may be old firmware, wrong port, reset or an
interrupted USB connection. Keep the raw file for diagnosis.
If a managed Windows policy blocks the launcher, do not change system policy;
send the error here. PowerShell must run in a normal interactive console.
