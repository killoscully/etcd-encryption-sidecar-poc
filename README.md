# Runbook: etcd Encryption Sidecar PoC (Kubernetes)

This runbook explains how to deploy, validate, and operate the **etcd + encryption sidecar** proof-of-concept in Kubernetes.

## Overview

**Components**
- **etcd**: key/value store (gRPC on port **2379**)
- **encryption-sidecar service** (called `etcd-client` deployment): Flask API that encrypts/decrypts values and stores/retrieves them from etcd (HTTP on port **5000**)

**In-cluster DNS names**
- etcd: `etcd.etcd-poc.svc.cluster.local` (short name `etcd`)
- sidecar API: `encryption-sidecar.etcd-poc.svc.cluster.local` (short name `encryption-sidecar`)

**Namespace**
- `etcd-poc`

---

## Prerequisites

- `kubectl` configured for the target cluster
- Namespace `etcd-poc` (this runbook creates it if missing)
- Files available locally:
  - `etcd-deployment.yaml` (etcd Deployment)
  - `etcd-client-deployment.yaml` (sidecar Deployment) *(if you do not have this, see the template below)*
  - Optional: `ConfigMap`/`Secret` YAML for encryption settings/keys (if used)

---

## Quick Start (clean deploy)

### 1) Create (or recreate) the namespace

If you want a clean start, recreate the namespace:

```bash
kubectl delete namespace etcd-poc --ignore-not-found
kubectl create namespace etcd-poc
```

If you **do not** want to delete existing resources, just ensure it exists:

```bash
kubectl get ns etcd-poc || kubectl create ns etcd-poc
```

(Optional) Set your current kubectl context namespace:

```bash
kubectl config set-context --current --namespace=etcd-poc
```

---

### 2) Deploy etcd

Apply your etcd deployment:

```bash
kubectl apply -n etcd-poc -f etcd-deployment.yaml
```

Wait for it to be Running:

```bash
kubectl rollout status -n etcd-poc deploy/etcd
kubectl get pods -n etcd-poc
```

Expected:
- `etcd-xxxxx` is `Running` and `READY 1/1`

---

### 3) Create the etcd Service (required)

Create a ClusterIP service named `etcd` (required for DNS resolution from the sidecar):

```bash
kubectl apply -n etcd-poc -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: etcd
spec:
  selector:
    app: etcd
  ports:
    - name: client
      port: 2379
      targetPort: 2379
EOF
```

Verify:

```bash
kubectl get svc -n etcd-poc
```

Expected:
- `etcd` on `2379/TCP`

---

### 4) Deploy the encryption sidecar service (`etcd-client`)

Apply your sidecar deployment:

```bash
kubectl apply -n etcd-poc -f etcd-client-deployment.yaml
```

Wait for it:

```bash
kubectl rollout status -n etcd-poc deploy/etcd-client
kubectl get pods -n etcd-poc --show-labels
```

Expected:
- `etcd-client-xxxxx` is `Running` and has label `app=etcd-client`

---

### 5) Create the sidecar Service (HTTP API)

```bash
kubectl apply -n etcd-poc -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: encryption-sidecar
spec:
  selector:
    app: etcd-client
  ports:
    - name: http
      port: 5000
      targetPort: 5000
EOF
```

Verify:

```bash
kubectl get svc -n etcd-poc
```

Expected:
- `encryption-sidecar` on `5000/TCP`

---

## Validation

### A) Validate DNS resolution from the sidecar pod

Run:

```bash
kubectl exec -n etcd-poc -it deploy/etcd-client -- sh -c "getent hosts etcd"
```

Expected output (example):
- `10.x.x.x  etcd.etcd-poc.svc.cluster.local`

> Note: Some minimal containers do not include `nslookup`. `getent hosts` is sufficient.

---

### B) Test the sidecar API from your workstation

Port-forward the sidecar service:

```bash
kubectl port-forward -n etcd-poc svc/encryption-sidecar 5000:5000
```

In a **second terminal**, run:

**PUT**
```bash
curl -X POST http://localhost:5000/put \
  -H "Content-Type: application/json" \
  -d '{"key":"poc-test","value":"hello"}'
```

**GET**
```bash
curl "http://localhost:5000/get?key=poc-test"
```

Expected:
- PUT returns success (implementation dependent; often JSON like `{"status":"ok"}`)
- GET returns the decrypted value for `poc-test`

---

## Operations

### View status

```bash
kubectl get all -n etcd-poc
```

### View logs

etcd:
```bash
kubectl logs -n etcd-poc deploy/etcd --tail=200
```

sidecar:
```bash
kubectl logs -n etcd-poc deploy/etcd-client --tail=200
```

Follow logs:
```bash
kubectl logs -n etcd-poc -f deploy/etcd-client --tail=200
```

### Restart deployments

```bash
kubectl rollout restart -n etcd-poc deploy/etcd
kubectl rollout restart -n etcd-poc deploy/etcd-client
```

---

## Troubleshooting

### 1) Sidecar errors: `DNS resolution failed for etcd:2379`

**Cause**
- The `etcd` Service is missing, wrong name, wrong namespace, or its selector does not match etcd pod labels.

**Fix**
- Ensure the Service exists:
  ```bash
  kubectl get svc -n etcd-poc
  ```
- Ensure it selects the etcd pod:
  ```bash
  kubectl get pods -n etcd-poc --show-labels
  kubectl describe svc -n etcd-poc etcd
  ```
- The etcd pod must have `app=etcd` and the Service selector must match `app: etcd`.

---

### 2) Port-forward fails: service not found

**Cause**
- `encryption-sidecar` Service not created or wrong namespace.

**Fix**
```bash
kubectl get svc -n etcd-poc
kubectl apply -n etcd-poc -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: encryption-sidecar
spec:
  selector:
    app: etcd-client
  ports:
    - port: 5000
      targetPort: 5000
EOF
```

---

### 3) Sidecar pod has no labels (`<none>`) and Service cannot route traffic

**Cause**
- The pod was created as a standalone Pod without labels.

**Fix**
- Prefer deploying as a Deployment with labels (`app=etcd-client`).
- Delete and recreate the pod using a Deployment manifest.

---

### 4) etcd is Running but sidecar shows connection refused / unavailable

**Checks**
- Confirm etcd Service endpoints:
  ```bash
  kubectl get endpoints -n etcd-poc etcd -o yaml
  ```
- Confirm etcd listens on 2379:
  ```bash
  kubectl logs -n etcd-poc deploy/etcd --tail=200
  ```
- Confirm the sidecar resolves `etcd`:
  ```bash
  kubectl exec -n etcd-poc -it deploy/etcd-client -- sh -c "getent hosts etcd"
  ```

---

## Reference: Template `etcd-client-deployment.yaml`

Use this if you need a known-good sidecar deployment. Adjust env vars to match your sidecar implementation.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: etcd-client
  namespace: etcd-poc
  labels:
    app: etcd-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: etcd-client
  template:
    metadata:
      labels:
        app: etcd-client
    spec:
      containers:
        - name: encryption-sidecar
          image: ramonrodriguez495/etcd-encryption-sidecar:latest
          ports:
            - containerPort: 5000
          env:
            - name: ETCD_HOST
              value: "etcd"
            - name: ETCD_PORT
              value: "2379"
            # Optional if you use them:
            # - name: ENCRYPTION_TYPE
            #   value: "aesgcm"
            # - name: ENCRYPTION_KEY_DATA
            #   valueFrom:
            #     secretKeyRef:
            #       name: sidecar-encryption-key
            #       key: key
```

---

## Rollback / Cleanup

To remove everything:

```bash
kubectl delete namespace etcd-poc
```

If you want to keep the namespace but remove resources:

```bash
kubectl delete deploy etcd etcd-client -n etcd-poc --ignore-not-found
kubectl delete svc etcd encryption-sidecar -n etcd-poc --ignore-not-found
```
