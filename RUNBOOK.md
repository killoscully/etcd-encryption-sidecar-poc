# Runbook – etcd Encryption Sidecar Experimental Platform

This runbook explains how to deploy the experimental environment and run the benchmarking experiments.

---

## Prerequisites

Ensure the following tools are installed:

Docker  
Kubernetes cluster (Docker Desktop, Minikube, or Kind)  
kubectl  
Python 3

Verify cluster connectivity:

kubectl cluster-info

---

## Step 1 – Deploy the Environment

Run:

./scripts/deploy.sh

This script:

1. Builds the container images
2. Creates the Kubernetes namespace
3. Deploys etcd
4. Deploys the encryption sidecar
5. Deploys the benchmark client
6. Waits for deployments to become ready

---

## Step 2 – Verify Deployment

Check pods:

kubectl -n etcd-dissertation get pods

Expected pods:

etcd  
encryption-sidecar  
bench-client

---

## Step 3 – Configure Benchmark Matrix

Experiments are defined in:

benchmark/config/benchmark_matrix.yaml

Typical configuration:

Payload sizes:
1024
10240
102400

Concurrency levels:
1
10
64
128

Repetitions:
5

---

## Step 4 – Run Experiments

Execute:

./scripts/run_benchmarks.sh

Or directly:

python3 benchmark/run_experiments.py

The runner will:

1. Read the experiment matrix
2. Configure the sidecar encryption mode
3. Execute benchmarks
4. Collect results
5. Store results in CSV and JSON format

---

## Step 5 – Generate Plots

After experiments complete:

python3 benchmark/plot_results.py

Plots are stored in:

benchmark/results/plots/

Generated figures include:

Throughput vs concurrency  
Read latency vs concurrency  
Write latency vs concurrency  
Write latency overhead vs baseline

---

## Step 6 – Generate Summary Table

Create aggregated results:

python3 benchmark/generate_summary_table.py

Output:

benchmark/results/summary_table.csv

---

## Step 7 – Cleanup

Remove the environment:

kubectl delete namespace etcd-dissertation

---

## Troubleshooting

Check logs:

kubectl -n etcd-dissertation logs deployment/encryption-sidecar

Check pod status:

kubectl -n etcd-dissertation get pods
