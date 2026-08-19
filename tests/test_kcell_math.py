from electrochem.kcell_math import calculate_from_replicates, calculate_K_cell


def test_calculate_from_replicates():
    res = calculate_from_replicates([10.0, 12.0, 11.0], 0.01)
    assert res["n"] == 3
    expected_mean = (10.0 + 12.0 + 11.0) / 3.0
    assert abs(res["Rs_mean"] - expected_mean) < 1e-6
    assert abs(res["Kcell"] - (expected_mean * 0.01)) < 1e-8


def test_calculate_K_cell():
    assert calculate_K_cell(100.0, 0.01) == 1.0
