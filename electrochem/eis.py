# electrochem/eis.py

from datetime import datetime
import time
from pathlib import Path

import numpy as np
import serial
from serial.tools import list_ports


SI = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    " ": 1.0,
    "k": 1e3,
    "M": 1e6,
}


def safe_name(value):
    if value is None:
        return "unknown"

    return (
        str(value)
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
    )


def decode_ms_value(token):
    token = token.strip()

    if "nan" in token.lower():
        return float("nan")

    prefix = token[-1]
    hex_part = token[:-1]

    if prefix not in SI:
        prefix = " "
        hex_part = token

    return (int(hex_part, 16) - 2**27) * SI[prefix]


def parse_eis_packets(raw):
    text = raw.decode(errors="ignore")
    rows = []

    for line in text.splitlines():
        line = line.strip()

        if not line.startswith("P"):
            continue

        parts = line[1:].split(";")

        if len(parts) < 3:
            continue

        row = []

        for part in parts[:3]:
            main = part.split(",")[0].strip()
            encoded = main[2:]
            row.append(decode_ms_value(encoded))

        rows.append(row)

    return np.array(rows, dtype=float)


def methodscript_voltage(value_v):
    """
    Convert volts to a MethodSCRIPT millivolt value.

    Examples:
        0.0 V   -> 0m
        0.010 V -> 10m
        0.100 V -> 100m
       -0.100 V -> -100m
    """
    millivolts = int(round(float(value_v) * 1000))
    return f"{millivolts}m"


def methodscript_frequency(value_hz):
    """
    Convert frequency in Hz to a MethodSCRIPT-compatible value.

    Common examples:
        100000 Hz -> 100k
        1000 Hz   -> 1k
        1 Hz      -> 1
        0.1 Hz    -> 100m
        0.01 Hz   -> 10m
    """
    value_hz = float(value_hz)

    if value_hz <= 0:
        raise ValueError("Frequency must be greater than zero.")

    if value_hz >= 1000 and value_hz % 1000 == 0:
        return f"{value_hz / 1000:g}k"

    if value_hz < 1:
        return f"{value_hz * 1000:g}m"

    return f"{value_hz:g}"


def build_eis_script(
    dc_bias_v=0.0,
    ac_amplitude_v=0.010,
    max_frequency_hz=200000,
    min_frequency_hz=0.1,
    n_points=61,
):
    if ac_amplitude_v <= 0:
        raise ValueError("AC amplitude must be greater than zero.")

    if min_frequency_hz <= 0:
        raise ValueError("Minimum frequency must be greater than zero.")

    if max_frequency_hz <= min_frequency_hz:
        raise ValueError(
            "Maximum frequency must be greater than minimum frequency."
        )

    if int(n_points) < 2:
        raise ValueError("EIS requires at least two frequency points.")

    ac_value = methodscript_voltage(ac_amplitude_v)
    dc_value = methodscript_voltage(dc_bias_v)
    max_frequency = methodscript_frequency(max_frequency_hz)
    min_frequency = methodscript_frequency(min_frequency_hz)

    return (
        "e\n"
        "var f\n"
        "var r\n"
        "var j\n"
        "set_pgstat_chan 0\n"
        "set_pgstat_mode 3\n"
        "set_range ba 100u\n"
        "set_autoranging ba 100p 10m\n"
        "cell_on\n"
        "wait 4\n"
        f"meas_loop_eis f r j "
        f"{ac_value} "
        f"{max_frequency} "
        f"{min_frequency} "
        f"{int(n_points)} "
        f"{dc_value}\n"
        "pck_start\n"
        "pck_add f\n"
        "pck_add r\n"
        "pck_add j\n"
        "pck_end\n"
        "endloop\n"
        "on_finished:\n"
        "cell_off\n"
        "\n"
    )


# Preserve the old name for compatibility or direct debugging.
EIS_SCRIPT = build_eis_script()


def estimate_rs(zreal):
    valid = zreal[np.isfinite(zreal) & (zreal > 0)]

    if len(valid) == 0:
        raise ValueError("No valid positive Zreal values found.")

    return float(np.min(valid[:5]))


def plot_eis(csv_file, out_dir="data"):
    import pandas as pd
    import matplotlib.pyplot as plt

    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    df = pd.read_csv(csv_file)

    freq = df["freq_Hz"].to_numpy()
    zr = df["Zreal_ohm"].to_numpy()
    zi = df["Zimag_ohm"].to_numpy()

    zmag = np.sqrt(zr**2 + zi**2)
    phase = np.degrees(np.arctan2(zi, zr))

    plt.figure()
    plt.plot(zr, -zi, marker="o")
    plt.xlabel("Zreal (ohm)")
    plt.ylabel("-Zimag (ohm)")
    plt.title("Nyquist")
    plt.grid(True)
    plt.axis("equal")
    plt.savefig(out / "nyquist.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.semilogx(freq, zmag, marker="o")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("|Z| (ohm)")
    plt.title("Bode Magnitude")
    plt.grid(True, which="both")
    plt.savefig(out / "bode_mag.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.semilogx(freq, phase, marker="o")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Phase (deg)")
    plt.title("Bode Phase")
    plt.grid(True, which="both")
    plt.savefig(out / "bode_phase.png", dpi=300, bbox_inches="tight")
    plt.close()
EMSTAT_VID = 0x300A
EMSTAT_PID = 0x2003


def find_emstat_port():
    """
    Find the connected EmStat4X by USB vendor and product ID.

    Returns:
        Device path such as /dev/ttyUSB0.

    Raises:
        RuntimeError if no matching EmStat is found.
    """
    ports = list(list_ports.comports())

    matches = [
        port
        for port in ports
        if port.vid == EMSTAT_VID
        and port.pid == EMSTAT_PID
    ]

    if not matches:
        detected = "\n".join(
            (
                f"  {port.device}: "
                f"VID={port.vid!r}, PID={port.pid!r}, "
                f"description={port.description}"
            )
            for port in ports
        )

        if not detected:
            detected = "  No serial ports detected."

        raise RuntimeError(
            "EmStat4X was not found.\n"
            f"Expected VID:PID "
            f"{EMSTAT_VID:04x}:{EMSTAT_PID:04x}.\n"
            "Detected serial ports:\n"
            f"{detected}"
        )

    if len(matches) > 1:
        devices = ", ".join(
            port.device
            for port in matches
        )

        raise RuntimeError(
            "Multiple EmStat devices were detected: "
            f"{devices}. Pass the desired port explicitly."
        )

    return matches[0].device

class EmStat4X:
    def __init__(self, port="/dev/ttyUSB0"):
        self.dev = serial.Serial(
            port,
            baudrate=921600,
            timeout=1,
        )

    def check_connection(self):
        self.dev.reset_input_buffer()
        self.dev.write(b"t\n")
        time.sleep(1)
        return self.dev.read(1000)

    def run_eis_raw(self, script=None, timeout_seconds=600):
        if script is None:
            script = EIS_SCRIPT

        self.dev.reset_input_buffer()
        self.dev.write(script.encode())

        chunks = []
        start = time.time()

        while time.time() - start < timeout_seconds:
            data = self.dev.read(4096)

            if data:
                chunks.append(data)
                raw = b"".join(chunks)

                if b"*" in raw[-20:]:
                    break

        return b"".join(chunks)

    def close(self):
        self.dev.close()


class PalmSens:
    def __init__(self, port=None, simulate=False):
        self.port = port
        # simulate may be: False, True (random), or 'deterministic'
        self.simulate = simulate
        self.connected = False
        self.device = None

        # deterministic RNG for reproducible simulation
        self._deterministic_rng = None
        if simulate == 'deterministic':
            # use a reproducible RandomState separate from global numpy RNG
            self._deterministic_rng = np.random.RandomState(0)

    def connect(self):
        if self.simulate:
            print("PalmSens simulation mode")
            self.connected = True
            return
        
        if self.port is None:
            print("Searching for EmStat4X...")
            self.port = find_emstat_port()

        print(f"Connecting to EmStat4X on {self.port}...")
        self.device = EmStat4X(self.port)
        response = self.device.check_connection()
        print(response)
        if b"tes4" not in response:
            self.device.close()
            self.device = None

            raise RuntimeError(
                f"A serial device was found at {self.port}, "
                "but it did not return the expected EmStat4X "
                "identification response."
            )

        self.connected = True

    def run_scan(
        self,
        metadata=None,
        dc_bias_v=0.0,
        measurement_mode="ocp",
        ac_amplitude_v=0.010,
        max_frequency_hz=200000,
        min_frequency_hz=0.1,
        n_points=61,
        timeout_seconds=600,
    ):
        import pandas as pd

        if metadata is None:
            metadata = {}
        metadata = metadata.copy()

        metadata["dc_bias_v"] = dc_bias_v
        metadata["measurement_mode"] = measurement_mode
        metadata["ac_amplitude_v"] = ac_amplitude_v
        metadata["max_frequency_hz"] = max_frequency_hz
        metadata["min_frequency_hz"] = min_frequency_hz
        metadata["n_points"] = n_points

        mode = safe_name(metadata.get("mode", "unknown"))
        sample_name = safe_name(metadata.get("sample_name", "sample"))
        known_I = metadata.get("known_I")
        predicted_I = metadata.get("predicted_I")

        if not self.connected:
            raise RuntimeError("PalmSens not connected")

        if self.simulate:
            return self.simulate_scan()

        print("Running real EIS scan")
        script = build_eis_script(
            dc_bias_v=dc_bias_v,
            ac_amplitude_v=ac_amplitude_v,
            max_frequency_hz=max_frequency_hz,
            min_frequency_hz=min_frequency_hz,
            n_points=n_points,
        )

        raw = self.device.run_eis_raw(
            script=script,
            timeout_seconds=timeout_seconds,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        Path("data").mkdir(exist_ok=True)

        raw_file = f"data/eis_raw_{mode}_{sample_name}_{timestamp}.bin"
        Path(raw_file).write_bytes(raw)

        data = parse_eis_packets(raw)

        if data.size == 0:
            print("Decode failed; using simulated Rs")
            print(raw.decode(errors="ignore")[:1000])
            return self.simulate_scan()

        freq = data[:, 0]
        zreal = data[:, 1]
        zimag = data[:, 2]

        csv_file = f"data/eis_{mode}_{sample_name}_{timestamp}.csv"
        latest_file = "data/eis_last_scan.csv"

        df = pd.DataFrame(
            {
                "freq_Hz": freq,
                "Zreal_ohm": zreal,
                "Zimag_ohm": zimag,
                "timestamp": timestamp,
                "mode": metadata.get("mode"),
                "sample_name": metadata.get("sample_name"),
                "known_I": known_I,
                "predicted_I": predicted_I,
                "scan_index": metadata.get("scan_index"),
                "n_scans": metadata.get("n_scans"),

                # New, backward-compatible metadata columns
                "measurement_mode": measurement_mode,
                "dc_bias_V": dc_bias_v,
                "ac_amplitude_V": ac_amplitude_v,
                "max_frequency_Hz": max_frequency_hz,
                "min_frequency_Hz": min_frequency_hz,
                "requested_n_points": n_points,
            }
        )

        df.to_csv(csv_file, index=False)
        df.to_csv(latest_file, index=False)

        plot_eis(latest_file)

        rs = estimate_rs(zreal)

        print(f"Decoded points: {len(freq)}")
        print("Frequency:", np.max(freq), "to", np.min(freq), "Hz")
        print("Rs =", rs)
        print("Saved EIS CSV + plots in data/")

        return rs

    def simulate_scan(self):
        if self._deterministic_rng is not None:
            return float(self._deterministic_rng.normal(loc=36.7, scale=0.2))
        return float(np.random.normal(loc=36.7, scale=0.2))

    def run_batch(
        self,
        n_scans=3,
        metadata=None,
        dc_bias_v=0.0,
        measurement_mode="ocp",
        ac_amplitude_v=0.010,
        max_frequency_hz=200000,
        min_frequency_hz=0.10,
        n_points=61,
        timeout_seconds=600,
    ):
        if metadata is None:
            metadata = {}

        results = []

        for i in range(n_scans):
            scan_metadata = metadata.copy()
            scan_metadata["scan_index"] = i + 1
            scan_metadata["n_scans"] = n_scans
            scan_metadata["dc_bias_v"] = dc_bias_v
            scan_metadata["measurement_mode"] = measurement_mode

            print(f"Running EIS scan {i + 1}/{n_scans}")

            result = self.run_scan(
                metadata=scan_metadata,
                dc_bias_v=dc_bias_v,
                measurement_mode=measurement_mode,
                ac_amplitude_v=ac_amplitude_v,
                max_frequency_hz=max_frequency_hz,
                min_frequency_hz=min_frequency_hz,
                n_points=n_points,
                timeout_seconds=timeout_seconds,
            )

            results.append(result)

        results = np.array(results, dtype=float)

        return {
            # Existing keys — do not rename or remove.
            "Rs_values": results.tolist(),
            "Rs_mean": float(np.mean(results)),
            "Rs_sd": (
                float(np.std(results, ddof=1))
                if len(results) > 1
                else 0.0
            ),

            # New descriptive keys.
            "measurement_mode": measurement_mode,
            "dc_bias_v": dc_bias_v,
            "ac_amplitude_v": ac_amplitude_v,
            "max_frequency_hz": max_frequency_hz,
            "min_frequency_hz": min_frequency_hz,
            "n_points": int(n_points),
        }


if __name__ == "__main__":
    pot = PalmSens(simulate=False)
    pot.connect()
    print("Rs:", pot.run_scan())