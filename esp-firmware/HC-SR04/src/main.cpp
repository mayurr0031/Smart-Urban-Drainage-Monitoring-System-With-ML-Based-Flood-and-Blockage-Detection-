#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>

#include "WaterLevel.h"
#include "ToxicGas.h"


// ======================================================
// PREFERENCES / DEVICE ID
// ======================================================

Preferences preferences;
uint32_t deviceId = 0;


uint32_t getOrCreateDeviceId()
{
    preferences.begin("sensor_cfg", false);

    uint32_t savedId = preferences.getUInt("device_id", 0);

    if (savedId == 0)
    {
        Serial.println("No device ID found in flash.");
        Serial.println("Enter device ID (number) and press Enter:");

        while (!Serial.available())
        {
            delay(100);
        }

        String input = Serial.readStringUntil('\n');
        input.trim();

        if (input.length() == 0)
        {
            input = "1";
        }

        savedId = input.toInt();

        preferences.putUInt("device_id", savedId);

        Serial.print("Saved device ID: ");
        Serial.println(savedId);
    }
    else
    {
        Serial.print("Loaded device ID: ");
        Serial.println(savedId);
    }

    preferences.end();

    return savedId;
}


// ======================================================
// WIFI CONFIGURATION
// ======================================================

const char* ssid = "Esptest";
const char* password = "Gouda#15";


// ======================================================
// SERVER CONFIGURATION
// ======================================================

const char* serverURL =
    "http://10.103.27.237:5000/api/sensor_readings";


// ======================================================
// WATER LEVEL SENSOR
// ======================================================

#define TRIG_PIN 5
#define ECHO_PIN 18

#define BASE_HEIGHT_CM 40.0


WaterLevel waterSensor(
    TRIG_PIN,
    ECHO_PIN,
    BASE_HEIGHT_CM
);


// ======================================================
// GAS SENSOR CONFIGURATION
// ======================================================

// MQ-4 AO -> ESP32 GPIO34
#define MQ4_PIN 34

// MQ-135 AO -> ESP32 GPIO35
#define MQ135_PIN 35

// Reed switch: externally pull GPIO26 down; switch connects it to 3.3V
// when the manhole cover is closed. GPIO26 has no internal pull resistor.
#define COVER_REED_PIN 26

bool manholeCoverClosed = false;


// ------------------------------------------------------
// IMPORTANT:
// Replace these Ro values with your calibrated values.
// ------------------------------------------------------

#define MQ4_RL 10.0
#define MQ4_RO 10.0

#define MQ135_RL 10.0
#define MQ135_RO 10.0


// ======================================================
// TOXIC GAS SENSOR OBJECTS
// ======================================================

ToxicGas mq4Sensor(
    MQ4_PIN,
    ToxicGas::MQ4_METHANE,
    MQ4_RL,
    MQ4_RO
);


ToxicGas mq135Sensor(
    MQ135_PIN,
    ToxicGas::MQ135_CO2,
    MQ135_RL,
    MQ135_RO
);


// ======================================================
// RAIN GAUGE (DEVICE 1 ONLY)
// ======================================================

#define REED_PIN 27
#define MM_PER_TIP 1.05f
#define DEBOUNCE_TIME 100UL

volatile unsigned long tipCount = 0;
volatile unsigned long lastTipTime = 0;

unsigned long previousRainSample = 0;
unsigned long previousTipCount = 0;
float rainIntensity = 0.0f;


void IRAM_ATTR reedInterrupt()
{
    unsigned long currentTime = millis();

    if (currentTime - lastTipTime >= DEBOUNCE_TIME)
    {
        tipCount++;
        lastTipTime = currentTime;
    }
}


String classifyMq4Status(float ppm)
{
    if (ppm < 300.0f) {
        return "NORMAL";
    }
    if (ppm < 1000.0f) {
        return "WARNING";
    }
    if (ppm < 5000.0f) {
        return "HIGH";
    }
    return "HIGH_DANGER";
}


String classifyMq135Status(float ppm)
{
    if (ppm < 25.0f) {
        return "NORMAL";
    }
    if (ppm < 50.0f) {
        return "WARNING";
    }
    if (ppm < 100.0f) {
        return "HIGH";
    }
    return "HIGH_DANGER";
}


// ======================================================
// TIMING
// ======================================================

unsigned long lastSendTime = 0;

const unsigned long sendInterval = 15000;


// ======================================================
// SETUP
// ======================================================

void setup()
{
    Serial.begin(115200);

    delay(1000);

    Serial.println();
    Serial.println("==========================================");
    Serial.println(" SMART URBAN DRAINAGE MONITORING SYSTEM");
    Serial.println("==========================================");


    // --------------------------------------------------
    // Get device ID
    // --------------------------------------------------

    deviceId = getOrCreateDeviceId();

    pinMode(COVER_REED_PIN, INPUT);
    manholeCoverClosed = digitalRead(COVER_REED_PIN) == HIGH;

    Serial.print("Manhole cover: ");
    Serial.println(manholeCoverClosed ? "CLOSED" : "OPEN");


    // GPIO 27 is reserved for the rain gauge on device 1.
    if (deviceId == 1)
    {
        pinMode(REED_PIN, INPUT_PULLUP);

        attachInterrupt(
            digitalPinToInterrupt(REED_PIN),
            reedInterrupt,
            FALLING
        );

        previousRainSample = millis();
        Serial.println("Rain gauge interrupt enabled on GPIO 27.");
    }
    else
    {
        Serial.println("Rain gauge disabled for this device.");
    }


    // --------------------------------------------------
    // ESP32 ADC configuration
    // --------------------------------------------------

    analogReadResolution(12);

    analogSetPinAttenuation(
        MQ4_PIN,
        ADC_11db
    );

    analogSetPinAttenuation(
        MQ135_PIN,
        ADC_11db
    );


    // --------------------------------------------------
    // Initialize water sensor
    // --------------------------------------------------

    waterSensor.begin();


    // --------------------------------------------------
    // Initialize gas sensors
    // --------------------------------------------------

    mq4Sensor.begin();

    mq135Sensor.begin();


    Serial.println();
    Serial.println("Sensors initialized.");


    // --------------------------------------------------
    // WiFi connection
    // --------------------------------------------------

    WiFi.begin(ssid, password);

    Serial.print("Connecting to WiFi");

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);

        Serial.print(".");
    }

    Serial.println();
    Serial.println("WiFi Connected!");

    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());

    Serial.println();
    Serial.println("System ready.");
    lastSendTime = millis();
    if (deviceId == 1)
    {
        previousTipCount = tipCount;
        previousRainSample = lastSendTime;
    }
}


// ======================================================
// LOOP
// ======================================================

void loop()
{
    // --------------------------------------------------
    // Update the cover input between scheduled sensor readings
    // --------------------------------------------------

    manholeCoverClosed = digitalRead(COVER_REED_PIN) == HIGH;

    unsigned long currentMillis = millis();


    if (deviceId == 1 && currentMillis - previousRainSample >= sendInterval)
    {
        unsigned long currentTipCount = tipCount;
        unsigned long elapsedMs = currentMillis - previousRainSample;
        unsigned long tipsThisSample = currentTipCount - previousTipCount;
        float totalRain = currentTipCount * MM_PER_TIP;
        rainIntensity = tipsThisSample * MM_PER_TIP * 3600000.0f / elapsedMs;

        Serial.println();
        Serial.println("Rain gauge report:");
        Serial.print("Total Rainfall: ");
        Serial.print(totalRain, 2);
        Serial.println(" mm");
        Serial.print("Rain Intensity: ");
        Serial.print(rainIntensity, 2);
        Serial.println(" mm/hour");

        previousTipCount = currentTipCount;
        previousRainSample = currentMillis;
    }


    // --------------------------------------------------
    // Send sensor data every 15 seconds
    // --------------------------------------------------

    if (currentMillis - lastSendTime >= sendInterval)
    {
        lastSendTime = currentMillis;

        bool waterLevelValid = waterSensor.update();
        if (!waterLevelValid)
        {
            Serial.println("Water-level measurement failed; reporting gas readings only.");
        }

        float mq4PPM = mq4Sensor.readPPM();
        float mq135PPM = mq135Sensor.readPPM();
        String mq4Status = classifyMq4Status(mq4PPM);
        String mq135Status = classifyMq135Status(mq135PPM);

        Serial.println();
        Serial.println("------------------------------------------");
        Serial.print("Device ID: ");
        Serial.println(deviceId);
        Serial.print("MQ-4 ADC: ");
        Serial.print(mq4Sensor.getRawADC());
        Serial.print(" | voltage: ");
        Serial.print(mq4Sensor.getVoltage(), 3);
        Serial.print(" V | Rs/Ro: ");
        Serial.print(mq4Sensor.getRatio(), 3);
        Serial.print(" | methane: ");
        Serial.print(mq4PPM, 2);
        Serial.println(" ppm");
        Serial.print("MQ-135 ADC: ");
        Serial.print(mq135Sensor.getRawADC());
        Serial.print(" | voltage: ");
        Serial.print(mq135Sensor.getVoltage(), 3);
        Serial.print(" V | Rs/Ro: ");
        Serial.print(mq135Sensor.getRatio(), 3);
        Serial.print(" | ppm: ");
        Serial.print(mq135PPM, 2);
        Serial.println(" ppm");

        String jsonData = "{\"device_id\":" + String(deviceId) +
            ",\"manhole_cover_status\":\"" +
            (manholeCoverClosed ? "CLOSED" : "OPEN") + "\"";
        if (waterLevelValid)
        {
            float waterLevel = waterSensor.getWaterLevel();
            float riseRate = waterSensor.getRiseRate();
            float percentage = waterSensor.getPercentageFilled(BASE_HEIGHT_CM);

            Serial.print("Water Level: ");
            Serial.print(waterLevel, 2);
            Serial.println(" cm");
            Serial.print("Rise Rate: ");
            Serial.print(riseRate, 4);
            Serial.println(" cm/min");
            Serial.print("Percentage: ");
            Serial.print(percentage, 2);
            Serial.println(" %");

            jsonData += ",\"water_level\":" + String(waterLevel, 2) +
                ",\"rise_rate\":" + String(riseRate, 4) +
                ",\"percentage\":" + String(percentage, 2) +
                ",\"rain_intensity\":" + String(rainIntensity, 2);
        }
        jsonData += ",\"mq4_ppm\":" + String(mq4PPM, 2) +
            ",\"mq4_status\":\"" + mq4Status +
            "\",\"mq135_ppm\":" + String(mq135PPM, 2) +
            ",\"mq135_status\":\"" + mq135Status + "\"";

        jsonData += "}";

        if (WiFi.status() == WL_CONNECTED)
        {
            Serial.println("JSON DATA:");
            Serial.println(jsonData);

            HTTPClient http;
            http.begin(serverURL);
            http.addHeader("Content-Type", "application/json");
            int httpResponseCode = http.POST(jsonData);

            if (httpResponseCode > 0)
            {
                Serial.print("HTTP Response Code: ");
                Serial.println(httpResponseCode);
                Serial.print("Server Response: ");
                Serial.println(http.getString());
            }
            else
            {
                Serial.print("HTTP Error: ");
                Serial.println(httpResponseCode);
            }

            http.end();
            Serial.println("------------------------------------------");
        }
        else
        {
            Serial.println(
                "WiFi Disconnected!"
            );

            // Try reconnecting
            WiFi.disconnect();
            WiFi.begin(ssid, password);
        }
    }
}