# electrochem/kcell_math.py

import numpy as np


def calculate_K_cell(
    Rs_standard,
    kappa_standard,
):
    return Rs_standard * kappa_standard



def calculate_from_replicates(
    Rs_values,
    kappa_standard,
):

    Rs_values = np.asarray(Rs_values)

    Rs_mean = np.mean(Rs_values)

    Rs_sd = np.std(
        Rs_values,
        ddof=1,
    )

    Kcell = calculate_K_cell(
        Rs_mean,
        kappa_standard,
    )

    return {
        "Kcell": float(Kcell),
        "Rs_mean": float(Rs_mean),
        "Rs_sd": float(Rs_sd),
        "n": len(Rs_values),
    }