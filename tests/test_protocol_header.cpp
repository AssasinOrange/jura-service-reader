#include "../firmware/JuraPinReader/JuraProtocol.h"

#include <cassert>
#include <cstdint>
#include <cstdio>

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

  char pin[5];
  const uint8_t bcd[] = {0x12, 0x34};
  assert(JuraProtocol::decodeBcdPin(bcd, pin));
  assert(pin[0] == '1' && pin[1] == '2' && pin[2] == '3' && pin[3] == '4');
  std::puts("JuraProtocol header tests passed");
}
