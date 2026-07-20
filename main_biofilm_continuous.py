# main_biofilm_continuous.py

from pathlib import Path
import csv
import re
import time

from electrochem.eis import PalmSens
from protocols.biofilm_pilot import log, run_timepoint


# --------------------------------------------------
# CONTINUOUS MONITORING SETTINGS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
EXPERIMENTS_DIR = PROJECT_ROOT / "data" / "experiments"

PALMSENS_PORT = "/dev/ttyUSB0"
SIMULATE = False

SEED_HOURS = 3
FLOW_RATE_UL_MIN = 5

MEASUREMENT_INTERVAL_MINUTES = 60
COUNTDOWN_LOG_INTERVAL_MINUTES = 10

# Set to True to collect one EIS timepoint as soon as
# the continuous script starts.
RUN_FIRST_TIMEPOINT_IMMEDIATELY = True

# Set this to a number only when summary.csv does not already
# contain a flow_tNh timepoint and you need to choose the next one.
#
# Example:
# MANUAL_START_FLOW_TIMEPOINT = 4
#
# Leave as None to determine the next timepoint automatically.
MANUAL_START_FLOW_TIMEPOINT = None

# Create this file to request a clean shutdown:
#
# touch ~/BioLoop/data/STOP_BIOFILM_CONTINUOUS
#
STOP_FILE = PROJECT_ROOT / "data" / "STOP_BIOFILM_CONTINUOUS"


def find_latest_experiment_folder():
    """
    Find the most recently created biofilm pilot experiment folder.
    """
    folders = [
        folder
        for folder in EXPERIMENTS_DIR.glob("*_biofilm_pilot")
        if folder.is_dir()
    ]

    if not folders:
        raise FileNotFoundError(
            f"No biofilm pilot experiment folders were found in:\n"
            f"{EXPERIMENTS_DIR}"
        )

    return max(folders, key=lambda folder: folder.stat().st_mtime)


def find_last_completed_flow_timepoint(folder):
    """
    Read summary.csv and return the largest completed flow_tNh number.

    Examples:
        flow_t3h -> 3
        flow_t12h -> 12

    Returns None when no flow timepoints are present.
    """
    summary_file = folder / "summary.csv"

    if not summary_file.exists():
        return None

    completed_hours = []

    with open(summary_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            timepoint = row.get("timepoint", "").strip()
            match = re.fullmatch(r"flow_t(\d+)h", timepoint)

            if match:
                completed_hours.append(int(match.group(1)))

    if not completed_hours:
        return None

    return max(completed_hours)


def determine_start_timepoint(folder):
    """
    Determine which flow timepoint should be collected next.
    """
    if MANUAL_START_FLOW_TIMEPOINT is not None:
        return MANUAL_START_FLOW_TIMEPOINT

    last_completed = find_last_completed_flow_timepoint(folder)

    if last_completed is None:
        return 1

    return last_completed + 1


def stop_requested():
    return STOP_FILE.exists()


def countdown_wait(total_seconds, folder, next_timepoint):
    """
    Wait in short chunks so the log shows that the process is alive
    and the stop file can be detected without waiting a full hour.
    """
    remaining = int(total_seconds)
    log_interval_seconds = COUNTDOWN_LOG_INTERVAL_MINUTES * 60

    while remaining > 0:
        if stop_requested():
            log(
                folder,
                f"Stop file detected while waiting for {next_timepoint}",
            )
            return False

        wait_chunk = min(log_interval_seconds, remaining)

        log(
            folder,
            f"Waiting for {next_timepoint}: "
            f"{remaining / 60:.1f} min remaining",
        )

        time.sleep(wait_chunk)
        remaining -= wait_chunk

    return True


def connect_palmsens(folder):
    """
    Create and connect a PalmSens instance.
    """
    log(folder, f"Connecting to PalmSens on {PALMSENS_PORT}")

    pot = PalmSens(
        port=PALMSENS_PORT,
        simulate=SIMULATE,
    )

    pot.connect()
    log(folder, "PalmSens connected")

    return pot


def close_palmsens(pot, folder):
    """
    Close the PalmSens serial connection when one is open.
    """
    if pot is None:
        return

    try:
        if hasattr(pot, "device") and pot.device is not None:
            pot.device.close()
            log(folder, "PalmSens connection closed")
    except Exception as exc:
        log(folder, f"PalmSens close warning: {exc}")


def run_continuous_monitoring():
    folder = find_latest_experiment_folder()
    next_hour = determine_start_timepoint(folder)

    # Remove an old stop request left from a previous run.
    if STOP_FILE.exists():
        STOP_FILE.unlink()

    log(folder, "Continuous biofilm monitoring started")
    log(folder, f"Experiment folder: {folder}")
    log(folder, f"Next timepoint: flow_t{next_hour}h")
    log(
        folder,
        f"Measurement interval: "
        f"{MEASUREMENT_INTERVAL_MINUTES} minutes",
    )
    log(
        folder,
        f"LB flow setting: {FLOW_RATE_UL_MIN} uL/min",
    )
    log(
        folder,
        f"Clean-stop file: {STOP_FILE}",
    )

    pot = None
    first_iteration = True

    try:
        pot = connect_palmsens(folder)

        while not stop_requested():
            timepoint = f"flow_t{next_hour}h"

            should_wait = (
                not first_iteration
                or not RUN_FIRST_TIMEPOINT_IMMEDIATELY
            )

            if should_wait:
                completed_wait = countdown_wait(
                    MEASUREMENT_INTERVAL_MINUTES * 60,
                    folder,
                    timepoint,
                )

                if not completed_wait:
                    break

            if stop_requested():
                break

            elapsed_hr = SEED_HOURS + next_hour

            try:
                run_timepoint(
                    pot=pot,
                    folder=folder,
                    timepoint=timepoint,
                    elapsed_hr=elapsed_hr,
                    notes=(
                        "Continuous weekend monitoring; "
                        f"LB flow at {FLOW_RATE_UL_MIN} uL/min"
                    ),
                )

                next_hour += 1

            except Exception as exc:
                log(
                    folder,
                    f"{timepoint} failed: "
                    f"{type(exc).__name__}: {exc}",
                )

                log(
                    folder,
                    "Closing and reconnecting PalmSens before retrying",
                )

                close_palmsens(pot, folder)
                pot = None

                if stop_requested():
                    break

                # Brief pause before reconnecting.
                time.sleep(30)

                try:
                    pot = connect_palmsens(folder)
                    log(
                        folder,
                        f"PalmSens reconnected; "
                        f"{timepoint} will be retried after the next interval",
                    )

                except Exception as reconnect_exc:
                    log(
                        folder,
                        "PalmSens reconnection failed: "
                        f"{type(reconnect_exc).__name__}: "
                        f"{reconnect_exc}",
                    )

                    pot = None

                    # Continue attempting recovery instead of terminating.
                    while pot is None and not stop_requested():
                        log(
                            folder,
                            "Waiting 10 minutes before another "
                            "PalmSens connection attempt",
                        )

                        time.sleep(600)

                        try:
                            pot = connect_palmsens(folder)
                        except Exception as retry_exc:
                            log(
                                folder,
                                "PalmSens connection retry failed: "
                                f"{type(retry_exc).__name__}: "
                                f"{retry_exc}",
                            )

            first_iteration = False

        log(folder, "Continuous monitoring stop requested")

    except KeyboardInterrupt:
        log(
            folder,
            "Continuous monitoring interrupted by Ctrl+C; "
            "completed data remain saved",
        )

    finally:
        close_palmsens(pot, folder)

        if STOP_FILE.exists():
            STOP_FILE.unlink()

        log(folder, "Continuous biofilm monitoring finished")


if __name__ == "__main__":
    run_continuous_monitoring()