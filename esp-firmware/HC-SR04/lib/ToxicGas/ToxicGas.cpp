#include "ToxicGas.h"
#include <math.h>


ToxicGas::ToxicGas(
    uint8_t analogPin,
    GasType gasType,
    float RL,
    float Ro
)
{
    _analogPin = analogPin;
    _gasType = gasType;

    _RL = RL;
    _Ro = Ro;

    _ppm = 0.0;
    _Rs = 0.0;
    _ratio = 0.0;
    _voltage = 0.0;

    _rawADC = 0;
}


void ToxicGas::begin()
{
    pinMode(_analogPin, INPUT);
}


float ToxicGas::calculateRs(float voltage)
{
    if (voltage <= 0.0)
    {
        return 0.0;
    }

    /*
     * Rs = ((VCC / Vout) - 1) × RL
     */

    float Rs = ((VCC / voltage) - 1.0) * _RL;

    return Rs;
}


float ToxicGas::calculatePPM(float ratio)
{
    if (ratio <= 0.0)
    {
        return 0.0;
    }

    float ppm;

    if (_gasType == MQ4_METHANE)
    {
        /*
         * MQ-4 Methane
         *
         * PPM = 1012.7 × (Rs/Ro)^-2.786
         */

        ppm = MQ4_A * pow(ratio, MQ4_B);

        /*
         * Natural ambient methane baseline.
         *
         * Do not report values below approximately 2 ppm
         * as meaningful methane concentration.
         */

        if (ppm < 2.0)
        {
            ppm = 2.0;
        }
    }

    else
    {
        /*
         * MQ-135
         *
         * Using the coefficients supplied by the user:
         *
         * PPM = 110.47 × (Rs/Ro)^-2.862
         */

        ppm = MQ135_A * pow(ratio, MQ135_B);

        if (ppm < 0.0)
        {
            ppm = 0.0;
        }
    }

    return ppm;
}


float ToxicGas::readPPM()
{
    float adcSum = 0.0;

    /*
     * Take multiple samples to reduce ADC noise.
     */

    for (int i = 0; i < SAMPLE_COUNT; i++)
    {
        adcSum += analogRead(_analogPin);
        delay(10);
    }

    _rawADC = (int)(adcSum / SAMPLE_COUNT);

    /*
     * Convert ADC value to voltage.
     *
     * ESP32 ADC:
     * 0 - 4095
     */

    _voltage =
        ((float)_rawADC / ADC_RESOLUTION) * VCC;


    /*
     * Calculate sensor resistance.
     */

    _Rs = calculateRs(_voltage);


    /*
     * Calculate Rs/Ro.
     */

    if (_Ro > 0.0)
    {
        _ratio = _Rs / _Ro;
    }
    else
    {
        _ratio = 0.0;
    }


    /*
     * Calculate gas concentration.
     */

    _ppm = calculatePPM(_ratio);

    return _ppm;
}


float ToxicGas::getPPM()
{
    return _ppm;
}


float ToxicGas::getRs()
{
    return _Rs;
}


float ToxicGas::getRatio()
{
    return _ratio;
}


int ToxicGas::getRawADC()
{
    return _rawADC;
}


float ToxicGas::getVoltage()
{
    return _voltage;
}


void ToxicGas::setRo(float Ro)
{
    if (Ro > 0.0)
    {
        _Ro = Ro;
    }
}


float ToxicGas::getRo()
{
    return _Ro;
}


void ToxicGas::setRL(float RL)
{
    if (RL > 0.0)
    {
        _RL = RL;
    }
}


float ToxicGas::getRL()
{
    return _RL;
}


// Safety/status/debug helpers removed to reduce firmware size