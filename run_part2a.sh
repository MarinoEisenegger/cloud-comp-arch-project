#!/usr/bin/env bash
set -euo pipefail

OUTDIR="part2_runs/part2a_runs"
mkdir -p "$OUTDIR"

WORKLOADS=("barnes" "blackscholes" "canneal" "freqmine" "radix" "streamcluster" "vips")
INTERFERENCES=("none" "cpu" "l1d" "l1i" "l2" "llc" "membw")

cleanup_current_jobs() {
  kubectl delete jobs --all --ignore-not-found=true >/dev/null 2>&1 || true
}

start_interference() {
  local interference="$1"

  if [[ "$interference" == "none" ]]; then
    return
  fi

  echo "=== Starting interference: ibench-${interference} ==="
  kubectl create -f "interference/ibench-${interference}.yaml"

  echo "Waiting for ibench-${interference} to be Running/Ready..."
  kubectl wait --for=condition=Ready "pod/ibench-${interference}" --timeout=5m

  kubectl get pods -o wide
}

stop_interference() {
  local interference="$1"

  if [[ "$interference" == "none" ]]; then
    return
  fi

  echo "=== Stopping interference: ibench-${interference} ==="
  kubectl delete pod "ibench-${interference}" --ignore-not-found=true
  kubectl wait --for=delete "pod/ibench-${interference}" --timeout=2m || true
}

run_workload() {
  local workload="$1"
  local interference="$2"
  local yaml="parsec-benchmarks/part2a/parsec-${workload}.yaml"
  local job_name="parsec-${workload}"
  local logfile="${OUTDIR}/${workload}_${interference}.txt"

  echo "=== Running ${workload} with ${interference} ==="

  kubectl create -f "$yaml"

  kubectl wait --for=condition=complete "job/${job_name}" --timeout=60m

  local pod_name
  pod_name=$(kubectl get pods --selector=job-name="${job_name}" \
    --output=jsonpath='{.items[0].metadata.name}')

  kubectl logs "$pod_name" | tee "$logfile"

  echo "Deleting PARSEC job ${job_name} only..."
  kubectl delete job "$job_name" --ignore-not-found=true

  echo "Saved: $logfile"
}

trap 'echo "Interrupted. Cleaning PARSEC jobs only."; cleanup_current_jobs; exit 1' INT TERM

for interference in "${INTERFERENCES[@]}"; do
  start_interference "$interference"

  for workload in "${WORKLOADS[@]}"; do
    run_workload "$workload" "$interference"
  done

  stop_interference "$interference"
done

echo "All Part 2a runs completed."
echo "Results saved in: $OUTDIR"
