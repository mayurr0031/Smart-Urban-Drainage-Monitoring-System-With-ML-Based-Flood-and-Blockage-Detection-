# HC-SR04 Water Level Library

A simple yet powerful library for measuring water level using the HC-SR04 ultrasonic sensor with Arduino-compatible microcontrollers.

## Features

- **Accurate Distance Measurement**: Measures distance in centimeters using HC-SR04
- **Water Level Calculation**: Automatically calculates water level from measured distance
- **Rise Rate Tracking**: Monitors the rate of change of water level
- **Container Percentage**: Calculates how full a container is
- **Error Handling**: Validates measurements and filters invalid readings

## API Reference

### Constructor

```cpp
WaterLevel(int trigPin, int echoPin, float baseHeightCm = 40.0);
```

**Parameters:**
- `trigPin`: GPIO pin connected to HC-SR04 trigger
- `echoPin`: GPIO pin connected to HC-SR04 echo
- `baseHeightCm`: Distance from sensor to container bottom (default: 40 cm)

### Methods

#### `void begin()`
Initialize the sensor and GPIO pins.

```cpp
waterLevel.begin();
```

#### `float measureDistance()`
Measure the distance from sensor to water surface.

**Returns:** Distance in centimeters

```cpp
float distance = waterLevel.measureDistance();
```

#### `float getWaterLevel()`
Get the current water level in the container.

**Returns:** Water level in centimeters from bottom

```cpp
float level = waterLevel.getWaterLevel();
```

#### `float getRiseRate()`
Get the current rate of water level change.

**Returns:** Rise rate in cm/s (positive = rising, negative = falling)

```cpp
float rate = waterLevel.getRiseRate();
```

#### `float getPercentageFilled(float containerHeightCm)`
Get the percentage of container that is filled with water.

**Parameters:**
- `containerHeightCm`: Total height of the container

**Returns:** Percentage filled (0-100%)

```cpp
float percentage = waterLevel.getPercentageFilled(100.0);
```

#### `void update()`
Update internal measurements and calculate rise rate.

Must be called regularly (at least once per measurement cycle) for accurate rise rate calculation.

```cpp
waterLevel.update();
```

## Usage Example

```cpp
#include <Arduino.h>
#include <WaterLevel.h>

// Create sensor instance
// Trigger on GPIO 5, Echo on GPIO 18, base height 40 cm
WaterLevel sensor(5, 18, 40.0);

void setup() {
    Serial.begin(115200);
    sensor.begin();  // Initialize sensor
}

void loop() {
    // Update measurements
    sensor.update();
    
    // Get measurements
    float distance = sensor.measureDistance();
    float level = sensor.getWaterLevel();
    float rate = sensor.getRiseRate();
    float fill = sensor.getPercentageFilled(100.0);
    
    // Print results
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.print(" cm | Level: ");
    Serial.print(level);
    Serial.print(" cm | Rate: ");
    Serial.print(rate);
    Serial.print(" cm/s | Fill: ");
    Serial.print(fill);
    Serial.println("%");
    
    delay(1000);  // Measure once per second
}
```

## Technical Details

### Distance Calculation

The library uses the time-of-flight method:

```
Distance = (Pulse Duration × Speed of Sound) / 2
Speed of Sound ≈ 343 m/s = 0.0343 cm/µs
```

### Water Level Calculation

```
Water Level = Base Height - Measured Distance
```

Example with base height of 40 cm:
- If distance = 30 cm → water level = 40 - 30 = 10 cm
- If distance = 35 cm → water level = 40 - 35 = 5 cm

### Rise Rate Calculation

```
Rise Rate = Δ Water Level / Δ Time
```

The library tracks changes between `update()` calls to calculate the rate of change.

## Hardware Requirements

- **Sensor**: HC-SR04 Ultrasonic Distance Sensor
- **Microcontroller**: ESP32 or compatible Arduino board
- **Supply**: 5V power for sensor
- **Pins**: 2 GPIO pins (trigger + echo)

### Pinout

```
HC-SR04        ESP32
VCC      ──→   5V
GND      ──→   GND
TRIG     ──→   GPIO5
ECHO     ──→   GPIO18
```

## Limitations

- **Maximum Range**: ~300 cm (typical)
- **Minimum Range**: ~2 cm
- **Accuracy**: ±0.5 cm (typical)
- **Response Time**: ~40 ms per measurement
- **Update Rate**: Limited by sensor response time

## Advanced Configuration

### Adjusting Base Height

Update the base height dynamically:

```cpp
// Initial setup with 40 cm base height
WaterLevel sensor(5, 18, 40.0);

// No direct setter, but you can recalibrate by recreating:
// WaterLevel sensor(5, 18, 50.0);  // New base height
```

### Multiple Sensors

Create multiple instances for different sensors:

```cpp
WaterLevel tank1(5, 18, 40.0);   // Tank 1
WaterLevel tank2(19, 21, 50.0);  // Tank 2

void setup() {
    tank1.begin();
    tank2.begin();
}

void loop() {
    tank1.update();
    tank2.update();
    
    float level1 = tank1.getWaterLevel();
    float level2 = tank2.getWaterLevel();
}
```

## Error Handling

The library includes error checking:

- **Invalid Measurements**: Returns previous valid reading
- **Out of Range**: Filters measurements >300 cm
- **Negative Water Level**: Clamped to 0 cm
- **Percentage Bounds**: Clamped to 0-100%

## Calibration Steps

1. **Measure Base Distance**: Measure distance from sensor to container bottom
2. **Update Constructor**: Set this as `baseHeightCm` parameter
3. **Test**: With empty container, `getWaterLevel()` should return ~0
4. **Verify**: Add known volume of water and verify reading

## Performance Considerations

- **CPU Load**: Minimal (<1% on ESP32)
- **Memory**: ~2KB RAM for library instance
- **Power**: Normal GPIO/sensor power consumption
- **Timing**: Each measurement takes ~40-50 ms

## Dependencies

- Arduino.h (standard Arduino framework)
- No external libraries required

## License

MIT License - Free to use and modify
