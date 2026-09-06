/* JuraFullCapture v4 - Arduino Mega 2560, manual TY: or 128-block RT sweep plus overlap check.
   DE-9 CONTACT NUMBERS (verified on the documented GIGA X8c):
   Jura 1 -> own 1k resistor -> Mega 19; Jura 2 -> Mega GND;
   Jura 3 -> own 1k resistor -> Mega 16 (white); Mega 17 disconnected.
   Jura 4 -> own 1k resistor -> Mega 15 (NOT the Mega 5V rail).
   Remove the 16-17 jumper. Unused RX17 has its internal pull-up enabled.
   Leave Mega 18/14 disconnected. Remove old test/loopback jumpers.
   Connect with power off. Requires the established isolated 0-5V interface.

   Upload, CLOSE SERIAL MONITOR, then run Start-Capture.cmd on Windows.
   PC link 500000 baud; three Jura inputs 9600 8N1. Binary output, not text.
   Receivers start on USB 'G', stop on USB 'S'; neither command reaches Jura.
   USB 'T' sends TY:\r\n; USB 'R' requests RT:0000, RT:0001, then RT:0000 through RT:07F0; one sweep or TY per capture, encoded with the
   legacy Q42 two-payload-bits-per-carrier algorithm. Only Mega 16 transmits,
   only during this query; it returns to input afterwards. No other commands.

   Every received UART byte is queued with ISR-time micros(), contact and
   hardware error flags. A full queue drops bytes AND increments per-contact
   loss counters. DOR reports hardware loss events, not exact lost-byte counts.
   This is a UART capture, not an analogue waveform/logic-analyser recording.

   Wire format: JLG1 | type:u8 | length:u16le | sequence:u32le | payload | crc:u16le.
   CRC-16/CCITT-FALSE covers type through payload. Max payload 168 bytes.
   D: records of [micros:u32le, contact:u8, UCSRnA&0x1C:u8, data:u8].
   H: idle hello, A: start, T: periodic status, E: stopped/drained footer,
   K: timestamp u32le + exact nine-byte RT command (13-byte payload).
   Q: TY query marker; U: RT:0000 query marker. Neither confirms acceptance.
   H/A/T/E/Q/U payload: millis:u32le, then three u32le each for received, queue
   drops, framing errors and hardware overruns, contacts in order 1,3,4.
   Micros wraps about every 71.6 minutes; status millis disambiguates wraps.
*/
#include <Arduino.h>
#include <avr/interrupt.h>
#include <util/atomic.h>
#if !defined(__AVR_ATmega2560__)
#error "Select Arduino Mega or Mega 2560 / ATmega2560."
#endif

struct __attribute__((packed)) Record { uint32_t us; uint8_t contact, flags, data; };
static_assert(sizeof(Record) == 7, "Record layout must be seven bytes");
static volatile Record queueData[512];
static volatile uint16_t head=0, tail=0;
static volatile uint32_t received[3]={}, lost[3]={}, frameErrors[3]={}, overruns[3]={};
static uint32_t sequence=0, lastStatus=0, lastPacket=0;
static bool active=false;
static bool querySent=false;
static bool sweepActive=false;
static uint16_t sweepBlock=0;
static uint32_t nextReadAt=0;
static volatile uint32_t lastReplyAt=0;

static void onByte(uint8_t index, uint8_t contact, uint8_t status, uint8_t data) {
  const uint32_t timestamp=micros();
  ++received[index];
  if(index==0) lastReplyAt=millis();
  if (status & 0x10) ++frameErrors[index];
  if (status & 0x08) ++overruns[index];
  const uint16_t next=(head+1)&511;
  if (next==tail) { ++lost[index]; return; }
  queueData[head].us=timestamp;
  queueData[head].contact=contact;
  queueData[head].flags=status&0x1C;
  queueData[head].data=data;
  head=next;
}
ISR(USART1_RX_vect) { uint8_t s=UCSR1A; uint8_t b=UDR1; onByte(0,1,s,b); }
ISR(USART2_RX_vect) { uint8_t s=UCSR2A; uint8_t b=UDR2; onByte(1,3,s,b); }
ISR(USART3_RX_vect) { uint8_t s=UCSR3A; uint8_t b=UDR3; onByte(2,4,s,b); }

static uint16_t crcByte(uint16_t crc, uint8_t b) {
  crc ^= uint16_t(b)<<8;
  for (uint8_t i=0;i<8;++i) crc=(crc&0x8000)?(crc<<1)^0x1021:crc<<1;
  return crc;
}
static void sendFrame(uint8_t type, const uint8_t* payload, uint16_t size) {
  const uint8_t magic[4]={'J','L','G','1'};
  uint8_t header[7]={type,uint8_t(size),uint8_t(size>>8),
    uint8_t(sequence),uint8_t(sequence>>8),uint8_t(sequence>>16),uint8_t(sequence>>24)};
  ++sequence;
  uint16_t crc=0xFFFF;
  for (uint8_t b:header) crc=crcByte(crc,b);
  for (uint16_t i=0;i<size;++i) crc=crcByte(crc,payload[i]);
  Serial.write(magic,4); Serial.write(header,7); Serial.write(payload,size);
  Serial.write(uint8_t(crc)); Serial.write(uint8_t(crc>>8));
}
static void sendStatus(uint8_t type) {
  uint32_t s[13]; s[0]=millis();
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    for (uint8_t i=0;i<3;++i) {
      s[1+i]=received[i]; s[4+i]=lost[i];
      s[7+i]=frameErrors[i]; s[10+i]=overruns[i];
    }
  }
  sendFrame(type,reinterpret_cast<uint8_t*>(s),sizeof(s));
}
static uint16_t pending() {
  uint16_t n;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { n=(head-tail)&511; }
  return n;
}
static void sendData() {
  Record records[24]; uint8_t n=0;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    // Copy at most 24 records; no serial output while interrupts are disabled.
    while (n<24 && tail!=head) {
      records[n].us=queueData[tail].us;
      records[n].contact=queueData[tail].contact;
      records[n].flags=queueData[tail].flags;
      records[n].data=queueData[tail].data;
      tail=(tail+1)&511; ++n;
    }
  }
  if (n) sendFrame('D',reinterpret_cast<uint8_t*>(records),uint16_t(n)*7);
  lastPacket=millis();
}
static void startCapture() {
  if (active) return;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    head=tail=0;
    for(uint8_t i=0;i<3;++i) received[i]=lost[i]=frameErrors[i]=overruns[i]=0;
  }
  sendStatus('A');
  // 16 MHz / (16*(103+1)) = 9615 baud. Start with RX only.
  UCSR1A=0; UBRR1H=0; UBRR1L=103; UCSR1C=_BV(UCSZ11)|_BV(UCSZ10);
  UCSR2A=0; UBRR2H=0; UBRR2L=103; UCSR2C=_BV(UCSZ21)|_BV(UCSZ20);
  UCSR3A=0; UBRR3H=0; UBRR3L=103; UCSR3C=_BV(UCSZ31)|_BV(UCSZ30);
  UCSR1B=_BV(RXEN1)|_BV(RXCIE1);
  UCSR2B=_BV(RXEN2)|_BV(RXCIE2);
  UCSR3B=_BV(RXEN3)|_BV(RXCIE3);
  active=true;
  querySent=false;
}
static uint8_t carrierByte(uint8_t value, uint8_t pair) {
  // Q42 uses FF with bits 2/5 replaced: fixed bits therefore form DB.
  return uint8_t(0xDB | (((value>>(2*pair))&1U)<<2) |
                        (((value>>(2*pair+1))&1U)<<5));
}
static void transmitCommand(const char* command) {
  UCSR2A=_BV(TXC2); // Clear transmit-complete; normal-speed UART retained.
  UCSR2B|=_BV(TXEN2);
  for(uint8_t c=0;command[c]!=0;++c) {
    for(uint8_t pair=0;pair<4;++pair) {
      while(!(UCSR2A&_BV(UDRE2))) { }
      UDR2=carrierByte(uint8_t(command[c]),pair);
      delay(1);
    }
    delay(14); // Q42's 7ms sender gap plus 7ms caller gap; conservative pacing.
  }
  while(!(UCSR2A&_BV(TXC2))) { }
  UCSR2B&=~_BV(TXEN2);
  pinMode(16,INPUT); digitalWrite(16,LOW);
}
static void manualQuery(bool memoryRead) {
  if (!active || querySent) return;
  querySent=true;
  if(memoryRead) { sweepActive=true; sweepBlock=0; nextReadAt=millis(); }
  else { sendStatus('Q'); transmitCommand("TY:\r\n"); }
}
static void serviceSweep() {
  if(!active || !sweepActive || int32_t(millis()-nextReadAt)<0) return;
  uint32_t last;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { last=lastReplyAt; }
  if(uint32_t(millis()-last)<100 || pending()) return;
  char command[]="RT:0000\r\n";
  // First compare offsets 0000/0001, then 128 blocks at stride 0x10.
  const uint16_t address=sweepBlock<2?sweepBlock:uint16_t((sweepBlock-2)*16);
  for(uint8_t digit=0;digit<4;++digit)
    command[3+digit]="0123456789ABCDEF"[(address>>(12-4*digit))&15];
  uint8_t marker[13];
  uint32_t now=millis();
  for(uint8_t i=0;i<4;++i) marker[i]=uint8_t(now>>(8*i));
  for(uint8_t i=0;i<9;++i) marker[4+i]=uint8_t(command[i]);
  sendFrame('K',marker,sizeof(marker));
  transmitCommand(command);
  nextReadAt=millis()+1500; // Keep servicing capture and stop requests in loop.
  if(++sweepBlock==130) sweepActive=false;
}
static void stopCapture() {
  if (!active) return;
  // Stop further receptions, preserving bytes already in the hardware buffers.
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    UCSR1B&=~_BV(RXCIE1); UCSR2B&=~_BV(RXCIE2); UCSR3B&=~_BV(RXCIE3);
    while(UCSR1A&_BV(RXC1)) { uint8_t s=UCSR1A,b=UDR1; onByte(0,1,s,b); }
    while(UCSR2A&_BV(RXC2)) { uint8_t s=UCSR2A,b=UDR2; onByte(1,3,s,b); }
    while(UCSR3A&_BV(RXC3)) { uint8_t s=UCSR3A,b=UDR3; onByte(2,4,s,b); }
    UCSR1B=0; UCSR2B=0; UCSR3B=0;
  }
  active=false; sweepActive=false;
  while(pending()) sendData();
  sendStatus('E'); Serial.flush();
}
void setup() {
  UCSR1B=0; UCSR2B=0; UCSR3B=0;
  for(uint8_t p=14;p<=19;++p) { pinMode(p,INPUT); digitalWrite(p,LOW); }
  digitalWrite(17,HIGH); // Bias disconnected RX2 idle; never wired to Jura in v4.
  Serial.begin(500000);
  sendStatus('H');
}
void loop() {
  while(Serial.available()) {
    int c=Serial.read();
    if(c=='G') startCapture();
    else if(c=='S') stopCapture();
    else if(c=='T') manualQuery(false);
    else if(c=='R') manualQuery(true);
  }
  serviceSweep();
  uint32_t now=millis();
  if(active && (pending()>=24 || (pending() && uint32_t(now-lastPacket)>=5))) sendData();
  if(uint32_t(now-lastStatus)>=1000) {
    sendStatus(active?'T':'H'); lastStatus=now;
  }
}
