/*
 * ESP8266 - WiFi uplink
 * ---------------------
 * Reads JSON lines coming from the Uno R3 over the UART and forwards each
 * one unchanged as an HTTP POST to the ASP.NET Core API.
 *
 * Board:   "Generic ESP8266 Module" (or the matching combo-board profile)
 * Libs:    ESP8266 core (ESP8266WiFi, ESP8266HTTPClient) - bundled with the core
 *
 * The line received from the Uno is already valid JSON that matches the API
 * contract, so we POST it verbatim (no parsing / no ArduinoJson needed).
 *
 * Combo board note: the ESP8266 talks to the ATmega over the same UART used
 * for USB. Keep the Uno sketch baud (9600) in sync with ESP_UART_BAUD below.
 *
 * Build footprint (ESP8266 core):
 *   RAM    ~28.3 KB / 80 KB  (35%)
 *   IRAM   ~59.7 KB / 64 KB  (91%)  <- high but < 100% => OK (WiFi + HTTP stack uses IRAM)
 *   Flash  ~254 KB / 1 MB    (24%)
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

// ---- configuration ----
const char* WIFI_SSID = "KT_GiGA_C2C0";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";   // <- 실제 WiFi 비밀번호로 변경 (test 스케치와 동일)

// Point this at the machine running docker-compose (the API host:port).
const char* API_URL   = "http://172.30.1.42:8080/api/readings";

// Set only if the API has API_KEY configured; otherwise leave empty.
const char* API_KEY   = "";

#define ESP_UART_BAUD 9600    // must match the Uno sketch

String lineBuffer;

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000UL) {
    delay(500);
  }
}

void postReading(const String& json) {
  connectWifi();
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  if (http.begin(client, API_URL)) {
    http.addHeader("Content-Type", "application/json");
    if (strlen(API_KEY) > 0) {
      http.addHeader("X-Api-Key", API_KEY);
    }
    http.POST(json);   // fire-and-forget; response ignored
    http.end();
  }
}

void setup() {
  Serial.begin(ESP_UART_BAUD);   // input from the Uno
  delay(200);
  lineBuffer.reserve(192);
  connectWifi();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      lineBuffer.trim();
      if (lineBuffer.startsWith("{")) {
        postReading(lineBuffer);
      }
      lineBuffer = "";
    } else if (c != '\r') {
      lineBuffer += c;
      if (lineBuffer.length() > 250) {   // overflow guard against garbage
        lineBuffer = "";
      }
    }
  }
}
