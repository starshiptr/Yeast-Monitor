"""Fake runs for testing the analysis before real data exists. NOT results.

Files go to data/sim/ (git-ignored) with a SIM_ prefix, so they can never be
mistaken for real runs. The numbers below are guesses from the design page,
not measurements.

    python analysis/simulate.py      # 6 sugar levels x 3 reps -> data/sim/
"""
from pathlib import Path

import numpy as np

VMAX, KS = 3.0, 0.5   # hPa/min, % sugar - invented, the real ones come from the experiment


def simulate_run(sugar, vmax=VMAX, ks=KS, minutes=25, noise=0.01, bio_cv=0.05,
                 drift_c=0.5, control_rate=0.05, seed=None):
    """Returns (ms, P_hPa, T_C) like the board would send."""
    rng = np.random.default_rng(seed)
    ms = np.arange(0, minutes * 60) * 1000
    tm = ms / 60000
    r = vmax * sugar / (ks + sugar) * (1 + bio_cv * rng.standard_normal()) + control_rate
    vapour = 4.0 * (1 - np.exp(-tm / 0.8))            # settles in ~3 min
    T = 30.0 + drift_c * tm / minutes                   # bath slowly warms
    P_at_T0 = 1010.0 + vapour + r * tm
    P = P_at_T0 * (T + 273.15) / (30.0 + 273.15) + noise * rng.standard_normal(ms.size)
    return ms, P, T


def write_run(folder, sugar, rep, yeast=0.2, day="20261103", **kw):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"SIM_{day}-1200_s{sugar:g}_y{yeast:.2f}_r{rep}.csv"
    ms, P, T = simulate_run(sugar, **kw)
    np.savetxt(path, np.column_stack([ms, P, T]), delimiter=",", fmt=["%d", "%.3f", "%.3f"],
               header="ms,P_hPa,T_C", comments="")
    return path


if __name__ == "__main__":
    for i, s in enumerate([0, 0.25, 0.5, 1, 2, 4]):
        for rep in (1, 2, 3):
            write_run("data/sim", s, rep, seed=10 * i + rep)
    print("wrote 18 SIMULATED runs to data/sim/  (true Vmax=3.0, Ks=0.5)")
