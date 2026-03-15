#!/usr/bin/env bash
set -euo pipefail

python benchmark/run_experiments.py --namespace etcd-dissertation --matrix benchmark/config/benchmark_matrix.yaml --results-dir benchmark/results
