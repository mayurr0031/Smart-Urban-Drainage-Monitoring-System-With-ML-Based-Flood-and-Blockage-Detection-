#ifndef TOXIC_GAS_H
#define TOXIC_GAS_H

#include <Arduino.h>

class ToxicGas
{
public:

    // Supported gas types
    enum GasType
    {
        MQ4_METHANE,
        MQ135_CO2
    };

    // (Removed safety-level enum to reduce firmware size)

    /*
     * Constructor
     *
     * analogPin      -> ESP32 ADC GPIO
     * gasType        -> MQ4_METHANE or MQ135_CO2
     * RL             -> Load resistance in kOhm
     * Ro             -> Sensor baseline resistance in kOhm
     */
    ToxicGas(
        uint8_t analogPin,
        GasType gasType,
        float RL = 10.0,
        float Ro = 10.0
    );

    // Initialize sensor
    void begin();

    // Read and calculate gas concentration
    float readPPM();

    // Get last calculated ppm
    float getPPM();

    // Get sensor resistance Rs in kOhm
    float getRs();

    // Get Rs/Ro ratio
    float getRatio();

    // Get raw ADC reading
    int getRawADC();

    // Get sensor output voltage
    float getVoltage();

    // Change Ro after calibration
    void setRo(float Ro);

    // Get Ro
    float getRo();

    // Change load resistance
    void setRL(float RL);

    // Get RL
    float getRL();

    // (Removed safety/status/debug helpers to reduce firmware size)

private:

    uint8_t _analogPin;
    GasType _gasType;

    float _RL;
    float _Ro;

    float _ppm;
    float _Rs;
    float _ratio;
    float _voltage;

    int _rawADC;

    static constexpr float VCC = 3.3;
    static constexpr float ADC_RESOLUTION = 4095.0;

    static constexpr int SAMPLE_COUNT = 50;

    // MQ-4 coefficients
    static constexpr float MQ4_A = 1012.7;
    static constexpr float MQ4_B = -2.786;

    // MQ-135 coefficients supplied by user
    static constexpr float MQ135_A = 110.47;
    static constexpr float MQ135_B = -2.862;

    // Calculate Rs
    float calculateRs(float voltage);

    // Calculate PPM
    float calculatePPM(float ratio);

    // (safety classification removed)
};

#endif