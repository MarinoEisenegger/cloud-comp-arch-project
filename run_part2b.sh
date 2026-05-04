#!/usr/bin/env bash
set -euo pipefail

OUTDIR="part2_runs/part2b_runs"
TMPDIR="/tmp/part2b_yamls"
mkdir -p "$OUTDIR" "$TMPDIR"

WORKLOADS=("barnes" "blackscholes" "canneal" "freqmine" "radix" "streamcluster" "vips")
THREADS=("1" "2" "4" "8")

cleanup_current_jobs() {
  kubectl delete jobs --all --ignore-not-found=true >/dev/null 2>&1 || true
}

run_workload_thread() {
  local workload="$1"
  local threads="$2"
  local src_yaml="parsec-benchmarks/part2b/parsec-${workload}.yaml"
  local tmp_yaml="${TMPDIR}/parsec-${workload}-${threads}.yaml"
  local job_name="parsec-${workload}"
  local logfile="${OUTDIR}/${workload}_${threads}threads.txt"

  echo "=== Running ${workload} with ${threads} thread(s) ==="

  cp "$src_yaml" "$tmp_yaml"

  sed -i -E "s/-n[[:space:]]+[0-9]+/-n ${threads}/g" "$tmp_yaml"

  kubectl create -f "$tmp_yaml"

  kubectl wait --for=condition=complete "job/${job_name}" --timeout=90m

  local pod_name
  pod_name=$(kubectl get pods --selector=job-name="${job_name}" \
    --output=jsonpath='{.items[0].metadata.name}')

  kubectl logs "$pod_name" | tee "$logfile"

  echo "Deleting PARSEC job ${job_name}..."
  kubectl delete job "$job_name" --ignore-not-found=true

  echo "Saved: $logfile"
}

trap 'echo "Interrupted. Cleaning PARSEC jobs only."; cleanup_current_jobs; exit 1' INT TERM

for workload in "${WORKLOADS[@]}"; do
  for threads in "${THREADS[@]}"; do
    run_workload_thread "$workload" "$threads"
  done
done

echo "All Part 2b runs completed."
echo "Results saved in: $OUTDIR"
