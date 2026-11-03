# Standalone reader build

## Parts

| Quantity | Part |
| ---: | --- |
| 1 | Arduino Mega 2560 or compatible |
| 1 | 128×64 SSD1306 I²C OLED, address `0x3C` |
| 1 | momentary push button |
| 2 | 1 kΩ resistors |
| 1 | male DE-9 breakout plug or solder-cup plug |
| 1 | USB cable and independent USB supply |

Choose an OLED breakout whose supply input is specified for the voltage you
intend to use. The firmware assumes a 128×64 SSD1306 at I²C address `0x3C`.

## Connections

| OLED/button | Mega |
| --- | --- |
| OLED SDA | 20 / SDA |
| OLED SCL | 21 / SCL |
| OLED GND | GND |
| OLED supply | supply supported by the module |
| button side 1 | 7 |
| button side 2 | GND |

The Jura connections are listed in [wiring.md](wiring.md). Pin 4 is not needed
by the standalone reader.

## Upload

1. Install **Adafruit GFX Library** and **Adafruit SSD1306** from Arduino
   Library Manager.
2. Open `firmware/JuraPinReader/JuraPinReader.ino`.
3. Select **Arduino Mega or Mega 2560** and the correct port.
4. Upload with the Jura connector unplugged.
5. Connect the harness, power the Mega by USB, then connect to the machine.
6. With the machine awake and idle, press the reader button.

The OLED first shows the identity stage. It displays the PIN fields only when
the machine replies with the exact verified identity `EF658M V15.26` and the
RT reply passes format and packed-BCD checks. The USB serial monitor at 115200
baud carries additional diagnostic text.

## Reproducible command-line builds

CI uses Arduino CLI 1.5.1, Arduino AVR core 1.8.6 and the library versions below.
From the repository root, with Arduino CLI installed:

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr@1.8.6
arduino-cli lib install --no-deps "Adafruit BusIO@1.17.4" "Adafruit GFX Library@1.13.0" "Adafruit SSD1306@2.5.17"
arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 firmware/JuraPinReader
arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 capture/JuraFullCapture/JuraFullCapture
```

These commands compile only; they do not upload firmware or contact a machine.
The Actions workflow runs on pushes and pull requests and can also be started
from **Actions → test → Run workflow**. It runs Python tests on 3.10 and 3.13
and the C++ protocol tests with address/undefined-behaviour sanitizers.

To run the C++ tests locally with a suitable GCC installation:

```sh
g++ -std=c++11 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer tests/test_protocol_header.cpp -o protocol-test
./protocol-test
```

Passing host tests and compilation are software checks. Physical operation
still depends on the wiring and the one verified controller profile.
