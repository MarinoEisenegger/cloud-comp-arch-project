import pathlib
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


def read_results(file_path: str) -> pd.DataFrame:
    """Parse a results text file (like results/part1_runs/baseline_run1.txt)
    and return a pandas DataFrame with appropriate columns and numeric types.

    The file has a header line starting with '#type' followed by data rows.
    The function stops reading when non-data lines (e.g. warnings) appear.
    """
    p = pathlib.Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    lines: List[str]
    with p.open() as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("#type"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError('Header line starting with "#type" not found')

    cols = lines[header_idx].lstrip("#").split()

    data = []
    for line in lines[header_idx + 1:]:
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith("warning") or low.startswith("cpu usage") or low.startswith("cpu usage stats"):
            break
        if s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) >= len(cols):
            data.append(parts[:len(cols)])

    df = pd.DataFrame(data, columns=cols)

    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="ignore")

    return df


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).resolve().parents[2]

    configs = {
        "no interference": "baseline",
        "ibench-cpu": "cpu_interference",
        "ibench-l1d": "l1d_interference",
        "ibench-l1i": "l1i_interference",
        "ibench-l2": "l2_interference",
        "ibench-llc": "llc_interference",
        "ibench-membw": "membw_interference",
    }

    fig = plt.figure(figsize=(6, 4))
    fig_ax = fig.gca()

    markers = ["o", "s", "D", "^", "v", "P", "*"]

    for (config, filename), marker in zip(configs.items(), markers):
        all_runs = []

        for run in range(1, 4):
            sample_file = repo_root / "results" / "part1_runs" / f"{filename}_run{run}.txt"
            try:
                df = read_results(str(sample_file))
                all_runs.append(df)
            except Exception as e:
                print(f"Error loading {config} results from {sample_file}:", e)

        if all_runs:
            combined_df = pd.concat(all_runs, ignore_index=True)
            bin_size = 5000
            combined_df["QPS_bin"] = (combined_df["QPS"] / bin_size).round() * bin_size
            combined_df["p95"] /= 1000.0

            # Calculate mean and std
            stats = combined_df.groupby("QPS_bin").agg(
                x_mean=("QPS", "mean"),
                x_std=("QPS", "std"),
                y_mean=("p95", "mean"),
                y_std=("p95", "std"),
            ).reset_index()

            # Plot with error bars
            fig_ax.errorbar(
                stats["x_mean"],
                stats["y_mean"],
                xerr=stats["x_std"],
                yerr=stats["y_std"],
                capsize=3,
                label=config,
                marker=marker
            )

    fig_ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
    fig_ax.legend()
    fig_ax.set_xlabel("kQPS (binned per 5 kQPS)")
    fig_ax.set_ylabel("p95 latency (ms)")
    fig_ax.set_xlim(0, 80000)
    fig_ax.set_ylim(0, 6)
    fig_ax.tick_params(axis="both", which="major", labelsize=10)
    fig_ax.set_xticks(range(0, 80001, 5000))
    fig_ax.set_yticks(range(0, 7, 1))
    fig_ax.set_xticklabels([f"{x//1000}" for x in range(0, 80001, 5000)])

    plt.tight_layout()
    plt.savefig("visualizations/part1/part1.pdf")