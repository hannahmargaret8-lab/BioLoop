# utils/logger.py

import pandas as pd
from datetime import datetime
from pathlib import Path


def log_result(
    result,
    filename="data/bioloop_log.csv",
):

    Path("data").mkdir(
        exist_ok=True
    )

    row = result.copy()

    row["timestamp"] = datetime.now().isoformat(
        timespec="seconds"
    )

    df = pd.DataFrame(
        [row]
    )

    file_exists = Path(
        filename
    ).exists()


    df.to_csv(
        filename,
        mode="a" if file_exists else "w",
        header=not file_exists,
        index=False,
    )