# main_biofilm_resume_t4.py

from pathlib import Path
import time

from electrochem.eis import PalmSens
from protocols.biofilm_pilot import log, run_timepoint


# --------------------------------------------------
# CONTINUATION SETTINGS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

# Existing experiment folder from the interrupted run
EXPERIMENT_FOLDER = (
    PROJECT_ROOT
    / "data"
    / "experiments"
    / "2026-07-09_16-32-20_biofilm_pilot"
)

PALMSENS_PORT = "/dev/ttyUSB0"
SIMULATE = False

SEED_HOURS = 3
FLOW_RATE_UL_MIN = 5

START_FLOW_TIMEPOINT = 4
FINAL_FLOW_TIMEPOINT = 8

# flow_t3h finished at 23:19:29.
# The experiment stopped at 23:24:14, so approximately
# 55 minutes remained before the intended flow_t4h scan.
WAIT_BEFORE_T4_MINUTES = 55


def countdown_wait(total_seconds, folder, next_timepoint):
    """
    Wait while logging progress every 10 minutes.

    This makes it easier to verify that the continuation
    script is still running when reconnecting through tmux.
    """
    remaining = int(total_seconds)

    while remaining > 0:
        wait_chunk = min(600, remaining)

        log(
            folder,
            f"Waiting for {next_timepoint}: "
            f"{remaining / 60:.1f} min remaining",
        )

        time.sleep(wait_chunk)
        remaining -= wait_chunk


def main():
    folder = EXPERIMENT_FOLDER

    if not folder.exists():
        raise FileNotFoundError(
            f"Existing experiment folder was not found:\n{folder}"
        )

    log(folder, "Biofilm pilot continuation started")
    log(folder, "Resuming after completed flow_t3h")
    log(
        folder,
        f"Continuation will run flow_t{START_FLOW_TIMEPOINT}h "
        f"through flow_t{FINAL_FLOW_TIMEPOINT}h",
    )

    pot = PalmSens(
        port=PALMSENS_PORT,
        simulate=SIMULATE,
    )

    pot.connect()

    try:
        if WAIT_BEFORE_T4_MINUTES > 0:
            log(
                folder,
                f"Waiting {WAIT_BEFORE_T4_MINUTES} min "
                "to preserve the intended flow_t4h timing",
            )

            countdown_wait(
                WAIT_BEFORE_T4_MINUTES * 60,
                folder,
                "flow_t4h",
            )

        # Run flow_t4h after the remaining wait.
        hour = START_FLOW_TIMEPOINT
        elapsed_hr = SEED_HOURS + hour

        run_timepoint(
            pot=pot,
            folder=folder,
            timepoint=f"flow_t{hour}h",
            elapsed_hr=elapsed_hr,
            notes=(
                f"Resumed after interruption; "
                f"LB flow at {FLOW_RATE_UL_MIN} uL/min"
            ),
        )

        # Continue hourly through flow_t8h.
        for hour in range(
            START_FLOW_TIMEPOINT + 1,
            FINAL_FLOW_TIMEPOINT + 1,
        ):
            log(
                folder,
                f"Waiting 1 hr before flow_t{hour}h",
            )

            countdown_wait(
                3600,
                folder,
                f"flow_t{hour}h",
            )

            elapsed_hr = SEED_HOURS + hour

            run_timepoint(
                pot=pot,
                folder=folder,
                timepoint=f"flow_t{hour}h",
                elapsed_hr=elapsed_hr,
                notes=(
                    f"Continuation run; "
                    f"LB flow at {FLOW_RATE_UL_MIN} uL/min"
                ),
            )

        log(folder, "Biofilm pilot continuation complete")
        log(folder, "Completed through flow_t8h")

    except KeyboardInterrupt:
        log(
            folder,
            "Continuation interrupted by Ctrl+C; "
            "completed data remain saved",
        )
        raise

    finally:
        if hasattr(pot, "device") and pot.device is not None:
            pot.device.close()

        log(folder, "PalmSens connection closed")


if __name__ == "__main__":
    main()