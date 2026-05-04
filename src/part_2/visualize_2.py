import pathlib
import re

import matplotlib.pyplot as plt


def read_results(file_path: str) -> float:
    """Extract the value after `real` from a benchmark result file in seconds.

    The file contains a timing summary near the end, for example:
    `real    2m13.292s`

    This returns the elapsed time as a float number of seconds.
    """
    p = pathlib.Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    real_value = None
    with p.open() as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].lower() == "real":
                real_value = parts[1]

    if real_value is None:
        raise ValueError('Could not find a line starting with "real"')

    match = re.fullmatch(r"(?:(\d+)m)?([\d.]+)s", real_value)
    if not match:
        raise ValueError(f'Could not parse real time value: {real_value!r}')

    minutes = int(match.group(1)) if match.group(1) else 0
    seconds = float(match.group(2))
    return minutes * 60 + seconds

if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).resolve().parents[2]

    configs = ["barnes", "blackscholes", "canneal", "freqmine", "radix", "streamcluster", "vips"]

    fig = plt.figure(figsize=(5, 4))
    fig_ax = fig.gca()

    markers = ["o", "s", "D", "^", "v", "P", "*"]

    for config, marker in zip(configs, markers):
        
        results = []

        for thread_num in [1, 2, 4, 8]:
            sample_file = repo_root / "results" / "part2_runs" / "part2b_runs" / f"{config}_{thread_num}threads.txt"
            try:
                seconds = read_results(str(sample_file))
                results.append(seconds)
            except Exception as e:
                print(f"Error loading {config} results from {sample_file}:", e)

        if len(results) > 0:
            df = {"threads": [1, 2, 4, 8], "speedup": [results[0] / results[i] for i in range(len(results))]}
            fig_ax.plot(df["threads"], df["speedup"], marker=marker, label=config)

    fig_ax.plot([1, 8], [1, 8], linestyle="--", color="gray", label="linear speedup", alpha=0.7)  # Add ideal speedup line

    fig_ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)

    fig_ax.legend(loc="upper left")
    fig_ax.set_xlabel("Number of threads")
    fig_ax.set_ylabel("Speedup")
    fig_ax.set_xlim(1, 8)
    fig_ax.set_ylim(1, 6.5)
    fig_ax.tick_params(axis="both", which="major", labelsize=10)
    fig_ax.set_xticks(range(1, 9))
    plt.tight_layout()
    plt.savefig("visualizations/part2/part2.pdf")