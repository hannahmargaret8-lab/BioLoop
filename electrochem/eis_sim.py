# electrochem/eis_sim.py

import numpy as np


class PalmSens:
    """
    Simulation version of PalmSens/EmStat interface.

    Mimics real EIS output:
    - run_scan() returns Rs
    - run_batch() returns mean and SD

    Used for software testing without hardware.
    """

    def __init__(self):

        self.connected = False

        print("PalmSens simulation mode")


    def connect(self):

        print("Simulated PalmSens connected")

        self.connected = True


    def simulate_scan(self):

        return np.random.normal(
            loc=36.7,
            scale=0.2,
        )


    def run_scan(self):

        if not self.connected:
            raise RuntimeError(
                "PalmSens not connected"
            )

        return self.simulate_scan()


    def run_batch(
        self,
        n_scans=3,
    ):

        results = []


        for i in range(n_scans):

            print(
                f"Running simulated EIS scan {i+1}/{n_scans}"
            )

            Rs = self.run_scan()

            results.append(Rs)


        results = np.array(results)


        return {

            "Rs_values":
                results.tolist(),

            "Rs_mean":
                float(
                    np.mean(results)
                ),

            "Rs_sd":
                float(
                    np.std(
                        results,
                        ddof=1,
                    )
                )
                if len(results) > 1
                else 0.0,
        }


if __name__ == "__main__":

    pot = PalmSens()

    pot.connect()

    print(
        pot.run_batch(
            n_scans=3
        )
    )