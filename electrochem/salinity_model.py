# electrochem/salinity_model.py

from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.interpolate import interp1d

from config.settings import GROUNDED_MODEL
from electrochem.kcell_calibration import get_latest_kcell
from scipy.optimize import minimize


# ==========================
# Basic conversions
# ==========================

def conductivity_from_Rs(Rs_ohm, Kcell=None):
    if Kcell is None:
        Kcell = get_latest_kcell()

    return Kcell / Rs_ohm


def molar_conductivity(kappa_S_cm, I_M):
    return 1000 * kappa_S_cm / I_M


# ==========================
# Grounded reference model
# Lambda = Lambda0 - K√I + B*I
# ==========================

def corrected_kohlrausch(I_M, model=GROUNDED_MODEL):
    I_M = np.asarray(I_M)

    return (
        model["Lambda0"]
        - model["K"] * np.sqrt(I_M)
        + model["B"] * I_M
    )


def predict_kappa_grounded(I_M, model=GROUNDED_MODEL):
    Lambda = corrected_kohlrausch(I_M, model=model)
    return Lambda * I_M / 1000


def predict_Rs_grounded(I_M, model=GROUNDED_MODEL, Kcell=None):
    if Kcell is None:
        Kcell = get_latest_kcell()

    kappa = predict_kappa_grounded(I_M, model=model)
    return Kcell / kappa


# ==========================
# Calibration data utilities
# ==========================

def load_calibration_points(path="data/calibration_points.csv"):
    cal_path = Path(path)

    if not cal_path.exists():
        return pd.DataFrame()

    cal = pd.read_csv(cal_path)

    if "accepted" in cal.columns:
        accepted_col = cal["accepted"].astype(str).str.lower()

        keep = (
            accepted_col.isin(["true", "1", "yes"])
            | cal["accepted"].isna()
            | (accepted_col == "nan")
            | (accepted_col == "")
        )

        cal = cal[keep]

    if len(cal) == 0:
        return cal

    if "Kcell_at_time" not in cal.columns:
        cal["Kcell_at_time"] = get_latest_kcell()
    else:
        cal["Kcell_at_time"] = cal["Kcell_at_time"].fillna(get_latest_kcell())

    cal["kappa_S_cm"] = cal["Kcell_at_time"] / cal["Rs_mean"]
    cal["Lambda_observed"] = 1000 * cal["kappa_S_cm"] / cal["I_known"]
    cal["sqrt_I"] = np.sqrt(cal["I_known"])

    cal["Lambda_grounded"] = corrected_kohlrausch(
        cal["I_known"].to_numpy(),
        model=GROUNDED_MODEL,
    )

    cal["grounded_residual"] = cal["Lambda_observed"] - cal["Lambda_grounded"]

    return cal


def fit_accepted_calibration_curve(cal, I_min=0.0, I_max=0.6):
    if cal is None or len(cal) < 3:
        return None

    cal = cal.sort_values("I_known")

    I = cal["I_known"].to_numpy(dtype=float)
    x = cal["sqrt_I"].to_numpy(dtype=float)
    y = cal["Lambda_observed"].to_numpy(dtype=float)

    # Initial unconstrained guess
    p0 = np.polyfit(x, y, 2)  # a, b, c

    x_check = np.linspace(np.sqrt(I_min), np.sqrt(I_max), 200)

    def objective(params):
        a, b, c = params
        y_pred = a * x**2 + b * x + c
        return np.sum((y - y_pred) ** 2)

    # Constraint: dLambda/dx = 2*a*x + b <= 0
    constraints = []

    for x_i in x_check:
        constraints.append({
            "type": "ineq",
            "fun": lambda params, x_i=x_i: -(2 * params[0] * x_i + params[1]),
        })

    result = minimize(
        objective,
        p0,
        constraints=constraints,
        method="SLSQP",
    )

    if result.success:
        a, b, c = result.x
        kind = "monotonic quadratic"
    else:
        # Still use quadratic, but mark warning
        a, b, c = p0
        kind = "unconstrained quadratic warning"

    def Lambda_from_I(I_M):
        x_eval = np.sqrt(I_M)
        return a * x_eval**2 + b * x_eval + c

    x_final = np.linspace(np.sqrt(I_min), np.sqrt(I_max), 200)
    slopes = 2 * a * x_final + b
    monotonic = np.all(slopes <= 1e-8)

    return {
        "I": I,
        "kind": kind,
        "a": a,
        "b": b,
        "c": c,
        "Lambda0_fit": c,
        "K_fit": -b,
        "B_fit": a,
        "monotonic": monotonic,
        "Lambda_from_I": Lambda_from_I,
    }


def predict_kappa_from_accepted_fit(I_M, fit):
    Lambda = fit["Lambda_from_I"](I_M)
    return Lambda * I_M / 1000


def predict_Rs_from_accepted_fit(I_M, fit, Kcell=None):
    if Kcell is None:
        Kcell = get_latest_kcell()

    kappa = predict_kappa_from_accepted_fit(I_M, fit)
    return Kcell / kappa


def solve_I_from_Rs(
    Rs_ohm,
    lower=None,
    upper=None,
    Kcell=None,
):
    """
    Predict ionic strength from Rs using accepted calibration points.

    Falls back to grounded reference only if there are not enough
    accepted calibration points.
    """
    if Kcell is None:
        Kcell = get_latest_kcell()

    measured_kappa = conductivity_from_Rs(Rs_ohm, Kcell=Kcell)

    cal = load_calibration_points()
    fit = fit_accepted_calibration_curve(cal)

    if fit is not None:
        model_name = "accepted calibration fit"

        if lower is None:
            lower = max(float(np.min(fit["I"])) * 0.5, 1e-6)

        if upper is None:
            upper = float(np.max(fit["I"])) * 1.5

        def residual(I):
            return predict_kappa_from_accepted_fit(I, fit) - measured_kappa

    else:
        model_name = "grounded reference fallback"

        if lower is None:
            lower = 1e-6

        if upper is None:
            upper = 2.0

        def residual(I):
            return predict_kappa_grounded(I) - measured_kappa

    try:
        return float(brentq(residual, lower, upper))

    except ValueError as exc:
        raise ValueError(
            f"Could not solve I from Rs using {model_name}. "
            f"Rs={Rs_ohm:.3f}, measured_kappa={measured_kappa:.6g}, "
            f"bounds=({lower}, {upper})"
        ) from exc


def calculate_K_cell(Rs_standard, kappa_standard):
    return Rs_standard * kappa_standard


# ==========================
# Diagnostic plotting
# ==========================

def plot_advanced_model_update(
    latest_I,
    latest_Rs,
    latest_Rs_sd=None,
    mode="known",
    accepted=False,
    sample_name=None,
):
    import matplotlib.pyplot as plt

    Path("data").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    current_Kcell = get_latest_kcell()

    latest_kappa = conductivity_from_Rs(
        latest_Rs,
        Kcell=current_Kcell,
    )

    latest_lambda = molar_conductivity(
        latest_kappa,
        latest_I,
    )

    if latest_Rs_sd is not None:
        Rs_low = max(latest_Rs - latest_Rs_sd, 1e-9)
        Rs_high = latest_Rs + latest_Rs_sd

        lambda_high = molar_conductivity(
            conductivity_from_Rs(Rs_low, Kcell=current_Kcell),
            latest_I,
        )

        lambda_low = molar_conductivity(
            conductivity_from_Rs(Rs_high, Kcell=current_Kcell),
            latest_I,
        )

        latest_lambda_sd = abs(lambda_high - lambda_low) / 2
    else:
        latest_lambda_sd = None

    try:
        predicted_I = solve_I_from_Rs(
            latest_Rs,
            Kcell=current_Kcell,
        )
    except Exception:
        predicted_I = None

    cal = load_calibration_points()
    fit = fit_accepted_calibration_curve(cal)

    I_grid = np.linspace(0.03, 0.70, 300)
    x_grid = np.sqrt(I_grid)

    Lambda_grounded = corrected_kohlrausch(
        I_grid,
        model=GROUNDED_MODEL,
    )

    Lambda_fit = None
    if fit is not None:
        Lambda_fit = fit["Lambda_from_I"](I_grid)

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

    # -------------------------
    # Main plot
    # -------------------------

    ax.plot(
        x_grid,
        Lambda_grounded,
        linestyle="--",
        label="Grounded Kohlrausch reference",
    )

    if Lambda_fit is not None:
        ax.plot(
            x_grid,
            Lambda_fit,
            linewidth=2.5,
            label=f"Accepted calibration fit ({fit['kind']})",
        )

    if len(cal) > 0:
        ax.scatter(
            np.sqrt(cal["I_known"]),
            cal["Lambda_observed"],
            label="Accepted calibration points",
        )

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

    if predicted_I is not None and fit is not None:
        predicted_lambda = fit["Lambda_from_I"](predicted_I)

        ax.scatter(
            np.sqrt(predicted_I),
            predicted_lambda,
            marker="o",
            facecolors="none",
            s=120,
            label="Predicted I from accepted fit",
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
    ax.set_title("BioLoop conductivity calibration diagnostic")
    ax.grid(True)
    ax.legend(fontsize=8)

    # -------------------------
    # Residual plot
    # -------------------------

    if len(cal) > 0:
        ax_resid.axhline(
            0,
            linestyle="--",
            linewidth=1,
        )

        ax_resid.scatter(
            np.sqrt(cal["I_known"]),
            cal["grounded_residual"],
            label="Accepted point residuals",
        )

        latest_grounded = corrected_kohlrausch(
            latest_I,
            model=GROUNDED_MODEL,
        )

        latest_residual = latest_lambda - latest_grounded

        ax_resid.scatter(
            [np.sqrt(latest_I)],
            [latest_residual],
            marker="x",
            s=80,
            label="Latest residual",
        )

        ax_resid.set_xlabel(r"$\sqrt{I}$")
        ax_resid.set_ylabel(r"$\Lambda_{obs} - \Lambda_{grounded}$")
        ax_resid.set_title("Residual vs grounded reference")
        ax_resid.grid(True)
        ax_resid.legend(fontsize=8)

    else:
        ax_resid.axis("off")

    # -------------------------
    # Summary table
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
        ["Kcell used", f"{current_Kcell:.6f} cm⁻¹"],
        ["Decision", "ACCEPT" if accepted else "REVIEW/REJECT"],

        ["", ""],
        ["Grounded model", ""],
        ["Λ0", f"{GROUNDED_MODEL['Lambda0']:.3f}"],
        ["K", f"{GROUNDED_MODEL['K']:.3f}"],
        ["B", f"{GROUNDED_MODEL['B']:.3f}"],
    ]

    if fit is not None:
        table_rows.extend(
            [
                ["", ""],
                ["Accepted fit", fit["kind"]],
                ["Λ0 fit", f"{fit['Lambda0_fit']:.3f}"],
                ["K fit", f"{fit['K_fit']:.3f}"],
                ["B fit", f"{fit['B_fit']:.3f}"],
                ["Accepted points", str(len(cal))],
                ["I range", f"{cal['I_known'].min():.3f}–{cal['I_known'].max():.3f} M"],
            ]
        )

    table = ax_table.table(
        cellText=table_rows,
        colLabels=["Metric", "Value"],
        loc="center",
        cellLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.25)

    ax_table.set_title("Run summary")

    out_path = Path(f"data/model_update_{timestamp}.png")
    latest_path = Path("data/model_update.png")

    fig.savefig(
        latest_path,
        dpi=300,
        bbox_inches="tight",
    )

    fig.savefig(
        out_path,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"Advanced model plot saved: {out_path}")

    return str(out_path)


def plot_model_update(
    latest_I,
    latest_Rs,
    accepted=False,
):
    return plot_advanced_model_update(
        latest_I=latest_I,
        latest_Rs=latest_Rs,
        accepted=accepted,
    )