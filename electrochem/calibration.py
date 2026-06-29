# electrochem/calibration.py

from pathlib import Path
from datetime import datetime
import csv


def save_calibration_point(
    Rs_mean,
    Rs_sd,
    I_known,
    empirical_error=None,
    grounded_error=None,
    path="data/calibration_points.csv",
    source="manual",
):
    """
    Save accepted salinity calibration points.

    These points update the empirical model.
    The grounded model is only a reference.
    """

    Path("data").mkdir(exist_ok=True)

    file_exists = Path(path).exists()

    with open(path, "a", newline="") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "I_known",
                "Rs_mean",
                "Rs_sd",
                "empirical_error_percent",
                "grounded_error_percent",
                "source",
            ],
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "I_known": I_known,
                "Rs_mean": Rs_mean,
                "Rs_sd": Rs_sd,
                "empirical_error_percent": empirical_error,
                "grounded_error_percent": grounded_error,
                "source": source,
            }
        )