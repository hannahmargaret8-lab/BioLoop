# electrochem/eis.py

import numpy as np
import serial
import time


class EmStat4X:

    def __init__(self, port="/dev/ttyUSB0"):
        self.dev = serial.Serial(
            port,
            baudrate=921600,
            timeout=5
        )

    def check_connection(self):
        self.dev.write(b"t\n")
        time.sleep(1)
        return self.dev.read(1000)

    def close(self):
        self.dev.close()


if __name__ == "__main__":
    em = EmStat4X()
    print(em.check_connection())
    em.close()
    

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
        self.device = EmStat4X(port=self.port)
        print(self.device.check_connection())
        self.connected = True

        # TODO: replace with real PyPalmSens / serial connection
        # Example future options:
        # self.device = pypalmsens.connect(self.port)
        # or self.device = serial.Serial(self.port, baudrate=...)


    def run_scan(self):
        if not self.connected:
            raise RuntimeError("PalmSens not connected")

        if self.simulate:
            return self.simulate_scan()

        print("Real EmStat4X connected; using simulated Rs until EIS MethodSCRIPT is implemented")
        return self.simulate_scan()
        # TODO:
        # 1. send MethodSCRIPT / run EIS method
        # 2. collect impedance data
        # 3. extract Rs
        # 4. return Rs

       

    def simulate_scan(self):
        return np.random.normal(loc=36.7, scale=0.2)

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