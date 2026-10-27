#ifndef WATER_LEVEL_H
#define WATER_LEVEL_H

#include <Arduino.h>

class WaterLevel {
private:
    int triggerPin;
    int echoPin;
    float baseHeight;
    float previousWaterLevel;
    float currentWaterLevel;
    float riseRate;
    unsigned long lastMeasureTime;
    bool hasPreviousMeasurement;
    
public:
    // Constructor
    WaterLevel(int trig, int echo, float baseHeightCm = 40.0);
    
    // Initialize the sensor pins
    void begin();
    
    // Measure distance using HC-SR04 (returns distance in cm)
    float measureDistance();
    
    // Get current water level (cm from bottom)
    float getWaterLevel();
    
    // Get rise rate (cm/min)
    float getRiseRate();
    
    // Get percentage of container filled (0-100%)
    float getPercentageFilled(float containerHeightCm);
    
    // Take a filtered measurement and update the cached water level and rise rate.
    bool update();
};

#endif
