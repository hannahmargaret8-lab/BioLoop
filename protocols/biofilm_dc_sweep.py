# protocols/biofilm_dc_sweep.py

from datetime import datetime
from pathlib import Path
import csv
import shutil
import time

import board
import busio
from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017

from electrochem.eis import PalmSens


# ============================================================
# PATHS
# ============================================================
BACKUP_ROOT = Path("/home/hhobbs/Bioloop_Backups")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = PROJECT_ROOT / "data" / "experiments"
GENERAL_DATA_DIR = PROJECT_ROOT / "data"

STOP_FILE = GENERAL_DATA_DIR / "STOP_BIOFILM_DC_EXPERIMENT"


# ============================================================
# BIOFILM SETTINGS
# ============================================================

SEED_HOURS = 3
FLOW_RATE_UL_MIN = 5
MEASUREMENT_INTERVAL_MINUTES = 60

ZERO_BIAS_SCANS = 3
DC_SWEEP_SCANS_PER_VOLTAGE = 1
BIAS_SETTLE_SECONDS = 10
ZERO_BIAS_RECOVERY_SECONDS = 10


# ============================================================
# EIS SETTINGS
# ============================================================

PALMSENS_PORT = "/dev/ttyUSB0"
PALMSENS_SIMULATE = False

AC_AMPLITUDE_V = 0.010
DC_BIAS_VALUES_V = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

MAX_FREQUENCY_HZ = 200000
MIN_FREQUENCY_HZ = 0.1
N_FREQUENCY_POINTS = 61

EIS_TIMEOUT_SECONDS = 240

# ============================================================
# PINCHER VALVE SETTINGS
# ============================================================

MCP_ADDRESS = 0x21
PINCHER_MCP_PIN = 13

# Powered during the three-hour attachment period so flow/waste
# follows the seeding-route path. It is switched OFF at 3 hours
# and remains OFF for the rest of the experiment.
PINCHER_ON_DURING_SEEDING = True
PINCHER_OFF_AFTER_SEEDING = False


# ============================================================
# GENERAL HELPERS
# ============================================================

def make_experiment_folder():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    folder = (
        EXPERIMENTS_DIR
        / f"{stamp}_biofilm_dc_sweep_pump"
    )

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "raw").mkdir(exist_ok=True)
    (folder / "plots").mkdir(exist_ok=True)

    backup_folder = (
        BACKUP_ROOT /
        folder.name
    )

    backup_folder.mkdir(parents=True, exist_ok=True)
    (backup_folder / "raw").mkdir(exist_ok=True)
    (backup_folder / "plots").mkdir(exist_ok=True)

    return folder, backup_folder


def log(folder, message):
    now = datetime.now().isoformat(timespec="seconds")
    line = f"[{now}] {message}"

    print(line, flush=True)

    with open(
        folder / "experiment.log",
        "a",
        encoding="utf-8",
    ) as file:
        file.write(line + "\n")


def stop_requested():
    return STOP_FILE.exists()


def clear_old_stop_file(folder):
    if STOP_FILE.exists():
        STOP_FILE.unlink()
        log(folder, f"Removed old stop file: {STOP_FILE}")


def countdown_wait(
    total_seconds,
    folder,
    next_event,
    log_interval_seconds=600,
):
    """
    Wait in chunks so the experiment log shows progress and
    the stop file can be detected during long waits.
    """
    remaining = int(total_seconds)

    while remaining > 0:
        if stop_requested():
            log(
                folder,
                f"Stop requested while waiting for {next_event}",
            )
            return False

        wait_chunk = min(
            log_interval_seconds,
            remaining,
        )

        log(
            folder,
            f"Waiting for {next_event}: "
            f"{remaining / 60:.1f} min remaining",
        )

        time.sleep(wait_chunk)
        remaining -= wait_chunk

    return True
class ManualSyringePump:
    def __init__(self):
        self.connected = True
        self.running = False
        self.flow_rate_ul_min = None

    def connect(self):
        print("Manual syringe pump selected")

    def start(self, flow_rate_ul_min):
        input(
            f"\nSet the syringe pump to {flow_rate_ul_min} uL/min "
            "and start flow.\nPress Enter after the pump is running..."
        )

        self.flow_rate_ul_min = flow_rate_ul_min
        self.running = True

        print(
            f"Manual syringe pump confirmed ON at "
            f"{flow_rate_ul_min} uL/min"
        )

    def stop(self):
        if self.running:
            input(
                "\nStop the syringe pump.\n"
                "Press Enter after the pump is stopped..."
            )

        self.running = False
        print("Manual syringe pump confirmed OFF")

    def close(self):
        self.connected = False
# ============================================================
# PINCHER VALVE CONTROLLER
# ============================================================

class PincherValve:
    def __init__(
        self,
        mcp_pin=PINCHER_MCP_PIN,
        mcp_address=MCP_ADDRESS,
    ):
        self.mcp_pin = mcp_pin
        self.mcp_address = mcp_address
        self.i2c = None
        self.mcp = None
        self.pin = None
        self.is_on = False
        self.connected = False

    def connect(self):
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.mcp = MCP23017(
            self.i2c,
            address=self.mcp_address,
        )
        self.pin = self.mcp.get_pin(self.mcp_pin)
        self.pin.direction = Direction.OUTPUT

        # Fail-safe default: route to the post-seeding state until
        # the experiment explicitly powers the pincher.
        self.pin.value = PINCHER_OFF_AFTER_SEEDING
        self.is_on = PINCHER_OFF_AFTER_SEEDING
        self.connected = True

        print(
            f"Pincher valve connected on MCP GP{self.mcp_pin}"
        )

    def set_state(self, powered):
        if not self.connected or self.pin is None:
            raise RuntimeError("Pincher valve is not connected")

        self.pin.value = bool(powered)
        self.is_on = bool(powered)

        state = "ON" if self.is_on else "OFF"
        print(
            f"Pincher valve MCP GP{self.mcp_pin} commanded {state}"
        )

    def on(self):
        self.set_state(True)

    def off(self):
        self.set_state(False)

    def close(self):
        # Leave the physical output OFF when the program exits.
        if self.pin is not None:
            self.pin.value = False
            self.is_on = False

        if self.i2c is not None:
            try:
                self.i2c.deinit()
            except AttributeError:
                pass

        self.pin = None
        self.mcp = None
        self.i2c = None
        self.connected = False


# ============================================================
# SUMMARY FILE
# ============================================================

SUMMARY_FIELDS = [
    "timepoint",
    "timestamp",
    "elapsed_hr",
    "measurement_mode",
    "dc_bias_v",
    "ac_amplitude_v",
    "max_frequency_hz",
    "min_frequency_hz",
    "n_frequency_points",
    "rs_mean",
    "rs_sd",
    "rs_values",
    "pump_running",
    "flow_rate_ul_min",
    "pincher_mcp_pin",
    "pincher_powered",
    "flow_route",
    "notes",
]


def append_summary(folder, row):
    summary_file = folder / "paired_summary.csv"
    exists = summary_file.exists()

    with open(
        summary_file,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SUMMARY_FIELDS,
        )

        if not exists:
            writer.writeheader()

        writer.writerow(row)


# ============================================================
# OUTPUT FILE HANDLING
# ============================================================

def snapshot_data_files():
    """
    Record the EIS output files that exist before a batch.
    This lets us copy all three newly created scan files,
    not only the last one.
    """
    patterns = [
        "eis_*.csv",
        "eis_raw_*.bin",
    ]

    files = set()

    for pattern in patterns:
        files.update(GENERAL_DATA_DIR.glob(pattern))

    return {
        path.resolve()
        for path in files
        if path.is_file()
    }


def copy_new_outputs(
    folder,
    label,
    files_before,
):
    files_after = snapshot_data_files()
    new_files = sorted(
        files_after - files_before,
        key=lambda path: path.stat().st_mtime,
    )

    for index, source in enumerate(
        new_files,
        start=1,
    ):
        destination_name = (
            f"{label}_scanfile{index:02d}_{source.name}"
        )

        shutil.copy2(
            source,
            folder / "raw" / destination_name,
        )

    for plot_name in [
        "nyquist.png",
        "bode_mag.png",
        "bode_phase.png",
    ]:
        source = GENERAL_DATA_DIR / plot_name

        if source.exists():
            shutil.copy2(
                source,
                folder / "plots" / f"{label}_{plot_name}",
            )

    return len(new_files)


# ============================================================
# EIS ACQUISITION
# ============================================================

def run_eis_mode(
    pot,
    pump,
    pincher,
    folder,
    timepoint,
    elapsed_hr,
    measurement_mode,
    dc_bias_v,
    n_scans,
    notes="",
):
    label = (
        f"{timepoint}_{measurement_mode}_"
        f"{int(round(dc_bias_v * 1000)):+d}mV"
    )

    log(
        folder,
        f"Starting {measurement_mode} EIS for {timepoint}: "
        f"DC bias={dc_bias_v:+.3f} V",
    )

    files_before = snapshot_data_files()

    result = pot.run_batch(
        n_scans=n_scans,
        metadata={
            "mode": "biofilm_dc_sweep_pump",
            "sample_name": label,
            "timepoint": timepoint,
            "elapsed_hr": elapsed_hr,
            "measurement_mode": measurement_mode,
            "dc_bias_v": dc_bias_v,
            "pump_running": pump.running,
            "flow_rate_ul_min": pump.flow_rate_ul_min,
            "pincher_mcp_pin": pincher.mcp_pin,
            "pincher_powered": pincher.is_on,
            "flow_route": (
                "seeding_waste_route"
                if pincher.is_on
                else "post_seed_media_route"
            ),
        },
        dc_bias_v=dc_bias_v,
        measurement_mode=measurement_mode,
        ac_amplitude_v=AC_AMPLITUDE_V,
        max_frequency_hz=MAX_FREQUENCY_HZ,
        min_frequency_hz=MIN_FREQUENCY_HZ,
        n_points=N_FREQUENCY_POINTS,
        timeout_seconds=EIS_TIMEOUT_SECONDS,
    )

    copied_count = copy_new_outputs(
        folder=folder,
        label=label,
        files_before=files_before,
    )
    
    append_summary(
        folder,
        {
            "timepoint": timepoint,
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "elapsed_hr": elapsed_hr,
            "measurement_mode": measurement_mode,
            "dc_bias_v": dc_bias_v,
            "ac_amplitude_v": AC_AMPLITUDE_V,
            "max_frequency_hz": MAX_FREQUENCY_HZ,
            "min_frequency_hz": MIN_FREQUENCY_HZ,
            "n_frequency_points": N_FREQUENCY_POINTS,
            "rs_mean": result["Rs_mean"],
            "rs_sd": result["Rs_sd"],
            "rs_values": result["Rs_values"],
            "pump_running": pump.running,
            "flow_rate_ul_min": pump.flow_rate_ul_min,
            "pincher_mcp_pin": pincher.mcp_pin,
            "pincher_powered": pincher.is_on,
            "flow_route": (
                "seeding_waste_route"
                if pincher.is_on
                else "post_seed_media_route"
            ),
            "notes": notes,
        },
    )

    log(
        folder,
        f"Finished {label}: "
        f"Rs_mean={result['Rs_mean']:.3f}, "
        f"Rs_sd={result['Rs_sd']:.3f}; "
        f"copied {copied_count} new files",
    )

    return result



def run_paired_timepoint(
    pot,
    pump,
    pincher,
    folder,
    timepoint,
    elapsed_hr,
    notes="",
    run_dc_sweep=True,
):
    """
    Always run three zero-bias EIS scans.

    When run_dc_sweep=True, also run one scan at each
    DC bias from +0.1 V through +0.8 V.
    """

    results = {}

    zero_result = run_eis_mode(
        pot=pot,
        pump=pump,
        pincher=pincher,
        folder=folder,
        timepoint=timepoint,
        elapsed_hr=elapsed_hr,
        measurement_mode="zero_bias",
        dc_bias_v=0.0,
        n_scans=ZERO_BIAS_SCANS,
        notes=f"{notes}; zero-DC-offset EIS",
    )

    results["zero_bias"] = zero_result

    # Ordinary hourly timepoints stop here.
    if not run_dc_sweep:
        log(
            folder,
            f"{timepoint}: zero-bias monitoring complete; "
            "full DC sweep not scheduled",
        )
        return results

    # Every third hour, baseline, and post-seed t0 continue here.
    for sweep_index, dc_bias_v in enumerate(
        DC_BIAS_VALUES_V,
        start=1,
    ):
        log(
            folder,
            f"Waiting {BIAS_SETTLE_SECONDS} s before "
            f"sweep step {sweep_index}/{len(DC_BIAS_VALUES_V)} "
            f"at {dc_bias_v:+.3f} V",
        )

        time.sleep(BIAS_SETTLE_SECONDS)

        measurement_mode = (
            f"dc_sweep_{int(round(dc_bias_v * 1000)):04d}mV"
        )

        biased_result = run_eis_mode(
            pot=pot,
            pump=pump,
            pincher=pincher,
            folder=folder,
            timepoint=timepoint,
            elapsed_hr=elapsed_hr,
            measurement_mode=measurement_mode,
            dc_bias_v=dc_bias_v,
            n_scans=DC_SWEEP_SCANS_PER_VOLTAGE,
            notes=(
                f"{notes}; DC-bias sweep step "
                f"{sweep_index}/{len(DC_BIAS_VALUES_V)} "
                f"at {dc_bias_v:+.3f} V"
            ),
        )

        results[f"{dc_bias_v:.1f}V"] = biased_result

    log(
        folder,
        f"Waiting {ZERO_BIAS_RECOVERY_SECONDS} s after "
        "completion of the DC-bias sweep",
    )

    time.sleep(ZERO_BIAS_RECOVERY_SECONDS)

    return results
# ============================================================
# EXPERIMENT
# ============================================================

def run_biofilm_dc_sweep_experiment():
    folder, backup_folder = make_experiment_folder()
    clear_old_stop_file(folder)

    log(folder, "Biofilm DC-bias sweep pump experiment started")
    log(folder, f"Experiment folder: {folder}")
    log(folder, f"Static seeding: {SEED_HOURS} hr")
    log(folder, f"Flow rate: {FLOW_RATE_UL_MIN} uL/min")

    pot = PalmSens(
        port=PALMSENS_PORT,
        simulate=PALMSENS_SIMULATE,
    )

    pump = ManualSyringePump()

    pincher = PincherValve(
        mcp_pin=PINCHER_MCP_PIN,
        mcp_address=MCP_ADDRESS,
    )

    experiment_start = datetime.now()

    try:
        pot.connect()
        pump.connect()
        pincher.connect()

        # -------------------------------
        # Initial routing
        # -------------------------------

        pincher.set_state(PINCHER_ON_DURING_SEEDING)
     

        input(
            "\nLoad sterile LB/media.\n"
            "Press Enter to collect the baseline..."
        )

        run_paired_timepoint(
            pot=pot,
            pump=pump,
            pincher=pincher,
            folder=folder,
            timepoint="baseline_media",
            elapsed_hr=0,
            notes="Sterile media baseline",
        )

        # -------------------------------
        # Seeding
        # -------------------------------

        input(
            "\nSeed bacteria.\n"
            "Press Enter to begin the 3-hour attachment..."
        )

        log(folder, "Static attachment started")

        completed_wait = countdown_wait(
            total_seconds=SEED_HOURS * 3600,
            folder=folder,
            next_event="post_seed_t0",
        )

        if not completed_wait:
            return

        pincher.set_state(PINCHER_OFF_AFTER_SEEDING)

        elapsed_hr = (
            datetime.now() - experiment_start
        ).total_seconds() / 3600

        run_paired_timepoint(
            pot=pot,
            pump=pump,
            pincher=pincher,
            folder=folder,
            timepoint="post_seed_t0",
            elapsed_hr=elapsed_hr,
            notes="End of attachment period",
        )

        # -------------------------------
        # Begin flow
        # -------------------------------

        pump.start(flow_rate_ul_min=FLOW_RATE_UL_MIN)

        log(
            folder,
            f"Continuous flow started at {FLOW_RATE_UL_MIN} uL/min",
        )

        flow_start_monotonic = time.monotonic()
        flow_hour = 1

        while not stop_requested():

            next_timepoint = f"flow_t{flow_hour}h"

            target_time = (
                flow_start_monotonic
                + flow_hour * MEASUREMENT_INTERVAL_MINUTES * 60
            )

            seconds_until_target = (
                target_time - time.monotonic()
            )

            if seconds_until_target > 0:

                completed_wait = countdown_wait(
                    total_seconds=seconds_until_target,
                    folder=folder,
                    next_event=next_timepoint,
                )

                if not completed_wait:
                    break

            else:

                log(
                    folder,
                    f"{next_timepoint} running late "
                    f"({abs(seconds_until_target)/60:.2f} min)"
                )

            timing_offset_seconds = (
                time.monotonic() - target_time
            )

            elapsed_hr = (
                datetime.now() - experiment_start
            ).total_seconds() / 3600

            perform_full_sweep = (
                flow_hour % 3 == 0
            )

            log(
                folder,
                f"{next_timepoint}: "
                + (
                    "ZERO-BIAS ONLY"
                    if not perform_full_sweep
                    else "ZERO-BIAS + FULL DC SWEEP"
                ),
            )

            try:

                run_paired_timepoint(
                    pot=pot,
                    pump=pump,
                    pincher=pincher,
                    folder=folder,
                    timepoint=next_timepoint,
                    elapsed_hr=elapsed_hr,
                    notes=(
                        "Continuous biofilm monitoring; "
                        f"offset={timing_offset_seconds:+.1f} s"
                    ),
                    run_dc_sweep=perform_full_sweep,
                )

            except Exception as exc:

                log(
                    folder,
                    f"{next_timepoint} failed: {exc}"
                )

            flow_hour += 1

        log(folder, "Experiment stop requested")

    except KeyboardInterrupt:

        log(
            folder,
            "Experiment interrupted by Ctrl+C",
        )

    finally:

        try:
            if pincher.connected:
                pincher.off()
        except Exception:
            pass

        try:
            pincher.close()
        except Exception:
            pass

        try:
            if pump.connected:
                pump.stop()
        except Exception:
            pass

        try:
            pump.close()
        except Exception:
            pass

        try:
            if hasattr(pot, "device") and pot.device is not None:
                pot.device.close()
        except Exception:
            pass

        if STOP_FILE.exists():
            STOP_FILE.unlink()

        log(folder, "Experiment finished")
if __name__ == "__main__":
    run_biofilm_dc_sweep_experiment()