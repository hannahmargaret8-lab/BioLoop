# protocols/biofilm_pilot.py

from datetime import datetime
from pathlib import Path
import time
import csv
import shutil

from electrochem.eis import PalmSens


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "experiments"

SEED_HOURS = 3
FLOW_RATE_UL_MIN = 5
N_HOURLY_MEASUREMENTS = 8
EIS_SCANS_PER_TIMEPOINT = 3
PALMSENS_PORT = "/dev/ttyUSB0"
SIMULATE = False


def make_experiment_folder():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = DATA_DIR / f"{stamp}_biofilm_pilot"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "raw").mkdir(exist_ok=True)
    (folder / "plots").mkdir(exist_ok=True)
    return folder


def log(folder, message):
    now = datetime.now().isoformat(timespec="seconds")
    print(f"[{now}] {message}")

    with open(folder / "experiment.log", "a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")


def append_summary(folder, row):
    summary_file = folder / "summary.csv"
    exists = summary_file.exists()

    with open(summary_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timepoint",
                "timestamp",
                "elapsed_hr",
                "rs_mean",
                "rs_sd",
                "rs_values",
                "notes",
            ],
        )

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def copy_latest_outputs(folder, timepoint):
    data_dir = PROJECT_ROOT / "data"

    for pattern in ["eis_*.csv", "eis_raw_*.bin"]:
        files = sorted(data_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        if files:
            newest = files[-1]
            shutil.copy2(newest, folder / "raw" / f"{timepoint}_{newest.name}")

    for plot_name in ["nyquist.png", "bode_mag.png", "bode_phase.png"]:
        plot_file = data_dir / plot_name
        if plot_file.exists():
            shutil.copy2(plot_file, folder / "plots" / f"{timepoint}_{plot_name}")


def run_timepoint(pot, folder, timepoint, elapsed_hr, notes=""):
    log(folder, f"Starting EIS timepoint: {timepoint}")

    result = pot.run_batch(
        n_scans=EIS_SCANS_PER_TIMEPOINT,
        metadata={
            "mode": "biofilm_pilot",
            "sample_name": timepoint,
            "timepoint": timepoint,
            "elapsed_hr": elapsed_hr,
        },
    )

    copy_latest_outputs(folder, timepoint)

    append_summary(
        folder,
        {
            "timepoint": timepoint,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "elapsed_hr": elapsed_hr,
            "rs_mean": result["Rs_mean"],
            "rs_sd": result["Rs_sd"],
            "rs_values": result["Rs_values"],
            "notes": notes,
        },
    )

    log(
        folder,
        f"Finished {timepoint}: Rs_mean={result['Rs_mean']:.3f}, "
        f"Rs_sd={result['Rs_sd']:.3f}",
    )


def run_biofilm_pilot():
    folder = make_experiment_folder()

    log(folder, "Biofilm pilot started")
    log(folder, f"Experiment folder: {folder}")
    log(folder, f"Seed time: {SEED_HOURS} hr")
    log(folder, f"Flow rate after seeding: {FLOW_RATE_UL_MIN} uL/min")
    log(folder, f"Hourly measurements: {N_HOURLY_MEASUREMENTS}")

    pot = PalmSens(port=PALMSENS_PORT, simulate=SIMULATE)
    pot.connect()

    try:
        input("Load clean/media baseline, then press Enter to run baseline EIS...")
        run_timepoint(pot, folder, "baseline_media", 0, "media only before bacteria")

        input("Seed bacteria on SPE, then press Enter to start 3 hr static attachment...")
        log(folder, "Static seeding period started")
        time.sleep(SEED_HOURS * 3600)

        run_timepoint(
            pot,
            folder,
            "post_seed_t0",
            SEED_HOURS,
            "after static seeding before flow",
        )

        input(f"Start LB flow at {FLOW_RATE_UL_MIN} uL/min, then press Enter to begin hourly loop...")
        log(folder, "LB flow started")

        for hour in range(1, N_HOURLY_MEASUREMENTS + 1):
            log(folder, f"Waiting 1 hr before timepoint {hour}")
            time.sleep(3600)

            elapsed_hr = SEED_HOURS + hour
            run_timepoint(
                pot,
                folder,
                f"flow_t{hour}h",
                elapsed_hr,
                f"LB flow at {FLOW_RATE_UL_MIN} uL/min",
            )

        log(folder, "Biofilm pilot complete")

    finally:
        if hasattr(pot, "device") and pot.device is not None:
            pot.device.close()
        log(folder, "PalmSens connection closed")


if __name__ == "__main__":
    run_biofilm_pilot()