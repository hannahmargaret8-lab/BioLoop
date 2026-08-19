# BioLoop

BioLoop is a prototype research platform for automated electrochemical monitoring and experimental control of microbial biofilm systems. The project was developed to integrate electrochemical impedance spectroscopy (EIS), fluidic control, embedded hardware, experimental scheduling, and data analysis within a modular Python-based software stack.

The broader BioLoop concept follows a sensor → controller → fluidics → biology → sensor architecture, with the long-term goal of enabling continuous, multiparametric biofilm characterization and adaptive experimental control.

   Research status: BioLoop is experimental research software developed as part of an undergraduate            research project. Individual subsystems and experimental workflows were tested during development, but      the complete platform should not be considered a fully validated laboratory instrument.

## Project Overview

BioLoop was developed to support automated and semi-automated laboratory workflows involving:

- Electrochemical impedance spectroscopy (EIS)
- Screen-printed electrochemical sensors
- Automated valve and fluidic control
- Embedded hardware control and experiment scheduling
- Salinity/conductivity calibration and exploratory ionic-strength estimation
- Electrode quality-control and cleaning studies
- Long-term biofilm monitoring experiments
- Automated status and rule-based feedback
- Experimental data logging and post-run analysis

The software is organized modularly so that sensing, hardware control, experimental protocols, analysis, and feedback methods can be developed or replaced independently.

## Repository layout

- `main.py` — primary entry point for a demonstration/integrated workflows
- `initialize.py` — hardware initialization and calibration loading
- `config/settings.py` — model, calibration, and hardware configuration
- `hardware/` — valve, pump, and LED control classes
- `electrochem/` — EIS acquisition, salinity modeling, calibration, and electrode quality-control tools
- `protocols/` — run workflows such as salinity tests, DC pump tests, and wash routines
- `feedback/` — salinity/fault interpretation logic
- `analysis/` — plotting and analysis utilities
- `utils/` — shared helper utilities
- `data/` — runtime experiment output; excluded from version control where appropriate

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

## Hardware Dependencies

Several BioLoop workflows require laboratory hardware and will not function on a standard computer without the appropriate devices connected and configured.

Hardware used during development included:

- Raspberry Pi controller
- PalmSens EmStat4X potentiostat
- Screen-printed electrodes
- Pneumatically actuated microfluidic valves
- Solenoid valve manifold
- Fluid delivery hardware
- LED status indicators

Hardware mappings, calibration parameters, and experimental settings may be specific to the original BioLoop configuration and should be verified before running experiments on a different system.

## Calibration and Scientific Use

Calibration models and parameter values included in this repository were developed for exploratory laboratory experiments and specific hardware configurations. In particular, salinity and ionic-strength estimation should be considered preliminary and should not be assumed to provide validated quantitative measurements outside the conditions under which the calibration was generated.

Users extending BioLoop should independently calibrate and validate the system for their electrodes, chamber geometry, solutions, organisms, and experimental conditions.

## Project Status

BioLoop should be considered a research prototype and development platform, rather than finished laboratory software.

During the initial development period, work focused on establishing:

- Potentiostat communication and automated EIS acquisition
- Embedded control of valves and visual status indicators
- Automated experimental scheduling and data logging
- Preliminary salinity/conductivity sensing
- Electrode cleaning and quality-control workflows
- Pilot long-term biofilm monitoring
- Foundations for automated experimental feedback

Some modules represent exploratory or partially validated work and are retained to support continued development. Future work should include additional biological replicates, improved calibration, independent biological validation of electrochemical measurements, and further integration of sensing with automated fluidic control.

## AI-Assisted Development

Generative AI tools, including OpenAI Codex and other AI coding assistants, were used during development of the BioLoop software stack to assist with tasks including code generation, debugging, refactoring, documentation, and software organization.

AI-generated or AI-assisted code was reviewed, modified, and integrated by the project developer. Because this repository contains prototype research software, all code—whether human-written or AI-assisted—should be independently reviewed and validated before use in critical or production laboratory applications.

