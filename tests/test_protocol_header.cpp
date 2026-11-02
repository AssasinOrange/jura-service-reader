#include "../firmware/JuraPinReader/JuraProtocol.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>

int main() {
  for (unsigned value = 0; value < 256; ++value) {
    uint8_t carriers[4];
    for (uint8_t pair = 0; pair < 4; ++pair) {
      carriers[pair] = JuraProtocol::encodeCarrier(value, pair);
      assert(JuraProtocol::looksLikeCarrier(carriers[pair]));
    }
    assert(JuraProtocol::decodeGroup(carriers) == value);
  }

  uint8_t memory[32];
  assert(JuraProtocol::parseRtLine(
      "rt:000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F\r\n",
      memory));
  for (uint8_t index = 0; index < 32; ++index) assert(memory[index] == index);

  assert(!JuraProtocol::parseRtLine(nullptr, memory));
  for (const char *shortLine : {"", "r", "rt", "rt:", "rt:00\r\n"}) {
    assert(!JuraProtocol::parseRtLine(shortLine, memory));
  }
  char line[] = "rt:000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F\r\n";
  line[3] = ' ';
  assert(!JuraProtocol::parseRtLine(line, memory));
  line[3] = 'G';
  assert(!JuraProtocol::parseRtLine(line, memory));
  line[3] = 'a';
  assert(JuraProtocol::parseRtLine(line, memory));
  line[67] = '\n';
  assert(!JuraProtocol::parseRtLine(line, memory));

  char pin[5];
  const uint8_t bcd[] = {0x12, 0x34};
  assert(JuraProtocol::decodeBcdPin(bcd, pin));
  assert(pin[0] == '1' && pin[1] == '2' && pin[2] == '3' && pin[3] == '4');
  const uint8_t leadingZero[] = {0x00, 0x01};
  assert(JuraProtocol::decodeBcdPin(leadingZero, pin));
  assert(std::strcmp(pin, "0001") == 0);
  const uint8_t invalidBcd[] = {0xFA, 0x34};
  assert(!JuraProtocol::decodeBcdPin(invalidBcd, pin));
  std::puts("JuraProtocol header tests passed");
}
