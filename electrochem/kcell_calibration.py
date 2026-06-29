# electrochem/kcell_calibration.py

from pathlib import Path
from datetime import datetime
import csv

import pandas as pd

from config.settings import K_CELL_DEFAULT


def save_kcell_calibration(
    Rs_mean,
    Rs_sd,
    kappa_standard,
    standard_name="0.1 M NaCl",
    accepted=True,
    path="data/kcell_calibration.csv",
):
    """
    Calculate and save electrode/cell constant calibration.

    Kcell = Rs * conductivity
    """

    Path("data").mkdir(exist_ok=True)

    Kcell = Rs_mean * kappa_standard

    file_exists = Path(path).exists()

    with open(path, "a", newline="") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "standard_name",
                "kappa_standard",
                "Rs_mean",
                "Rs_sd",
                "Kcell",
                "accepted",
            ],
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "standard_name": standard_name,
                "kappa_standard": kappa_standard,
                "Rs_mean": Rs_mean,
                "Rs_sd": Rs_sd,
                "Kcell": Kcell,
                "accepted": accepted,
            }
        )

    return Kcell



def get_latest_kcell(
    path="data/kcell_calibration.csv",
):
    """
    Returns most recent accepted Kcell.
    Falls back to original value.
    """

    p = Path(path)

    if not p.exists():
        return K_CELL_DEFAULT


    df = pd.read_csv(p)


    if len(df) == 0:
        return K_CELL_DEFAULT


    if "accepted" in df.columns:
        df = df[df["accepted"] == True]


    if len(df) == 0:
        return K_CELL_DEFAULT


    return float(
        df.iloc[-1]["Kcell"]
    )