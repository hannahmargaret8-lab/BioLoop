from electrochem.eis import methodscript_voltage, methodscript_frequency, build_eis_script


def test_methodscript_voltage():
    assert methodscript_voltage(0.01) == "10m"
    assert methodscript_voltage(0.0) == "0m"


def test_methodscript_frequency():
    assert methodscript_frequency(1000) == "1k"
    assert methodscript_frequency(0.1) == "100m"


def test_build_eis_script_valid():
    s = build_eis_script(ac_amplitude_v=0.01, n_points=3)
    assert "meas_loop_eis" in s
