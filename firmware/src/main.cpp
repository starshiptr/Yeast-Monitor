// Yeast monitor — firmware.
// The board only measures: once a second it prints `ms,P_hPa,T_C`.
// All maths happens on the laptop (analysis/). Lines starting with '#'
// are status messages the Python side skips.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>

const int SDA_PIN = 21;
const int SCL_PIN = 22;
const uint8_t CHIP_ID_REG = 0xD0;  // 0x56-0x58 = BMP280, 0x60 = BME280 (same P/T registers)

Adafruit_BMP280 bmp(&Wire);

uint8_t readChipId(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(CHIP_ID_REG);
  if (Wire.endTransmission() != 0) return 0;
  Wire.requestFrom(addr, (uint8_t)1);
  return Wire.available() ? Wire.read() : 0;
}

void scanBus() {
  Serial.print("# i2c devices:");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) Serial.printf(" 0x%02X", a);
  }
  Serial.println();
}

// Tries 0x76 (SDO->GND, our wiring) then 0x77. Returns true once the sensor is up.
bool startSensor() {
  for (uint8_t addr : {0x76, 0x77}) {
    uint8_t id = readChipId(addr);
    // 0x56/0x57 = early-batch BMP280s that cheap modules still ship with.
    if (id == 0x56 || id == 0x57 || id == 0x58 || id == 0x60) {
      Serial.printf("# sensor at 0x%02X chip id 0x%02X (%s)\n", addr, id,
                    id == 0x60 ? "BME280" : "BMP280");
      if (!bmp.begin(addr, id)) return false;
      // Max pressure oversampling + IIR filter: smoothest slope. A reading
      // takes ~40 ms, far inside the 1 s sample period.
      bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,
                      Adafruit_BMP280::SAMPLING_X2,    // temperature
                      Adafruit_BMP280::SAMPLING_X16,   // pressure
                      Adafruit_BMP280::FILTER_X16,
                      Adafruit_BMP280::STANDBY_MS_500);
      return true;
    }
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.println("# yeast-monitor");
  scanBus();
  while (!startSensor()) {
    Serial.println("# sensor not found at 0x76/0x77 - check wiring (VCC->3V3, SDA->21, SCL->22)");
    delay(2000);
    scanBus();
  }
  Serial.println("ms,P_hPa,T_C");
}

void loop() {
  static uint32_t next = 0;
  uint32_t now = millis();
  if (now < next) return;
  next = now + 1000;
  float p = bmp.readPressure() / 100.0f;  // Pa -> hPa
  float t = bmp.readTemperature();
  Serial.printf("%lu,%.3f,%.3f\n", (unsigned long)now, p, t);
}
