# etcd Encryption Sidecar

This repository contains the implementation of an encryption sidecar
used to evaluate the performance impact of applying additional
cryptographic protection to data stored in etcd.

The platform accompanies the MSc dissertation:

**"Performance Analysis of Sidecar-Based Encryption for etcd in
Kubernetes Environments."**

The system introduces an encryption layer between application workloads
and the etcd datastore using the sidecar architectural pattern. A
Python-based sidecar service performs encryption before data is written
to etcd and decrypts data when it is retrieved.

The implementation is designed for **controlled experimental
benchmarking** rather than production deployment.

------------------------------------------------------------------------

## Research Motivation

In Kubernetes environments, etcd acts as the primary datastore for
cluster state, configuration data, and secrets. While Kubernetes
supports encryption at rest, this functionality typically relies on
internal encryption mechanisms integrated within the control plane.

This research explores an alternative architectural approach: applying
encryption externally through a **sidecar-based service**. The objective
is to evaluate whether encryption can be introduced transparently
without modifying etcd itself, and to measure the resulting performance
overhead.

------------------------------------------------------------------------

## System Architecture

The experimental platform consists of three main components:

  -----------------------------------------------------------------------
  Component                      Description
  ------------------------------ ----------------------------------------
  Benchmark Client               Generates controlled read/write workload

  Encryption Sidecar             Python service that encrypts data before
                                 storage and decrypts data during
                                 retrieval

  etcd                           Distributed key--value datastore used as
                                 the persistent storage layer
  -----------------------------------------------------------------------

Data flow:

Benchmark Client → Encryption Sidecar → etcd

All write operations pass through the sidecar before reaching etcd.

------------------------------------------------------------------------

## Experimental Design

The experiment matrix varies three primary factors:

-   encryption mode
-   payload size
-   repeated read/write operations

### Encryption modes

-   PLAINTEXT -- baseline without encryption
-   AES_GCM
-   AES_CBC
-   RSA
-   HYBRID_AES_GCM_RSA

### Payload sizes

-   1 KB
-   10 KB
-   100 KB

Each experiment executes repeated read/write operations under controlled
workload conditions.

------------------------------------------------------------------------

## Repository Structure

benchmark/ config/benchmark_matrix.yaml run_experiments.py results/

client/ app/run_bench.py Dockerfile

k8s/ namespace.yaml etcd.yaml sidecar-secret.yaml sidecar.yaml
bench-client.yaml

scripts/ deploy.sh run_benchmarks.sh

Dockerfile etcd_encryption_sidecar.py encryption_plugin_system.py

------------------------------------------------------------------------

## Running the Experiment

Deploy and run:

./scripts/deploy.sh ./scripts/run_benchmarks.sh

Results are written to:

benchmark/results/run_results.csv

Raw benchmark data is stored in:

benchmark/results/raw/

------------------------------------------------------------------------

## Notes

-   RSA keys are automatically generated if not supplied.
-   The PLAINTEXT mode keeps the same storage flow for fair comparison.
-   This platform is designed only for research benchmarking.
