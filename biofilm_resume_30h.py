#!/usr/bin/env python3
"""Resume an interrupted BioLoop biofilm experiment at flow hour 30."""

from pathlib import Path
import glob
import time

from electrochem.eis import PalmSens
from protocols.biofilm_dc_sweep import (
    EXPERIMENTS_DIR,
    FLOW_RATE_UL_MIN,
    MCP_ADDRESS,
    MEASUREMENT_INTERVAL_MINUTES,
    PALMSENS_PORT,
    PALMSENS_SIMULATE,
    PINCHER_MCP_PIN,
    PINCHER_OFF_AFTER_SEEDING,
    STOP_FILE,
    ManualSyringePump,
    PincherValve,
    clear_old_stop_file,
    countdown_wait,
    log,
    run_paired_timepoint,
    stop_requested,
)

START_HOUR = 30
END_HOUR = 48
RUN_START_HOUR_IMMEDIATELY = True


def find_latest_experiment_folder() -> Path:
    candidates = [
        path
        for path in EXPERIMENTS_DIR.glob("*biofilm_dc_sweep_pump*")
        if path.is_dir()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No existing biofilm experiment folders found in {EXPERIMENTS_DIR}"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def choose_palmsens_port() -> str:
    if Path("/dev/emstat").exists():
        return "/dev/emstat"

    if Path(PALMSENS_PORT).exists():
        return PALMSENS_PORT

    detected = sorted(glob.glob("/dev/ttyUSB*"))

    if len(detected) == 1:
        return detected[0]

    if not detected:
        raise RuntimeError(
            "No PalmSens serial device found. Power on/reconnect the EmStat "
            "and confirm that a /dev/ttyUSB* device exists."
        )

    print("\nMultiple USB serial ports detected:")
    for index, port in enumerate(detected, start=1):
        print(f"  {index}: {port}")

    while True:
        choice = input("Select the EmStat port number: ").strip()
        try:
            return detected[int(choice) - 1]
        except (ValueError, IndexError):
            print("Enter one of the listed numbers.")


def confirm_resume_folder(folder: Path) -> None:
    sweep_hours = [
        str(hour)
        for hour in range(START_HOUR, END_HOUR + 1)
        if hour % 3 == 0
    ]

    print("\nBioLoop resume configuration")
    print("----------------------------")
    print(f"Experiment folder: {folder}")
    print(f"Starting hour:     flow_t{START_HOUR}h")
    print(f"Ending hour:       flow_t{END_HOUR}h")
    print(f"DC sweep hours:    {', '.join(sweep_hours)}")

    answer = input(
        "\nAppend resumed measurements to this folder? [y/N]: "
    ).strip().lower()

    if answer not in {"y", "yes"}:
        raise SystemExit("Resume cancelled without collecting data.")


def run_resume_experiment() -> None:
    if END_HOUR < START_HOUR:
        raise ValueError("END_HOUR must be >= START_HOUR")

    folder = find_latest_experiment_folder()
    confirm_resume_folder(folder)
    clear_old_stop_file(folder)

    palmsens_port = choose_palmsens_port()

    log(folder, "=" * 60)
    log(
        folder,
        f"Resume protocol started at flow_t{START_HOUR}h; "
        f"planned final timepoint flow_t{END_HOUR}h",
    )
    log(folder, f"PalmSens port selected: {palmsens_port}")

    pot = PalmSens(port=palmsens_port, simulate=PALMSENS_SIMULATE)
    pump = ManualSyringePump()
    pincher = PincherValve(
        mcp_pin=PINCHER_MCP_PIN,
        mcp_address=MCP_ADDRESS,
    )

    try:
        pot.connect()
        pump.connect()
        pincher.connect()

        # Post-seeding route must remain selected during resumed flow.
        pincher.set_state(PINCHER_OFF_AFTER_SEEDING)
        log(
            folder,
            f"Pincher MCP GP{PINCHER_MCP_PIN} confirmed OFF for "
            "the post-seeding flow route",
        )

        pump.start(flow_rate_ul_min=FLOW_RATE_UL_MIN)
        log(
            folder,
            f"Manual syringe pump confirmed running at "
            f"{FLOW_RATE_UL_MIN} uL/min",
        )

        schedule_start = time.monotonic()

        for flow_hour in range(START_HOUR, END_HOUR + 1):
            if stop_requested():
                log(folder, f"Stop requested before flow_t{flow_hour}h")
                break

            interval_index = flow_hour - START_HOUR
            if not RUN_START_HOUR_IMMEDIATELY:
                interval_index += 1

            target_time = (
                schedule_start
                + interval_index * MEASUREMENT_INTERVAL_MINUTES * 60
            )
            seconds_until_target = target_time - time.monotonic()

            if seconds_until_target > 0:
                completed_wait = countdown_wait(
                    total_seconds=seconds_until_target,
                    folder=folder,
                    next_event=f"flow_t{flow_hour}h",
                )
                if not completed_wait:
                    break

            timing_offset_seconds = time.monotonic() - target_time
            timepoint = f"flow_t{flow_hour}h"
            perform_full_sweep = flow_hour % 3 == 0

            log(
                folder,
                f"{timepoint}: "
                + (
                    "ZERO-BIAS + FULL DC SWEEP"
                    if perform_full_sweep
                    else "ZERO-BIAS ONLY"
                ),
            )

            try:
                run_paired_timepoint(
                    pot=pot,
                    pump=pump,
                    pincher=pincher,
                    folder=folder,
                    timepoint=timepoint,
                    elapsed_hr=float(flow_hour),
                    notes=(
                        "Resumed continuous biofilm monitoring after "
                        "EmStat interruption; "
                        f"scheduled offset={timing_offset_seconds:+.1f} s"
                    ),
                    run_dc_sweep=perform_full_sweep,
                )
            except Exception as exc:
                log(
                    folder,
                    f"{timepoint} failed: {type(exc).__name__}: {exc}",
                )
                log(
                    folder,
                    "Resume loop remains active and will advance to "
                    "the next scheduled hour.",
                )

        log(folder, "Resume measurement loop finished")

    except KeyboardInterrupt:
        log(
            folder,
            "Resume experiment interrupted by Ctrl+C; completed data remain saved",
        )

    finally:
        try:
            if pincher.connected:
                pincher.off()
        except Exception as exc:
            log(folder, f"Pincher shutdown warning: {exc}")

        try:
            pincher.close()
        except Exception as exc:
            log(folder, f"Pincher close warning: {exc}")

        try:
            if pump.connected:
                pump.stop()
        except Exception as exc:
            log(folder, f"Pump shutdown warning: {exc}")

        try:
            pump.close()
        except Exception as exc:
            log(folder, f"Pump close warning: {exc}")

        try:
            if hasattr(pot, "device") and pot.device is not None:
                pot.device.close()
        except Exception as exc:
            log(folder, f"PalmSens close warning: {exc}")

        if STOP_FILE.exists():
            STOP_FILE.unlink()

        log(folder, "Biofilm resume protocol finished")


if __name__ == "__main__":
    run_resume_experiment()