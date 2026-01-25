#!/bin/bash
set -euo pipefail

NAMESPACE="etcd-poc"
TIMEOUT=120

command -v kubectl >/dev/null 2>&1 || {
  echo "kubectl not found in PATH"
  exit 1
}

echo "--- Starting etcd Encryption PoC Deployment ---"

# 1. Create Namespace
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply configuration (optional, if used)
if [ -f encryption-config.yaml ]; then
  echo "Applying ConfigMap..."
  kubectl apply -f encryption-config.yaml -n "$NAMESPACE"
fi

# 3. Deploy etcd
echo "Deploying etcd..."
kubectl apply -f etcd-deployment.yaml -n "$NAMESPACE"
kubectl apply -f etcd-service.yaml -n "$NAMESPACE"

# 4. Wait for etcd to be ready
echo "Waiting for etcd pod to be ready..."
kubectl wait \
  --for=condition=available \
  deploy/etcd \
  -n "$NAMESPACE" \
  --timeout="${TIMEOUT}s"

# 5. Deploy encryption sidecar (proxy service)
echo "Deploying encryption sidecar..."
kubectl apply -f etcd-client-deployment.yaml -n "$NAMESPACE"
kubectl apply -f encryption-sidecar-service.yaml -n "$NAMESPACE"

# 6. Wait for sidecar to be ready
echo "Waiting for encryption sidecar to be ready..."
kubectl wait \
  --for=condition=available \
  deploy/etcd-client \
  -n "$NAMESPACE" \
  --timeout="${TIMEOUT}s"

# 7. DNS sanity check
echo "Verifying DNS resolution for etcd from sidecar..."
kubectl exec -n "$NAMESPACE" deploy/etcd-client -- sh -c "getent hosts etcd"

echo "--- Running Functional Test ---"

# 8. Functional test (in-cluster)
echo "Encrypted PUT via sidecar..."
kubectl exec -n "$NAMESPACE" deploy/etcd-client -- \
  curl -s -X POST http://encryption-sidecar:5000/put \
    -H "Content-Type: application/json" \
    -d '{"key":"poc-test","value":"top-secret-data"}'

echo
echo "Decrypted GET via sidecar..."
kubectl exec -n "$NAMESPACE" deploy/etcd-client -- \
  curl -s "http://encryption-sidecar:5000/get?key=poc-test"

echo
echo "--- Deployment Complete ---"
