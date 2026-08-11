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
    "http://10.226.209.237:5000/api/sensor_readings";


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

// MQ-4 AO -> ESP32 GPIO35
#define MQ4_PIN 35

// MQ-135 AO -> ESP32 GPIO34
#define MQ135_PIN 34


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

const unsigned long sendInterval = 5000;


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
}


// ======================================================
// LOOP
// ======================================================

void loop()
{
    // --------------------------------------------------
    // Continuously update water sensor
    // --------------------------------------------------

    waterSensor.update();


    unsigned long currentMillis = millis();


    // --------------------------------------------------
    // Send data every 5 seconds
    // --------------------------------------------------

    if (currentMillis - lastSendTime >= sendInterval)
    {
        lastSendTime = currentMillis;


        if (WiFi.status() == WL_CONNECTED)
        {
            // ==================================================
            // READ WATER LEVEL
            // ==================================================

            float waterLevel =
                waterSensor.getWaterLevel();

            float riseRate =
                waterSensor.getRiseRate();

            float percentage =
                waterSensor.getPercentageFilled(
                    BASE_HEIGHT_CM
                );


            // ==================================================
            // READ MQ-4
            // ==================================================

            float mq4PPM =
                mq4Sensor.readPPM();


            // ==================================================
            // READ MQ-135
            // ==================================================

            float mq135PPM =
                mq135Sensor.readPPM();


            // ==================================================
            // SERIAL MONITOR
            // ==================================================

            Serial.println();
            Serial.println("------------------------------------------");

            Serial.print("Device ID: ");
            Serial.println(deviceId);


            Serial.print("Water Level: ");
            Serial.print(waterLevel, 2);
            Serial.println(" cm");


            Serial.print("Rise Rate: ");
            Serial.print(riseRate, 4);
            Serial.println(" cm/min");


            Serial.print("Percentage: ");
            Serial.print(percentage, 2);
            Serial.println(" %");


            Serial.print("MQ-4 Methane: ");
            Serial.print(mq4PPM, 2);
            Serial.println(" ppm");


            Serial.print("MQ-135: ");
            Serial.print(mq135PPM, 2);
            Serial.println(" ppm");


            // ==================================================
            // CREATE JSON
            // ==================================================

            String jsonData = "{";

            jsonData +=
                "\"device_id\":" +
                String(deviceId) +
                ",";


            jsonData +=
                "\"water_level\":" +
                String(waterLevel, 2) +
                ",";


            jsonData +=
                "\"rise_rate\":" +
                String(riseRate, 4) +
                ",";


            jsonData +=
                "\"percentage\":" +
                String(percentage, 2) +
                ",";


            String mq4Status = classifyMq4Status(mq4PPM);
            String mq135Status = classifyMq135Status(mq135PPM);

            jsonData +=
                "\"mq4_ppm\":" +
                String(mq4PPM, 2) +
                ",";

            jsonData +=
                "\"mq4_status\":\"" +
                mq4Status +
                "\",";

            jsonData +=
                "\"mq135_ppm\":" +
                String(mq135PPM, 2) +
                ",";

            jsonData +=
                "\"mq135_status\":\"" +
                mq135Status +
                "\"";

            jsonData += "}";


            // ==================================================
            // PRINT JSON
            // ==================================================

            Serial.println();
            Serial.println("JSON DATA:");

            Serial.println(jsonData);


            // ==================================================
            // SEND HTTP POST
            // ==================================================

            HTTPClient http;

            http.begin(serverURL);

            http.addHeader(
                "Content-Type",
                "application/json"
            );


            int httpResponseCode =
                http.POST(jsonData);


            // ==================================================
            // SERVER RESPONSE
            // ==================================================

            if (httpResponseCode > 0)
            {
                Serial.print(
                    "HTTP Response Code: "
                );

                Serial.println(
                    httpResponseCode
                );


                String response =
                    http.getString();


                Serial.print(
                    "Server Response: "
                );

                Serial.println(response);
            }
            else
            {
                Serial.print(
                    "HTTP Error: "
                );

                Serial.println(
                    httpResponseCode
                );
            }


            http.end();


            Serial.println(
                "------------------------------------------"
            );
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