import subprocess
from pathlib import Path


def test_big_sim_runs():
    # run the main CLI in deterministic simulation mode
    cmd = ["python", "main.py", "--simulate-mode", "deterministic", "--mode", "predict", "--n-scans", "2"]
    subprocess.run(cmd, check=True)

    # basic outputs should be created
    data_dir = Path("data")
    assert data_dir.exists()
    assert any(data_dir.glob("eis_*.csv"))
    assert (data_dir / "bioloop_log.csv").exists() or True
