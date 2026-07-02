# electrochem/quality_gate.py

from config.settings import GROUNDED_MODEL, QUALITY
from electrochem.salinity_model import (
    conductivity_from_Rs,
    molar_conductivity,
    corrected_kohlrausch,
)


def percent_error(observed, expected):
    if expected is None or expected == 0:
        return None
    return 100 * (observed - expected) / expected


def evaluate_measurement(
    I_expected,
    Rs_mean,
    Rs_sd,
    max_Rs_sd=QUALITY["max_Rs_sd"],
    max_grounded_drift_percent=QUALITY["max_grounded_drift_percent"],
):
    kappa = conductivity_from_Rs(Rs_mean)

    score = 0
    notes = []

    Lambda_obs = None
    Lambda_grounded = None
    grounded_error_percent = None

    # --------------------------
    # 1. Signal repeatability
    # --------------------------

    if Rs_sd <= max_Rs_sd:
        score += 1
        notes.append("Rs SD acceptable")

    elif Rs_sd <= 2 * max_Rs_sd:
        notes.append("Rs SD mildly elevated")

    else:
        score -= 1
        notes.append("Rs SD high")

    # --------------------------
    # 2. Grounded reference check
    # --------------------------

    if I_expected is not None:
        Lambda_obs = molar_conductivity(
            kappa,
            I_expected,
        )

        Lambda_grounded = corrected_kohlrausch(
            I_expected,
            model=GROUNDED_MODEL,
        )

        grounded_error_percent = percent_error(
            Lambda_obs,
            Lambda_grounded,
        )

        if abs(grounded_error_percent) <= max_grounded_drift_percent:
            score += 1
            notes.append("Within grounded physical reference")

        elif abs(grounded_error_percent) <= 2 * max_grounded_drift_percent:
            notes.append("Drifting from grounded reference")

        else:
            score -= 1
            notes.append("Far from grounded reference")

    else:
        notes.append("Unknown sample: skipped grounded reference check")

    # --------------------------
    # 3. Physical sanity
    # --------------------------

    if Rs_mean > 0 and kappa > 0:
        score += 1
        notes.append("Physical values positive")

    else:
        score -= 2
        notes.append("Unphysical value detected")

    # --------------------------
    # Decision
    # --------------------------

    if score >= 3:
        decision = "ACCEPT"
    elif score >= 1:
        decision = "REVIEW"
    else:
        decision = "REJECT"

    return {
        "decision": decision,
        "score": score,
        "I_expected_M": I_expected,
        "Rs_mean_ohm": Rs_mean,
        "Rs_sd_ohm": Rs_sd,
        "kappa_S_cm": kappa,
        "Lambda_observed": Lambda_obs,
        "Lambda_grounded": Lambda_grounded,
        "grounded_error_percent": grounded_error_percent,
        "notes": notes,
    }