# Runbook: etcd Encryption Sidecar PoC (Kubernetes)

This runbook describes how to deploy, validate, operate, and clean up the **etcd + encryption sidecar** proof-of-concept in Kubernetes using declarative YAML files. It reflects the **final, consistent configuration** where the sidecar listens on **port 5000 everywhere** (application, container, Service, and port-forwarding).

---

## Architecture Overview

**Components**

* **etcd** (Deployment + Service)

  * gRPC client endpoint on port **2379**
* **Encryption Sidecar Service** (Deployment + Service, named `etcd-client`)

  * HTTP API on port **5000**
  * Encrypts/decrypts values before storing/retrieving them from etcd

**In-cluster DNS**

* etcd: `etcd.etcd-poc.svc.cluster.local` (short name: `etcd`)
* sidecar API: `encryption-sidecar.etcd-poc.svc.cluster.local`

**Namespace**

* `etcd-poc`

---

## Prerequisites

* `kubectl` configured for the target cluster
* Docker image available (public):

  * `killoscully/etcd-encryption-sidecar:latest`
* Local manifest files:

  * `etcd-deployment.yaml`
  * `etcd-service.yaml`
  * `etcd-client-deployment.yaml`
  * `encryption-sidecar-service.yaml`

---

## 1. Namespace Setup

Create or reset the namespace.

### Clean reset (recommended for PoC)

```bash
kubectl delete namespace etcd-poc --ignore-not-found
kubectl create namespace etcd-poc
```

### Or ensure it exists

```bash
kubectl get ns etcd-poc || kubectl create ns etcd-poc
```

(Optional) Set default namespace:

```bash
kubectl config set-context --current --namespace=etcd-poc
```

---

## 2. Deploy etcd

### Apply Deployment

```bash
kubectl apply -f etcd-deployment.yaml
```

### Apply Service

```bash
kubectl apply -f etcd-service.yaml
```

### Verify

```bash
kubectl rollout status deploy/etcd
kubectl get pods
kubectl get svc
```

Expected:

* `etcd-xxxxx` → `Running`
* `etcd` Service → `2379/TCP`

---

## 3. Deploy Encryption Sidecar (etcd-client)

### Apply Deployment

```bash
kubectl apply -f etcd-client-deployment.yaml
```

### Apply Service

```bash
kubectl apply -f encryption-sidecar-service.yaml
```

### Verify

```bash
kubectl rollout status deploy/etcd-client
kubectl get pods --show-labels
kubectl get svc
```

Expected:

* `etcd-client-xxxxx` → `Running`
* `encryption-sidecar` Service → `5000/TCP`

---

## 4. DNS and Connectivity Validation

### Verify etcd DNS from sidecar

```bash
kubectl exec -it deploy/etcd-client -- sh -c "getent hosts etcd"
```

Expected:

* IP address returned for `etcd.etcd-poc.svc.cluster.local`

---

## 5. Functional Test (PUT / GET)

### Port-forward sidecar API (5000 → 5000)

```bash
kubectl port-forward svc/encryption-sidecar 5000:5000
```

### PUT

```bash
curl -X POST http://localhost:5000/put \
  -H "Content-Type: application/json" \
  -d '{"key":"poc-test","value":"hello"}'
```

### GET

```bash
curl "http://localhost:5000/get?key=poc-test"
```

Expected:

* Value returned matches input

---

## 6. Operations

### View status

```bash
kubectl get all
```

### Logs

etcd:

```bash
kubectl logs deploy/etcd --tail=200
```

sidecar:

```bash
kubectl logs deploy/etcd-client --tail=200
```

### Restart

```bash
kubectl rollout restart deploy/etcd
kubectl rollout restart deploy/etcd-client
```

---

## 7. Troubleshooting

### Issue: Sidecar starts but requests fail

**Check**

```bash
kubectl logs deploy/etcd-client --tail=50
```

Ensure log line shows:

```
Starting sidecar on 0.0.0.0:5000
```

If it shows another port, the image was not rebuilt or pulled.

---

### Issue: DNS resolution failed for `etcd`

**Fix**

```bash
kubectl describe svc etcd
kubectl get pods --show-labels
```

Ensure:

* Pod label: `app=etcd`
* Service selector: `app: etcd`

---

## 8. Cleanup

```bash
kubectl delete namespace etcd-poc
```

---

## Automated Deployment (Recommended)

For repeatable runs, use the deployment script.

### Script

* `deploy_poc.sh`

### Run

```bash
chmod +x deploy_poc.sh
./deploy_poc.sh
```

### When to use

* Benchmarks
* Demos
* CI or repeated experiments

---

## Notes for Benchmarking (Next Phase)

* Add `ENCRYPTION_TYPE=none` for baseline
* Instrument encryption/decryption latency
* Run controlled load tests
* Capture CPU/memory per pod

This runbook defines a **stable, repeatable baseline** suitable for performance and security research.
