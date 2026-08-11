#include "WaterLevel.h"

WaterLevel::WaterLevel(int trig, int echo, float baseHeightCm)
    : triggerPin(trig), echoPin(echo), baseHeight(baseHeightCm),
      previousDistance(baseHeightCm), riseRate(0), lastMeasureTime(0) {}

void WaterLevel::begin() {
    pinMode(triggerPin, OUTPUT);
    pinMode(echoPin, INPUT);
    
    // Stabilize sensor with initial measurements
    delay(100);
    for (int i = 0; i < 5; i++) {
        float dist = measureDistance();
        if (dist > 0) {
            previousDistance = dist;
        }
        delay(50);
    }
    
    lastMeasureTime = millis();
}

float WaterLevel::measureDistance() {
    // Ensure trigger pin is low initially
    digitalWrite(triggerPin, LOW);
    delayMicroseconds(2);
    
    // Send 10µs pulse on trigger pin
    digitalWrite(triggerPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(triggerPin, LOW);
    
    // Measure echo pulse duration with 50ms timeout (max ~8.5m)
    unsigned long pulseDuration = pulseIn(echoPin, HIGH, 50000);
    
    // Calculate distance: distance = (time * speed of sound) / 2
    // Speed of sound = 343 m/s = 0.0343 cm/µs
    float distance = (pulseDuration * 0.0343) / 2.0;
    
    // Validate measurement
    // Valid range: 2cm to 400cm
    if (distance < 2.0 || distance > 400.0 || pulseDuration == 0) {
        // Return previous distance only if it was valid
        if (previousDistance > 0 && previousDistance < 400.0) {
            return previousDistance;
        }
        return 0;  // Return 0 as fallback for invalid readings
    }
    
    return distance;
}

float WaterLevel::getWaterLevel() {
    // Water level = base height - distance from sensor to water surface
    float distance = measureDistance();
    
    // If we got 0 (invalid reading), return previous level
    if (distance == 0 && previousDistance > 0) {
        distance = previousDistance;
    }
    
    float waterLevel = baseHeight - distance;
    
    // Ensure non-negative water level
    if (waterLevel < 0) {
        waterLevel = 0;
    }
    
    return waterLevel;
}

float WaterLevel::getRiseRate() {
    return riseRate;
}

float WaterLevel::getPercentageFilled(float containerHeightCm) {
    float waterLevel = getWaterLevel();
    float percentage = (waterLevel / containerHeightCm) * 100.0;
    
    // Clamp to 0-100%
    if (percentage < 0) percentage = 0;
    if (percentage > 100) percentage = 100;
    
    return percentage;
}

void WaterLevel::update() {
    unsigned long currentTime = millis();
    float currentDistance = measureDistance();

    if (currentDistance == 0) return;

    float newWaterLevel = baseHeight - currentDistance;
    float previousWaterLevel = baseHeight - previousDistance;

    float timeDiff = (currentTime - lastMeasureTime) / 1000.0;

    if (timeDiff >= 0.5) {
        riseRate = (newWaterLevel - previousWaterLevel) / timeDiff;

        if (abs(riseRate) > 50) {
            riseRate = 0;
        }

        previousDistance = currentDistance;
        lastMeasureTime = currentTime;
        currentWaterLevel = newWaterLevel;  // ✅ store
    }
}