from initialize import initialize_bioloop
from protocols.salinity_test import run_salinity_demo


def test_run_salinity_demo_sim():
    system = initialize_bioloop(simulate=True)
    # run in simulation mode; should complete and produce a log row
    run_salinity_demo(system=system, mode="predict", n_scans=1, simulate=True)
    from pathlib import Path

    log_file = Path("data") / "bioloop_log.csv"
    assert log_file.exists()
