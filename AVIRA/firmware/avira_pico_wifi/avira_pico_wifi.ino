/*
 * AVIRA – Pico W Direct WiFi Firmware
 * =====================================
 * Hardware: Raspberry Pi Pico W
 * Sensors:  MAX30102 (Heart Rate + SpO2) + MPU6500 (Accelerometer)
 * Network:  WiFi → HTTP POST to Flask backend (no BLE/Flutter needed)
 *
 * Libraries required (Arduino IDE):
 *   - arduino-pico core by Earle F. Philhower
 *     (Board Manager URL: https://github.com/earlephilhower/arduino-pico)
 *   - SparkFun MAX3010x Sensor Library
 *   - ArduinoJson (v6)
 *   - WiFi (built-in with arduino-pico core)
 *
 * Board: "Raspberry Pi Pico W" from the RP2040 boards menu
 *
 * Data flow:
 *   Sensor reading → JSON payload → HTTP POST /api/v1/device/upload
 *
 * Edit WIFI_SSID, WIFI_PASS, SERVER_HOST, COW_ID below before uploading.
 */

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "MAX30105.h"
#include "spo2_algorithm.h"
#include <math.h>

// ─────────────────────────────────────────────
//  USER CONFIGURATION  ← Edit these
// ─────────────────────────────────────────────
const char* WIFI_SSID    = "HANAMAR";
const char* WIFI_PASS    = "12341234";
const char* SERVER_HOST  = "http://192.168.1.100:5000";  // Your PC's local IP
const char* API_ENDPOINT = "/api/v1/device/upload";
const char* COW_ID       = "COW_001";
const char* DEVICE_ID    = "PICO_01";
const char* BREED        = "HF";   // See breed list in README

// Upload interval: post data every N cycles (1 cycle ≈ 1 second)
const int UPLOAD_EVERY_N_CYCLES = 5;  // upload every 5 seconds

// ─────────────────────────────────────────────
//  MPU6500 Configuration
// ─────────────────────────────────────────────
#define MPU_ADDR 0x68

int16_t axRaw, ayRaw, azRaw;
float   ax, ay, az;
float   motionMagnitude;

// ─────────────────────────────────────────────
//  MAX30102 Configuration
// ─────────────────────────────────────────────
MAX30105 particleSensor;

#if defined(__AVR_ATmega328P__) || defined(__AVR_ATmega168__)
uint16_t irBuffer[100];
uint16_t redBuffer[100];
#else
uint32_t irBuffer[100];
uint32_t redBuffer[100];
#endif

int32_t bufferLength;
int32_t spo2;
int8_t  validSPO2;
int32_t heartRate;
int8_t  validHeartRate;

// ─────────────────────────────────────────────
//  State
// ─────────────────────────────────────────────
int   cycleCount        = 0;
bool  wifiConnected     = false;
String currentSessionId = "";   // backend assigns session, we reuse it

// LED pin (Pico W onboard LED is on GP25)
#define LED_PIN 25

// ─────────────────────────────────────────────
//  WiFi
// ─────────────────────────────────────────────

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println();
    Serial.print("WiFi connected! IP: ");
    Serial.println(WiFi.localIP());
    // Blink LED 3 times to signal success
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_PIN, HIGH); delay(200);
      digitalWrite(LED_PIN, LOW);  delay(200);
    }
  } else {
    wifiConnected = false;
    Serial.println("\nWiFi connection failed. Will retry on next cycle.");
    // LED stays off
  }
}

bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  wifiConnected = false;
  Serial.println("WiFi lost. Reconnecting...");
  connectWiFi();
  return wifiConnected;
}

// ─────────────────────────────────────────────
//  HTTP Upload
// ─────────────────────────────────────────────

void uploadToServer() {
  if (!ensureWiFi()) {
    Serial.println("Skipping upload – no WiFi.");
    return;
  }

  String url = String(SERVER_HOST) + String(API_ENDPOINT);

  // Build JSON payload
  StaticJsonDocument<512> doc;
  doc["cow_id"]           = COW_ID;
  doc["device_id"]        = DEVICE_ID;
  doc["breed"]            = BREED;
  doc["heart_rate"]       = (int32_t)heartRate;
  doc["heart_rate_valid"] = (bool)validHeartRate;
  doc["spo2"]             = (int32_t)spo2;
  doc["spo2_valid"]       = (bool)validSPO2;
  doc["accel_x"]          = round(ax * 1000.0) / 1000.0;
  doc["accel_y"]          = round(ay * 1000.0) / 1000.0;
  doc["accel_z"]          = round(az * 1000.0) / 1000.0;
  doc["motion_magnitude"] = round(motionMagnitude * 1000.0) / 1000.0;

  // Reuse session ID if already assigned by server
  if (currentSessionId.length() > 0) {
    doc["session_id"] = currentSessionId;
  }

  String payload;
  serializeJson(doc, payload);

  Serial.print("Uploading to: ");
  Serial.println(url);
  Serial.println(payload);

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "AVIRA-PicoW/1.0");
  http.setTimeout(8000);

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    Serial.print("HTTP Response: ");
    Serial.println(httpCode);

    if (httpCode == 201 || httpCode == 200) {
      String response = http.getString();
      Serial.println(response);

      // Parse session_id from response and save it
      StaticJsonDocument<512> respDoc;
      DeserializationError err = deserializeJson(respDoc, response);
      if (!err && respDoc.containsKey("session_id")) {
        const char* sid = respDoc["session_id"];
        currentSessionId = String(sid);
        Serial.print("Session ID: ");
        Serial.println(currentSessionId);
      }

      // Blink LED once to signal successful upload
      digitalWrite(LED_PIN, HIGH); delay(100);
      digitalWrite(LED_PIN, LOW);
    }
  } else {
    Serial.print("HTTP Error: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
}

// ─────────────────────────────────────────────
//  MPU6500
// ─────────────────────────────────────────────

void initMPU6500() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);  // Wake up
  Wire.endTransmission();

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1C);
  Wire.write(0x00);  // Accelerometer ±2g
  Wire.endTransmission(true);

  Serial.println("MPU6500 Initialized");
}

void readMPU6500() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // ACCEL_XOUT_H
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 6);

  if (Wire.available() == 6) {
    axRaw = (Wire.read() << 8) | Wire.read();
    ayRaw = (Wire.read() << 8) | Wire.read();
    azRaw = (Wire.read() << 8) | Wire.read();

    ax = axRaw / 16384.0;
    ay = ayRaw / 16384.0;
    az = azRaw / 16384.0;

    motionMagnitude = sqrt(ax * ax + ay * ay + az * az);
  }
}

// ─────────────────────────────────────────────
//  Serial Print (for debugging)
// ─────────────────────────────────────────────

void printSensorData() {
  Serial.println();
  Serial.println("=========== DATA ===========");

  if (validHeartRate) {
    Serial.print("Heart Rate : ");
    Serial.print(heartRate);
    Serial.println(" BPM");
  } else {
    Serial.println("Heart Rate : Invalid");
  }

  if (validSPO2) {
    Serial.print("SpO2       : ");
    Serial.print(spo2);
    Serial.println(" %");
  } else {
    Serial.println("SpO2       : Invalid");
  }

  Serial.print("Accel X    : "); Serial.println(ax, 3);
  Serial.print("Accel Y    : "); Serial.println(ay, 3);
  Serial.print("Accel Z    : "); Serial.println(az, 3);
  Serial.print("Motion Mag : "); Serial.println(motionMagnitude, 3);
  Serial.println("============================");
  Serial.println();
}

// ─────────────────────────────────────────────
//  Setup
// ─────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("AVIRA Pico W – Starting up...");

  // I2C on Pico pins GP0 (SDA) and GP1 (SCL)
  Wire.setSDA(0);
  Wire.setSCL(1);
  Wire.begin();

  // Initialize MAX30102
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 not found! Check wiring.");
    // Blink LED rapidly to signal hardware error
    while (1) {
      digitalWrite(LED_PIN, HIGH); delay(100);
      digitalWrite(LED_PIN, LOW);  delay(100);
    }
  }

  byte ledBrightness = 60;
  byte sampleAverage = 4;
  byte ledMode       = 2;
  byte sampleRate    = 100;
  int  pulseWidth    = 411;
  int  adcRange      = 4096;
  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
  Serial.println("MAX30102 Initialized");

  initMPU6500();

  // Connect to WiFi
  connectWiFi();

  Serial.println("AVIRA ready. Beginning measurements...");
  delay(1000);

  // ── Initial buffer fill (100 samples = 4 seconds) ──
  bufferLength = 100;
  for (byte i = 0; i < bufferLength; i++) {
    while (particleSensor.available() == false)
      particleSensor.check();

    redBuffer[i] = particleSensor.getRed();
    irBuffer[i]  = particleSensor.getIR();
    particleSensor.nextSample();
  }

  maxim_heart_rate_and_oxygen_saturation(
    irBuffer, bufferLength, redBuffer,
    &spo2, &validSPO2, &heartRate, &validHeartRate
  );
}

// ─────────────────────────────────────────────
//  Main Loop
// ─────────────────────────────────────────────

void loop() {
  // Shift old samples: discard first 25, keep last 75
  for (byte i = 25; i < 100; i++) {
    redBuffer[i - 25] = redBuffer[i];
    irBuffer[i - 25]  = irBuffer[i];
  }

  // Collect 25 new samples
  for (byte i = 75; i < 100; i++) {
    while (particleSensor.available() == false)
      particleSensor.check();

    redBuffer[i] = particleSensor.getRed();
    irBuffer[i]  = particleSensor.getIR();
    particleSensor.nextSample();
  }

  // Recalculate HR and SpO2
  maxim_heart_rate_and_oxygen_saturation(
    irBuffer, bufferLength, redBuffer,
    &spo2, &validSPO2, &heartRate, &validHeartRate
  );

  // Read accelerometer
  readMPU6500();

  // Print to Serial (for debugging)
  printSensorData();

  // Upload every N cycles
  cycleCount++;
  if (cycleCount >= UPLOAD_EVERY_N_CYCLES) {
    cycleCount = 0;
    uploadToServer();
  }
}
