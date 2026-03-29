#!/bin/bash

NAMESPACE=etcd-dissertation

echo "Deleting namespace and all resources..."
kubectl delete namespace $NAMESPACE