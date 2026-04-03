#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

kubectl cluster-info >/dev/null
echo "Cluster connection verified."

echo "Building sidecar image..."
docker build -t etcd-encryption-sidecar:latest "$PROJECT_ROOT"

echo "Building benchmark client image..."
docker build -t etcd-bench-client:latest "$PROJECT_ROOT/client"

echo "Deploying namespace..."
kubectl apply -f "$PROJECT_ROOT/k8s/namespace.yaml"

echo "Deploying etcd..."
kubectl apply -f "$PROJECT_ROOT/k8s/etcd.yaml"

echo "Deploying sidecar secrets..."
kubectl apply -f "$PROJECT_ROOT/k8s/sidecar-secret.yaml"

echo "Deploying encryption sidecar..."
kubectl apply -f "$PROJECT_ROOT/k8s/sidecar.yaml"

echo "Deploying benchmark client..."
kubectl apply -f "$PROJECT_ROOT/k8s/bench-client.yaml"

echo "Waiting for etcd deployment..."
kubectl -n etcd-dissertation rollout status deployment/etcd --timeout=180s

echo "Waiting for sidecar deployment..."
kubectl -n etcd-dissertation rollout status deployment/encryption-sidecar --timeout=180s

echo "Waiting for benchmark client deployment..."
kubectl -n etcd-dissertation rollout status deployment/bench-client --timeout=180s