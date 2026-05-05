"""
Evaluator for the simulated job scheduler (evolve_target.py).

OpenEvolve calls this script after each code mutation.
It must print a single float to stdout — higher is better.

Score = 1 / makespan   (so shorter wall-clock time → higher score)

Exit code 0 = evaluation succeeded.
Exit code 1 = evaluation failed (e.g. crashed or constraint violated).
"""

import subprocess
import sys
import re
import time
from openevolve.evaluation_result import EvaluationResult

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET_SCRIPT = "evolve_target.py"

# Known total work: every job must be scheduled (sum of all durations)
JOBS = {
    "barnes":        3.2,
    "blackscholes":  1.5,
    "canneal":       4.8,
    "freqmine":      5.1,
    "radix":         2.3,
    "streamcluster": 6.0,
    "vips":          3.7,
}
ALL_JOBS = set(JOBS.keys())
TOTAL_WORK = sum(JOBS.values())          # theoretical minimum with ∞ workers
SERIAL_TIME = TOTAL_WORK                  # worst case: one worker, no overlap

TIMEOUT = 60  # seconds — kill runaway processes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_makespan(output: str) -> float | None:
    """Extract MAKESPAN=<float> from the script's stdout."""
    m = re.search(r"MAKESPAN=([0-9]+\.[0-9]+)", output)
    return float(m.group(1)) if m else None


def check_all_jobs_ran(output: str) -> bool:
    """Verify every job appeared at least once in the output."""
    return all(job in output for job in ALL_JOBS)


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate(script_path: str = TARGET_SCRIPT) -> EvaluationResult:
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"[evaluator] TIMEOUT after {TIMEOUT}s", file=sys.stderr)
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": f"Timed out after {TIMEOUT} minutes"}
        )
    except Exception as e:
        print(f"[evaluator] Subprocess error: {e}", file=sys.stderr)
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": f"sys.stderr: {str(e)}"}
        )

    stdout = result.stdout
    stderr = result.stderr

    # --- Hard constraints ---
    if result.returncode != 0:
        print(f"[evaluator] Script exited with code {result.returncode}", file=sys.stderr)
        print(stderr, file=sys.stderr)
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": f"Script exited with code {result.returncode}"}
        )

    if not check_all_jobs_ran(stdout):
        missing = ALL_JOBS - {j for j in ALL_JOBS if j in stdout}
        print(f"[evaluator] Missing jobs in output: {missing}", file=sys.stderr)
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": f"Missing jobs in output: {missing}"}
        )

    makespan = parse_makespan(stdout)
    if makespan is None:
        print("[evaluator] Could not parse MAKESPAN from output", file=sys.stderr)
        return EvaluationResult(
            metrics={"combined_score": 0.0, "tail_latency": float('inf')},
            artifacts={"error": "Could not parse MAKESPAN from output"}
        )
    
    # --- Soft scoring ---
    # Optimal lower bound = longest single job (if we had unlimited workers)
    # Practical lower bound ≈ max(job durations) = 6.0
    optimal_lower_bound = max(JOBS.values())   # 6.0 s

    # Score: fraction of the way from serial to optimal
    # score = (serial_time - makespan) / (serial_time - optimal_lower_bound)
    # Clamped to [0, 1] — but we return raw so OpenEvolve can track improvements
    score = 1.0 / makespan

    print(f"[evaluator] makespan={makespan:.3f}s  "
          f"optimal_lb={optimal_lower_bound:.1f}s  "
          f"score={score:.5f}")
    return EvaluationResult(
        metrics={"combined_score": score, "tail_latency": float('inf')},
        artifacts={"error": None}
    )


if __name__ == "__main__":
    print("hi")
    script = sys.argv[1] if len(sys.argv) > 1 else TARGET_SCRIPT
    score = evaluate(script)
    print(score)          # OpenEvolve reads this final line
