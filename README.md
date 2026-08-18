# BioLoop

BioLoop is a Python-based laboratory control and analysis stack for electrochemical biofilm and salinity testing. It coordinates hardware control, conductivity calibration, quality checks, and experiment logging for a bench-top fluidic and measurement workflow.

## What this project does

- Initializes and manages fluidic hardware such as valves and LEDs
- Runs electrochemical impedance spectroscopy (EIS) and salinity workflows
- Uses calibration and model-based ionic strength estimation
- Logs results and supports fault/salinity classification feedback
- Provides analysis scripts for post-run plotting and review

## Repository layout

- `main.py` — primary entry point for a demo run
- `initialize.py` — hardware startup and calibration loading
- `config/settings.py` — model, calibration, and valve configuration
- `hardware/` — valve, pump, and LED control classes
- `electrochem/` — EIS, salinity modeling, calibration, and quality checks
- `protocols/` — run workflows such as salinity tests, DC pump tests, and wash routines
- `feedback/` — salinity/fault interpretation logic
- `analysis/` — plotting and analysis utilities
- `utils/` — shared helper utilities
- `data/` — runtime experiment output (ignored by git)

## Quick start

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   . .venv/bin/activate   # Linux/macOS
   # or .\.venv\Scripts\activate  # Windows PowerShell
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run a demo:
   ```bash
   python main.py
   ```

4. Adjust the mode or sample settings in `main.py` as needed for your experiment.

## Notes

- Several scripts assume access to hardware connected to the device (valves, LEDs, and the PalmSens instrument).
- Calibration and prediction behavior is controlled by values in `config/settings.py`.
- This repository is intended for experimental workflows and should be treated as a prototype stack that evolves with hardware configuration and lab procedures.
