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

    # Options:yy
    # "known"      → validate known sample
    # "predict"    → unknown sample, predict ionic strength
    # "calibrate"  → add accepted point to empirical model
    # "kcell"      → recalibrate electrode cell constant

    mode="predict",

    # required for known/calibrate
    # ignored for predict
    expected_I = 0.18,


    sample_name = "0.18M_PBS",

    n_scans=3,
)


print("BioLoop run complete")
