#include <Wire.h>
#include <WiFi.h>          // Native Pico W WiFi library for Philhower core
#include <HTTPClient.h>    // Used to send HTTP requests to Render
#include "MAX30105.h"
#include "spo2_algorithm.h"
#include <math.h>

#define MPU_ADDR 0x68

// =========================================================================
// CRITICAL FIX: Change this to a 2.4 GHz network (5G networks are invisible to Pico W)
// =========================================================================
const char* ssid     = "CSE";  // e.g., Your phone hotspot set to 2.4GHz
const char* password = "12345678";

// Render Backend API Server Endpoint URL
const char* serverUrl = "https://final-qj39.onrender.com/api/v1/device/upload";

int16_t axRaw, ayRaw, azRaw;
float ax, ay, az;
float motionMagnitude;

MAX30105 particleSensor;

#define MAX_BRIGHTNESS 255

#if defined(__AVR_ATmega328P__) || defined(__AVR_ATmega168__)
uint16_t irBuffer[100]; 
uint16_t redBuffer[100];  
#else
uint32_t irBuffer[100]; 
uint32_t redBuffer[100];  
#endif

int32_t bufferLength; 
int32_t spo2; 
int8_t validSPO2; 
int32_t heartRate; 
int8_t validHeartRate; 

void initMPU6500()
{
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);
  Wire.endTransmission();

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1C);
  Wire.write(0x00);
  Wire.endTransmission(true);

  Serial.println("MPU6500 Initialized");
}

void readMPU6500()
{
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);            
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 6);

  if (Wire.available() == 6)
  {
    axRaw = (Wire.read() << 8) | Wire.read();
    ayRaw = (Wire.read() << 8) | Wire.read();
    azRaw = (Wire.read() << 8) | Wire.read();

    ax = axRaw / 16384.0;
    ay = ayRaw / 16384.0;
    az = azRaw / 16384.0;

    motionMagnitude = sqrt(ax * ax + ay * ay + az * az);
  }
}

// Helper function to establish connection to your router
void connectToWiFi() {
  Serial.print("Connecting to WiFi Network: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi Connected Successfully!");
  Serial.print("Pico W IP Address: ");
  Serial.println(WiFi.localIP());
}

void setup()
{
  Serial.begin(115200); 
  
  // Custom I2C pin mappings for Philhower core setup
  Wire.setSDA(0);
  Wire.setSCL(1);
  Wire.begin();

  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) 
  {
    Serial.println(F("MAX30105 was not found. Please check wiring/power."));
    while (1);
  }

  Serial.println("Sensors Started");
  delay(2000);

  byte ledBrightness = 60; 
  byte sampleAverage = 4; 
  byte ledMode = 2; 
  byte sampleRate = 100; 
  int pulseWidth = 411; 
  int adcRange = 4096; 

  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange); 
  initMPU6500();

  // Initialize the wireless internet connection profile
  connectToWiFi();
}

void loop()
{
  bufferLength = 100; 

  for (byte i = 0 ; i < bufferLength ; i++)
  {
    while (particleSensor.available() == false) 
      particleSensor.check(); 

    redBuffer[i] = particleSensor.getRed();
    irBuffer[i] = particleSensor.getIR();
    particleSensor.nextSample(); 
  }

  maxim_heart_rate_and_oxygen_saturation(irBuffer, bufferLength, redBuffer, &spo2, &validSPO2, &heartRate, &validHeartRate);

  while (1)
  {
    // Check if the board dropped its connection to the router and reconnect
    if (WiFi.status() != WL_CONNECTED) {
      connectToWiFi();
    }

    for (byte i = 25; i < 100; i++)
    {
      redBuffer[i - 25] = redBuffer[i];
      irBuffer[i - 25] = irBuffer[i];
    }

    for (byte i = 75; i < 100; i++)
    {
      while (particleSensor.available() == false) 
        particleSensor.check(); 

      redBuffer[i] = particleSensor.getRed();
      irBuffer[i] = particleSensor.getIR();
      particleSensor.nextSample(); 
    }

    maxim_heart_rate_and_oxygen_saturation(irBuffer, bufferLength, redBuffer, &spo2, &validSPO2, &heartRate, &validHeartRate);
    readMPU6500();

    // =========================================================
    // Build JSON Payload Data matching your Backend Requirements
    // =========================================================
    String jsonPayload = "{";
    jsonPayload += "\"heartRate\":" + String(validHeartRate ? String(heartRate) : "0") + ",";
    jsonPayload += "\"spo2\":" + String(validSPO2 ? String(spo2) : "0") + ",";
    jsonPayload += "\"accelX\":" + String(ax, 3) + ",";
    jsonPayload += "\"accelY\":" + String(ay, 3) + ",";
    jsonPayload += "\"accelZ\":" + String(az, 3) + ",";
    jsonPayload += "\"motionMagnitude\":" + String(motionMagnitude, 3);
    jsonPayload += "}";

    // Print to Serial Monitor for verification
    Serial.println("\n--- Outgoing JSON ---");
    Serial.println(jsonPayload);

    // Send HTTP POST over network stack straight to Render
    HTTPClient http;
    WiFiClientSecure client;
    
    // Ignore SSL certificate checks for deployment simplification
    client.setInsecure(); 

    if (http.begin(client, serverUrl)) {
      http.addHeader("Content-Type", "application/json");
      
      int httpResponseCode = http.POST(jsonPayload);
      
      if (httpResponseCode > 0) {
        Serial.print("Render Server Response Code: ");
        Serial.println(httpResponseCode);
        String response = http.getString();
        Serial.println("Server Body: " + response);
      } else {
        Serial.print("Error sending HTTP POST packet data: ");
        Serial.println(http.errorToString(httpResponseCode).c_str());
      }
      
      http.end();
    } else {
      Serial.println("Unable to initialize connection to Render server.");
    }

    delay(2000); // 2-second sleep cycle between server updates
  }
}