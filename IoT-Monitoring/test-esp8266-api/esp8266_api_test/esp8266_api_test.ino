/*
 * ESP8266 -> API test
 * -------------------
 * Verifies ONLY the ESP8266 -> ASP.NET API path (no Uno / NRF / sensor).
 * Connects to WiFi, POSTs a fake reading every few seconds, and prints the
 * HTTP status + response body so you can confirm the API stores it (201).
 *
 * Board: "Generic ESP8266 Module" (combo board: DIP USB<->ESP8266 to flash + monitor).
 * Serial Monitor @115200.
 *
 * Prereqs: docker stack running (docker compose up -d) and reachable on the LAN.
 */
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

// ---- configuration ----
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* API_URL   = "http://172.30.1.42:8080/api/readings";  // docker host IP (not localhost)
const char* API_KEY   = "";           // set only if the API has API_KEY configured
const char* DEVICE_ID = "esp-test";

#define POST_PERIOD_MS 5000

uint32_t seq = 0;

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("WiFi connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000UL) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi OK, IP=");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi FAILED - check SSID/PASS");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== ESP8266 -> API test ===");
  Serial.print("API_URL = ");
  Serial.println(API_URL);
  connectWifi();
}

void loop() {
  connectWifi();
  if (WiFi.status() != WL_CONNECTED) {
    delay(POST_PERIOD_MS);
    return;
  }

  seq++;
  // fake reading (no sensor needed) - matches the API DTO
  float t = 25.0 + (seq % 10) * 0.1;
  float h = 50.0 + (seq % 5);
  String json = String("{\"deviceId\":\"") + DEVICE_ID +
                "\",\"temperature\":" + String(t, 2) +
                ",\"humidity\":" + String(h, 2) +
                ",\"light\":" + String(500 + (int)(seq % 100)) +
                ",\"lightPercent\":" + String((int)(seq % 100)) +
                ",\"sequence\":" + String(seq) + "}";

  WiFiClient client;
  HTTPClient http;
  if (http.begin(client, API_URL)) {
    http.addHeader("Content-Type", "application/json");
    if (strlen(API_KEY) > 0) http.addHeader("X-Api-Key", API_KEY);

    int code = http.POST(json);
    String resp = http.getString();

    Serial.print("POST #");   Serial.print(seq);
    Serial.print(" -> HTTP "); Serial.print(code);
    Serial.print("  body=");   Serial.println(resp);
    http.end();
  } else {
    Serial.println("http.begin() failed - bad URL?");
  }

  delay(POST_PERIOD_MS);
}
