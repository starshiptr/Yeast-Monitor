"""Demo: guess a mystery bottle's sugar % live, re-estimating every 30 s.

    python analysis/predict_live.py                        # live from COM3
    python analysis/predict_live.py --replay run.csv       # rehearse on a recorded run
Uses the fitted curve in data/raw/model.json (from analyse.py).
"""
import argparse
import json

from analyse import SETTLE_MIN, correct, invert, rate

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--port", default="COM3")
ap.add_argument("--replay", help="CSV to replay instead of reading the board")
ap.add_argument("--model", default="data/raw/model.json")
ap.add_argument("--every", type=float, default=30, help="seconds between estimates")
a = ap.parse_args()

m = json.load(open(a.model))
if m.get("simulated"):
    print("!! model was fitted on SIMULATED data - rehearsal only, not a real prediction")


def lines():
    if a.replay:
        yield from open(a.replay)
    else:
        import serial
        with serial.Serial(a.port, 115200, timeout=2) as ser:
            while True:
                yield ser.readline().decode(errors="ignore")


t, P, T = [], [], []
ms0, next_s = None, (SETTLE_MIN + 0.5) * 60
print(f"waiting {SETTLE_MIN + 0.5:.1f} min for the vapour to settle...")
try:
    for line in lines():
        try:
            ms, p, temp = (float(x) for x in line.strip().split(","))
        except ValueError:
            continue  # header, '#' status lines, garbage after reset
        ms0 = ms if ms0 is None else ms0
        t.append((ms - ms0) / 60000)
        P.append(p)
        T.append(temp)
        if t[-1] * 60 < next_s:
            continue
        next_s += a.every
        r = rate(t, correct(P, T)) - m["control_rate"]
        sugar, status = invert(r, m["vmax"], m["ks"])
        guess = {"ok": f"~{sugar:.2f} %", "zero": "~0 % (no rise above control)",
                 "plateau": f">= {sugar:.1f} % (on the plateau)"}[status]
        print(f"t={t[-1]:5.1f} min  rate={r:6.3f} hPa/min  ->  sugar {guess}")
except KeyboardInterrupt:
    pass
