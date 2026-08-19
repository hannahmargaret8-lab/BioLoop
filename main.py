# main.py - master CLI for BioLoop

import argparse
from initialize import initialize_bioloop
from protocols.salinity_test import run_salinity_demo


def main():
    parser = argparse.ArgumentParser(description="Run BioLoop workflows")
    parser.add_argument("--simulate", action="store_true", help="Run in simulation mode (no hardware)")
    parser.add_argument("--simulate-mode", choices=["random", "deterministic", "none"], default="none", help="Simulation mode behavior")
    parser.add_argument("--mode", default="predict", help="Mode for salinity demo: known,predict,calibrate,kcell")
    parser.add_argument("--expected-i", type=float, default=None, help="Expected I for known/calibrate modes")
    parser.add_argument("--sample-name", default=None, help="Sample name for logging")
    parser.add_argument("--n-scans", type=int, default=3, help="Number of EIS scans per batch")

    args = parser.parse_args()

    # Determine final simulate mode: priority --simulate-mode unless none, then --simulate flag
    if args.simulate_mode != "none":
        simulate_mode = args.simulate_mode
    else:
        simulate_mode = "random" if args.simulate else "none"

    system = initialize_bioloop(simulate=(simulate_mode != "none"))

    run_salinity_demo(
        system=system,
        mode=args.mode,
        expected_I=args.expected_i,
        n_scans=args.n_scans,
        sample_name=args.sample_name,
        simulate=(simulate_mode if simulate_mode != "none" else False),
    )

    print("BioLoop run complete")


if __name__ == "__main__":
    main()
