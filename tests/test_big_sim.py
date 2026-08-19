import subprocess
from pathlib import Path


def test_big_sim_runs():
    # run the main CLI in deterministic simulation mode
    cmd = ["python", "main.py", "--simulate-mode", "deterministic", "--mode", "predict", "--n-scans", "2"]
    subprocess.run(cmd, check=True)

    # basic outputs should be created
    data_dir = Path("data")
    assert data_dir.exists()
    eis_files = list(data_dir.glob("eis_*.csv"))
    assert len(eis_files) >= 1
    assert (data_dir / "bioloop_log.csv").exists()
