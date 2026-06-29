# electrochem/eis.py

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


EIS_SCRIPT = (
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
    "meas_loop_eis f r j 10m 100k 1 51 0m\n"
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

    def run_eis_raw(self):
        self.dev.reset_input_buffer()
        self.dev.write(EIS_SCRIPT.encode())

        chunks = []
        start = time.time()

        while time.time() - start < 75:
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
    def __init__(self, port="/dev/ttyUSB0", simulate=False):
        self.port = port
        self.simulate = simulate
        self.connected = False
        self.device = None

    def connect(self):
        if self.simulate:
            print("PalmSens simulation mode")
            self.connected = True
            return

        print("Connecting to EmStat4X...")
        self.device = EmStat4X(self.port)
        print(self.device.check_connection())
        self.connected = True

    def run_scan(self, metadata=None):
        import pandas as pd

        if metadata is None:
            metadata = {}

        mode = safe_name(metadata.get("mode", "unknown"))
        sample_name = safe_name(metadata.get("sample_name", "sample"))
        known_I = metadata.get("known_I")
        predicted_I = metadata.get("predicted_I")

        if not self.connected:
            raise RuntimeError("PalmSens not connected")

        if self.simulate:
            return self.simulate_scan()

        print("Running real EIS scan")

        raw = self.device.run_eis_raw()
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
        return float(np.random.normal(loc=36.7, scale=0.2))

    def run_batch(self, n_scans=3, metadata=None):
        if metadata is None:
            metadata = {}

        results = []

        for i in range(n_scans):
            scan_metadata = metadata.copy()
            scan_metadata["scan_index"] = i + 1
            scan_metadata["n_scans"] = n_scans

            print(f"Running EIS scan {i + 1}/{n_scans}")
            results.append(self.run_scan(metadata=scan_metadata))

        results = np.array(results)

        return {
            "Rs_values": results.tolist(),
            "Rs_mean": float(np.mean(results)),
            "Rs_sd": float(np.std(results, ddof=1)) if len(results) > 1 else 0.0,
        }


if __name__ == "__main__":
    pot = PalmSens(simulate=False)
    pot.connect()
    print("Rs:", pot.run_scan())