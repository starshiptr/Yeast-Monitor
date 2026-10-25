# p19-yeast-monitor

Measuring how fast yeast ferments sugar with a pressure sensor, then predicting a mystery bottle's sugar level live.

Yeast eats sugar and releases CO₂. In a sealed bottle, that pushes the pressure up, and a BMP280 under the cap tracks it. More sugar means faster fermentation, up to a limit: the Monod saturation curve, `rate = Vmax·S / (Ks + S)`. We calibrate that curve across sugar levels, then run it backwards to guess the sugar in a bottle someone else mixed.

## How it works

```
BMP280 ──I²C──> ESP32 ──USB serial──> laptop
                (firmware/)           log_run.py      one CSV per bottle
                prints ms,P,T @1 Hz   analyse.py      rate per run → Monod fit → model.json
                                      predict_live.py live guess for the mystery bottle
```

The board only measures. All the maths runs on the laptop:

1. **Temperature correction.** Pressure rises ~3.3 hPa per °C with no yeast involved. Each reading is scaled to the starting temperature: `P × T₀/T` (kelvin).
2. **Rate.** A linear slope (hPa/min) from **minute 3**, after water vapour has filled the headspace, to minute 20, cut before the 1100 hPa sensor ceiling.
3. **Control subtraction.** The mean rate of the 0 % sugar bottles from the same session is subtracted.
4. **Monod fit** across all runs gives `Vmax` and `Ks`.
5. **Prediction** inverts the curve: `S = Ks·r / (Vmax − r)`. Above 90 % of Vmax the curve is too flat to read, so it reports "≥ X % (plateau)" instead of inventing a number.

## Wiring (GY-BMP280-3.3)

| BMP280 | ESP32 | Note |
|---|---|---|
| VCC | 3V3 | **Never 5V.** The module has no regulator |
| GND | GND | |
| SCL | GPIO 22 | |
| SDA | GPIO 21 | |
| SDO | GND | Sets address 0x76. Don't leave it floating |
| CSB | — | Leave unconnected (pulled high = I²C) |

## Usage

```powershell
# firmware (PlatformIO)
cd firmware; pio run -t upload -t monitor     # expect: chip id 0x58, ~1000 hPa

# python
python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt

python analysis/log_run.py --sugar 2 --yeast 0.20 --rep 1    # one bottle, 30 min
python analysis/analyse.py data/raw                          # fit -> model.json + calibration.png
python analysis/predict_live.py                              # the demo
python -m pytest                                             # the maths still works
```

Rehearse without hardware: `python analysis/simulate.py`, then `analyse.py data/sim`, then `predict_live.py --replay <file> --model data/sim/model.json`.

## Run protocol

- 100 mL water (syringe), yeast weighed to 0.01 g, sugar weighed. Room-temperature water basin. **Sugar is the only variable.**
- Seal, then start `log_run.py` straight away. Swirl, don't shake.
- Randomise the sugar order each session. Run a 0 % control at the start, middle and end.
- Loosen the cap after every run and dry the sensor for 1–2 min.

## Data honesty

- `data/raw/` holds **real runs only**.
- Simulated runs live in `data/sim/` with a `SIM_` prefix and are git-ignored.
- Any model or plot fitted on simulated data is labelled `SIMULATED`.
- No numbers in this repo are results until they come from `data/raw/`.

## Limitations

- At low sugar, yeast partly respires instead of fermenting. Respiration doesn't change the pressure, so the low end of the curve reads steep.
- About 15 calibration runs is a small dataset. The ML step (scikit-learn, leave-one-out) comes after the real runs, and the question is whether it beats the textbook curve.

MIT licence.
