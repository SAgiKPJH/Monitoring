/*
 * NRF24L01 link test - Arduino Uno R3 (RECEIVER)
 * ----------------------------------------------
 * Receives the counter from the Pico and prints it over USB serial, with
 * received/missed statistics. Same radio config + wiring as production.
 *
 * Board: "Arduino Uno"   Lib: RF24 (TMRh20)
 *
 * Wiring (NRF24L01 -> Uno):
 *   VCC -> 3V3 (NEVER 5V)   GND -> GND
 *   CE  -> D9   CSN -> D10   SCK -> D13   MOSI -> D11   MISO -> D12
 *
 * IMPORTANT (UNO+WiFi combo board):
 *   Set DIP switches to USB <-> ATmega (commonly 3+4 ON) so the USB Serial
 *   Monitor works. The ESP8266 is NOT needed for this radio test.
 *   Open Serial Monitor @115200.
 *
 * NOTE: no LED indicator on purpose - LED_BUILTIN is D13 = SPI SCK here, so
 *       toggling it would corrupt the SPI bus. Watch the serial output instead.
 */
#include <SPI.h>
#include <RF24.h>

#define RF_CE_PIN  9
#define RF_CSN_PIN 10

const uint8_t address[6] = "Node1";   // MUST match the transmitter
RF24 radio(RF_CE_PIN, RF_CSN_PIN);

// Test payload (same 8 bytes on both ends).
struct TestPacket {
  uint32_t counter;
  uint32_t senderMillis;
};

uint32_t received = 0, missed = 0, lastCounter = 0;
bool first = true;

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println(F("=== Uno NRF24L01 RX test ==="));
  if (!radio.begin()) {
    Serial.println(F("RF24 init FAILED - check wiring/power (3V3, CE=D9, CSN=D10)"));
    while (true) { }
  }
  radio.setAutoAck(false);            // one-way link, no ACK (matches the MicroPython Pico)
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(101);              // above the WiFi band -> less 2.4GHz interference
  radio.setPayloadSize(sizeof(TestPacket));
  radio.openReadingPipe(1, address);
  radio.startListening();             // receiver mode

  Serial.print(F("payload size = ")); Serial.println(sizeof(TestPacket));
  Serial.println(F("waiting for packets from the Pico..."));
}

void loop() {
  if (radio.available()) {
    TestPacket p;
    radio.read(&p, sizeof(p));
    received++;

    // gap detection (counts skipped sequence numbers)
    if (!first && p.counter > lastCounter + 1) {
      missed += (p.counter - lastCounter - 1);
    }
    first = false;
    lastCounter = p.counter;

    Serial.print(F("RX #"));         Serial.print(p.counter);
    Serial.print(F("  senderMs="));  Serial.print(p.senderMillis);
    Serial.print(F("   [recv="));    Serial.print(received);
    Serial.print(F(" missed="));     Serial.print(missed);
    Serial.println(F("]"));
  }
}
