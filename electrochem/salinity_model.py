# electrochem/salinity_model.py

import numpy as np
from scipy.optimize import curve_fit, brentq

from config.settings import (
    EMPIRICAL_MODEL,
    GROUNDED_MODEL,
)
from electrochem.kcell_calibration import get_latest_kcell

# ==========================
# Basic conversions
# ==========================

def conductivity_from_Rs(
    Rs_ohm,
    Kcell=None):
    if Kcell is None:
        Kcell = get_latest_kcell()

    return Kcell / Rs_ohm


def molar_conductivity(
    kappa_S_cm,
    I_M,
):
    return 1000 * kappa_S_cm / I_M


# ==========================
# Conductivity model
#
# Lambda = Lambda0 - K√I + B*I
# ==========================

def corrected_kohlrausch(
    I_M,
    model=EMPIRICAL_MODEL,
):
    return (
        model["Lambda0"]
        - model["K"] * np.sqrt(I_M)
        + model["B"] * I_M
    )


def predict_kappa(
    I_M,
    model=EMPIRICAL_MODEL,
):
    Lambda = corrected_kohlrausch(
        I_M,
        model=model,
    )

    return Lambda * I_M / 1000


def predict_Rs_from_I(
    I_M,
    model=EMPIRICAL_MODEL,
    Kcell=None,
):
    if Kcell is None:
        Kcell = get_latest_kcell()

    kappa = predict_kappa(
        I_M,
        model=model,
    )

    return Kcell / kappa


# ==========================
# Prediction
# ==========================

def solve_I_from_Rs(
    Rs_ohm,
    model=EMPIRICAL_MODEL,
    lower=1e-6,
    upper=2.0,
):

    measured_kappa = conductivity_from_Rs(
        Rs_ohm
    )

    def residual(I):
        return (
            predict_kappa(
                I,
                model=model,
            )
            - measured_kappa
        )

    return float(
        brentq(
            residual,
            lower,
            upper,
        )
    )


# ==========================
# Model updating
# ==========================

def fit_empirical_model(
    I_M,
    Rs_ohm,
    Kcell=None,
):
    if Kcell is None:
        Kcell = get_latest_kcell()

    I_M = np.asarray(I_M)
    Rs_ohm = np.asarray(Rs_ohm)

    kappa = conductivity_from_Rs(
        Rs_ohm,
        Kcell,
    )

    Lambda = molar_conductivity(
        kappa,
        I_M,
    )

    def model_func(I, Lambda0, K, B):
        return (
            Lambda0
            - K * np.sqrt(I)
            + B * I
        )

    popt, _ = curve_fit(
        model_func,
        I_M,
        Lambda,
        p0=[
            EMPIRICAL_MODEL["Lambda0"],
            EMPIRICAL_MODEL["K"],
            EMPIRICAL_MODEL["B"],
        ],
    )

    return {
        "Lambda0": popt[0],
        "K": popt[1],
        "B": popt[2],
    }


def calculate_K_cell(
    Rs_standard,
    kappa_standard,
):
    return Rs_standard * kappa_standard


# ==========================
# Diagnostic plotting
# ==========================

def plot_model_update(
    latest_I,
    latest_Rs,
    accepted=False,
):
    import pandas as pd
    import matplotlib.pyplot as plt
    from pathlib import Path

    Path("data").mkdir(exist_ok=True)

    I_grid = np.linspace(0.05, 0.60, 200)
    x_grid = np.sqrt(I_grid)

    Lambda_empirical = corrected_kohlrausch(
        I_grid,
        model=EMPIRICAL_MODEL,
    )

    Lambda_grounded = corrected_kohlrausch(
        I_grid,
        model=GROUNDED_MODEL,
    )

    plt.figure(figsize=(7, 5))

    plt.plot(
        x_grid,
        Lambda_empirical,
        label="Empirical quadratic fit",
    )

    plt.plot(
        x_grid,
        Lambda_grounded,
        linestyle="--",
        label="Grounded reference model",
    )

    cal_path = Path("data/calibration_points.csv")

    if cal_path.exists():
        cal = pd.read_csv(cal_path)

        Lambda_points = []
        for _, row in cal.iterrows():
            kappa = conductivity_from_Rs(row["Rs_mean"])
            Lambda_points.append(
                molar_conductivity(kappa, row["I_known"])
            )

        plt.scatter(
            np.sqrt(cal["I_known"]),
            Lambda_points,
            label="Accepted calibration points",
        )

    latest_kappa = conductivity_from_Rs(latest_Rs)
    latest_lambda = molar_conductivity(latest_kappa, latest_I)

    plt.scatter(
        [np.sqrt(latest_I)],
        [latest_lambda],
        marker="x",
        s=120,
        label="Latest measurement" if accepted else "Latest review point",
    )

    plt.xlabel(r"$\sqrt{I}$  [$M^{1/2}$]")
    plt.ylabel(r"Molar Conductivity $\Lambda_m$  [S cm$^2$/mol]")
    plt.title("BioLoop conductivity model diagnostic")
    plt.legend()
    plt.tight_layout()

    plt.savefig(
        "data/model_update.png",
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()

def plot_advanced_model_update(
    latest_I,
    latest_Rs,
    latest_Rs_sd=None,
    mode="known",
    accepted=False,
    sample_name=None,
):
    from pathlib import Path
    from datetime import datetime

    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt

    Path("data").mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    Kcell = get_latest_kcell()

    latest_kappa = conductivity_from_Rs(
        latest_Rs,
        Kcell=Kcell,
    )

    latest_lambda = molar_conductivity(
        latest_kappa,
        latest_I,
    )

    if latest_Rs_sd is not None:
        Rs_low = max(latest_Rs - latest_Rs_sd, 1e-9)
        Rs_high = latest_Rs + latest_Rs_sd

        lambda_high = molar_conductivity(
            conductivity_from_Rs(Rs_low, Kcell=Kcell),
            latest_I,
        )

        lambda_low = molar_conductivity(
            conductivity_from_Rs(Rs_high, Kcell=Kcell),
            latest_I,
        )

        latest_lambda_sd = abs(lambda_high - lambda_low) / 2

    else:
        latest_lambda_sd = None

    # -------------------------
    # Model prediction
    # -------------------------

    try:
        predicted_I = solve_I_from_Rs(
            latest_Rs,
            model=EMPIRICAL_MODEL,
        )

    except Exception:
        predicted_I = None

    I_grid = np.linspace(0.03, 0.70, 300)
    x_grid = np.sqrt(I_grid)

    Lambda_empirical = corrected_kohlrausch(
        I_grid,
        model=EMPIRICAL_MODEL,
    )

    Lambda_grounded = corrected_kohlrausch(
        I_grid,
        model=GROUNDED_MODEL,
    )

    # -------------------------
    # Build uncertainty band from accepted calibration points
    # -------------------------

    band_upper = None
    band_lower = None

    cal_path = Path("data/calibration_points.csv")

    if cal_path.exists():
        cal = pd.read_csv(cal_path)

        if len(cal) >= 3:
            Lambda_points = []

            for _, row in cal.iterrows():
                kappa = conductivity_from_Rs(
                    row["Rs_mean"],
                    Kcell=Kcell,
                )

                Lambda_points.append(
                    molar_conductivity(
                        kappa,
                        row["I_known"],
                    )
                )

            Lambda_points = np.array(Lambda_points)

            Lambda_fit_at_points = corrected_kohlrausch(
                cal["I_known"].to_numpy(),
                model=EMPIRICAL_MODEL,
            )

            residuals = Lambda_points - Lambda_fit_at_points

            residual_sd = np.nanstd(
                residuals,
                ddof=1,
            )

            band_upper = Lambda_empirical + 2 * residual_sd
            band_lower = Lambda_empirical - 2 * residual_sd
    
    candidate_model = None

    if cal_path.exists():
        cal_for_fit = pd.read_csv(cal_path)

        if len(cal_for_fit) >= 3:
            candidate_model = fit_empirical_model(
                cal_for_fit["I_known"].to_numpy(),
                cal_for_fit["Rs_mean"].to_numpy(),
                Kcell=Kcell,
            )
    # -------------------------
    # Figure layout
    # -------------------------

    fig = plt.figure(
        figsize=(12, 7),
        constrained_layout=True,
    )

    gs = fig.add_gridspec(
        2,
        2,
        width_ratios=[2.2, 1],
        height_ratios=[2, 1],
    )

    ax = fig.add_subplot(gs[:, 0])
    ax_table = fig.add_subplot(gs[0, 1])
    ax_resid = fig.add_subplot(gs[1, 1])

    if band_upper is not None:

        ax_resid.axhline(
            0,
            color="k",
            linestyle="--",
        )

        ax_resid.scatter(
            np.sqrt(cal["I_known"]),
            residuals,
        )

        ax_resid.set_ylabel("Residual")
        ax_resid.set_xlabel(r"$\sqrt{I}$")
        ax_resid.grid(True)

    else:

            ax_resid.axis("off")
    # -------------------------
    # Main model plot
    # -------------------------

    if band_upper is not None:
        ax.fill_between(
            x_grid,
            band_lower,
            band_upper,
            alpha=0.2,
            label="Approx. model band",
        )

    ax.plot(
        x_grid,
        Lambda_empirical,
        label="Empirical BioLoop model",
    )
    # Candidate updated model
    if candidate_model is not None:

        Lambda_candidate = corrected_kohlrausch(
            I_grid,
            model=candidate_model,
    )

        ax.plot(
            x_grid,
            Lambda_candidate,
            linestyle=":",
            linewidth=2.5,
            label="Candidate updated model",
        )
    ax.plot(
        x_grid,
        Lambda_grounded,
        linestyle="--",
        label="Grounded reference model",
    )

    # Existing accepted calibration points
    if cal_path.exists():
        cal = pd.read_csv(cal_path)

        if len(cal) > 0:
            Lambda_points = []

            for _, row in cal.iterrows():
                kappa = conductivity_from_Rs(
                    row["Rs_mean"],
                    Kcell=Kcell,
                )

                Lambda_points.append(
                    molar_conductivity(
                        kappa,
                        row["I_known"],
                    )
                )

            ax.scatter(
                np.sqrt(cal["I_known"]),
                Lambda_points,
                label="Accepted calibration points",
            )

    # Latest true/known point
    if latest_lambda_sd is not None:
        ax.errorbar(
            np.sqrt(latest_I),
            latest_lambda,
            yerr=latest_lambda_sd,
            fmt="x",
            markersize=10,
            capsize=4,
            label="Latest measured point ± SD",
        )

    else:
        ax.scatter(
            np.sqrt(latest_I),
            latest_lambda,
            marker="x",
            s=100,
            label="Latest measured point",
        )

    # Where model predicts this Rs would fall
    if predicted_I is not None:
        predicted_lambda = corrected_kohlrausch(
            predicted_I,
            model=EMPIRICAL_MODEL,
        )

        ax.scatter(
            np.sqrt(predicted_I),
            predicted_lambda,
            marker="o",
            facecolors="none",
            s=120,
            label="Model-predicted I from Rs",
        )

        ax.plot(
            [np.sqrt(latest_I), np.sqrt(predicted_I)],
            [latest_lambda, predicted_lambda],
            linestyle=":",
            linewidth=1,
            label="Known vs predicted offset",
        )

    ax.set_xlabel(r"$\sqrt{I}$  [$M^{1/2}$]")
    ax.set_ylabel(r"Molar conductivity $\Lambda_m$  [S cm$^2$/mol]")
    ax.set_title("BioLoop conductivity model diagnostic")
    ax.grid(True)
    ax.legend(fontsize=8)

    # -------------------------
    # Summary table panel
    # -------------------------

    ax_table.axis("off")

    table_rows = [
        ["Mode", mode],
        ["Sample", sample_name if sample_name else "not specified"],
        ["Known I", f"{latest_I:.4f} M"],
        ["Predicted I", f"{predicted_I:.4f} M" if predicted_I is not None else "n/a"],
        ["Rs mean", f"{latest_Rs:.3f} Ω"],
        ["Rs SD", f"{latest_Rs_sd:.3f} Ω" if latest_Rs_sd is not None else "n/a"],
        ["Lambda", f"{latest_lambda:.2f}"],
        ["Kcell", f"{Kcell:.6f} cm⁻¹"],
        ["Decision", "ACCEPT" if accepted else "REVIEW/REJECT"],

        ["", ""],
        ["Validated model", ""],
        ["Λ0", f"{EMPIRICAL_MODEL['Lambda0']:.3f}"],
        ["K",  f"{EMPIRICAL_MODEL['K']:.3f}"],
        ["B",  f"{EMPIRICAL_MODEL['B']:.3f}"],
    ]

    if candidate_model is not None:

        table_rows.extend([
            ["", ""],
            ["Candidate model", ""],
            ["Λ0*", f"{candidate_model['Lambda0']:.3f}"],
            ["K*",  f"{candidate_model['K']:.3f}"],
            ["B*",  f"{candidate_model['B']:.3f}"],
        ])

    table = ax_table.table(
        cellText=table_rows,
        colLabels=["Metric", "Value"],
        loc="center",
        cellLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.25)

    ax_table.set_title("Run Summary")
    plt.savefig(
    "data/model_update.png",
    dpi=300,
    bbox_inches="tight",
    )

    plt.savefig(
    f"data/model_update_{timestamp}.png",
    dpi=300,
    bbox_inches="tight",
    )

    plt.close(fig)