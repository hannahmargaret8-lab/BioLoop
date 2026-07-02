# electrochem/calibration.py

from pathlib import Path
from datetime import datetime
import pandas as pd

from electrochem.kcell_calibration import get_latest_kcell


CALIBRATION_FILE = Path("data/calibration_points.csv")


def save_calibration_point(
    Rs_mean,
    Rs_sd,
    I_known,
    empirical_error=None,
    grounded_error=None,
    sample_name=None,
    source="user_accepted",
    recommendation=None,
    accepted=True,
    Kcell_at_time=None,
):
    Path("data").mkdir(exist_ok=True)

    if Kcell_at_time is None:
        Kcell_at_time = get_latest_kcell()

    new_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sample_name": sample_name,
        "I_known": I_known,
        "Rs_mean": Rs_mean,
        "Rs_sd": Rs_sd,
        "Kcell_at_time": Kcell_at_time,
        "empirical_error_percent": empirical_error,
        "grounded_error_percent": grounded_error,
        "recommendation": recommendation,
        "accepted": accepted,
        "source": source,
    }

    columns = list(new_row.keys())

    if CALIBRATION_FILE.exists():
        df = pd.read_csv(CALIBRATION_FILE)

        for col in columns:
            if col not in df.columns:
                df[col] = None

        df = df[columns]
    else:
        df = pd.DataFrame(columns=columns)

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(CALIBRATION_FILE, index=False)

    return new_row
