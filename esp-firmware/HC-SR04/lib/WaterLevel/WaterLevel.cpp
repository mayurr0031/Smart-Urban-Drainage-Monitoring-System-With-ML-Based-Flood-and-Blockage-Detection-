#include "WaterLevel.h"

namespace {
constexpr int DISTANCE_SAMPLE_COUNT = 5;
constexpr int MIN_VALID_SAMPLES = 3;
constexpr unsigned long SAMPLE_INTERVAL_MS = 60;
constexpr float MILLISECONDS_PER_MINUTE = 60000.0f;
}

WaterLevel::WaterLevel(int trig, int echo, float baseHeightCm)
    : triggerPin(trig), echoPin(echo),
      baseHeight(baseHeightCm > 0.0f ? baseHeightCm : 0.0f),
      previousWaterLevel(0.0f), currentWaterLevel(0.0f), riseRate(0.0f),
      lastMeasureTime(0), hasPreviousMeasurement(false) {}

void WaterLevel::begin() {
    pinMode(triggerPin, OUTPUT);
    pinMode(echoPin, INPUT);
    update();
}

float WaterLevel::measureDistance() {
    digitalWrite(triggerPin, LOW);
    delayMicroseconds(2);

    digitalWrite(triggerPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(triggerPin, LOW);

    unsigned long pulseDuration = pulseIn(echoPin, HIGH, 30000);
    if (pulseDuration == 0) {
        return 0.0f;
    }

    float distance = (pulseDuration * 0.0343f) / 2.0f;
    if (distance < 2.0f || distance > 400.0f) {
        return 0.0f;
    }

    return distance;
}

float WaterLevel::getWaterLevel() {
    return currentWaterLevel;
}

float WaterLevel::getRiseRate() {
    return riseRate;
}

float WaterLevel::getPercentageFilled(float containerHeightCm) {
    if (containerHeightCm <= 0.0f) {
        return 0.0f;
    }

    float percentage = (currentWaterLevel / containerHeightCm) * 100.0f;
    if (percentage < 0.0f) percentage = 0.0f;
    if (percentage > 100.0f) percentage = 100.0f;
    return percentage;
}

bool WaterLevel::update() {
    float distances[DISTANCE_SAMPLE_COUNT];
    int validSampleCount = 0;

    for (int i = 0; i < DISTANCE_SAMPLE_COUNT; ++i) {
        float distance = measureDistance();
        if (distance > 0.0f) {
            distances[validSampleCount++] = distance;
        }

        if (i + 1 < DISTANCE_SAMPLE_COUNT) {
            delay(SAMPLE_INTERVAL_MS);
        }
    }

    if (validSampleCount < MIN_VALID_SAMPLES) {
        riseRate = 0.0f;
        return false;
    }

    for (int i = 1; i < validSampleCount; ++i) {
        float value = distances[i];
        int j = i;
        while (j > 0 && distances[j - 1] > value) {
            distances[j] = distances[j - 1];
            --j;
        }
        distances[j] = value;
    }

    float distance = distances[validSampleCount / 2];
    if (validSampleCount % 2 == 0) {
        distance = (distance + distances[validSampleCount / 2 - 1]) / 2.0f;
    }

    float measuredWaterLevel = baseHeight - distance;
    if (measuredWaterLevel < 0.0f) measuredWaterLevel = 0.0f;
    if (measuredWaterLevel > baseHeight) measuredWaterLevel = baseHeight;

    unsigned long measurementTime = millis();
    if (hasPreviousMeasurement) {
        unsigned long elapsedMs = measurementTime - lastMeasureTime;
        if (elapsedMs > 0) {
            riseRate =
                (measuredWaterLevel - previousWaterLevel) * MILLISECONDS_PER_MINUTE / elapsedMs;
        } else {
            riseRate = 0.0f;
        }
    } else {
        riseRate = 0.0f;
        hasPreviousMeasurement = true;
    }

    currentWaterLevel = measuredWaterLevel;
    previousWaterLevel = measuredWaterLevel;
    lastMeasureTime = measurementTime;
    return true;
}