#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=etcd-dissertation

echo "Deleting namespace and all resources..."
kubectl delete namespace "$NAMESPACE"