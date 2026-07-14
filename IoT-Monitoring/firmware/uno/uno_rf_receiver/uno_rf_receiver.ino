/*
 * Arduino Uno R3 (ATmega328) - NRF24L01 receiver -> ESP8266 uplink
 * ----------------------------------------------------------------
 * Receives the sensor struct over NRF24L01 and forwards it as ONE line
 * of JSON over the hardware UART to the on-board ESP8266.
 *
 * Board:   "Arduino Uno"  (CH340G USB-serial)
 * Libs:    "RF24" (TMRh20)
 *
 * IMPORTANT - UNO+WiFi combo board DIP switches:
 *   This sketch sends JSON to the ESP8266 over the ATmega hardware UART (D0/D1).
 *   Set the on-board DIP switches so that ATmega TX/RX <-> ESP8266 RX/TX
 *   (commonly switches 1+2 ON, 3+4 OFF). Because D0/D1 are then wired to the
 *   ESP, the USB serial monitor can NOT be used at the same time.
 *   To flash the ATmega: switches 3+4 ON (USB <-> ATmega), then flip back.
 *
 * Wiring (NRF24L01 -> Uno):
 *   VCC  -> 3V3   (NEVER 5V; add a 10uF cap across VCC/GND for stability)
 *   GND  -> GND
 *   CE   -> D9
 *   CSN  -> D10
 *   SCK  -> D13
 *   MOSI -> D11
 *   MISO -> D12
 *   IRQ  -> (unused)
 */

#include <SPI.h>
#include <RF24.h>

#define RF_CE_PIN   9
#define RF_CSN_PIN  10

// deviceId is set by the Pico and forwarded as-is (no formatting here).

// Radio address — MUST match the Pico transmitter.
const uint8_t address[6] = "Node1";

RF24 radio(RF_CE_PIN, RF_CSN_PIN);

// Wire payload — identical layout on Pico (TX) and Uno (RX). Do NOT pack/reorder.
struct SensorPayload {
  float    temperature;
  float    humidity;
  uint32_t sequence;
  uint16_t light;
  uint16_t lightPercent;
  float    battery;         // 18650 voltage (V)
  uint16_t batteryPercent;  // 0..100
  char     deviceId[6];     // id set by the Pico (forwarded as-is, <=5 chars)
};

void setup() {
  Serial.begin(9600);   // -> ESP8266 (must match the ESP sketch baud)

  if (!radio.begin()) {
    // Serial goes to the ESP here, so signal failure on the on-board LED.
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);
  }
  radio.setAutoAck(false);    // one-way, no ACK (matches the MicroPython Pico)
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(101);      // above the WiFi band -> less 2.4GHz interference
  radio.setPayloadSize(sizeof(SensorPayload));
  radio.openReadingPipe(1, address);
  radio.startListening();   // receiver mode
}

void loop() {
  if (radio.available()) {
    SensorPayload p;
    radio.read(&p, sizeof(p));

    // Skip empty/garbage payloads (all sensor values 0) — do not forward to the ESP.
    if (p.temperature == 0.0f && p.humidity == 0.0f && p.light == 0 && p.lightPercent == 0) {
      return;
    }

    // AVR sprintf has no %f -> format floats with dtostrf().
    char tbuf[12], hbuf[12], bbuf[12];
    dtostrf(p.temperature, 0, 2, tbuf);
    dtostrf(p.humidity, 0, 2, hbuf);
    dtostrf(p.battery, 0, 2, bbuf);
    p.deviceId[sizeof(p.deviceId) - 1] = '\0';   // ensure null-terminated; id comes from the Pico as-is

    char line[200];
    snprintf(line, sizeof(line),
      "{\"deviceId\":\"%s\",\"temperature\":%s,\"humidity\":%s,"
      "\"light\":%u,\"lightPercent\":%u,\"battery\":%s,\"batteryPercent\":%u,\"sequence\":%lu}",
      p.deviceId, tbuf, hbuf,
      (unsigned)p.light, (unsigned)p.lightPercent, bbuf, (unsigned)p.batteryPercent, (unsigned long)p.sequence);

    Serial.println(line);   // one JSON object per line -> ESP8266
  }
}
