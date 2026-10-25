import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))

from analyse import correct, fit_monod, invert, rate, run_rates  # noqa: E402
from simulate import KS, VMAX, simulate_run, write_run  # noqa: E402


def test_temperature_drift_is_removed():
    # No yeast activity at all, only the bath warming 0.5 C.
    ms, P, T = simulate_run(0, control_rate=0, noise=0, seed=1)
    t = ms / 60000
    assert rate(t, P) > 0.05                    # uncorrected: drift looks like fermentation
    assert abs(rate(t, correct(P, T))) < 0.01   # corrected: gone


def test_pipeline_recovers_sugar(tmp_path):
    paths = [write_run(tmp_path, s, rep, bio_cv=0, seed=rep)
             for s in (0, 0.25, 0.5, 1, 2, 4) for rep in (1, 2)]
    runs, ctrl = run_rates(paths)
    vmax, ks = fit_monod([r["sugar"] for r in runs], [r["net"] for r in runs])
    assert abs(vmax - VMAX) / VMAX < 0.10
    assert abs(ks - KS) / KS < 0.10

    for s in (0.25, 0.5, 1, 2):
        ms, P, T = simulate_run(s, bio_cv=0, seed=99)
        sugar, status = invert(rate(ms / 60000, correct(P, T)) - ctrl, vmax, ks)
        assert status == "ok" and abs(sugar - s) < 0.3, (s, sugar, status)

    assert invert(0.95 * vmax, vmax, ks)[1] == "plateau"
    assert invert(-0.1, vmax, ks) == (0.0, "zero")
