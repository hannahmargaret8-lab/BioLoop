#!/usr/bin/env python3
"""
baseline_standardized_salinity.py

Use the fresh-LB baseline of a biofilm experiment to calculate an
experiment-specific effective Kcell, then convert later Rs measurements into
apparent ionic-strength-equivalent values using the BioLoop salinity model.

This script reads the per-scan CSV created by analyze_biofilm_eis.py:
    biofilm_scan_features.csv

Model:
    Lambda(I) = Lambda0 - K*sqrt(I) + B*I
    kappa(I)  = Lambda(I)*I/1000        [S/cm]
    Kcell_eff = mean(Rs_baseline)*kappa(I_LB)
    kappa_t   = Kcell_eff/Rs_t

Important:
The later concentration result is an apparent NaCl/ionic-strength equivalent.
It is not proof that biofilm-related Rs changes are caused only by salinity.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import brentq


DEFAULT_MODEL = {
    "Lambda0": 142.82,
    "K": 74.737,
    "B": -79.236,
}


def corrected_kohlrausch(
    ionic_strength_m: float | np.ndarray,
    model: dict[str, float],
) -> float | np.ndarray:
    """Return molar conductivity Lambda in S cm^2/mol."""
    ionic_strength_m = np.asarray(ionic_strength_m, dtype=float)
    return (
        model["Lambda0"]
        - model["K"] * np.sqrt(ionic_strength_m)
        + model["B"] * ionic_strength_m
    )


def predict_kappa(
    ionic_strength_m: float | np.ndarray,
    model: dict[str, float],
) -> float | np.ndarray:
    """Return predicted conductivity in S/cm."""
    ionic_strength_m = np.asarray(ionic_strength_m, dtype=float)
    return corrected_kohlrausch(ionic_strength_m, model) * ionic_strength_m / 1000.0


def positive_model_limit(model: dict[str, float], requested_upper: float) -> float:
    """
    Limit inversion to the region where predicted molar conductivity remains
    positive. This prevents meaningless roots after the model crosses zero.
    """
    grid = np.linspace(1e-9, requested_upper, 20000)
    lam = corrected_kohlrausch(grid, model)
    positive = grid[lam > 0]

    if len(positive) == 0:
        raise ValueError("The selected model has no positive-conductivity region.")

    return float(positive[-1])


def find_all_roots(
    measured_kappa_s_cm: float,
    model: dict[str, float],
    lower: float,
    upper: float,
) -> list[float]:
    """
    Find every concentration root in the selected interval.

    The empirical polynomial correction can make kappa(I) non-monotonic, so a
    single wide brentq bracket is unsafe. This scans for sign changes and solves
    each valid local bracket.
    """
    if not np.isfinite(measured_kappa_s_cm) or measured_kappa_s_cm <= 0:
        return []

    safe_upper = positive_model_limit(model, upper)
    grid = np.geomspace(max(lower, 1e-9), safe_upper, 5000)
    residual = predict_kappa(grid, model) - measured_kappa_s_cm

    roots: list[float] = []

    for i in range(len(grid) - 1):
        y1 = residual[i]
        y2 = residual[i + 1]

        if not np.isfinite(y1) or not np.isfinite(y2):
            continue

        if y1 == 0:
            root = float(grid[i])
        elif y1 * y2 < 0:
            root = float(
                brentq(
                    lambda x: float(predict_kappa(x, model) - measured_kappa_s_cm),
                    float(grid[i]),
                    float(grid[i + 1]),
                )
            )
        else:
            continue

        if not roots or abs(root - roots[-1]) > 1e-6:
            roots.append(root)

    return roots


def choose_continuous_root(
    roots: list[float],
    reference_m: float,
) -> float:
    """
    Choose the root closest to the previous estimate.

    This keeps the time course on a continuous model branch when the empirical
    kappa(I) relation has more than one mathematical solution.
    """
    if not roots:
        return math.nan

    return min(roots, key=lambda value: abs(value - reference_m))


def classify_scan(filename: str) -> tuple[str, float]:
    """Create a readable condition label and numeric plotting order."""
    name = Path(filename).stem.lower()

    if "baseline" in name:
        return "baseline_media", -1.0

    if "post_seed" in name:
        return "post_seed_t0", 0.0

    flow_match = re.search(r"flow[_\-]?t(\d+(?:\.\d+)?)", name)
    if flow_match:
        timepoint = float(flow_match.group(1))
        bias = ""
        if "zero" in name or "0v" in name:
            bias = "_zero_bias"
        elif "dc" in name or "bias" in name:
            bias = "_dc_bias"
        return f"flow_t{timepoint:g}{bias}", timepoint

    time_match = re.search(r"(?:^|[_\-])t(\d+(?:\.\d+)?)", name)
    if time_match:
        timepoint = float(time_match.group(1))
        return f"t{timepoint:g}", timepoint

    return Path(filename).stem, math.nan


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate effective experiment Kcell from fresh-LB baseline and "
            "convert later Rs values to apparent ionic-strength equivalents."
        )
    )
    parser.add_argument(
        "scan_features_csv",
        type=Path,
        help="biofilm_scan_features.csv from analyze_biofilm_eis.py",
    )
    parser.add_argument(
        "--lb-equivalent",
        type=float,
        default=0.18,
        help="Assumed fresh-LB ionic-strength equivalent in M. Default: 0.18",
    )
    parser.add_argument(
        "--baseline-keyword",
        default="baseline",
        help="Case-insensitive filename text identifying baseline scans.",
    )
    parser.add_argument(
        "--rs-column",
        default="rs_high_frequency_ohm",
        help="Column containing per-scan Rs values.",
    )
    parser.add_argument(
        "--lambda0",
        type=float,
        default=DEFAULT_MODEL["Lambda0"],
    )
    parser.add_argument(
        "--k",
        type=float,
        default=DEFAULT_MODEL["K"],
    )
    parser.add_argument(
        "--b",
        type=float,
        default=DEFAULT_MODEL["B"],
    )
    parser.add_argument(
        "--min-equivalent",
        type=float,
        default=1e-6,
        help="Minimum concentration searched during inversion.",
    )
    parser.add_argument(
        "--max-equivalent",
        type=float,
        default=1.0,
        help="Maximum concentration searched during inversion.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: sibling folder named baseline_standardized_salinity",
    )
    args = parser.parse_args()

    input_csv = args.scan_features_csv.expanduser().resolve()
    if not input_csv.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_csv}")

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else input_csv.parent / "baseline_standardized_salinity"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    model = {
        "Lambda0": args.lambda0,
        "K": args.k,
        "B": args.b,
    }

    data = pd.read_csv(input_csv)

    required = {"file", args.rs_column}
    missing = required - set(data.columns)
    if missing:
        raise KeyError(
            f"Missing required columns: {sorted(missing)}. "
            f"Available columns: {list(data.columns)}"
        )

    data[args.rs_column] = pd.to_numeric(data[args.rs_column], errors="coerce")
    data = data[
        np.isfinite(data[args.rs_column])
        & (data[args.rs_column] > 0)
    ].copy()

    baseline_mask = data["file"].astype(str).str.contains(
        args.baseline_keyword,
        case=False,
        regex=False,
        na=False,
    )
    baseline = data.loc[baseline_mask].copy()

    if baseline.empty:
        raise RuntimeError(
            f"No baseline scans contained keyword "
            f"{args.baseline_keyword!r} in the file column."
        )

    baseline_rs_mean = float(baseline[args.rs_column].mean())
    baseline_rs_sd = float(baseline[args.rs_column].std(ddof=1))
    baseline_n = int(len(baseline))

    lb_kappa_s_cm = float(predict_kappa(args.lb_equivalent, model))
    if lb_kappa_s_cm <= 0:
        raise ValueError(
            "The salinity model predicts non-positive conductivity at the "
            "selected LB equivalent."
        )

    effective_kcell_cm_inv = baseline_rs_mean * lb_kappa_s_cm

    labels = data["file"].astype(str).apply(classify_scan)
    data["condition"] = [item[0] for item in labels]
    data["time_order"] = [item[1] for item in labels]

    data["effective_kcell_cm_inv"] = effective_kcell_cm_inv
    data["apparent_kappa_s_cm"] = effective_kcell_cm_inv / data[args.rs_column]
    data["apparent_kappa_ms_cm"] = 1000.0 * data["apparent_kappa_s_cm"]

    # Solve in filename/time order so ambiguous roots can stay on a continuous branch.
    sort_columns = ["time_order", "condition", "file"]
    ordered = data.sort_values(sort_columns, na_position="last").copy()

    previous_equivalent = args.lb_equivalent
    equivalents: list[float] = []
    root_counts: list[int] = []
    all_roots_text: list[str] = []

    for _, row in ordered.iterrows():
        roots = find_all_roots(
            measured_kappa_s_cm=float(row["apparent_kappa_s_cm"]),
            model=model,
            lower=args.min_equivalent,
            upper=args.max_equivalent,
        )

        selected = choose_continuous_root(roots, previous_equivalent)

        if np.isfinite(selected):
            previous_equivalent = selected

        equivalents.append(selected)
        root_counts.append(len(roots))
        all_roots_text.append(";".join(f"{root:.8g}" for root in roots))

    ordered["apparent_ionic_strength_equivalent_m"] = equivalents
    ordered["number_of_model_roots"] = root_counts
    ordered["candidate_roots_m"] = all_roots_text
    ordered["relative_rs_to_baseline"] = (
        ordered[args.rs_column] / baseline_rs_mean
    )
    ordered["percent_rs_change_from_baseline"] = (
        100.0 * (ordered[args.rs_column] - baseline_rs_mean) / baseline_rs_mean
    )

    # Per-condition mean and SD.
    numeric_columns = [
        args.rs_column,
        "apparent_kappa_s_cm",
        "apparent_kappa_ms_cm",
        "apparent_ionic_strength_equivalent_m",
        "relative_rs_to_baseline",
        "percent_rs_change_from_baseline",
    ]

    grouped = ordered.groupby(
        ["time_order", "condition"],
        dropna=False,
        sort=True,
    )

    mean_df = grouped[numeric_columns].mean().add_suffix("_mean")
    sd_df = grouped[numeric_columns].std(ddof=1).add_suffix("_sd")
    n_df = grouped.size().rename("n_scans")

    summary = pd.concat([n_df, mean_df, sd_df], axis=1).reset_index()
    summary = summary.sort_values(["time_order", "condition"], na_position="last")

    ordered.to_csv(
        output_dir / "baseline_standardized_scan_results.csv",
        index=False,
    )
    summary.to_csv(
        output_dir / "baseline_standardized_timepoint_summary.csv",
        index=False,
    )

    calibration = pd.DataFrame(
        [
            {
                "lb_assumed_equivalent_m": args.lb_equivalent,
                "lb_model_kappa_s_cm": lb_kappa_s_cm,
                "lb_model_kappa_ms_cm": 1000.0 * lb_kappa_s_cm,
                "baseline_rs_mean_ohm": baseline_rs_mean,
                "baseline_rs_sd_ohm": baseline_rs_sd,
                "baseline_n_scans": baseline_n,
                "effective_kcell_cm_inv": effective_kcell_cm_inv,
                "Lambda0": model["Lambda0"],
                "K": model["K"],
                "B": model["B"],
            }
        ]
    )
    calibration.to_csv(
        output_dir / "effective_kcell_calibration.csv",
        index=False,
    )

    # Plot raw Rs.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        summary["time_order"],
        summary[f"{args.rs_column}_mean"],
        yerr=summary[f"{args.rs_column}_sd"],
        marker="o",
        capsize=3,
    )
    ax.axhline(
        baseline_rs_mean,
        linestyle="--",
        linewidth=1,
        label="Fresh-LB baseline mean",
    )
    ax.set_xlabel("Experiment timepoint")
    ax.set_ylabel("Rs (ohm)")
    ax.set_title("Raw Rs relative to fresh-LB baseline")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "rs_over_time.png", dpi=200)
    plt.close(fig)

    # Plot apparent ionic-strength equivalent.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        summary["time_order"],
        summary["apparent_ionic_strength_equivalent_m_mean"],
        yerr=summary["apparent_ionic_strength_equivalent_m_sd"],
        marker="o",
        capsize=3,
    )
    ax.axhline(
        args.lb_equivalent,
        linestyle="--",
        linewidth=1,
        label=f"Assumed fresh LB = {args.lb_equivalent:g} M equivalent",
    )
    ax.set_xlabel("Experiment timepoint")
    ax.set_ylabel("Apparent ionic-strength equivalent (M)")
    ax.set_title("Baseline-standardized apparent ionic-strength equivalent")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(
        output_dir / "apparent_ionic_strength_equivalent_over_time.png",
        dpi=200,
    )
    plt.close(fig)

    print(f"Baseline scans used: {baseline_n}")
    print(f"Baseline Rs mean: {baseline_rs_mean:.6f} ohm")
    print(f"Baseline Rs SD: {baseline_rs_sd:.6f} ohm")
    print(f"Assumed fresh-LB equivalent: {args.lb_equivalent:.6f} M")
    print(f"Model LB conductivity: {1000.0 * lb_kappa_s_cm:.6f} mS/cm")
    print(f"Effective experiment Kcell: {effective_kcell_cm_inv:.6f} cm^-1")
    print(f"Results saved to: {output_dir}")

    unresolved = int(
        ordered["apparent_ionic_strength_equivalent_m"].isna().sum()
    )
    ambiguous = int((ordered["number_of_model_roots"] > 1).sum())

    if unresolved:
        print(
            f"Warning: {unresolved} scans could not be inverted within the "
            "selected model range."
        )
    if ambiguous:
        print(
            f"Note: {ambiguous} scans had multiple mathematical roots; "
            "the root nearest the previous timepoint was selected."
        )


if __name__ == "__main__":
    main()