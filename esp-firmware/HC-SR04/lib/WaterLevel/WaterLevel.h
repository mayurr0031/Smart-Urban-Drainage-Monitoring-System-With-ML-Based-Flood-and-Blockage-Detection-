#ifndef WATER_LEVEL_H
#define WATER_LEVEL_H

#include <Arduino.h>

class WaterLevel {
private:
    int triggerPin;
    int echoPin;
    float baseHeight;  // cm - distance from sensor to container bottom
    float previousDistance;
    float riseRate;    // cm/s
    unsigned long lastMeasureTime;
     float currentWaterLevel;
    
public:
    // Constructor
    WaterLevel(int trig, int echo, float baseHeightCm = 40.0);
    
    // Initialize the sensor pins
    void begin();
    
    // Measure distance using HC-SR04 (returns distance in cm)
    float measureDistance();
    
    // Get current water level (cm from bottom)
    float getWaterLevel();
    
    // Get rise rate (cm/s)
    float getRiseRate();
    
    // Get percentage of container filled (0-100%)
    float getPercentageFilled(float containerHeightCm);
    
    // Perform measurement and update rise rate
    void update();
};

#endif
