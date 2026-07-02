# electrochem/reference_restore.py

from datetime import datetime
import time
from pathlib import Path

import numpy as np
import serial


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


def encode_ms_value(value):
    """
    Convert decimal value to simple MethodSCRIPT literal.
    Examples:
      -0.25 -> -250m
       0.1  -> 100m
       10   -> 10
    """
    value = float(value)

    if abs(value) < 1:
        return f"{value * 1000:g}m"

    return f"{value:g}"


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


def parse_ca_packets(raw):
    text = raw.decode(errors="ignore")
    rows = []

    for line in text.splitlines():
        line = line.strip()

        if not line.startswith("P"):
            continue

        parts = line[1:].split(";")

        if len(parts) < 2:
            continue

        row = []

        for part in parts[:2]:
            main = part.split(",")[0].strip()
            encoded = main[2:]
            row.append(decode_ms_value(encoded))

        rows.append(row)

    return np.array(rows, dtype=float)


def build_ca_script(hold_v=-0.20, hold_s=5.0, interval_s=0.1):
    hold = encode_ms_value(hold_v)
    interval = encode_ms_value(interval_s)
    runtime = encode_ms_value(hold_s)

    return (
        "e\n"
        "var p\n"
        "var c\n"
        "set_pgstat_chan 0\n"
        "set_pgstat_mode 2\n"
        "set_range ba 100u\n"
        "set_autoranging ba 100p 10m\n"
        "cell_on\n"
        f"meas_loop_ca p c {hold} {interval} {runtime}\n"
        "pck_start\n"
        "pck_add p\n"
        "pck_add c\n"
        "pck_end\n"
        "endloop\n"
        "on_finished:\n"
        "cell_off\n"
        "\n"
    )


def summarize_ca(time_s, potential_v, current_a):
    current_uA = current_a * 1e6

    if len(time_s) > 1:
        charge_c = np.trapezoid(current_a, time_s)
    else:
        charge_c = np.nan

    return {
        "I_initial_uA": float(current_uA[0]),
        "I_final_uA": float(current_uA[-1]),
        "I_min_uA": float(np.min(current_uA)),
        "I_max_uA": float(np.max(current_uA)),
        "charge_uC": float(charge_c * 1e6),
        "n_points": int(len(current_a)),
        "potential_mean_V": float(np.mean(potential_v)),
    }

def plot_reference_restore(csv_file, out_dir="data"):
    import pandas as pd
    import matplotlib.pyplot as plt

    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    df = pd.read_csv(csv_file)

    time_s = df["time_s"].to_numpy()
    potential_v = df["potential_V"].to_numpy()
    current_uA = df["current_uA"].to_numpy()

    plt.figure()
    plt.plot(time_s, current_uA, marker="o")
    plt.xlabel("Time (s)")
    plt.ylabel("Current (uA)")
    plt.title("Reference Restoration: Current vs Time")
    plt.grid(True)
    plt.savefig(out / "ref_restore_current.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.plot(time_s, potential_v, marker="o")
    plt.xlabel("Time (s)")
    plt.ylabel("Potential vs fresh Ag/AgCl (V)")
    plt.title("Reference Restoration: Potential vs Time")
    plt.grid(True)
    plt.savefig(out / "ref_restore_potential.png", dpi=300, bbox_inches="tight")
    plt.close()

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

    def run_ca_raw(self, hold_v=-0.20, hold_s=5.0, interval_s=0.1):
        script = build_ca_script(
            hold_v=hold_v,
            hold_s=hold_s,
            interval_s=interval_s,
        )

        self.dev.reset_input_buffer()
        self.dev.write(script.encode())

        chunks = []
        start = time.time()
        timeout = hold_s + 30

        while time.time() - start < timeout:
            data = self.dev.read(4096)

            if data:
                chunks.append(data)
                raw = b"".join(chunks)

                if b"*" in raw[-20:]:
                    break

        return b"".join(chunks), script

    def close(self):
        self.dev.close()


class ReferenceRestorer:
    def __init__(self, port="/dev/ttyUSB0", simulate=False):
        self.port = port
        self.simulate = simulate
        self.connected = False
        self.device = None

    def connect(self):
        if self.simulate:
            print("Reference restoration simulation mode")
            self.connected = True
            return

        print("Connecting to EmStat4X for reference restoration...")
        self.device = EmStat4X(self.port)
        print(self.device.check_connection())
        self.connected = True

    def run_restore(self, metadata=None):
        import pandas as pd

        if metadata is None:
            metadata = {}

        if not self.connected:
            raise RuntimeError("ReferenceRestorer not connected")

        electrode_id = safe_name(metadata.get("electrode_id", "SPE01"))
        electrolyte = safe_name(metadata.get("electrolyte", "MgSO4"))

        hold_v = float(metadata.get("hold_v", -0.20))
        hold_s = float(metadata.get("hold_s", 5.0))
        interval_s = float(metadata.get("interval_s", 0.1))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        Path("data").mkdir(exist_ok=True)

        if self.simulate:
            time_s = np.arange(0, hold_s + interval_s, interval_s)
            potential_v = np.full_like(time_s, hold_v, dtype=float)
            current_a = -2e-6 * np.exp(-time_s / 3) - 0.2e-6
            raw = b"SIMULATED"
            script = build_ca_script(hold_v, hold_s, interval_s)
        else:
            print("Running chronoamperometric reference restoration")
            print("WIRING:")
            print("  WE = damaged Poten Ag/AgCl reference")
            print("  RE = fresh Poten Ag/AgCl reference")
            print("  CE = fresh Poten counter electrode")
            print(f"Hold: {hold_v:+.3f} V for {hold_s} s")

            raw, script = self.device.run_ca_raw(
                hold_v=hold_v,
                hold_s=hold_s,
                interval_s=interval_s,
            )

            data = parse_ca_packets(raw)

            if data.size == 0:
                raw_text = raw.decode(errors="ignore")
                print("CA decode failed. Raw response preview:")
                print(raw_text[:1200])
                raise RuntimeError("No valid CA packets decoded")

            potential_v = data[:, 0]
            current_a = data[:, 1]
            time_s = np.arange(len(current_a)) * interval_s

        summary = summarize_ca(time_s, potential_v, current_a)

        raw_file = f"data/ref_restore_raw_{electrode_id}_{electrolyte}_{timestamp}.bin"
        method_file = f"data/ref_restore_method_{electrode_id}_{electrolyte}_{timestamp}.txt"
        csv_file = f"data/ref_restore_{electrode_id}_{electrolyte}_{timestamp}.csv"
        latest_file = "data/ref_restore_last_scan.csv"

        Path(raw_file).write_bytes(raw)
        Path(method_file).write_text(script)

        df = pd.DataFrame(
            {
                "time_s": time_s,
                "potential_V": potential_v,
                "current_A": current_a,
                "current_uA": current_a * 1e6,
                "timestamp": timestamp,
                "mode": "reference_restore_CA",
                "electrode_id": metadata.get("electrode_id"),
                "electrolyte": metadata.get("electrolyte"),
                "hold_v": hold_v,
                "hold_s": hold_s,
                "interval_s": interval_s,
                "WE": "damaged Poten Ag/AgCl reference",
                "RE": "fresh Poten Ag/AgCl reference",
                "CE": "fresh Poten counter electrode",
                **summary,
            }
        )

        df.to_csv(csv_file, index=False)
        df.to_csv(latest_file, index=False)

        plot_reference_restore(latest_file)

        print("Reference restoration complete")
        print(f"I final = {summary['I_final_uA']:.3f} uA")
        print(f"Charge = {summary['charge_uC']:.3f} uC")
        print(f"Saved: {csv_file}")
        print("Saved plots: data/ref_restore_current.png and data/ref_restore_potential.png")

        return summary

    def close(self):
        if self.device is not None:
            self.device.close()


if __name__ == "__main__":
    restorer = ReferenceRestorer(port="/dev/ttyUSB0", simulate=False)
    restorer.connect()

    result = restorer.run_restore(
        metadata={
            "electrode_id": "SPE01",
            "electrolyte": "MgSO4",
            "hold_v": -0.20,
            "hold_s": 5.0,
            "interval_s": 0.1,
        }
    )

    print(result)