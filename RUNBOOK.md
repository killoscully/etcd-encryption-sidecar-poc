# Runbook -- etcd Encryption Sidecar Experimental Platform

This runbook explains how to deploy the experimental platform and
execute the benchmark experiments.

------------------------------------------------------------------------

## Prerequisites

Install the following:

-   Docker
-   Kubernetes (Docker Desktop, Minikube, or Kind)
-   kubectl
-   Python 3

Verify cluster connectivity:

kubectl cluster-info

------------------------------------------------------------------------

## Step 1 -- Deploy the Environment

Run:

./scripts/deploy.sh

This script will:

1.  Build the container images
2.  Deploy the Kubernetes namespace
3.  Deploy etcd
4.  Deploy the encryption sidecar
5.  Deploy the benchmark client
6.  Wait for all components to become ready

------------------------------------------------------------------------

## Step 2 -- Verify Deployment

Check running pods:

kubectl -n etcd-dissertation get pods

Expected:

etcd Running encryption-sidecar Running bench-client Running

------------------------------------------------------------------------

## Step 3 -- Run Benchmark Experiments

Execute:

./scripts/run_benchmarks.sh

The script reads the experiment matrix defined in:

benchmark/config/benchmark_matrix.yaml

Each scenario runs a set of read/write operations using the configured
encryption mode and payload size.

------------------------------------------------------------------------

## Step 4 -- Monitor Execution

To watch sidecar logs:

kubectl -n etcd-dissertation logs deployment/encryption-sidecar -f

To monitor pod resource usage:

kubectl top pods -n etcd-dissertation

------------------------------------------------------------------------

## Step 5 -- Inspect Results

Results are stored in:

benchmark/results/run_results.csv

Raw benchmark data:

benchmark/results/raw/

These files can be used for analysis and plotting graphs for the
dissertation.

------------------------------------------------------------------------

## Step 6 -- Cleanup

To remove the environment:

kubectl delete namespace etcd-dissertation

------------------------------------------------------------------------

## Troubleshooting

Check pod status:

kubectl -n etcd-dissertation get pods

Check sidecar logs:

kubectl -n etcd-dissertation logs deployment/encryption-sidecar

Ensure images exist locally if using Docker Desktop Kubernetes:

docker build -t etcd-encryption-sidecar:latest . docker build -t
etcd-bench-client:latest ./client
