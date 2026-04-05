# Runbook – etcd Encryption Sidecar Experimental Platform

## Purpose

This runbook explains how to deploy the current experimental platform, run the
benchmark workload, and generate benchmark outputs from the reviewed codebase.

---

## Prerequisites

Install and verify the following:

- Docker
- Kubernetes cluster
- kubectl
- Python 3

Check cluster connectivity:

```bash
kubectl cluster-info
```

---

## Namespace

The current manifests and scripts use this namespace:

```text
etcd-dissertation
```

---

## Step 1 – Deploy the Environment

Run:

```bash
./scripts/deploy.sh
```

This script:

1. builds the sidecar image
2. builds the benchmark client image
3. applies the Kubernetes namespace
4. deploys etcd
5. deploys the sidecar secret
6. deploys the encryption sidecar
7. deploys the benchmark client
8. waits for the deployments to become ready

---

## Step 2 – Verify the Deployment

Check deployments:

```bash
kubectl -n etcd-dissertation get deploy
```

Check pods:

```bash
kubectl -n etcd-dissertation get pods
```

Expected deployments:

- `etcd`
- `encryption-sidecar`
- `bench-client`

---

## Step 3 – Check the Sidecar Health Endpoint

```bash
kubectl -n etcd-dissertation port-forward svc/sidecar 5000:5000
```

Then in another terminal:

```bash
curl -s http://127.0.0.1:5000/healthz
```

Expected output includes:

- `"ok": true`
- current `encryption_type`
- supported algorithms
- etcd endpoint

---

## Step 4 – Review the Benchmark Matrix

Benchmark definitions are stored in:

```text
benchmark/config/benchmark_matrix.yaml
```

The current matrix includes:

- `NATIVE`
- `PLAINTEXT`
- `AES_GCM`
- `AES_CBC`
- `RSA`
- `HYBRID_AES_GCM_RSA`

Typical test dimensions include:

- payload sizes
- concurrency levels
- repetitions

---

## Step 5 – Run Benchmark Experiments

Run the full benchmark set:

```bash
./scripts/run_benchmarks.sh
```

Or run the Python entrypoint directly:

```bash
python3 benchmark/run_experiments.py   --namespace etcd-dissertation   --matrix benchmark/config/benchmark_matrix.yaml   --results-dir benchmark/results
```

The runner will:

1. load the experiment matrix
2. set the sidecar `ENCRYPTION_TYPE`
3. roll out the sidecar when needed
4. execute benchmark PUT/GET pairs
5. collect latency, throughput, and CPU data
6. write raw outputs to the results directory

---

## Step 6 – Generate Plots

After benchmark execution:

```bash
python3 benchmark/plot_results.py
```

Plots are written under:

```text
benchmark/results/plots/
```

---

## Step 7 – Generate the Summary Table

Create the aggregated results table:

```bash
python3 benchmark/generate_summary_table.py
```

Output:

```text
benchmark/results/summary_table.csv
```

---

## Step 8 – Cleanup

Remove the experimental environment:

```bash
./scripts/cleanup.sh
```

---

## Troubleshooting

### Check pod status

```bash
kubectl -n etcd-dissertation get pods
```

### Check sidecar logs

```bash
kubectl -n etcd-dissertation logs deployment/encryption-sidecar
```

### Check benchmark client logs

```bash
kubectl -n etcd-dissertation logs deployment/bench-client
```

### Check etcd logs

```bash
kubectl -n etcd-dissertation logs deployment/etcd
```

### Verify the current sidecar environment

```bash
kubectl -n etcd-dissertation get deployment encryption-sidecar -o yaml
```

### CPU monitoring note

The benchmark code reads CPU usage using `docker stats`.
If your Kubernetes environment is not using a Docker-visible container runtime,
CPU monitoring may return zero or require adaptation.
