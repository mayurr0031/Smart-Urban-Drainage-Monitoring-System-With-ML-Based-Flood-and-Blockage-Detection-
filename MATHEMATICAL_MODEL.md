# Sensor and Prediction Mathematical Model

This note documents how the firmware converts sensor inputs into the values
stored by the server. Unless noted otherwise, each node samples once every
15 seconds. Water-level values and rates are reported in centimetres and
centimetres per minute; rain-gauge intensity is in millimetres per hour.

## Water level (HC-SR04)

The firmware takes five echo-pulse samples, discards invalid/out-of-range
samples, and uses the median of the valid samples when at least three remain.
For echo duration \(t\) in microseconds, the measured sensor-to-water distance
is:

\[
d = \frac{t \cdot 0.0343}{2}\ \text{cm}
\]

The factor \(0.0343\ \text{cm}/\mu\text{s}\) is the assumed speed of sound in
air; division by two accounts for the outgoing and returning sound path.
Distances below 2 cm, above 400 cm, or without a pulse are rejected.

For configured sensor-to-bottom height \(H\) and filtered distance \(d\), the
water level from the bottom is:

\[
L = \min(H,\max(0,H-d))\ \text{cm}
\]

The filled percentage for container height \(H_c>0\) is:

\[
P = \min(100,\max(0,100L/H_c))\ \%
\]

## Water-level rise rate

For consecutive valid levels \(L_k\) and \(L_{k-1}\), measured at times
\(t_k\) and \(t_{k-1}\) milliseconds apart, the signed rate is:

\[
R = \frac{(L_k-L_{k-1})\cdot 60{,}000}{t_k-t_{k-1}}\ \text{cm/min}
\]

Positive values mean the level is rising; negative values mean it is falling.
The first valid reading has a rate of zero. If a reading fails, it is not
reported; the next valid rate spans from the last valid measurement. This
15-second sampling cadence avoids estimating the rate from loop-speed,
sub-second level changes.

## Rain gauge intensity

The tipping-bucket gauge on device 1 uses the calibrated bucket amount
\(q=1.05\) mm per tip. For \(N\) new tips in elapsed time \(\Delta t\)
milliseconds:

\[
I_{\text{rain}} = \frac{N \cdot q \cdot 3{,}600{,}000}{\Delta t}
  \ \text{mm/h}
\]

Total measured rainfall since boot is \(Q_{\text{total}}=N_{\text{total}}q\)
mm. The rain-gauge intensity is distinct from the weather provider's forecast
precipitation intensity, although device 1's gauge intensity is used as the
model's current precipitation-intensity feature.

## MQ gas sensors

Each MQ sensor reading is the mean of 50 ADC samples. For mean 12-bit ADC code
\(A\), the firmware estimates voltage as:

\[
V_{\text{out}} = \frac{A}{4095}\cdot 3.3\ \text{V}
\]

Given load resistance \(R_L\) and calibrated sensor baseline resistance
\(R_o\), both in kOhm:

\[
R_s = \left(\frac{3.3}{V_{\text{out}}}-1\right)R_L,\qquad
\rho = R_s/R_o
\]

The configured empirical curves estimate concentration in ppm:

\[
\text{MQ-4 methane ppm} = \max(2,\ 1012.7\rho^{-2.786})
\]

\[
\text{MQ-135 ppm} = \max(0,\ 110.47\rho^{-2.862})
\]

When \(V_{\text{out}}\leq0\), \(R_o\leq0\), or \(\rho\leq0\), the code
returns zero ppm. The MQ-4 lower floor and both curve coefficients are firmware
configuration assumptions, not a substitute for calibration against the
specific sensor and gas environment. The firmware's status labels are
threshold classifications: MQ-4 thresholds are 300, 1000, and 5000 ppm;
MQ-135 thresholds are 25, 50, and 100 ppm.

## Manhole-cover input

The digital reed-switch input is reported as `CLOSED` when GPIO 26 is HIGH and
`OPEN` when it is LOW. The external pull-down resistor is required by the
firmware's wiring configuration.

## Prediction features

The server constructs the model feature vector in this order:

\[
x = [L_1,\ L_2,\ L_1-L_2,\ R_1,\ R_2,\ I_{\text{current}},
     p_{\text{rain}},\ I_{\text{next-hour}}]
\]

Here, \(L_i\) is a node's water level (cm), \(R_i\) is its signed rate
(cm/min), gauge intensity and forecast intensities are in mm/h, and
\(p_{\text{rain}}\) is forecast precipitation probability (percent).
Forecast values come from the weather provider, not a sensor formula. The
Random Forest supplies class probabilities; each displayed class percentage
is its predicted class probability multiplied by 100. Gas concentrations and
cover state are logged/displayed but are not model input features.
