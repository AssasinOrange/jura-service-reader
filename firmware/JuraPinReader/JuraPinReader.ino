/*
  JuraPinReader - read-only standalone reader for a verified Jura profile.

  Tested profile: GIGA X8c Professional, controller EF658M V15.26.
  Hardware: Arduino Mega 2560 + 128x64 SSD1306 I2C OLED + momentary button.

  Jura DE-9 pin 1 (TX)  -> 1k resistor -> Mega 19 (RX1)
  Jura DE-9 pin 2 (GND) ----------------> Mega GND
  Jura DE-9 pin 3 (RX)  -> 1k resistor -> Mega 16 (TX2)
  Jura DE-9 pin 4 (+5V) is not connected.

  OLED: SDA 20, SCL 21, GND and a supply supported by your module.
  Button: Mega 7 to GND; INPUT_PULLUP is used.

  Dependencies from Arduino Library Manager:
  - Adafruit GFX Library
  - Adafruit SSD1306
*/
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "JuraProtocol.h"

namespace {
constexpr uint8_t kButtonPin = 7;
constexpr uint8_t kOledAddress = 0x3C;
constexpr uint16_t kReplyTimeoutMs = 3000;
constexpr size_t kLineCapacity = 80;
constexpr char kVerifiedIdentity[] = "ty:EF658M V15.26\r\n";

Adafruit_SSD1306 display(128, 64, &Wire, -1);

void screen(const __FlashStringHelper *line1,
            const __FlashStringHelper *line2 = nullptr,
            const char *line3 = nullptr,
            const char *line4 = nullptr) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(line1);
  if (line2) display.println(line2);
  if (line3) display.println(line3);
  if (line4) display.println(line4);
  display.display();
}

void sendCommand(const char *command) {
  while (Serial1.available()) (void)Serial1.read();
  for (size_t index = 0; command[index] != '\0'; ++index) {
    for (uint8_t pair = 0; pair < 4; ++pair) {
      Serial2.write(JuraProtocol::encodeCarrier(
          static_cast<uint8_t>(command[index]), pair));
      Serial2.flush();
      delay(1);
    }
    delay(14);
  }
}

bool readDecodedLine(char *line, size_t capacity, uint16_t timeoutMs) {
  uint8_t group[4];
  uint8_t groupSize = 0;
  size_t length = 0;
  const uint32_t started = millis();
  while (static_cast<uint32_t>(millis() - started) < timeoutMs) {
    if (!Serial1.available()) continue;
    const uint8_t carrier = static_cast<uint8_t>(Serial1.read());
    if (!JuraProtocol::looksLikeCarrier(carrier)) {
      groupSize = 0;
      continue;
    }
    group[groupSize++] = carrier;
    if (groupSize != 4) continue;
    groupSize = 0;
    const char decoded = static_cast<char>(JuraProtocol::decodeGroup(group));
    if (length + 1 >= capacity) return false;
    line[length++] = decoded;
    if (decoded == '\n') {
      line[length] = '\0';
      return true;
    }
  }
  line[length] = '\0';
  return false;
}

bool transact(const char *command, char *reply, size_t capacity) {
  sendCommand(command);
  return readDecodedLine(reply, capacity, kReplyTimeoutMs);
}

void showPins(const char *identity, const char *mainPin, const char *cleanPin) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(F("JURA SERVICE READER"));
  display.println(identity + 3);  // omit the "ty:" prefix
  display.println();
  display.print(F("Main PIN:  "));
  display.println(mainPin);
  display.print(F("Clean PIN: "));
  display.println(cleanPin);
  display.display();
}

void runReader() {
  char reply[kLineCapacity];
  char identity[kLineCapacity];
  screen(F("JURA SERVICE READER"), F("Identifying..."));
  if (!transact("TY:\r\n", reply, sizeof(reply))) {
    screen(F("NO TY RESPONSE"), F("Check connection"));
    return;
  }

  Serial.print(F("Identity: "));
  Serial.print(reply);
  if (strcmp(reply, kVerifiedIdentity) != 0) {
    screen(F("UNVERIFIED PROFILE"), F("Serial monitor has"), reply);
    return;
  }
  strcpy(identity, reply);
  identity[strlen(identity) - 2] = '\0';  // remove CR/LF for the OLED

  screen(F("EF658M V15.26"), F("Reading settings..."));
  if (!transact("RT:01E0\r\n", reply, sizeof(reply))) {
    screen(F("NO RT RESPONSE"), F("Try again"));
    return;
  }

  uint8_t block[32];
  if (!JuraProtocol::parseRtLine(reply, block)) {
    screen(F("INVALID RT REPLY"), F("See serial output"));
    Serial.print(F("RT reply: "));
    Serial.print(reply);
    return;
  }

  char cleanPin[5];
  char mainPin[5];
  // RT:01E0 starts at relative byte 0x03C0 on this word-addressed profile.
  if (!JuraProtocol::decodeBcdPin(&block[4], cleanPin) ||
      !JuraProtocol::decodeBcdPin(&block[8], mainPin)) {
    screen(F("PIN DATA INVALID"), F("Profile mismatch?"));
    return;
  }
  showPins(identity, mainPin, cleanPin);
}
}  // namespace

void setup() {
  pinMode(kButtonPin, INPUT_PULLUP);
  Serial.begin(115200);
  Serial1.begin(9600, SERIAL_8N1);
  Serial2.begin(9600, SERIAL_8N1);
  Wire.begin();
  if (!display.begin(SSD1306_SWITCHCAPVCC, kOledAddress)) {
    Serial.println(F("SSD1306 not found at 0x3C"));
    while (true) delay(1000);
  }
  screen(F("JURA SERVICE READER"), F("Press button"));
}

void loop() {
  if (digitalRead(kButtonPin) != LOW) return;
  delay(25);
  if (digitalRead(kButtonPin) != LOW) return;
  while (digitalRead(kButtonPin) == LOW) delay(10);
  runReader();
}
