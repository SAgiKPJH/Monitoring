/*
 * NRF24L01 link test - Raspberry Pi Pico (TRANSMITTER)
 * ----------------------------------------------------
 * Sends an incrementing counter to the Uno R3 once per second using the SAME
 * radio config + wiring as the production firmware. If this test passes, the
 * real wiring/config is correct.
 *
 * Board: "Raspberry Pi Pico" (arduino-pico core by earlephilhower)
 * Lib:   RF24 (TMRh20)
 *
 * Wiring (NRF24L01 -> Pico, SPI0):
 *   VCC -> 3V3 (NEVER 5V)     GND -> GND
 *   CE  -> GP14   CSN -> GP15
 *   SCK -> GP6    MOSI -> GP7  MISO -> GP4
 *   (10~100uF cap across VCC/GND strongly recommended)
 *
 * Open Serial Monitor @115200 to watch TX results.
 */
#include <SPI.h>
#include <RF24.h>

#define RF_CE_PIN  14
#define RF_CSN_PIN 15

const uint8_t address[6] = "Node1";   // MUST match the receiver
RF24 radio(RF_CE_PIN, RF_CSN_PIN);

// Test payload (same 8 bytes on both ends).
struct TestPacket {
  uint32_t counter;
  uint32_t senderMillis;
};

uint32_t counter = 0;
uint32_t okCount = 0, failCount = 0;

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 2000) { }   // wait briefly for USB monitor

  // Route SPI0 to the wired pins BEFORE radio.begin().
  SPI.setRX(4);    // MISO (GP4)
  SPI.setSCK(6);   // SCK  (GP6)
  SPI.setTX(7);    // MOSI (GP7)
  SPI.begin();

  Serial.println();
  Serial.println(F("=== Pico NRF24L01 TX test ==="));
  if (!radio.begin()) {
    Serial.println(F("RF24 init FAILED - check SPI pins (4/6/7), CE/CSN, 3V3 power, caps"));
    while (true) { delay(1000); }
  }
  radio.setAutoAck(false);           // one-way link, no ACK (keeps it identical to the MicroPython Pico)
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(76);
  radio.setPayloadSize(sizeof(TestPacket));
  radio.openWritingPipe(address);
  radio.stopListening();              // transmitter mode

  Serial.print(F("payload size = ")); Serial.println(sizeof(TestPacket));
  Serial.println(F("sending 1 packet/sec  (confirm on the Uno's RX #n)"));
}

void loop() {
  TestPacket p;
  p.counter = ++counter;
  p.senderMillis = millis();

  bool ok = radio.write(&p, sizeof(p));
  if (ok) okCount++; else failCount++;

  Serial.print(F("TX #"));   Serial.print(p.counter);
  Serial.print(F("  -> "));  Serial.print(ok ? F("sent") : F("TX FAIL"));
  Serial.print(F("   [sent=")); Serial.print(okCount);
  Serial.print(F(" fail="));  Serial.print(failCount);
  Serial.println(F("]"));

  delay(1000);
}
