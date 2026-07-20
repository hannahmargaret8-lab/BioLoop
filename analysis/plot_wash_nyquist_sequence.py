from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
import argparse

DATA_DIR = Path("data")
OUT_DIR = Path("data/wash_matrix_plots")


ELECTRODE_ID = "SPE01"


def parse_file_info(path):
    name = path.stem

    # expected: eis_wash_matrix_after_SPE01_ethanol_DI_after_0.1M_NaCl_20260703_174746
    m = re.match(
        r"eis_wash_matrix_(before|after)_(.+?)_(before|after)_0\.1M_NaCl_(\d{8}_\d{6})",
        name,
    )

    if not m:
        return None

    mode_stage, middle, stage, timestamp = m.groups()

    if not middle.startswith(ELECTRODE_ID + "_"):
        return None

    treatment = middle.replace(ELECTRODE_ID + "_", "")

    return {
        "stage": stage,
        "treatment": treatment,
        "timestamp": timestamp,
    }


def load_eis_files():
    rows = []

    for path in sorted(DATA_DIR.glob("eis_wash_matrix_*_*.csv")):
        info = parse_file_info(path)

        if info is None:
            continue

        df = pd.read_csv(path)

        rows.append(
            {
                "path": path,
                "timestamp": info["timestamp"],
                "treatment": info["treatment"],
                "stage": info["stage"],
                "df": df,
            }
        )

    rows = sorted(rows, key=lambda x: x["timestamp"])
    return rows


def plot_all_nyquist(rows):
    plt.figure(figsize=(11, 8))

    treatments = sorted(set(r["treatment"] for r in rows))
    color_map = {
        t: plt.cm.tab20(i % 20)
        for i, t in enumerate(treatments)
    }

    for r in rows:
        df = r["df"]
        zr = df["Zreal_ohm"]
        zi = -df["Zimag_ohm"]

        linestyle = "-" if r["stage"] == "before" else "--"
        label = f"{r['treatment']} {r['stage']}"

        plt.plot(
            zr,
            zi,
            marker="o",
            markersize=3,
            linewidth=1.5,
            linestyle=linestyle,
            color=color_map[r["treatment"]],
            label=label,
        )

    plt.xlabel("Zreal (ohm)")
    plt.ylabel("-Zimag (ohm)")
    plt.title(f"{ELECTRODE_ID} Nyquist plots across wash matrix")
    plt.grid(True)
    plt.axis("equal")
    plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()

    out = OUT_DIR / f"{ELECTRODE_ID}_all_nyquist.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"Saved {out}")


def plot_timelapse_frames(rows):
    frame_dir = OUT_DIR / f"{ELECTRODE_ID}_timelapse_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    treatments = sorted(set(r["treatment"] for r in rows))
    color_map = {
        t: plt.cm.tab20(i % 20)
        for i, t in enumerate(treatments)
    }

    max_zr = max(r["df"]["Zreal_ohm"].max() for r in rows)
    max_zi = max((-r["df"]["Zimag_ohm"]).max() for r in rows)

    for frame_idx in range(1, len(rows) + 1):
        plt.figure(figsize=(8, 6))

        for r in rows[:frame_idx]:
            df = r["df"]
            linestyle = "-" if r["stage"] == "before" else "--"

            plt.plot(
                df["Zreal_ohm"],
                -df["Zimag_ohm"],
                marker="o",
                markersize=3,
                linewidth=1.5,
                linestyle=linestyle,
                color=color_map[r["treatment"]],
                label=f"{r['treatment']} {r['stage']}",
            )

        latest = rows[frame_idx - 1]

        plt.xlabel("Zreal (ohm)")
        plt.ylabel("-Zimag (ohm)")
        plt.title(
            f"{ELECTRODE_ID} Nyquist time lapse\n"
            f"{frame_idx}/{len(rows)}: {latest['treatment']} {latest['stage']}"
        )
        plt.xlim(0, max_zr * 1.05)
        plt.ylim(0, max_zi * 1.05)
        plt.grid(True)
        plt.legend(fontsize=7, ncol=2)
        plt.tight_layout()

        out = frame_dir / f"frame_{frame_idx:03d}.png"
        plt.savefig(out, dpi=200)
        plt.close()

    print(f"Saved frames to {frame_dir}")


def main():
    global DATA_DIR, OUT_DIR, ELECTRODE_ID

    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--electrode", default="SPE01")
    args = p.parse_args()

    DATA_DIR = Path(args.data_dir)
    OUT_DIR = Path(args.out_dir) if args.out_dir else DATA_DIR / "wash_matrix_plots"
    ELECTRODE_ID = args.electrode
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_eis_files()

    if not rows:
        raise RuntimeError(f"No wash matrix EIS files found for {ELECTRODE_ID}")

    print(f"Found {len(rows)} files for {ELECTRODE_ID}")

    plot_all_nyquist(rows)
    plot_timelapse_frames(rows)


if __name__ == "__main__":
    main()