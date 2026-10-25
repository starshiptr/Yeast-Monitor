"""Record one bottle: serial stream -> data/raw/<date>-<time>_s<sugar>_y<yeast>_r<rep>.csv

Seal the bottle, then start this straight away (t=0 is roughly the seal).
    python analysis/log_run.py --sugar 2 --yeast 0.20 --rep 1
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import serial

P_WARN = 1090.0  # sensor ceiling is 1100 hPa

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--port", default="COM3")
ap.add_argument("--sugar", type=float, required=True, help="sugar %% w/v (0 = control)")
ap.add_argument("--yeast", type=float, required=True, help="dry yeast in grams")
ap.add_argument("--rep", type=int, required=True, help="replicate number")
ap.add_argument("--minutes", type=float, default=30)
ap.add_argument("--out", default="data/raw")
a = ap.parse_args()

out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
path = out / f"{datetime.now():%Y%m%d-%H%M}_s{a.sugar:g}_y{a.yeast:.2f}_r{a.rep}.csv"

rows = 0
with serial.Serial(a.port, 115200, timeout=2) as ser, open(path, "w") as f:
    f.write("ms,P_hPa,T_C\n")
    t0 = time.time()
    try:
        while time.time() - t0 < a.minutes * 60:
            line = ser.readline().decode(errors="ignore").strip()
            if line.startswith("#"):
                print(line)  # board status (sensor found, chip id, wiring errors)
                continue
            parts = line.split(",")
            try:
                p = float(parts[1])
                [float(x) for x in parts]
            except (ValueError, IndexError):
                continue  # header line, blank or a garbled first line after reset
            f.write(line + "\n")
            f.flush()
            rows += 1
            warn = "  << NEAR SENSOR CEILING - loosen the cap" if p > P_WARN else ""
            print(f"\r{(time.time() - t0) / 60:5.1f} min  {p:8.2f} hPa{warn}   ", end="", flush=True)
    except KeyboardInterrupt:
        print("\nstopped early")
print(f"\nsaved {rows} readings to {path}")
