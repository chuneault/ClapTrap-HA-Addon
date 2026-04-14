#include <WiFi.h>
#include "AudioTools.h"
#include "AudioTools/Communication/VBANStream.h"

I2SStream i2sStream;
VBANStream vbanStream;

// Buffers (plus petits = moins de latence)
int32_t inBuffer[256];
int16_t outBuffer[128];

unsigned long lastLog = 0;
unsigned long lastDataTime = 0;
unsigned long totalOutBytes = 0;

// Mode test: privilégier un signal fidèle pour YAMNet plutôt qu'un son "amélioré"
constexpr int32_t NOISE_GATE_THRESHOLD = 80;
constexpr int32_t SOFTWARE_GAIN_NUM = 2;
constexpr int32_t SOFTWARE_GAIN_DEN = 1;
constexpr int32_t LIMITER_MAX = 30000;

void setup() {
  Serial.begin(115200);
  delay(1000);

  AudioLogger::instance().begin(Serial, AudioLogger::Warning);

  Serial.println();
  Serial.println("=== ESP32 INMP441 -> VBAN (stable) ===");

  // -----------------------------
  // I2S RX
  // -----------------------------
  auto cfg_i2s = i2sStream.defaultConfig(RX_MODE);
  cfg_i2s.sample_rate = 16000;
  cfg_i2s.bits_per_sample = 32;
  cfg_i2s.channels = 2;       // 2 slots, on prend LEFT
  cfg_i2s.use_apll = false;
  cfg_i2s.auto_clear = true;
  cfg_i2s.pin_bck = 26;
  cfg_i2s.pin_ws = 25;
  cfg_i2s.pin_data = 33;

  Serial.println("Starting I2S...");
  bool i2sOk = i2sStream.begin(cfg_i2s);
  Serial.print("I2S begin: ");
  Serial.println(i2sOk ? "OK" : "FAIL");

  // -----------------------------
  // VBAN TX
  // -----------------------------
  auto cfg_vban = vbanStream.defaultConfig(TX_MODE);
  cfg_vban.ssid = "chwifi2";
  cfg_vban.password = "newlife2028";
  cfg_vban.stream_name = "ESP32Mic";
  cfg_vban.channels = 1;
  cfg_vban.sample_rate = 16000;
  cfg_vban.bits_per_sample = 16;
  cfg_vban.target_ip = IPAddress(192, 168, 1, 159);
  cfg_vban.udp_port = 6980;

  Serial.println("Starting VBAN...");
  bool vbanOk = vbanStream.begin(cfg_vban);
  Serial.print("VBAN begin: ");
  Serial.println(vbanOk ? "OK" : "FAIL");

  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());

  lastDataTime = millis();
}

void loop() {
  int bytesRead = i2sStream.readBytes((uint8_t *)inBuffer, sizeof(inBuffer));
  int samplesRead = bytesRead / sizeof(int32_t);

  if (samplesRead >= 2) {

    int outCount = 0;
    int32_t peak = 0;
    long long sumAbs = 0;

    // LEFT channel seulement
    for (int i = 0; i < samplesRead - 1; i += 2) {

      int32_t left = inBuffer[i];

      // Conversion 32 -> 16
      int32_t s16 = left >> 16;

      // Noise gate leger pour couper le souffle sans ecraser les transitoires
      if (abs(s16) < NOISE_GATE_THRESHOLD) {
        s16 = 0;
      } else {
        s16 = (s16 * SOFTWARE_GAIN_NUM) / SOFTWARE_GAIN_DEN;
      }

      // Limiteur plus haut pour eviter d'aplatir les claps
      if (s16 > LIMITER_MAX) s16 = LIMITER_MAX;
      if (s16 < -LIMITER_MAX) s16 = -LIMITER_MAX;

      outBuffer[outCount++] = (int16_t)s16;

      int32_t a = abs(s16);
      sumAbs += a;
      if (a > peak) peak = a;
    }

    int written = 0;

    if (outCount > 0) {
      written = vbanStream.write((uint8_t *)outBuffer, outCount * sizeof(int16_t));

      if (written > 0) {
        lastDataTime = millis();
        totalOutBytes += written;
      }
    }

    // -----------------------------
    // DEBUG (toutes les 3 sec)
    // -----------------------------
    if (millis() - lastLog > 3000) {
      lastLog = millis();

      int32_t avg = 0;
      if (outCount > 0) {
        avg = sumAbs / outCount;
      }

      Serial.print("WiFi=");
      Serial.print(WiFi.status() == WL_CONNECTED ? "OK" : "DOWN");
      Serial.print(" RSSI=");
      Serial.print(WiFi.RSSI());
      Serial.print(" bytesRead=");
      Serial.print(bytesRead);
      Serial.print(" written=");
      Serial.print(written);
      Serial.print(" outBytes=");
      Serial.print(totalOutBytes);
      Serial.print(" peak=");
      Serial.print(peak);
      Serial.print(" avg=");
      Serial.print(avg);
      Serial.print(" idle_ms=");
      Serial.println(millis() - lastDataTime);

      totalOutBytes = 0;
    }

  } else {
    // DEBUG I2S
    if (millis() - lastLog > 3000) {
      lastLog = millis();
      Serial.print("⚠️ I2S faible bytesRead=");
      Serial.println(bytesRead);
    }
  }
}
