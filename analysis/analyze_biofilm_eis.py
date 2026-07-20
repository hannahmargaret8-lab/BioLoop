#!/usr/bin/env python3
"""
analyze_biofilm_eis.py

Feature-based analysis for BioLoop biofilm EIS time-course experiments.

What it does
------------
1. Recursively finds CSV files in an experiment folder.
2. Detects frequency, Zreal, and Zimag columns using common aliases.
3. Extracts timepoint and replicate numbers from filenames.
4. Computes robust, model-free EIS features:
   - high-frequency solution resistance estimate (Rs)
   - |Z| and phase at selected frequencies
   - Z' and -Z'' at selected frequencies
   - phase-extremum value and frequency
   - maximum -Z'' value and frequency
   - low-/mid-/high-frequency log-slopes
   - apparent series capacitance and parallel capacitance
5. Saves per-scan and per-timepoint summary CSV files.
6. Creates time-course plots and overlay Bode/Nyquist plots.

Important interpretation note
-----------------------------
The capacitance values are "apparent" frequency-dependent metrics:
    C_series = -1 / (2*pi*f*Zimag)
    C_parallel = imag(1/Z) / (2*pi*f)

They are not equivalent-circuit capacitances unless the selected circuit
and frequency region justify that interpretation.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


FREQ_ALIASES = (
    "frequency", "frequency_hz", "freq", "freq_hz", "f", "hz"
)
ZREAL_ALIASES = (
    "zreal", "z_real", "real", "re_z", "zre", "z'", "real_ohm"
)
ZIMAG_ALIASES = (
    "zimag", "z_imag", "imag", "im_z", "zim", "z''", "imag_ohm"
)

DEFAULT_TARGET_FREQS = (0.1, 1.0, 10.0, 100.0, 1_000.0, 10_000.0, 100_000.0)


def normalized_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def find_column(df: pd.DataFrame, aliases: Iterable[str]) -> str:
    normalized = {normalized_name(c): c for c in df.columns}
    for alias in aliases:
        key = normalized_name(alias)
        if key in normalized:
            return normalized[key]

    # Partial-match fallback
    for alias in aliases:
        key = normalized_name(alias)
        for norm, original in normalized.items():
            if key and (key in norm or norm in key):
                return original

    raise KeyError(
        f"Could not identify a column matching {list(aliases)}. "
        f"Available columns: {list(df.columns)}"
    )


def parse_timepoint(path: Path) -> float:
    """
    Recognizes names such as:
      t1, t01, timepoint_1, timepoint-12, hour_5, h24
    """
    text = path.stem.lower()
    patterns = (
        r"(?:^|[_\-\s])t(?:imepoint)?[_\-\s]*(\d+(?:\.\d+)?)",
        r"(?:^|[_\-\s])hour[_\-\s]*(\d+(?:\.\d+)?)",
        r"(?:^|[_\-\s])h[_\-\s]*(\d+(?:\.\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

    # Last-resort: use the final number in the filename
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    return float(numbers[-1]) if numbers else math.nan


def parse_replicate(path: Path) -> float:
    text = path.stem.lower()
    patterns = (
        r"(?:rep|replicate|scan|run)[_\-\s]*(\d+)",
        r"(?:^|[_\-\s])r[_\-\s]*(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return math.nan


def load_eis_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    f_col = find_column(df, FREQ_ALIASES)
    zr_col = find_column(df, ZREAL_ALIASES)
    zi_col = find_column(df, ZIMAG_ALIASES)

    out = pd.DataFrame(
        {
            "frequency_hz": pd.to_numeric(df[f_col], errors="coerce"),
            "zreal_ohm": pd.to_numeric(df[zr_col], errors="coerce"),
            "zimag_ohm": pd.to_numeric(df[zi_col], errors="coerce"),
        }
    ).dropna()

    out = out[out["frequency_hz"] > 0].copy()
    out = out.sort_values("frequency_hz", ascending=False).drop_duplicates(
        "frequency_hz"
    )

    if len(out) < 5:
        raise ValueError(f"{path.name}: fewer than five valid EIS points.")

    out["zmag_ohm"] = np.hypot(out["zreal_ohm"], out["zimag_ohm"])
    out["phase_deg"] = np.degrees(
        np.arctan2(out["zimag_ohm"], out["zreal_ohm"])
    )

    # Admittance Y = 1/Z
    denom = out["zreal_ohm"] ** 2 + out["zimag_ohm"] ** 2
    out["conductance_s"] = out["zreal_ohm"] / denom
    out["susceptance_s"] = -out["zimag_ohm"] / denom

    omega = 2.0 * np.pi * out["frequency_hz"]

    # Apparent series capacitance; valid as a physical C only for an appropriate
    # series-capacitive interpretation.
    out["c_series_f"] = np.where(
        np.abs(out["zimag_ohm"]) > 0,
        -1.0 / (omega * out["zimag_ohm"]),
        np.nan,
    )

    # Apparent parallel capacitance from admittance.
    out["c_parallel_f"] = out["susceptance_s"] / omega

    return out.reset_index(drop=True)


def log_interp(freq: np.ndarray, values: np.ndarray, target: float) -> float:
    mask = np.isfinite(freq) & np.isfinite(values) & (freq > 0)
    freq = np.asarray(freq[mask], dtype=float)
    values = np.asarray(values[mask], dtype=float)

    if len(freq) < 2 or target < freq.min() or target > freq.max():
        return math.nan

    order = np.argsort(freq)
    return float(np.interp(np.log10(target), np.log10(freq[order]), values[order]))


def log_slope(
    freq: np.ndarray,
    values: np.ndarray,
    f_min: float,
    f_max: float,
) -> float:
    mask = (
        np.isfinite(freq)
        & np.isfinite(values)
        & (freq >= f_min)
        & (freq <= f_max)
        & (freq > 0)
        & (values > 0)
    )
    if mask.sum() < 3:
        return math.nan

    x = np.log10(freq[mask])
    y = np.log10(values[mask])
    return float(np.polyfit(x, y, 1)[0])


def estimate_rs(df: pd.DataFrame, n_high_frequency_points: int = 5) -> float:
    """
    Robust high-frequency real-axis estimate.

    Uses the median Z' of the highest-frequency points. This is safer than
    calling the minimum positive Z' an intercept when the spectrum does not
    visibly reach the real axis.
    """
    high = df.nlargest(n_high_frequency_points, "frequency_hz")
    positive = high.loc[high["zreal_ohm"] > 0, "zreal_ohm"]
    return float(positive.median()) if not positive.empty else math.nan


def extract_features(
    df: pd.DataFrame,
    target_freqs: Iterable[float],
) -> dict[str, float]:
    f = df["frequency_hz"].to_numpy()
    zr = df["zreal_ohm"].to_numpy()
    zi = df["zimag_ohm"].to_numpy()
    zm = df["zmag_ohm"].to_numpy()
    ph = df["phase_deg"].to_numpy()
    cs = df["c_series_f"].to_numpy()
    cp = df["c_parallel_f"].to_numpy()

    features: dict[str, float] = {
        "rs_high_frequency_ohm": estimate_rs(df),
        "zreal_min_ohm": float(np.nanmin(zr)),
        "zreal_max_ohm": float(np.nanmax(zr)),
        "minus_zimag_max_ohm": float(np.nanmax(-zi)),
        "freq_at_minus_zimag_max_hz": float(f[np.nanargmax(-zi)]),
        "phase_min_deg": float(np.nanmin(ph)),
        "freq_at_phase_min_hz": float(f[np.nanargmin(ph)]),
        "phase_max_deg": float(np.nanmax(ph)),
        "freq_at_phase_max_hz": float(f[np.nanargmax(ph)]),
        "zmag_slope_low": log_slope(f, zm, 0.1, 10.0),
        "zmag_slope_mid": log_slope(f, zm, 10.0, 1_000.0),
        "zmag_slope_high": log_slope(f, zm, 1_000.0, 100_000.0),
    }

    for target in target_freqs:
        tag = (
            f"{target:g}"
            .replace(".", "p")
            .replace("+", "")
        )
        features[f"zmag_at_{tag}hz_ohm"] = log_interp(f, zm, target)
        features[f"phase_at_{tag}hz_deg"] = log_interp(f, ph, target)
        features[f"zreal_at_{tag}hz_ohm"] = log_interp(f, zr, target)
        features[f"minus_zimag_at_{tag}hz_ohm"] = -log_interp(f, zi, target)
        features[f"cseries_at_{tag}hz_f"] = log_interp(f, cs, target)
        features[f"cparallel_at_{tag}hz_f"] = log_interp(f, cp, target)

    return features


def summarize_timepoints(scan_features: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        c for c in scan_features.select_dtypes(include=[np.number]).columns
        if c not in {"timepoint", "replicate"}
    ]

    grouped = scan_features.groupby("timepoint", dropna=False)
    mean_df = grouped[numeric_cols].mean().add_suffix("_mean")
    sd_df = grouped[numeric_cols].std(ddof=1).add_suffix("_sd")
    n_df = grouped.size().rename("n_scans")

    summary = pd.concat([n_df, mean_df, sd_df], axis=1).reset_index()
    return summary.sort_values("timepoint")


def save_feature_plot(
    summary: pd.DataFrame,
    feature: str,
    output_dir: Path,
    ylabel: str,
) -> None:
    mean_col = f"{feature}_mean"
    sd_col = f"{feature}_sd"
    if mean_col not in summary.columns:
        return

    x = summary["timepoint"]
    y = summary[mean_col]
    yerr = summary[sd_col] if sd_col in summary.columns else None

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(x, y, yerr=yerr, marker="o", capsize=3)
    ax.set_xlabel("Timepoint")
    ax.set_ylabel(ylabel)
    ax.set_title(ylabel + " over time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"{feature}_over_time.png", dpi=200)
    plt.close(fig)


def save_overlay_plots(
    spectra: list[tuple[float, str, pd.DataFrame]],
    output_dir: Path,
) -> None:
    # One curve per timepoint: use the first scan found for a clean overview.
    chosen: dict[float, tuple[str, pd.DataFrame]] = {}
    for timepoint, name, df in spectra:
        if timepoint not in chosen:
            chosen[timepoint] = (name, df)

    # Nyquist
    fig, ax = plt.subplots(figsize=(7, 6))
    for timepoint in sorted(chosen):
        _, df = chosen[timepoint]
        ax.plot(df["zreal_ohm"], -df["zimag_ohm"], label=f"t{timepoint:g}")
    ax.set_xlabel("Z' (Ω)")
    ax.set_ylabel("-Z'' (Ω)")
    ax.set_title("Nyquist spectra over time")
    ax.grid(True, alpha=0.3)
    if len(chosen) <= 15:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "nyquist_overlay.png", dpi=200)
    plt.close(fig)

    # Bode magnitude
    fig, ax = plt.subplots(figsize=(8, 5))
    for timepoint in sorted(chosen):
        _, df = chosen[timepoint]
        ax.loglog(df["frequency_hz"], df["zmag_ohm"], label=f"t{timepoint:g}")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("|Z| (Ω)")
    ax.set_title("Bode magnitude over time")
    ax.grid(True, which="both", alpha=0.3)
    if len(chosen) <= 15:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "bode_magnitude_overlay.png", dpi=200)
    plt.close(fig)

    # Bode phase
    fig, ax = plt.subplots(figsize=(8, 5))
    for timepoint in sorted(chosen):
        _, df = chosen[timepoint]
        ax.semilogx(df["frequency_hz"], df["phase_deg"], label=f"t{timepoint:g}")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Phase (degrees)")
    ax.set_title("Bode phase over time")
    ax.grid(True, which="both", alpha=0.3)
    if len(chosen) <= 15:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "bode_phase_overlay.png", dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Model-free feature extraction for biofilm EIS time courses."
    )
    parser.add_argument(
        "input_dirs",
        type=Path,
        nargs="+",
        help="One or more experiment folders containing EIS CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output folder. Default: <input_dir>/biofilm_analysis",
    )
    parser.add_argument(
        "--target-frequencies",
        type=float,
        nargs="+",
        default=list(DEFAULT_TARGET_FREQS),
        help="Frequencies in Hz at which features are interpolated.",
    )
    args = parser.parse_args()

    input_dirs = [
        p.expanduser().resolve()
        for p in args.input_dirs
    ]

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else input_dirs[0] / "biofilm_analysis"
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_paths = []

    for folder in input_dirs:
        csv_paths.extend(
            p for p in folder.rglob("*.csv")
            if output_dir not in p.parents
        )

    csv_paths = sorted(csv_paths)
    # Keep only the first occurrence of each scan filename.
    # This allows resumed experiments to span multiple folders
    # without analyzing duplicated baseline files.
    seen = set()
    unique_paths = []

    for path in csv_paths:
        if path.name in seen:
            continue
        seen.add(path.name)
        unique_paths.append(path)

    csv_paths = unique_paths
    
    if not csv_paths:
        raise FileNotFoundError("No CSV files found.")

    rows: list[dict] = []
    spectra: list[tuple[float, str, pd.DataFrame]] = []
    failures: list[str] = []

    for path in csv_paths:
        try:
            df = load_eis_csv(path)
            timepoint = parse_timepoint(path)
            replicate = parse_replicate(path)
            row = {
                "file": path.name,
                "timepoint": timepoint,
                "replicate": replicate,
                **extract_features(df, args.target_frequencies),
            }
            rows.append(row)
            spectra.append((timepoint, path.name, df))
        except Exception as exc:
            failures.append(f"{path}: {exc}")

    if not rows:
        raise RuntimeError(
            "No files could be analyzed.\n" + "\n".join(failures)
        )

    scan_features = pd.DataFrame(rows).sort_values(
        ["timepoint", "replicate", "file"],
        na_position="last",
    )
    summary = summarize_timepoints(scan_features)

    scan_features.to_csv(output_dir / "biofilm_scan_features.csv", index=False)
    summary.to_csv(output_dir / "biofilm_timepoint_summary.csv", index=False)

    save_feature_plot(
        summary,
        "rs_high_frequency_ohm",
        output_dir,
        "High-frequency Rs estimate (Ω)",
    )
    save_feature_plot(
        summary,
        "phase_min_deg",
        output_dir,
        "Minimum phase angle (degrees)",
    )
    save_feature_plot(
        summary,
        "freq_at_phase_min_hz",
        output_dir,
        "Frequency at minimum phase (Hz)",
    )
    save_feature_plot(
        summary,
        "minus_zimag_max_ohm",
        output_dir,
        "Maximum -Z'' (Ω)",
    )
    save_feature_plot(
        summary,
        "freq_at_minus_zimag_max_hz",
        output_dir,
        "Frequency at maximum -Z'' (Hz)",
    )

    # Automatically plot target-frequency magnitude, phase, and parallel C.
    for target in args.target_frequencies:
        tag = f"{target:g}".replace(".", "p").replace("+", "")
        save_feature_plot(
            summary,
            f"zmag_at_{tag}hz_ohm",
            output_dir,
            f"|Z| at {target:g} Hz (Ω)",
        )
        save_feature_plot(
            summary,
            f"phase_at_{tag}hz_deg",
            output_dir,
            f"Phase at {target:g} Hz (degrees)",
        )
        save_feature_plot(
            summary,
            f"cparallel_at_{tag}hz_f",
            output_dir,
            f"Apparent parallel capacitance at {target:g} Hz (F)",
        )

    save_overlay_plots(spectra, output_dir)

    if failures:
        (output_dir / "analysis_failures.txt").write_text(
            "\n".join(failures),
            encoding="utf-8",
        )

    print(f"Analyzed {len(rows)} CSV files.")
    print(f"Results saved to: {output_dir}")
    if failures:
        print(f"{len(failures)} files failed; see analysis_failures.txt")


if __name__ == "__main__":
    main()
