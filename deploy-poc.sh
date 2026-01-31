#!/bin/bash
set -euo pipefail

NAMESPACE="etcd-poc"
TIMEOUT=180

command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found in PATH"; exit 1; }

echo "--- Starting etcd Encryption Sidecar PoC (Multi-Client) ---"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

echo "Applying sidecar key Secret..."
kubectl apply -f sidecar-encryption-key-secret.yaml -n "$NAMESPACE"

echo "Deploying etcd..."
kubectl apply -f etcd.yaml -n "$NAMESPACE"

echo "Waiting for etcd to be ready..."
kubectl wait --for=condition=available deploy/etcd -n "$NAMESPACE" --timeout="${TIMEOUT}s"

CLIENTS=("aesgcm" "chacha" "cbc" "fernet")

echo "Deploying clients (each has its own Service)..."
for c in "${CLIENTS[@]}"; do
  kubectl apply -f "etcd-client-${c}.yaml" -n "$NAMESPACE"
done

echo "Waiting for clients..."
for c in "${CLIENTS[@]}"; do
  kubectl wait --for=condition=available "deploy/etcd-client-${c}" -n "$NAMESPACE" --timeout="${TIMEOUT}s"
done

echo "Verifying DNS resolution for etcd from each sidecar..."
for c in "${CLIENTS[@]}"; do
  kubectl exec -n "$NAMESPACE" "deploy/etcd-client-${c}" -c encryption-sidecar -- sh -c "getent hosts etcd"
done

echo "--- Functional Test (inside each client pod: app -> localhost sidecar) ---"
for c in "${CLIENTS[@]}"; do
  echo
  echo "== Client: ${c} =="
  KEY="${c}/poc-test"
  kubectl exec -n "$NAMESPACE" "deploy/etcd-client-${c}" -c app --     curl -s -X POST http://127.0.0.1:5000/put       -H "Content-Type: application/json"       -d "{\"key\":\"${KEY}\",\"value\":\"top-secret-data-${c}\"}"
  echo
  kubectl exec -n "$NAMESPACE" "deploy/etcd-client-${c}" -c app --     curl -s "http://127.0.0.1:5000/get?key=${KEY}"
  echo
done

echo
echo "--- Deployment Complete ---"
echo "Services created (one per encryption client):"
kubectl get svc -n "$NAMESPACE" | grep encryption-sidecar- || true
