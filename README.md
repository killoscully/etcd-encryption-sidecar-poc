# Runbook: etcd Encryption *Sidecar* PoC (Kubernetes)

This runbook deploys etcd plus a **true sidecar** encryption component, colocated with an **application container in the same Pod**.
The application talks to the sidecar over **localhost**, and the sidecar talks to etcd over the cluster Service.

---

## Architecture Overview

**Single Pod (etcd-client Deployment)**

* **app container**
  * Generates requests (benchmark/workload)
  * Calls the sidecar on `http://127.0.0.1:5000`

* **encryption-sidecar container**
  * Encrypts on PUT, decrypts on GET
  * Connects to etcd at `etcd:2379`

**Cluster**

* **etcd** (Deployment + Service)
  * Client endpoint: `etcd:2379`

**Data path**

`app -> localhost:5000 (sidecar) -> etcd service -> etcd pod`

> Note: A Kubernetes Service for the sidecar is **not required** for the sidecar pattern. Only use a Service/port-forward if you want to debug from outside the Pod.

---

## Files

* `etcd-deployment.yaml`, `etcd-service.yaml` : etcd
* `etcd-client-deployment.yaml` : **app + sidecar in the same Pod**
* `encryption-config.yaml` : optional config (e.g., `ENCRYPTION_TYPE`)

---

## Deploy + Functional Test

### One command

```bash
bash deploy_poc.sh
```

The script:
1. Deploys etcd
2. Deploys the app + sidecar pod
3. Runs a PUT and GET **from the app container** to `127.0.0.1:5000`

---

## Manual Test (inside cluster)

```bash
kubectl exec -n etcd-poc deploy/etcd-client -c app --   curl -s -X POST http://127.0.0.1:5000/put   -H "Content-Type: application/json"   -d '{"key":"poc-test","value":"top-secret-data"}'
```

```bash
kubectl exec -n etcd-poc deploy/etcd-client -c app --   curl -s "http://127.0.0.1:5000/get?key=poc-test"
```

---

## Optional: Debug from your laptop (NOT required)

If you really want to call the sidecar from outside the pod, you can temporarily apply `encryption-sidecar-service.yaml` and port-forward it:

```bash
kubectl apply -n etcd-poc -f encryption_sidecar_service.yaml
kubectl port-forward -n etcd-poc svc/encryption-sidecar 5000:5000
```

But for the thesis “sidecar pattern” claim, keep the benchmark traffic **app -> localhost -> sidecar**.

---

## Cleanup

```bash
kubectl delete namespace etcd-poc
```
