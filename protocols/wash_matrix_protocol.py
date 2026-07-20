# protocols/wash_matrix_protocol.py

from datetime import datetime
from pathlib import Path
import sys
import csv
import time
import random


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from electrochem.eis import PalmSens
from electrochem.reference_restore import ReferenceRestorer


PORT = "/dev/ttyUSB0"
SIMULATE = False
N_SCANS = 3

TEST_SOLUTION = "0.1M_NaCl"

WASH_MATRIX = [
    {
        "category": "control",
        "treatment": "DI_only",
        "steps": [
            ("DI_water", 30),
        ],
    },
    {
        "category": "media_exposure",
        "treatment": "LB_DI",
        "steps": [
            ("LB_media", 60),
            ("DI_water", 120),
        ],
    },
    {
        "category": "sterilization",
        "treatment": "ethanol_DI",
        "steps": [
            ("70_percent_ethanol", 60),
            ("DI_water", 120),
        ],
    },
    {
        "category": "cleaning_sterilization",
        "treatment": "detergent_ethanol_DI",
        "steps": [
            ("detergent_water", 30),
            ("DI_water", 60),
            ("70_percent_ethanol", 60),
            ("DI_water", 120),
        ],
    },
    {
        "category": "cleaning",
        "treatment": "detergent_DI",
        "steps": [
            ("detergent_water", 30),
            ("DI_water", 60),
        ],
    },
    {
        "category": "conditioning",
        "treatment": "MgSO4_DI",
        "steps": [
            ("0.1M_MgSO4", 60),
            ("DI_water", 60),
        ],
    },
    {
        "category": "electrochemical_conditioning",
        "treatment": "MgSO4_CA_DI",
        "steps": [
            ("0.1M_MgSO4", 60),
            ("RUN_CA_RESTORE", 5),
            ("DI_water", 60),
        ],
    },
    {
        "category": "oxidizing_cleaning",
        "treatment": "detergent_DI_bleach_DI",
        "steps": [
            ("detergent_water", 30),
            ("DI_water", 180),
            ("1_to_10_bleach", 10),
            ("DI_water", 120),
        ],
    },
    {
        "category": "acid_cleaning",
        "treatment": "acetic_acid_DI",
        "steps": [
            ("dilute_acetic_acid_or_vinegar", 30),
            ("DI_water", 120),
        ],
    },
    {
        "category": "cleaning_conditioning",
        "treatment": "detergent_MgSO4_DI",
        "steps": [
            ("detergent_water", 30),
            ("DI_water", 60),
            ("0.1M_MgSO4", 60),
            ("DI_water", 60),
        ],
    },
    {
        "category": "organic_residue_control",
        "treatment": "glucose_DI",
        "steps": [
            ("glucose_water", 30),
            ("DI_water", 120),
        ],
    },
    {
        "category": "sterilization",
        "treatment": "isopropanol_DI",
        "steps": [
            ("70_percent_isopropanol", 60),
            ("DI_water", 120),
        ],
    },

]


def prompt_step(solution, duration_s, electrode_id=None):
    if solution == "RUN_CA_RESTORE":
        print("\n--------------------------------")
        print("Run MgSO4 chronoamperometry restoration")
        print("Suggested: -0.20 V for 5 s")
        print("--------------------------------")
        
        restorer = ReferenceRestorer(port=PORT, simulate=SIMULATE)
        try:
            restorer.connect()
            restorer.run_restore(
                metadata={
                    "electrode_id": electrode_id or "unknown",
                    "electrolyte": "MgSO4",
                    "hold_v": -0.20,
                    "hold_s": duration_s,
                    "interval_s": 0.1,
                }
            )
        finally:
            restorer.close()
        return


    print("\n--------------------------------")
    print(f"Apply wash: {solution}")
    print(f"Duration: {duration_s} s")
    print("--------------------------------")
    input("Press Enter once applied...")
    print("Timing wash...")
    time.sleep(duration_s)
    input("Remove/rinse as needed, then press Enter to continue...")

def append_summary(row, path="data/wash_matrix_summary.csv"):
    Path("data").mkdir(exist_ok=True)
    file_exists = Path(path).exists()

    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def run_condition(pot, electrode_id, treatment_name, stage, extra_metadata=None):
    metadata = {
        "mode": f"wash_matrix_{stage}",
        "sample_name": f"{electrode_id}_{treatment_name}_{stage}_{TEST_SOLUTION}",
        "electrode_id": electrode_id,
        "treatment": treatment_name,
        "stage": stage,
        "test_solution": TEST_SOLUTION,
        "category": extra_metadata.get("category") if extra_metadata else None,
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    result = pot.run_batch(n_scans=N_SCANS, metadata=metadata)

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "electrode_id": electrode_id,
        "treatment": treatment_name,
        "stage": stage,
        "test_solution": TEST_SOLUTION,
        "Rs_mean": result["Rs_mean"],
        "Rs_sd": result["Rs_sd"],
        "Rs_values": result["Rs_values"],
        "WE_appearance": extra_metadata.get("WE_appearance") if extra_metadata else None,
        "RE_appearance": extra_metadata.get("RE_appearance") if extra_metadata else None,
        "category": extra_metadata.get("category") if extra_metadata else None,
    }

    append_summary(row)
    return result


def main():
    print("==========================")
    print("BioLoop Wash Matrix")
    print("==========================")

    electrode_id = input("Electrode ID, e.g. SPE01: ").strip()
    we_score = input("WE appearance: matte / semi_shiny / shiny: ").strip()
    re_score = input("RE appearance: normal / gray / dark / black: ").strip()

    pot = PalmSens(port=PORT, simulate=SIMULATE)
    pot.connect()

    treatments = WASH_MATRIX.copy()
    random.shuffle(treatments)

    print("\nRandomized treatment order:")
    order_file = Path("data") / f"treatment_order_{electrode_id}_{datetime.now():%Y%m%d_%H%M%S}.txt"
    Path("data").mkdir(exist_ok=True)

    with open(order_file, "w") as f:
        for i, condition in enumerate(treatments, start=1):
            line = f"{i}. {condition['treatment']}"
            print(line)
            f.write(line + "\n")

    print(f"\nSaved treatment order: {order_file}")

    try:
        for condition in treatments:
            category = condition["category"]
            treatment = condition["treatment"]

            print(f"\n\n=== Treatment: {treatment} ===")
            input(f"Place {electrode_id} in {TEST_SOLUTION} for BEFORE EIS, then press Enter.")

            before = run_condition(
                pot,
                electrode_id,
                treatment,
                "before",
                {"category": category,"WE_appearance": we_score, "RE_appearance": re_score},
            )

            print(f"Before: Rs mean={before['Rs_mean']:.3f}, sd={before['Rs_sd']:.3f}")

            for solution, duration_s in condition["steps"]:
                prompt_step(solution, duration_s, electrode_id=electrode_id)

            input(f"Place {electrode_id} back in {TEST_SOLUTION} for AFTER EIS, then press Enter.")

            after = run_condition(
                pot,
                electrode_id,
                treatment,
                "after",
                {"category": category,"WE_appearance": we_score, "RE_appearance": re_score},
            )

            print(f"After: Rs mean={after['Rs_mean']:.3f}, sd={after['Rs_sd']:.3f}")
            print(f"Delta Rs: {after['Rs_mean'] - before['Rs_mean']:.3f} ohm")

    finally:
        pot.device.close()


if __name__ == "__main__":
    main()