"""Lightweight EmStat4X simulation helper.

This file provides a minimal EmStat4X wrapper and PalmSens shim used during
development and testing. It is intentionally simple and not a full-featured
hardware driver. Prefer the main `electrochem/eis.py` module for production-
grade code; this helper is for local experimentation.
"""

from pathlib import Path
import time
import numpy as np

# Optional dependency: pyserial. Guard import for environments without hardware.
try:
    import serial
    _HAS_SERIAL = True
except Exception:
    serial = None
    _HAS_SERIAL = False


class EmStat4X:
    """Tiny wrapper around a serial EmStat4X device for quick connectivity checks."""

    def __init__(self, port="/dev/ttyUSB0"):
        if not _HAS_SERIAL:
            raise RuntimeError("pyserial not available; cannot open EmStat4X device")
        self.dev = serial.Serial(port, baudrate=921600, timeout=5)

    def check_connection(self):
        # Send a simple identification command; the exact sequence depends on firmware.
        self.dev.write(b"t\n")
        time.sleep(1)
        return self.dev.read(1000)

    def close(self):
        self.dev.close()


class PalmSens:
    """Simple PalmSens shim used for quick runs and simulation during development.

    - If simulate is True, run simulated scans.
    - Otherwise use EmStat4X when pyserial is available.
    """

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

        if not _HAS_SERIAL:
            raise RuntimeError("pyserial is required to use the real EmStat4X device")

        print("Connecting to EmStat4X...")
        self.device = EmStat4X(port=self.port)
        print(self.device.check_connection())
        self.connected = True

    def run_scan(self):
        if not self.connected:
            raise RuntimeError("PalmSens not connected")

        if self.simulate:
            return self.simulate_scan()

        # Placeholder behavior while a full MethodSCRIPT implementation is added.
        # TODO: implement MethodSCRIPT submission and packet parsing.
        print("Real EmStat4X connected; MethodSCRIPT not implemented in this helper")
        return self.simulate_scan()

    def simulate_scan(self):
        # Return a realistic-looking Rs value
        return float(np.random.normal(loc=36.7, scale=0.2))

    def run_batch(self, n_scans=3):
        results = []
        for i in range(n_scans):
            print(f"Running EIS scan {i + 1}/{n_scans}")
            Rs = self.run_scan()
            results.append(Rs)

        results = np.array(results)
        return {
            "Rs_values": results.tolist(),
            "Rs_mean": float(np.mean(results)),
            "Rs_sd": float(np.std(results, ddof=1)),
        }


if __name__ == "__main__":
    # quick manual test when running this file directly
    p = PalmSens(simulate=True)
    p.connect()
    print(p.run_batch(2))