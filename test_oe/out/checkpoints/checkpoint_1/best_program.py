"""
Simulated job scheduler — OpenEvolve target.

The EVOLVE-BLOCK contains the Scheduler class.
OpenEvolve should improve it to minimise total makespan
(wall-clock time until the last job finishes).

Each "job" has a known simulated duration (seconds of sleep).
Workers run jobs sequentially; workers themselves run in parallel threads.
The evaluator measures actual wall-clock time.
"""

import threading
import time

# ---------------------------------------------------------------------------
# Job catalogue: name → simulated runtime in seconds
# ---------------------------------------------------------------------------
JOBS = {
    "barnes":        3.2,
    "blackscholes":  1.5,
    "canneal":       4.8,
    "freqmine":      5.1,
    "radix":         2.3,
    "streamcluster": 6.0,
    "vips":          3.7,
}

# ---------------------------------------------------------------------------
# Worker runtime — just sleeps for the job's duration
# ---------------------------------------------------------------------------
def run_job(job_name: str, worker_id: int, duration: float) -> None:
    print(f"[worker-{worker_id}] START  {job_name}  ({duration:.1f}s)")
    time.sleep(duration)
    print(f"[worker-{worker_id}] DONE   {job_name}")


def worker(worker_cfg: dict) -> None:
    w_id = worker_cfg["id"]
    for job in worker_cfg["jobs"]:
        run_job(job, w_id, JOBS[job])
    print(f"[worker-{w_id}] finished all jobs.")


# ---------------------------------------------------------------------------
# EVOLVE-BLOCK-START
# ---------------------------------------------------------------------------
class Scheduler:
    """
    Assign jobs from JOBS to workers so that total wall-clock time is minimised.

    Rules
    -----
    * Every job must appear in exactly one worker's 'jobs' list.
    * Workers execute their jobs sequentially (one after another).
    * Workers themselves run in parallel threads.
    * Minimise makespan = max over workers of sum(durations of their jobs).

    Hint: try longest-processing-time (LPT) or any smarter heuristic.
    """

    def __init__(self):
        # LPT (Longest Processing Time) heuristic for makespan minimization
        # Sort jobs by duration descending, assign to least-loaded worker
        sorted_jobs = sorted(JOBS.keys(), key=lambda j: JOBS[j], reverse=True)
        n_workers = 4  # More workers allows better parallelization

        buckets: list[list[str]] = [[] for _ in range(n_workers)]
        loads: list[float] = [0.0] * n_workers

        for job in sorted_jobs:
            # Assign to worker with smallest current load
            min_load_idx = loads.index(min(loads))
            buckets[min_load_idx].append(job)
            loads[min_load_idx] += JOBS[job]

        self.worker_config = [
            {"jobs": buckets[i]} for i in range(n_workers)
        ]

    def run(self) -> None:
        threads = []
        for idx, cfg in enumerate(self.worker_config):
            cfg["id"] = idx
            t = threading.Thread(target=worker, args=(cfg,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

# ---------------------------------------------------------------------------
# EVOLVE-BLOCK-END
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    t0 = time.perf_counter()
    Scheduler().run()
    makespan = time.perf_counter() - t0
    # Print in a format the evaluator can parse
    print(f"MAKESPAN={makespan:.4f}")