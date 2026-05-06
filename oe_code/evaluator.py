import re
import subprocess
from openevolve.evaluation_result import EvaluationResult

OUTDIR = "oe_runs"

def parse_time_to_seconds(time_str):
    h, m, s = map(int, time_str.split(":"))
    return h * 3600 + m * 60 + s

def total_time_seconds(file_path):
    total = float('inf')
    pattern = re.compile(r"Total time:\s*(\d+:\d+:\d+)")

    timings = ""

    with open(file_path, "r") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                total = min(total, parse_time_to_seconds(match.group(1)))

            timings += line

    return total, timings

def max_p95(file_path):
    max_val = float("-inf")

    with open(file_path, "r") as f:
        for line in f:
            if not line.startswith("read"):
                continue

            parts = line.split()
            try:
                p95 = float(parts[12])  # p95 column
                max_val = max(max_val, p95)
            except (IndexError, ValueError):
                continue

    return max_val

def evaluate(program_path: str) -> EvaluationResult:
    """
    Evaluate the evolved program at "program_path" and return an EvaluationResult object containing the evaluation metrics.
    """

    try:
        process = subprocess.run(
            ["uv", "run", program_path],
            timeout=480,  # 8 minutes
            capture_output=True,
            text=True
        )
    except subprocess.TimeoutExpired:
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": "Timed out after 8 minutes", "timings": "No timings"}
        )

    if process.returncode != 0:
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": process.stderr, "timings": "No timings due to error"}
        )

    total_time, timings = total_time_seconds(f"{OUTDIR}/timings_1.txt")

    max_tail_latency = max_p95(f"{OUTDIR}/mcperf_1.txt")


    time_score = max(0.0, 480 - total_time) / 480  # Normalize to [0,1], with a cap at 8 minutes (480 seconds)

    # Latency score: 1.0 at or below target, decays to 0 at threshold, negative beyond threshold
    latency_score = max(-1.0, (1000 - max_tail_latency) / (1000-300))

    if latency_score <= 0:
        # Hard penalty: latency is unacceptable, but score reflects how bad
        combined_score = max(0.0, latency_score) * 0.1
    else:
        # Both metrics contribute; latency is a multiplier on time
        combined_score = time_score + (0.1 * latency_score)

    return EvaluationResult(
        metrics={"combined_score": combined_score, "tail_latency": max_tail_latency},
        artifacts={"error": None, "timings": timings,
                   "time_score": str(round(time_score, 3)),
                   "latency_score": str(round(latency_score, 3))}
    )

if __name__ == "__main__":
    result = evaluate("./oe_code/initial_program.py")
    print("Evaluation Metrics:", result.metrics)
    print("Evaluation Artifacts:", result.artifacts)