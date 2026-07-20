# protocols/biofilm_dc_pump.py

from datetime import datetime
from pathlib import Path
import csv
import shutil
import time

import serial
import board
import busio
from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017

from electrochem.eis import PalmSens


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = PROJECT_ROOT / "data" / "experiments"
GENERAL_DATA_DIR = PROJECT_ROOT / "data"

STOP_FILE = GENERAL_DATA_DIR / "STOP_BIOFILM_DC_RESUME_EXPERIMENT"


# ============================================================
# BIOFILM SETTINGS
# ============================================================

SEED_HOURS = 3
FLOW_RATE_UL_MIN = 5
MEASUREMENT_INTERVAL_MINUTES = 60

EIS_SCANS_PER_MODE = 3
BIAS_SETTLE_SECONDS = 10
ZERO_BIAS_RECOVERY_SECONDS = 10


# ============================================================
# EIS SETTINGS
# ============================================================

PALMSENS_PORT = "/dev/ttyUSB0"
PALMSENS_SIMULATE = False

AC_AMPLITUDE_V = 0.010
DC_BIAS_V = 0.100

MAX_FREQUENCY_HZ = 200000
MIN_FREQUENCY_HZ = 0.1
N_FREQUENCY_POINTS = 61

EIS_TIMEOUT_SECONDS = 240


# ============================================================
# PUMP SETTINGS
# ============================================================

# The Arduino will commonly appear as /dev/ttyACM0.
# Verify this before running.
PUMP_PORT = "/dev/ttyUSB0"
PUMP_BAUDRATE = 9600
PUMP_TIMEOUT_SECONDS = 1

PUMP_SIMULATE = False

# The Arduino code uses these reserved commands.
PUMP_STOP_COMMAND = 0
PUMP_START_COMMAND = 123

# The Arduino uses readString(), so allow enough time between
# separate commands to prevent them from being combined.
PUMP_COMMAND_DELAY_SECONDS = 1.5

STOP_PUMP_WHEN_EXPERIMENT_ENDS = True


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
        / f"{stamp}_biofilm_dc_resume_post_seed"
    )

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "raw").mkdir(exist_ok=True)
    (folder / "plots").mkdir(exist_ok=True)

    return folder


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


# ============================================================
# PUMP CONTROLLER
# ============================================================

class DSCMPump:
    def __init__(
        self,
        port=PUMP_PORT,
        baudrate=PUMP_BAUDRATE,
        timeout=PUMP_TIMEOUT_SECONDS,
        simulate=PUMP_SIMULATE,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.simulate = simulate

        self.device = None
        self.connected = False
        self.running = False
        self.flow_rate_ul_min = None

    def connect(self):
        if self.simulate:
            print("DSCPM pump simulation mode")
            self.connected = True
            return

        print(
            f"Connecting to DSCPM Arduino on {self.port} "
            f"at {self.baudrate} baud..."
        )

        self.device = serial.Serial(
            self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
        )

        # Many Arduino boards reset when the USB serial port opens.
        time.sleep(2)

        self.device.reset_input_buffer()
        self.device.reset_output_buffer()

        self.connected = True
        print("DSCPM Arduino connected")

    def read_available(self):
        if self.simulate or self.device is None:
            return ""

        waiting = self.device.in_waiting

        if waiting <= 0:
            return ""

        return self.device.read(waiting).decode(
            errors="ignore"
        )

    def send_command(self, command):
        if not self.connected:
            raise RuntimeError("DSCPM pump is not connected")

        command_text = f"{command}\n"

        if self.simulate:
            print(f"[PUMP SIMULATION] Sent: {command_text!r}")
            return ""

        # Remove continuous telemetry before sending a command.
        self.read_available()
        self.device.reset_input_buffer()

        self.device.write(command_text.encode("ascii"))
        self.device.flush()

        time.sleep(PUMP_COMMAND_DELAY_SECONDS)

        response = self.read_available()

        print(f"DSCPM command sent: {command}")

        if response:
            print("DSCPM response:")
            print(response[-1000:])

        return response

    def stop(self):
        self.send_command(PUMP_STOP_COMMAND)

        self.running = False
        print("DSCPM pump commanded OFF")

    def set_flow_rate(self, flow_rate_ul_min):
        flow_rate = int(flow_rate_ul_min)

        if flow_rate != flow_rate_ul_min:
            raise ValueError(
                "The current DSCPM Arduino firmware accepts "
                "integer flow-rate commands only."
            )

        if flow_rate <= 0:
            raise ValueError(
                "Flow rate must be greater than zero."
            )

        if flow_rate > 40:
            raise ValueError(
                "DSCPM firmware warns not to exceed "
                "40 uL/min."
            )

        self.send_command(flow_rate)
        self.flow_rate_ul_min = flow_rate

        print(
            f"DSCPM flow rate set to "
            f"{flow_rate} uL/min"
        )

    def start(self, flow_rate_ul_min=None):
        if flow_rate_ul_min is not None:
            self.set_flow_rate(flow_rate_ul_min)

        if self.flow_rate_ul_min is None:
            raise RuntimeError(
                "Set a flow rate before starting the pump."
            )

        self.send_command(PUMP_START_COMMAND)

        self.running = True
        print("DSCPM pump commanded ON")

    def close(self):
        if self.device is not None:
            self.device.close()
            self.device = None

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
        n_scans=EIS_SCANS_PER_MODE,
        metadata={
            "mode": "biofilm_dc_pump",
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
):
    """
    Run zero-bias EIS first, then +100 mV biased EIS.
    """

    zero_result = run_eis_mode(
        pot=pot,
        pump=pump,
        pincher=pincher,
        folder=folder,
        timepoint=timepoint,
        elapsed_hr=elapsed_hr,
        measurement_mode="zero_bias",
        dc_bias_v=0.0,
        notes=f"{notes}; zero-DC-offset EIS",
    )

    log(
        folder,
        f"Waiting {BIAS_SETTLE_SECONDS} s "
        f"before {DC_BIAS_V:+.3f} V EIS",
    )
    time.sleep(BIAS_SETTLE_SECONDS)

    biased_result = run_eis_mode(
        pot=pot,
        pump=pump,
        pincher=pincher,
        folder=folder,
        timepoint=timepoint,
        elapsed_hr=elapsed_hr,
        measurement_mode="dc_bias",
        dc_bias_v=DC_BIAS_V,
        notes=(
            f"{notes}; DC-biased EIS at "
            f"{DC_BIAS_V:+.3f} V"
        ),
    )

    log(
        folder,
        f"Waiting {ZERO_BIAS_RECOVERY_SECONDS} s "
        "after biased EIS",
    )
    time.sleep(ZERO_BIAS_RECOVERY_SECONDS)

    return {
        "zero_bias": zero_result,
        "dc_bias": biased_result,
    }


# ============================================================
# EXPERIMENT
# ============================================================

def run_biofilm_dc_resume_post_seed():
    folder = make_experiment_folder()
    clear_old_stop_file(folder)

    log(folder, "Biofilm DC-bias experiment resumed after completed seeding")
    log(folder, f"Experiment folder: {folder}")
    log(folder, "Media baseline and static seeding are skipped because they were completed previously")
    log(folder, f"Flow rate: {FLOW_RATE_UL_MIN} uL/min")
    log(
        folder,
        f"Pincher routing: MCP GP{PINCHER_MCP_PIN} remains OFF "
        "for this post-seeding resumed experiment",
    )
    log(
        folder,
        f"EIS range: {MAX_FREQUENCY_HZ:g} Hz to "
        f"{MIN_FREQUENCY_HZ:g} Hz",
    )
    log(
        folder,
        f"AC amplitude: {AC_AMPLITUDE_V:.3f} V",
    )
    log(folder, f"DC-bias scan: {DC_BIAS_V:+.3f} V")
    log(
        folder,
        "Experiment will continue until the stop file is created",
    )

    pot = PalmSens(
        port=PALMSENS_PORT,
        simulate=PALMSENS_SIMULATE,
    )

    pump = DSCMPump(
        port=PUMP_PORT,
        baudrate=PUMP_BAUDRATE,
        timeout=PUMP_TIMEOUT_SECONDS,
        simulate=PUMP_SIMULATE,
    )

    pincher = PincherValve(
        mcp_pin=PINCHER_MCP_PIN,
        mcp_address=MCP_ADDRESS,
    )

    experiment_start = datetime.now()
    # Time zero for this file is the start of the resumed post-seeding stage.

    try:
        pot.connect()
        pump.connect()
        pincher.connect()

        # This resume script starts after the three-hour seeding period.
        # Keep MCP GP13 de-energized for the post-seeding media route.
        pincher.set_state(PINCHER_OFF_AFTER_SEEDING)
        log(
            folder,
            f"Pincher MCP GP{PINCHER_MCP_PIN} OFF: "
            "post-seeding media route selected",
        )

        # Critical: firmware defaults to ON, so explicitly stop it
        # until the post-seed t0 EIS measurement is complete.
        pump.stop()
        log(folder, "Pump confirmed commanded OFF")

        log(
            folder,
            "Skipping media-baseline EIS and three-hour seeding; "
            "both were completed before this resumed run",
        )

        input(
            "\nRESUME AFTER COMPLETED SEEDING\n"
            "Confirm MCP GP13 is OFF and the post-seeding media route "
            "is selected.\n"
            "Confirm the pump is OFF.\n"
            "Press Enter to run post-seed t0 EIS and then begin LB flow..."
        )

        elapsed_hr = 0.0

        run_paired_timepoint(
            pot=pot,
            pump=pump,
            pincher=pincher,
            folder=folder,
            timepoint="post_seed_t0",
            elapsed_hr=elapsed_hr,
            notes=(
                "Resumed after completed static attachment; "
                "pincher OFF; post-seeding media route selected; "
                "pump still off"
            ),
        )

        pump.start(
            flow_rate_ul_min=FLOW_RATE_UL_MIN
        )

        log(
            folder,
            f"Continuous LB flow started at "
            f"{FLOW_RATE_UL_MIN} uL/min",
        )

        flow_hour = 1

        while not stop_requested():
            next_timepoint = f"flow_t{flow_hour}h"

            completed_wait = countdown_wait(
                total_seconds=(
                    MEASUREMENT_INTERVAL_MINUTES * 60
                ),
                folder=folder,
                next_event=next_timepoint,
            )

            if not completed_wait:
                break

            elapsed_hr = (
                datetime.now() - experiment_start
            ).total_seconds() / 3600

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
                        "pincher OFF; post-seeding media route; "
                        f"LB flow at "
                        f"{FLOW_RATE_UL_MIN} uL/min"
                    ),
                )

                flow_hour += 1

            except Exception as exc:
                log(
                    folder,
                    f"{next_timepoint} failed: "
                    f"{type(exc).__name__}: {exc}",
                )

                log(
                    folder,
                    "Experiment loop remains active; "
                    "the same timepoint will be retried "
                    "after the next interval",
                )

        log(folder, "Experiment stop requested")

    except KeyboardInterrupt:
        log(
            folder,
            "Experiment interrupted by Ctrl+C; "
            "completed data remain saved",
        )

    finally:
        try:
            if pincher.connected:
                pincher.off()
                log(
                    folder,
                    f"Pincher MCP GP{PINCHER_MCP_PIN} "
                    "commanded OFF on exit",
                )
        except Exception as exc:
            log(
                folder,
                f"Could not switch pincher OFF cleanly: {exc}",
            )

        try:
            pincher.close()
            log(folder, "Pincher MCP connection closed")
        except Exception as exc:
            log(folder, f"Pincher close warning: {exc}")

        if STOP_PUMP_WHEN_EXPERIMENT_ENDS:
            try:
                if pump.connected:
                    pump.stop()
                    log(folder, "Pump commanded OFF on exit")
            except Exception as exc:
                log(
                    folder,
                    f"Could not stop pump cleanly: {exc}",
                )

        try:
            pump.close()
            log(folder, "Pump serial connection closed")
        except Exception as exc:
            log(folder, f"Pump close warning: {exc}")

        try:
            if (
                hasattr(pot, "device")
                and pot.device is not None
            ):
                pot.device.close()

            log(folder, "PalmSens connection closed")
        except Exception as exc:
            log(folder, f"PalmSens close warning: {exc}")

        if STOP_FILE.exists():
            STOP_FILE.unlink()

        log(folder, "Post-seeding resumed biofilm DC-bias experiment finished")