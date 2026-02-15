#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BENCH_DIR="${ROOT_DIR}/benchmarks"
SCRIPTS_DIR="${BENCH_DIR}/scripts"

echo "[bench] repo=${ROOT_DIR}"
echo "[bench] starting matrix run..."

python3 "${SCRIPTS_DIR}/run_matrix_driver.py" \
  --namespace etcd-bench \
  --matrix "${BENCH_DIR}/configs/matrix_core.yaml" \
  --results-dir "${BENCH_DIR}/results"

echo "[bench] done"
echo "[bench] results: ${BENCH_DIR}/results/run_results.csv"
