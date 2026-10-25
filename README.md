# Yeast monitor

Measuring how fast yeast ferments sugar with a pressure sensor, and how that rate changes with the amount of sugar.

Yeast eats sugar and releases CO₂. In a sealed bottle, that pushes the pressure up, and a BMP280 under the cap tracks it. More sugar means faster fermentation, up to a limit: the Monod saturation curve, `rate = Vmax·S / (Ks + S)`. We run one session of bottles at 0–4 % sugar and plot how the rate rises and then levels off.

## How it works

```
BMP280 ──I²C──> ESP32 ──USB serial──> laptop
                (firmware/)           log_run.py      one CSV per bottle
                prints ms,P,T @1 Hz   analyse.py      rate per bottle → Monod fit → two graphs
```

The board only measures. All the maths runs on the laptop:

1. **Temperature correction.** Pressure rises ~3.3 hPa per °C with no yeast involved. Each reading is scaled to the starting temperature: `P × T₀/T` (kelvin).
2. **Rate.** A linear slope (hPa/min) from **minute 3**, after water vapour has filled the headspace, to minute 20, cut before the 1100 hPa sensor ceiling.
3. **Control subtraction.** The mean rate of the 0 % sugar bottles from the same session is subtracted.
4. **Monod fit** across all bottles gives `Vmax` (top speed) and `Ks` (the sugar % at half of top speed).

### Outputs

| File | Shows |
|---|---|
| `pressure_vs_time.png` | One line per bottle: pressure rise over time. High sugar climbs steeply, the 0 % control stays flat |
| `rate_vs_sugar.png` | One dot per bottle (its slope) against sugar %, with the Monod curve: the rate rises, then levels off |
| `model.json` | The fitted `Vmax`, `Ks` and control rate |

## Prediction: works in theory, not part of the experiment

The fitted curve can be run backwards to predict an unknown bottle's sugar from its rate: `S = Ks·r / (Vmax − r)`. Above 90 % of Vmax the curve is too flat to read, so it reports "≥ X % (plateau)" instead of inventing a number. `predict_live.py` does this live, re-estimating every 30 s.

A reliable prediction needs repeated calibration runs (2–3 per sugar level), which are out of scope. The predictor is demonstrated **on simulated data only**: a simulated 1.5 % bottle was predicted at 1.55 %. That shows the method works. It is not a measured result.

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

python analysis/log_run.py --sugar 2 --yeast 1.00 --rep 1 --minutes 25   # one bottle
python analysis/analyse.py data/raw                                      # table + both graphs
python -m pytest                                                         # the maths still works
```

Try it without hardware: `python analysis/simulate.py`, then `python analysis/analyse.py data/sim`. The prediction demo: `python analysis/predict_live.py --replay <sim file> --model data/sim/model.json`.

## Run protocol (one session)

- **Bottles:** 0, 4, 0.5, 1, 1.5, 2 % sugar, plus a second 0 % control at the end. % = grams of sugar in 100 mL water.
- **Order:** 0 % first, 4 % second (it checks the yeast dose against the sensor ceiling), the middle four shuffled, then the end control.
- **Every bottle:** 100 mL water (syringe), 1.00 g yeast, sugar weighed to 0.01 g, room-temperature water basin. **Sugar is the only variable.**
- Add yeast, seal, swirl (don't shake), then start `log_run.py` straight away. 25 min per bottle.
- Loosen the cap slowly after every run and dry the sensor for 1–2 min.

## Data honesty

- `data/raw/` holds **real runs only**.
- Simulated runs live in `data/sim/` with a `SIM_` prefix and are git-ignored.
- Any model or plot fitted on simulated data is labelled `SIMULATED`.
- No numbers in this repo are results until they come from `data/raw/`.

## Limitations

- One bottle per sugar level: the session shows the shape of the curve, but not how much repeats vary.
- At low sugar, yeast partly respires instead of fermenting. Respiration doesn't change the pressure, so the low end of the curve reads steep.
- One sensor, so bottles run one after another over ~4 h. The start and end controls check for drift across the session.

MIT licence.
