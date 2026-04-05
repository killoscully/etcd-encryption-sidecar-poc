# etcd Encryption Sidecar – Dissertation Experimental Platform

## Overview

This repository contains a **Python-based encryption sidecar** used to evaluate the
performance impact of adding cryptographic protection to data stored in **etcd**
in a Kubernetes environment.

The project supports **controlled benchmarking** of multiple encryption modes by
placing a sidecar service between a benchmark client and the etcd datastore.
The sidecar encrypts values before storage and decrypts them on retrieval.

This implementation is designed for **experimental evaluation**, not production use.

---

## What the Current Codebase Actually Implements

After reviewing the current codebase, the platform is organised around these components:

- **Benchmark client**
  - A lightweight client container that runs the benchmark driver
  - Generates PUT and GET workloads against either the sidecar or etcd directly
- **Encryption sidecar**
  - Python Flask service exposing `/put`, `/get`, `/all`, and `/healthz`
  - Performs encryption and decryption before interacting with etcd
- **etcd**
  - Persistent key-value store used as the storage backend
- **Benchmark tooling**
  - Python scripts for running experiments, collecting raw metrics, generating plots, and building summary tables

---

## Current Architecture

### Runtime Data Path

```text
Benchmark Client → Encryption Sidecar → etcd
```

### Benchmark Comparison Path

The benchmark runner supports two paths:

- **Sidecar path**  
  Benchmark client → sidecar → etcd

- **Native path**  
  Benchmark client → etcd directly

This allows comparison between:

- direct etcd access
- sidecar plaintext mode
- sidecar encryption modes

---

## Implemented Encryption Modes

The current code registers the following modes in `encryption_plugin_system.py`:

- `PLAINTEXT`
- `AES_GCM`
- `AES_CBC`
- `RSA`
- `HYBRID_AES_GCM_RSA`

### Notes on the implemented modes

- **PLAINTEXT**
  - Used as a sidecar baseline without encryption
- **AES_GCM**
  - Symmetric authenticated encryption
- **AES_CBC**
  - Implemented with **AES-CBC + HMAC-SHA256** for integrity protection
- **RSA**
  - RSA-OAEP based asymmetric encryption
  - Payloads are split into chunks to fit RSA encryption limits
- **HYBRID_AES_GCM_RSA**
  - Uses AES-GCM for payload encryption
  - Uses RSA-OAEP to encrypt the randomly generated data encryption key

### Important clarification

The current repository **does not implement** these modes in the reviewed codebase:

- `CHACHA20_POLY1305`
- `FERNET`
- `JWT_SIGNED`
- `JWT_ENCRYPTED`

Those modes should **not** be documented as active features for this repository version.

---

## Benchmark Matrix in the Current Repository

The benchmark configuration file currently includes these experiment sets:

- `NATIVE`
- `PLAINTEXT`
- `AES_GCM`
- `AES_CBC`
- `RSA`
- `HYBRID_AES_GCM_RSA`

This means the repository is already structured to benchmark both:

- **symmetric encryption**
- **asymmetric encryption**
- **hybrid encryption**
- **direct etcd access**

---

## Sidecar Service Behaviour

The sidecar service:

- connects to etcd using `etcd3`
- selects the encryption mode using the `ENCRYPTION_TYPE` environment variable
- encrypts data during `/put`
- decrypts data during `/get`
- exposes `/healthz` for readiness checks
- exposes `/all` to inspect stored keys and values

The `/healthz` endpoint also reports the current encryption mode and the list of
supported algorithms.

---

## Key Material Handling

The current code loads shared key material from:

- `ENCRYPTION_KEY_DATA`

It also supports RSA key material using:

- `RSA_PRIVATE_KEY_PEM`
- `RSA_PUBLIC_KEY_PEM`

If RSA key material is not provided, the current implementation can generate an
RSA keypair automatically at runtime for experimental use.

This is suitable for benchmarking, but it is **not a production key-management design**.

---

## Kubernetes Deployment Model

The current repository uses a **separate benchmark client deployment** and a
**separate sidecar deployment**.

### Current Kubernetes resources

- `k8s/namespace.yaml`
- `k8s/etcd.yaml`
- `k8s/sidecar.yaml`
- `k8s/bench-client.yaml`
- `k8s/sidecar-secret.yaml`

### Current namespace

All provided manifests and scripts use:

```text
etcd-dissertation
```

### Important clarification

The current repository version is **not** using the “application container and sidecar
in the same Pod” multi-client layout that appeared in later discussion.

The reviewed codebase uses:

- one sidecar deployment
- one benchmark client deployment
- one etcd deployment

So the README should describe this repository as a **benchmark platform with a sidecar service**,
not as a multi-client same-Pod experimental layout.

---

## Scripts Included

### Deployment
`./scripts/deploy.sh`

This script:

1. builds the sidecar image
2. builds the benchmark client image
3. deploys the namespace
4. deploys etcd
5. deploys the sidecar secret
6. deploys the sidecar deployment
7. deploys the benchmark client deployment
8. waits for rollouts to complete

### Benchmark execution
`./scripts/run_benchmarks.sh`

This runs:

```bash
python3 benchmark/run_experiments.py
```

### Cleanup
`./scripts/cleanup.sh`

This removes the benchmark namespace.

---

## Benchmarking Features

The repository includes these benchmark utilities:

- `benchmark/run_experiments.py`
- `benchmark/plot_results.py`
- `benchmark/generate_summary_table.py`

### Metrics collected

The benchmark runner records:

- payload size
- iterations
- concurrency
- total operations
- throughput
- wall time
- average, p50, p95, and p99 write latency
- average, p50, p95, and p99 read latency
- error rates
- average CPU usage
- peak CPU usage

### CPU monitoring note

The CPU monitor uses `docker stats` and resolves the sidecar container name from
the local Docker runtime.

This means CPU collection assumes an environment where Kubernetes containers are
visible through Docker naming conventions. That may require adjustment for
non-Docker runtimes.

---

## Repository Structure

```text
.
├── Dockerfile
├── README.md
├── RUNBOOK.md
├── encryption_plugin_system.py
├── etcd_encryption_sidecar.py
├── k8s/
│   ├── namespace.yaml
│   ├── etcd.yaml
│   ├── sidecar.yaml
│   ├── bench-client.yaml
│   └── sidecar-secret.yaml
├── client/
│   ├── Dockerfile
│   └── app/
│       └── run_bench.py
├── benchmark/
│   ├── config/
│   │   └── benchmark_matrix.yaml
│   ├── run_experiments.py
│   ├── plot_results.py
│   └── generate_summary_table.py
└── scripts/
    ├── deploy.sh
    ├── run_benchmarks.sh
    └── cleanup.sh
```

---

## How to Run

### 1. Deploy the environment

```bash
./scripts/deploy.sh
```

### 2. Run the benchmark suite

```bash
./scripts/run_benchmarks.sh
```

### 3. Generate plots

```bash
python3 benchmark/plot_results.py
```

### 4. Generate the summary table

```bash
python3 benchmark/generate_summary_table.py
```

### 5. Clean up

```bash
./scripts/cleanup.sh
```

---

## Research Positioning

This platform is suitable for evaluating:

- overhead introduced by a sidecar encryption service
- performance differences between plaintext, symmetric, asymmetric, and hybrid modes
- comparison between sidecar-based protection and direct etcd access

It is not intended to provide:

- production-grade key management
- Kubernetes control-plane integration
- operational hardening for live clusters

