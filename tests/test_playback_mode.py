from pathlib import Path
import subprocess


def test_playback_main_runs():
    # run the main CLI in playback simulation mode
    cmd = ["python", "main.py", "--simulate-mode", "playback", "--mode", "predict", "--n-scans", "2"]
    subprocess.run(cmd, check=True)

    data_dir = Path("data")
    assert data_dir.exists()
    eis_files = list(data_dir.glob("eis_*.csv"))
    assert len(eis_files) >= 1
