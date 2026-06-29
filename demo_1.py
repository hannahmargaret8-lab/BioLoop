# main.py

from initialize import initialize_bioloop
from protocols.salinity_test import run_salinity_demo


# =========================
# Start BioLoop
# =========================

system = initialize_bioloop()


# =========================
# Select operating mode
# =========================

run_salinity_demo(
    system=system,

    # Options:
    # "known"      → validate known sample
    # "predict"    → unknown sample, predict ionic strength
    # "calibrate"  → add accepted point to empirical model
    # "kcell"      → recalibrate electrode cell constant

    mode="known",

    # required for known/calibrate
    # ignored for predict
    expected_I=0.180,

    n_scans=3,
)


print("BioLoop run complete")