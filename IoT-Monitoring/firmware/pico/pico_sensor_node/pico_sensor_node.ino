/*
 * Raspberry Pi Pico - sensor node (NRF24L01 transmitter)
 * ------------------------------------------------------
 * Reads a DHT temperature/humidity sensor + a CdS light sensor and
 * transmits a fixed-size struct over NRF24L01 to the Uno R3 receiver.
 *
 * Board:   Raspberry Pi Pico (arduino-pico core by earlephilhower)
 *          Tools > Board > "Raspberry Pi Pico/RP2040" > "Raspberry Pi Pico"
 * Libs:    "RF24" (TMRh20), "DHT sensor library" (Adafruit) + "Adafruit Unified Sensor"
 *
 * Wiring (Pico GPIO):
 *   NRF24L01    Pico
 *   --------    ----
 *   VCC    ->   3V3 (OUT, pin 36)      (NEVER 5V)
 *   GND    ->   GND
 *   CE     ->   GP14
 *   CSN    ->   GP15
 *   SCK    ->   GP6   (SPI0 SCK)
 *   MOSI   ->   GP7   (SPI0 TX)
 *   MISO   ->   GP4   (SPI0 RX)
 *   IRQ    ->   (unused)
 *
 *   DHT (4-pin)  Pico
 *   VCC    ->   3V3
 *   DATA   ->   GP2    (moved off GP15, which is now NRF CSN; add 10k pull-up DATA->VCC if no on-board resistor)
 *   GND    ->   GND
 *
 *   CdS light sensor (voltage divider):
 *   3V3 -- [CdS] --+-- GP26 (ADC0)
 *                  |
 *                 [10k] -- GND
 *   (more light -> higher voltage on GP26 -> higher ADC value)
 */

#include <SPI.h>
#include <RF24.h>
#include <DHT.h>

// ---- configuration ----
#define DHT_PIN     2          // moved off GP15 (now NRF CSN)
#define DHT_TYPE    DHT11      // change to DHT22 if you use an AM2302
#define LDR_PIN     26         // GP26 = ADC0
#define RF_CE_PIN   14
#define RF_CSN_PIN  15
#define SEND_PERIOD 5000UL     // ms between transmissions

// Radio address — MUST match the Uno receiver.
const uint8_t address[6] = "Node1";

RF24 radio(RF_CE_PIN, RF_CSN_PIN);
DHT  dht(DHT_PIN, DHT_TYPE);

// Wire payload — identical layout on Pico (TX) and Uno (RX). Do NOT pack/reorder.
struct SensorPayload {
  float    temperature;   // degrees Celsius
  float    humidity;      // %RH
  uint32_t sequence;      // increments on every send
  uint16_t light;         // raw ADC 0..1023
  uint16_t lightPercent;  // 0..100 (100 = brightest)
};

uint32_t sequence = 0;

void setup() {
  Serial.begin(115200);
  analogReadResolution(10);   // ADC -> 0..1023
  dht.begin();

  // Route SPI0 to the wired pins (MUST be set before radio.begin()).
  SPI.setRX(4);    // MISO (GP4 = SPI0 RX)
  SPI.setSCK(6);   // SCK  (GP6 = SPI0 SCK)
  SPI.setTX(7);    // MOSI (GP7 = SPI0 TX)
  SPI.begin();

  if (!radio.begin()) {
    Serial.println(F("[pico] RF24 init FAILED - check wiring/power"));
  }
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(76);
  radio.setPayloadSize(sizeof(SensorPayload));
  radio.openWritingPipe(address);
  radio.stopListening();      // transmitter mode

  Serial.println(F("[pico] sensor node ready"));
}

void loop() {
  SensorPayload p;

  float h = dht.readHumidity();
  float t = dht.readTemperature();   // Celsius
  if (isnan(h) || isnan(t)) {
    Serial.println(F("[pico] DHT read failed"));
    h = 0.0f;
    t = 0.0f;
  }

  int raw = analogRead(LDR_PIN);     // 0..1023
  int pct = map(raw, 0, 1023, 0, 100);

  p.temperature  = t;
  p.humidity     = h;
  p.sequence     = ++sequence;
  p.light        = (uint16_t)raw;
  p.lightPercent = (uint16_t)pct;

  bool ok = radio.write(&p, sizeof(p));

  Serial.print(F("[pico] seq=")); Serial.print(p.sequence);
  Serial.print(F(" t="));         Serial.print(t, 2);
  Serial.print(F(" h="));         Serial.print(h, 2);
  Serial.print(F(" light="));     Serial.print(raw);
  Serial.print(F(" tx="));        Serial.println(ok ? F("OK") : F("FAIL"));

  delay(SEND_PERIOD);
}
