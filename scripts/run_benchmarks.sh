#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 "$PROJECT_ROOT/benchmark/run_experiments.py" \
  --namespace etcd-dissertation \
  --matrix "$PROJECT_ROOT/benchmark/config/benchmark_matrix.yaml" \
  --results-dir "$PROJECT_ROOT/benchmark/results"