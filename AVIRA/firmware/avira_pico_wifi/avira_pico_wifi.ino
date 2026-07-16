/*
 * AVIRA Pico W Firmware – Fixed Version
 * =======================================
 * Fixes:
 *   1. Session ID is saved from server response and REUSED every upload
 *      (all readings go into one session file per power-on)
 *   2. cow_id and breed are sent with every payload
 *   3. heart_rate and spo2 are only included when the sensor reads a VALID value
 *      (finger must be on sensor – 0 values are not sent to avoid false alerts)
 *   4. Added ArduinoJson for reliable JSON parsing of server response
 *
 * Hardware: Raspberry Pi Pico W
 * Sensors : MAX30102 (HR + SpO2) + MPU6500 (Accelerometer)
 * Network : WiFi → HTTPS POST to Flask backend on Render
 *
 * ─── Arduino IDE Libraries needed ─────────────────────────────────────────
 *   Tools → Manage Libraries:
 *     • SparkFun MAX3010x Sensor Library  (by SparkFun Electronics)
 *     • ArduinoJson                        (by Benoit Blanchon, version 6.x)
 *   Board: Raspberry Pi Pico W  (Earle Philhower core)
 * ──────────────────────────────────────────────────────────────────────────
 */

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "MAX30105.h"
#include "spo2_algorithm.h"
#include <math.h>

// ════════════════════════════════════════════════════
//  ★  ONLY EDIT THESE LINES  ★
// ════════════════════════════════════════════════════
const char* ssid       = "HANAMAR";       // 2.4 GHz WiFi name
const char* password   = "12341234";      // WiFi password
const char* COW_ID     = "COW_PICO_01";  // Animal tag shown in app
const char* BREED      = "GIR";           // Breed code for AI analysis
// ════════════════════════════════════════════════════
// Breed codes: GIR / SAHIWAL / HF / JERSEY / MURRAH
// ════════════════════════════════════════════════════

// Server endpoint (your hosted Render server – do not change)
const char* serverUrl = "https://final-qj39.onrender.com/api/v1/device/upload";

// ─── Session state ────────────────────────────────────────────────────────
// The server assigns a session_id on first upload.
// We store it here and send it with EVERY subsequent upload so all readings
// from this power-on go into ONE session file (not a new file each time).
String sessionId = "";   // empty until server assigns one

// ─── MPU6500 ─────────────────────────────────────────────────────────────
#define MPU_ADDR 0x68
int16_t axRaw, ayRaw, azRaw;
float   ax, ay, az, motionMagnitude;

// ─── MAX30102 ─────────────────────────────────────────────────────────────
MAX30105 particleSensor;

#if defined(__AVR_ATmega328P__) || defined(__AVR_ATmega168__)
  uint16_t irBuffer[100];
  uint16_t redBuffer[100];
#else
  uint32_t irBuffer[100];
  uint32_t redBuffer[100];
#endif

int32_t bufferLength = 100;
int32_t spo2;
int8_t  validSPO2;
int32_t heartRate;
int8_t  validHeartRate;

// ─── WiFi helpers ─────────────────────────────────────────────────────────

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi FAILED – retrying next cycle");
  }
}

// ─── Upload to server ─────────────────────────────────────────────────────

void uploadData() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("No WiFi – skipping upload");
    connectWiFi();
    return;
  }

  // ── Build JSON payload ─────────────────────────────────────────────────
  // Only include HR/SpO2 when the sensor gives a valid reading
  // (finger must be placed on MAX30102 for valid values)
  StaticJsonDocument<384> doc;

  doc["cow_id"] = COW_ID;
  doc["breed"]  = BREED;

  if (validHeartRate && heartRate >= 20 && heartRate <= 300) {
    doc["heartRate"]       = heartRate;
    doc["heartRateValid"]  = true;
  }
  // If no valid HR: server treats it as unknown (no false 0-BPM alert)

  if (validSPO2 && spo2 >= 50 && spo2 <= 100) {
    doc["spo2"]      = spo2;
    doc["spo2Valid"] = true;
  }
  // If no valid SpO2: server treats it as unknown

  doc["accelX"]          = roundf(ax * 1000.0f) / 1000.0f;
  doc["accelY"]          = roundf(ay * 1000.0f) / 1000.0f;
  doc["accelZ"]          = roundf(az * 1000.0f) / 1000.0f;
  doc["motionMagnitude"] = roundf(motionMagnitude * 1000.0f) / 1000.0f;

  // ★ KEY FIX: send sessionId so server keeps all readings in ONE session
  if (sessionId.length() > 0) {
    doc["session_id"] = sessionId;
  }

  String payload;
  serializeJson(doc, payload);

  Serial.println("\n--- Outgoing JSON ---");
  Serial.println(payload);

  // ── HTTPS POST ────────────────────────────────────────────────────────
  WiFiClientSecure client;
  client.setInsecure();   // Skip cert verification (Render cert is valid but
                          // storing root CA on Pico requires extra setup)
  HTTPClient http;
  http.begin(client, serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "AVIRA-PicoW/2.0");
  http.setTimeout(15000);   // 15s – Render free tier can be slow to wake

  int code = http.POST(payload);
  Serial.print("Render Server Response Code: ");
  Serial.println(code);

  if (code == 200 || code == 201) {
    String responseBody = http.getString();
    Serial.println("Server Body: " + responseBody);

    // ★ Parse session_id from server response ──────────────────────────
    // On first upload: server creates new session_id → we save it
    // On subsequent uploads: server returns same session_id → we confirm it
    StaticJsonDocument<512> resp;
    DeserializationError err = deserializeJson(resp, responseBody);
    if (!err) {
      if (resp.containsKey("session_id")) {
        String newSessionId = resp["session_id"].as<String>();
        if (sessionId != newSessionId) {
          sessionId = newSessionId;
          Serial.println("★ Session ID saved: " + sessionId);
          Serial.println("  All future uploads will use this session.");
        }
      }
    }

  } else if (code < 0) {
    Serial.println("HTTP error: " + http.errorToString(code));
    Serial.println("(Render may be waking up – next attempt in 5 seconds)");
  } else {
    // 4xx error – print the body for debugging
    Serial.println("Server returned error: " + http.getString());
  }

  http.end();
}

// ─── MPU6500 init & read ──────────────────────────────────────────────────

void initMPU6500() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B); Wire.write(0x00);   // wake up
  Wire.endTransmission();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1C); Wire.write(0x00);   // ±2g
  Wire.endTransmission(true);
  Serial.println("MPU6500 Initialized");
}

void readMPU6500() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 6);
  if (Wire.available() == 6) {
    axRaw = (Wire.read() << 8) | Wire.read();
    ayRaw = (Wire.read() << 8) | Wire.read();
    azRaw = (Wire.read() << 8) | Wire.read();
    ax = axRaw / 16384.0f;
    ay = ayRaw / 16384.0f;
    az = azRaw / 16384.0f;
    motionMagnitude = sqrtf(ax*ax + ay*ay + az*az);
  }
}

// ─── Setup ────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n============================");
  Serial.println("  AVIRA Pico W v2.0");
  Serial.println("  Server: Render (HTTPS)");
  Serial.println("============================");

  Wire.setSDA(0);
  Wire.setSCL(1);
  Wire.begin();

  // MAX30102 init
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 NOT FOUND! Check wiring.");
    while (1) { delay(200); }
  }
  particleSensor.setup(60, 4, 2, 100, 411, 4096);
  Serial.println("MAX30102 OK");

  initMPU6500();
  connectWiFi();

  // Fill initial 100-sample buffer
  Serial.println("Collecting initial 100 samples...");
  for (byte i = 0; i < 100; i++) {
    while (!particleSensor.available()) particleSensor.check();
    redBuffer[i] = particleSensor.getRed();
    irBuffer[i]  = particleSensor.getIR();
    particleSensor.nextSample();
  }
  maxim_heart_rate_and_oxygen_saturation(
    irBuffer, bufferLength, redBuffer,
    &spo2, &validSPO2, &heartRate, &validHeartRate);

  Serial.println("Ready! Starting measurement loop.");
  Serial.println("Place finger on sensor for HR/SpO2 readings.");
  Serial.println("Motion data (MPU6500) always sent.");
}

// ─── Main loop ────────────────────────────────────────────────────────────

void loop() {
  // Reconnect WiFi if dropped
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  // Slide window: discard oldest 25, collect 25 new samples
  for (byte i = 25; i < 100; i++) {
    redBuffer[i - 25] = redBuffer[i];
    irBuffer[i - 25]  = irBuffer[i];
  }
  for (byte i = 75; i < 100; i++) {
    while (!particleSensor.available()) particleSensor.check();
    redBuffer[i] = particleSensor.getRed();
    irBuffer[i]  = particleSensor.getIR();
    particleSensor.nextSample();
  }

  maxim_heart_rate_and_oxygen_saturation(
    irBuffer, bufferLength, redBuffer,
    &spo2, &validSPO2, &heartRate, &validHeartRate);

  readMPU6500();

  // Print to Serial Monitor
  Serial.print("HR: ");
  if (validHeartRate) { Serial.print(heartRate); Serial.print(" BPM"); }
  else Serial.print("-- (place finger on sensor)");
  Serial.print("  |  SpO2: ");
  if (validSPO2) { Serial.print(spo2); Serial.print("%"); }
  else Serial.print("--");
  Serial.print("  |  Motion: ");
  Serial.println(motionMagnitude, 3);

  // Upload to server
  uploadData();

  delay(2000);  // 2-second cycle
}