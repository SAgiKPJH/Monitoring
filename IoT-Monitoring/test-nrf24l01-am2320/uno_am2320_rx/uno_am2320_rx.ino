/*
 * AM2320 test receiver - Arduino Uno R3 (RF24). One-way, auto-ACK off.
 * Wiring (NRF24L01 -> Uno): CE=D9 CSN=D10 SCK=D13 MOSI=D11 MISO=D12 VCC=3V3
 * Combo board: DIP switches USB<->ATmega. Serial Monitor @115200.
 */
#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);                  // CE=D9, CSN=D10
const uint8_t address[6] = "Node1"; // MUST match the Pico

struct Payload {                    // 12 bytes, matches struct.pack("<ffI", ...)
  float temperature;
  float humidity;
  uint32_t sequence;
};

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== Uno AM2320 RX ==="));
  if (!radio.begin()) {
    Serial.println(F("RF24 init FAILED - check wiring/power"));
    while (true) { }
  }
  radio.setAutoAck(false);
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(101);
  radio.setPayloadSize(sizeof(Payload));
  radio.openReadingPipe(1, address);
  radio.startListening();
  Serial.println(F("waiting for AM2320 data..."));
}

void loop() {
  if (radio.available()) {
    Payload p;
    radio.read(&p, sizeof(p));
    char t[10], h[10];
    dtostrf(p.temperature, 0, 1, t);   // AVR printf has no %f
    dtostrf(p.humidity, 0, 1, h);
    Serial.print(F("#"));    Serial.print(p.sequence);
    Serial.print(F("  T=")); Serial.print(t); Serial.print(F("C"));
    Serial.print(F("  H=")); Serial.print(h); Serial.println(F("%"));
  }
}
