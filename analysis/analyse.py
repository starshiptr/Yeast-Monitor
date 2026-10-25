"""Turn fermentation runs into a calibration curve (AI layer 1: the Monod fit).

Per run:     load -> temperature-correct -> slope from minute 3 -> minus the control
Across runs: fit rate = Vmax*S/(Ks+S), then invert it to predict sugar from a rate.

    python analysis/analyse.py data/raw     # writes model.json + calibration.png there
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

SETTLE_MIN = 3.0     # water vapour fills the headspace first; skip it
END_MIN = 20.0       # fit the linear part only
P_CEILING = 1090.0   # BMP280 tops out at 1100 hPa; stop fitting before it
PLATEAU = 0.9        # above 90 % of Vmax the curve is too flat to invert honestly

# e.g. 20261103-1412_s2_y0.20_r1.csv  (SIM_ prefix = simulated)
NAME = re.compile(r"(\d{8})-\d{4}_s([\d.]+)_y([\d.]+)_r(\d+)\.csv$")


def parse_name(path):
    m = NAME.search(Path(path).name)
    if not m:
        raise ValueError(f"{path}: name must look like 20261103-1412_s2_y0.20_r1.csv")
    return {"date": m[1], "sugar": float(m[2]), "yeast": float(m[3]), "rep": int(m[4]),
            "simulated": Path(path).name.startswith("SIM_")}


def load_run(path):
    d = np.genfromtxt(path, delimiter=",", names=True)
    t_min = (d["ms"] - d["ms"][0]) / 60000.0
    return t_min, d["P_hPa"], d["T_C"], parse_name(path)


def correct(P, T):
    """Remove temperature drift: at fixed gas amount P is proportional to T (kelvin),
    so scale every reading back to the run's starting temperature."""
    Tk = np.asarray(T) + 273.15
    return np.asarray(P) * Tk[0] / Tk


def rate(t, Pc):
    """Pressure rise rate in hPa/min: linear fit from SETTLE_MIN to END_MIN,
    cut off before the sensor ceiling."""
    t, Pc = np.asarray(t), np.asarray(Pc)
    below = np.cumsum(Pc >= P_CEILING) == 0
    m = (t >= SETTLE_MIN) & (t <= END_MIN) & below
    if m.sum() < 10:
        raise ValueError("not enough data after minute 3 (run too short or hit the ceiling)")
    return np.polyfit(t[m], Pc[m], 1)[0]


def run_rates(paths):
    """Rate per run, minus the mean control (0 % sugar) rate of the same session (date).
    A session with no control falls back to the mean of all controls."""
    runs = []
    for p in paths:
        t, P, T, meta = load_run(p)
        runs.append({**meta, "file": Path(p).name, "rate": rate(t, correct(P, T))})
    controls = [r for r in runs if r["sugar"] == 0]
    if not controls:
        raise ValueError("no 0 % control runs - every session needs one")
    all_ctrl = float(np.mean([c["rate"] for c in controls]))
    for r in runs:
        same = [c["rate"] for c in controls if c["date"] == r["date"]]
        r["control"] = float(np.mean(same)) if same else all_ctrl
        r["net"] = r["rate"] - r["control"]
    return runs, all_ctrl


def monod(S, vmax, ks):
    return vmax * S / (ks + S)


def fit_monod(S, r):
    S, r = np.asarray(S, float), np.asarray(r, float)
    (vmax, ks), _ = curve_fit(monod, S, r, p0=[max(r.max(), 1e-3), 1.0], bounds=(0, np.inf))
    return float(vmax), float(ks)


def invert(r, vmax, ks):
    """Predict sugar % from a net rate. Returns (sugar, status):
    'ok', 'zero' (no rise above control) or 'plateau' (sugar is a lower bound)."""
    if r <= 0:
        return 0.0, "zero"
    if r >= PLATEAU * vmax:
        return ks * PLATEAU / (1 - PLATEAU), "plateau"
    return ks * r / (vmax - r), "ok"


def main(folder):
    folder = Path(folder)
    paths = sorted(folder.glob("*.csv"))
    if not paths:
        sys.exit(f"no runs in {folder}")
    runs, ctrl = run_rates(paths)
    vmax, ks = fit_monod([r["sugar"] for r in runs], [r["net"] for r in runs])
    simulated = any(r["simulated"] for r in runs)

    print(f"{'file':42} {'sugar%':>6} {'rate':>7} {'net':>7}  hPa/min")
    for r in runs:
        print(f"{r['file']:42} {r['sugar']:6.2f} {r['rate']:7.3f} {r['net']:7.3f}")
    print(f"\nVmax = {vmax:.3f} hPa/min   Ks = {ks:.3f} %   control = {ctrl:.3f} hPa/min"
          f"   ({len(runs)} runs{', SIMULATED' if simulated else ''})")
    print(f"Plateau: rates above {PLATEAU * vmax:.2f} hPa/min only tell you sugar >= "
          f"{ks * PLATEAU / (1 - PLATEAU):.2f} %")

    model = {"vmax": vmax, "ks": ks, "control_rate": ctrl, "n_runs": len(runs),
             "fitted": date.today().isoformat(), "simulated": simulated}
    (folder / "model.json").write_text(json.dumps(model, indent=2))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    S = np.linspace(0, max(r["sugar"] for r in runs) * 1.1, 200)
    plt.scatter([r["sugar"] for r in runs], [r["net"] for r in runs], label="runs")
    plt.plot(S, monod(S, vmax, ks), label=f"Monod fit: Vmax={vmax:.2f}, Ks={ks:.2f}%")
    plt.xlabel("sugar (% w/v)")
    plt.ylabel("net pressure rise rate (hPa/min)")
    plt.title("Yeast fermentation rate vs sugar" + ("  [SIMULATED DATA]" if simulated else ""))
    plt.legend()
    plt.savefig(folder / "calibration.png", dpi=150, bbox_inches="tight")
    print(f"wrote {folder / 'model.json'} and {folder / 'calibration.png'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
