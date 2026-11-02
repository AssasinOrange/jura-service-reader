#pragma once

#include <stdint.h>
#include <string.h>

namespace JuraProtocol {

inline uint8_t encodeCarrier(uint8_t value, uint8_t pair) {
  return static_cast<uint8_t>(
      0xDBu | (((value >> (2u * pair)) & 1u) << 2u) |
      (((value >> (2u * pair + 1u)) & 1u) << 5u));
}

inline bool looksLikeCarrier(uint8_t value) {
  // Both 0x5B/0x5F/... and 0xDB/0xDF/... forms satisfy this mask.
  return (value & 0x5Bu) == 0x5Bu;
}

inline uint8_t decodeGroup(const uint8_t group[4]) {
  uint8_t value = 0;
  for (uint8_t pair = 0; pair < 4; ++pair) {
    value |= static_cast<uint8_t>(((group[pair] >> 2u) & 1u) << (2u * pair));
    value |= static_cast<uint8_t>(((group[pair] >> 5u) & 1u) << (2u * pair + 1u));
  }
  return value;
}

inline int8_t hexNibble(char value) {
  if (value >= '0' && value <= '9') return static_cast<int8_t>(value - '0');
  if (value >= 'A' && value <= 'F') return static_cast<int8_t>(value - 'A' + 10);
  if (value >= 'a' && value <= 'f') return static_cast<int8_t>(value - 'a' + 10);
  return -1;
}

inline bool parseRtLine(const char *line, uint8_t output[32]) {
  // Check the complete length before indexing a possibly truncated string.
  if (!line || strlen(line) != 69 || strncmp(line, "rt:", 3) != 0) return false;
  for (uint8_t index = 0; index < 32; ++index) {
    const int8_t high = hexNibble(line[3 + index * 2]);
    const int8_t low = hexNibble(line[4 + index * 2]);
    if (high < 0 || low < 0) return false;
    output[index] = static_cast<uint8_t>((high << 4) | low);
  }
  return line[67] == '\r' && line[68] == '\n' && line[69] == '\0';
}

inline bool decodeBcdPin(const uint8_t input[2], char output[5]) {
  const uint8_t nibbles[4] = {
      static_cast<uint8_t>(input[0] >> 4), static_cast<uint8_t>(input[0] & 15u),
      static_cast<uint8_t>(input[1] >> 4), static_cast<uint8_t>(input[1] & 15u)};
  for (uint8_t index = 0; index < 4; ++index) {
    if (nibbles[index] > 9) return false;
    output[index] = static_cast<char>('0' + nibbles[index]);
  }
  output[4] = '\0';
  return true;
}

}  // namespace JuraProtocol
