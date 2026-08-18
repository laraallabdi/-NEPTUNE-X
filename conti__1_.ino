#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// LCD
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ESP32 Pins
#define DHTPIN 4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

const int BUZZER_PIN = 19;
const int PIEZO_PIN  = 34;
const int WATER_PIN  = 35;
const int GAS_PIN    = 32;
const int FAN_INA    = 26;
const int FAN_INB    = 27;

// Thresholds
const float TEMP_LIMIT = 30.0;
const int GAS_LIMIT = 400;
const int WATER_LIMIT = 200;
const int PIEZO_LIMIT = 100;

unsigned long lastChange = 0;
int displayPage = 0;

unsigned long buzzerStartTime = 0;
bool isBuzzerRunning = false;

void setup() {
  Serial.begin(115200);

  Wire.begin(21, 22);   // SDA = 21, SCL = 22
  dht.begin();

  lcd.init();
  lcd.backlight();

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(FAN_INA, OUTPUT);
  pinMode(FAN_INB, OUTPUT);

  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(FAN_INA, LOW);
  digitalWrite(FAN_INB, LOW);

  lcd.setCursor(0, 0);
  lcd.print("NeptuneX AI Dashboard");
  lcd.setCursor(0, 1);
  lcd.print("System Ready");
  delay(2000);
  lcd.clear();
}

void loop() {
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  int gas = analogRead(GAS_PIN);
  int water = analogRead(WATER_PIN);
  int piezo = analogRead(PIEZO_PIN);

  if (isnan(temp) || isnan(hum)) {
    temp = 0;
    hum = 0;
  }

  bool tempAlert = temp > TEMP_LIMIT;
  bool gasAlert = gas > GAS_LIMIT;
  bool waterAlert = water > WATER_LIMIT;
  bool piezoAlert = piezo > PIEZO_LIMIT;

  // --- Buzzer Control with different tones ---
  if (tempAlert || gasAlert || waterAlert || piezoAlert) {
    if (!isBuzzerRunning) {
      buzzerStartTime = millis();
      isBuzzerRunning = true;
      
      if (tempAlert) tone(BUZZER_PIN, 1000);      // Tone for Temp
      else if (gasAlert) tone(BUZZER_PIN, 2000);  // High tone for Gas
      else if (waterAlert) tone(BUZZER_PIN, 500); // Low tone for Water
      else if (piezoAlert) tone(BUZZER_PIN, 1500);// Medium tone for Vibration
    }
  }

  if (isBuzzerRunning && millis() - buzzerStartTime > 1000) {
    noTone(BUZZER_PIN);
    isBuzzerRunning = false;
  }

  // --- Fan Control (Directly from ESP32) ---
  if (temp > TEMP_LIMIT) {
    digitalWrite(FAN_INA, HIGH);
    digitalWrite(FAN_INB, LOW);
  } else {
    digitalWrite(FAN_INA, LOW);
    digitalWrite(FAN_INB, LOW);
  }

  // --- Serial Output for Python Dashboard ---
  static unsigned long lastSend = 0;
  if (millis() - lastSend > 2000) {
    Serial.print("DATA,");
    Serial.print(temp); Serial.print(",");
    Serial.print(hum); Serial.print(",");
    Serial.print(gas); Serial.print(",");
    Serial.print(water); Serial.print(",");
    Serial.println(piezo);
    lastSend = millis();
  }

  // --- LCD Display Logic ---
  if (millis() - lastChange > 3000) {
    displayPage = (displayPage + 1) % 3;
    lastChange = millis();
    lcd.clear();
  }

  if (displayPage == 0) {
    lcd.setCursor(0, 0);
    lcd.print("T:"); lcd.print(temp, 1);
    lcd.print("C H:"); lcd.print(hum, 0);
    lcd.setCursor(0, 1);
    lcd.print("Gas:"); lcd.print(gas);
  } 
  else if (displayPage == 1) {
    lcd.setCursor(0, 0);
    lcd.print("Water:"); lcd.print(water);
    lcd.setCursor(0, 1);
    lcd.print("Piezo:"); lcd.print(piezo);
  } 
  else {
    lcd.setCursor(0, 0);
    if (tempAlert || gasAlert || waterAlert || piezoAlert) lcd.print("STATUS: ALERT!");
    else lcd.print("STATUS: SAFE");
    
    lcd.setCursor(0, 1);
    if (tempAlert) lcd.print("High Temp");
    else if (gasAlert) lcd.print("Gas Alert");
    else if (waterAlert) lcd.print("Water Alert");
    else if (piezoAlert) lcd.print("Vibration");
    else lcd.print("Normal");
  }
}