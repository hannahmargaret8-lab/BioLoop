# config/settings.py


# =========================
# Cell calibration
# =========================

# =========================
# Cell calibration
# =========================

# fallback value from original calibration
# used only if no kcell_calibration.csv exists
K_CELL_DEFAULT = 0.6145  # cm^-1


CALIBRATION = {
    # calibration standard
    "standard_name": "0.1 M NaCl",

    # known concentration / ionic strength
    "standard_I_M": 0.100,

    # conductivity of 0.1 M NaCl standard
    # update if using exact temp-corrected value
    "standard_kappa_S_cm": 0.0106,

    # record keeping
    "K_cell_source": "latest accepted calibration",
}
# =========================
# Conductivity model
# Lambda = Lambda0 - K√I + B*I
# =========================
EMPIRICAL_MODEL = {
    "Lambda0": 142.82,
    "K": 74.737,
    "B": -79.236,
}

GROUNDED_MODEL = {
    "Lambda0": 126.45,   # S cm^2/mol
    "K": 60.0,
    "B": -60.21253491,        # fitted correction
}


# =========================
# Measurement quality
# =========================

QUALITY = {

    # repeatability check
    "max_Rs_sd": 1.5,

    # empirical model agreement
    "max_empirical_error_percent": 15.0,

    # physical sanity check
    "max_grounded_drift_percent": 30.0,
}

# =========================
# Fluid routing
# =========================

VALVES = {
    "sample": 8,
    "wash": 9,
    "waste": 11,
    "air": 12,
}


# =========================
# Demo samples
# =========================

TEST_SAMPLES = {

    "PBS": {
        "I_expected": 0.156,
        "Rs_mean": 38.7731,
        "Rs_sd": 0.54701,
    },

    "LB": {
        "I_expected": 0.180,
        "Rs_mean": 36.6598,
        "Rs_sd": 0.28319,
    },

}