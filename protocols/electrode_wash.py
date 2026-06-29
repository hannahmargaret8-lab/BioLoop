# protocols/electrode_wash.py

import time


def run(
    valves,
    load_time=3,
    wash_time=5,
):
    """
    Electrode conditioning / wash routine.

    Flow:
        sample exposure
            ↓
        wash electrode
            ↓
        stop flow
            ↓
        ready for EIS
    """

    print("=== Electrode Wash Protocol ===")


    try:
        # -------------------------
        # Sample loading
        # -------------------------

        print("Loading sample")

        valves.release_all()
        time.sleep(0.5)

        valves.open("sample")

        time.sleep(load_time)


        # -------------------------
        # Wash step
        # -------------------------

        print("Washing electrode")

        valves.release_all()
        time.sleep(0.5)

        valves.open("wash")

        time.sleep(wash_time)


        # -------------------------
        # Measurement state
        # -------------------------

        print("Stopping flow for measurement")

        valves.release_all()

        print("Ready for EIS measurement")


    finally:

        print("Ensuring valves safe")

        valves.release_all()