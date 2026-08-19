# initialize.py

from pathlib import Path
from hardware.valves import ValveController
from hardware.leds import LEDController

from config.settings import (
    EMPIRICAL_MODEL,
    GROUNDED_MODEL,
)

from electrochem.kcell_calibration import get_latest_kcell


def initialize_bioloop(simulate=False):

    print("======================")
    print("Starting BioLoop")
    print("======================")


    # -----------------------
    # Hardware initialization
    # -----------------------

    print("Checking valve controller...")
    valves = ValveController(simulate=simulate)


    print("Checking LED controller...")
    leds = LEDController(simulate=simulate)


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

    # optional: load playback config into system so protocols can access canned files
    playback_cfg_path = Path("simulator/config.yaml")
    if playback_cfg_path.exists():
        # Prefer PyYAML if available, but fall back to a simple parser if not installed.
        try:
            import yaml

            cfg = yaml.safe_load(playback_cfg_path.read_text())
            if cfg and "files" in cfg:
                playback = cfg["files"]
            else:
                playback = None
        except Exception:
            # Simple fallback parser for a minimal YAML list under 'files:'
            try:
                lines = playback_cfg_path.read_text().splitlines()
                files = []
                in_files = False
                for ln in lines:
                    ln = ln.strip()
                    if not in_files:
                        if ln.startswith("files:"):
                            in_files = True
                        continue
                    if ln.startswith("-"):
                        files.append(ln.lstrip("- ").strip())
                playback = files if files else None
            except Exception:
                playback = None
    else:
        playback = None

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
        "playback": playback,
    }