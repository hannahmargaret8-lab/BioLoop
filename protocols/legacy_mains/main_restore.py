# main_restore.py

from electrochem.reference_restore import ReferenceRestorer


PORT = "/dev/ttyUSB0"
SIMULATE = False


RESTORE_SETTINGS = {
    "electrode_id": "SPE01",
    "electrolyte": "MgSO4",
    "hold_v": -0.20,
    "hold_s": 5.0,
    "interval_s": 0.1,
}


def main():
    print("==============================")
    print("BioLoop Reference Restoration")
    print("==============================")

    print("\nConfirm wiring before continuing:")
    print("  PalmSens WE -> damaged Poten Ag/AgCl reference")
    print("  PalmSens RE -> fresh Poten Ag/AgCl reference")
    print("  PalmSens CE -> fresh Poten counter electrode")
    print("\nStarting restoration...")

    restorer = ReferenceRestorer(port=PORT, simulate=SIMULATE)

    try:
        restorer.connect()
        summary = restorer.run_restore(metadata=RESTORE_SETTINGS)

        print("\nSummary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")

    finally:
        restorer.close()


if __name__ == "__main__":
    main()