BioLoop simulation guide

This file documents how to run BioLoop in simulation mode (no hardware required).

Quick simulation run

1. Create a virtual environment and install dev requirements:

   python -m venv .venv
   # Activate: .\.venv\Scripts\activate (PowerShell)
   pip install -r requirements.txt
   pip install -r requirements-dev.txt

2. Run the master CLI in simulation mode:

   python main.py --simulate --mode predict --n-scans 1

3. Output files are written to the `data/` directory. Logs are appended to `data/bioloop_log.csv`.

Automated tests

Run the test suite (CI runs these automatically):

   pytest -q

Design notes

- Simulation mode forces LED and Valve controllers into a simulated mode that prints status instead of touching hardware. The PalmSens interface supports a `simulate=True` flag that returns synthetic Rs values.
- The master CLI accepts `--simulate` and forwards this to initialization and protocols.
- Keep hardware-specific libraries out of CI by using simulation mode and guarding real hardware initialization.

If you need a richer simulator (pre-recorded EIS files or deterministic Rs values), add a `simulator/` submodule and a simple configuration file `simulator/config.yaml` to control behavior.