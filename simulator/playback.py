from pathlib import Path
import pandas as pd
import numpy as np

class PlaybackSimulator:
    def __init__(self, files_or_dir):
        # files_or_dir may be a single file, a list of files, or a directory
        if isinstance(files_or_dir, (list, tuple)):
            self.files = [Path(p) for p in files_or_dir]
        else:
            p = Path(files_or_dir)
            if p.is_dir():
                self.files = sorted(list(p.glob("*.csv")))
            else:
                self.files = [p]

        self.index = 0

        if not self.files:
            raise ValueError("No playback files found")

    def _estimate_rs_from_csv(self, path: Path):
        df = pd.read_csv(path)
        if "Zreal_ohm" in df.columns:
            zr = df["Zreal_ohm"].to_numpy()
        elif "Zreal" in df.columns:
            zr = df["Zreal"].to_numpy()
        else:
            # fallback: try first numeric column
            numeric = df.select_dtypes(include=["number"])
            if numeric.shape[1] == 0:
                raise ValueError("No numeric columns to estimate Rs")
            zr = numeric.iloc[:, 0].to_numpy()

        valid = zr[np.isfinite(zr) & (zr > 0)]
        if len(valid) == 0:
            return float("nan")
        return float(np.min(valid[:5]))

    def next_rs(self):
        path = self.files[self.index % len(self.files)]
        self.index += 1
        return self._estimate_rs_from_csv(path)
