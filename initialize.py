# initialize.py

from hardware.valves import ValveController
from hardware.leds import LEDController

from config.settings import (
    EMPIRICAL_MODEL,
    GROUNDED_MODEL,
)

from electrochem.kcell_calibration import get_latest_kcell


def initialize_bioloop():

    print("======================")
    print("Starting BioLoop")
    print("======================")


    # -----------------------
    # Hardware initialization
    # -----------------------

    print("Checking valve controller...")
    valves = ValveController()


    print("Checking LED controller...")
    leds = LEDController()


    # -----------------------
    # Safe startup state
    # -----------------------

    valves.release_all()
    leds.fault_off()


    # -----------------------
    # Load calibration state
    # -----------------------

    Kcell = get_latest_kcell()

    print("Loaded Kcell:", Kcell)

    print(
        "Empirical model:",
        EMPIRICAL_MODEL,
    )

    print(
        "Grounded reference:",
        GROUNDED_MODEL,
    )


    print("Initialization complete")


    return {
        "valves": valves,
        "leds": leds,

        # useful metadata
        "Kcell": Kcell,
        "empirical_model": EMPIRICAL_MODEL,
        "grounded_model": GROUNDED_MODEL,
    }