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
            timeout=600,  # 10 minutes
            capture_output=True,
            text=True
        )
    except subprocess.TimeoutExpired:
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": "Timed out after 10 minutes", "timings": "No timings"}
        )

    if process.returncode != 0:
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": process.stderr, "timings": "No timings due to error"}
        )

    total_time, timings = total_time_seconds(f"{OUTDIR}/timings_1.txt")

    max_tail_latency = max_p95(f"{OUTDIR}/mcperf_1.txt")


    comb_score = max(0.0, 600 - total_time) / 600  # Normalize to [0,1], with a cap at 10 minutes (600 seconds)

    if max_tail_latency == float("-inf"):
        return EvaluationResult(metrics={"combined_score": 0.0, "tail_latency": max_tail_latency}, 
                                artifacts={"error": "No tail latency found...", "timings": timings})
    
    elif max_tail_latency > 1000:
        return EvaluationResult(metrics={"combined_score": 0.0, "tail_latency": max_tail_latency}, 
                                artifacts={"error": "Tail latency exceeds threshold", "timings": timings})

    return EvaluationResult(metrics={"combined_score": comb_score, "tail_latency": max_tail_latency}, 
                            artifacts={"error": None, "timings": timings})

if __name__ == "__main__":
    result = evaluate("./oe_code/initial_program.py")
    print("Evaluation Metrics:", result.metrics)
    print("Evaluation Artifacts:", result.artifacts)