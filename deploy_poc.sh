#!/bin/bash
set -euo pipefail

NAMESPACE="etcd-poc"
TIMEOUT=120

command -v kubectl >/dev/null 2>&1 || {
  echo "kubectl not found in PATH"
  exit 1
}

echo "--- Starting etcd Encryption Sidecar PoC (True Sidecar) ---"

# 1) Namespace
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# 2) Config (optional)
if [ -f encryption-config.yaml ]; then
  echo "Applying ConfigMap..."
  kubectl apply -f encryption-config.yaml -n "$NAMESPACE"
fi

# 3) etcd
echo "Deploying etcd..."
kubectl apply -f etcd_deployment.yaml -n "$NAMESPACE"
kubectl apply -f etcd_service.yaml -n "$NAMESPACE"

echo "Waiting for etcd to be ready..."
kubectl wait --for=condition=available deploy/etcd -n "$NAMESPACE" --timeout="${TIMEOUT}s"

# 4) App + sidecar (same pod)
echo "Deploying app + encryption sidecar (same pod)..."
kubectl apply -f etcd_client_deployment.yaml -n "$NAMESPACE"

echo "Waiting for app+sidecar to be ready..."
kubectl wait --for=condition=available deploy/etcd-client -n "$NAMESPACE" --timeout="${TIMEOUT}s"

echo "Verifying DNS resolution for etcd from sidecar..."
kubectl exec -n "$NAMESPACE" deploy/etcd-client -c encryption-sidecar -- sh -c "getent hosts etcd"

echo "--- Running Functional Test (from app container -> localhost sidecar) ---"

echo "Encrypted PUT via sidecar..."
kubectl exec -n "$NAMESPACE" deploy/etcd-client -c app --   curl -s -X POST http://127.0.0.1:5000/put     -H "Content-Type: application/json"     -d '{"key":"poc-test","value":"top-secret-data"}'

echo
echo "Decrypted GET via sidecar..."
kubectl exec -n "$NAMESPACE" deploy/etcd-client -c app --   curl -s "http://127.0.0.1:5000/get?key=poc-test"

echo
echo "--- Deployment Complete ---"
