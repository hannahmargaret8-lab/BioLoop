from utils.logger import log_result
from pathlib import Path


def test_log_result(tmp_path):
    filename = tmp_path / "test_log.csv"
    row = {"value": 1}
    log_result(row, filename=str(filename))
    assert filename.exists()
    text = filename.read_text()
    assert "value" in text
