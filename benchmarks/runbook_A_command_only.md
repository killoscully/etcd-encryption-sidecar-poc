# Runbook A — Command-Only Checklist (Option A)

## Purpose
Execute the full etcd benchmark matrix using kubectl exec into a long-running client pod.

---

## A1) Local preparation
```bash
kubectl version --client
kubectl cluster-info
chmod +x benchmarks/scripts/*.sh
```

---

## A2) Build and push images
```bash
docker build -t killoscully/etcd-bench-client:latest ./client
docker push killoscully/etcd-bench-client:latest

docker build -t killoscully/etcd-encryption-sidecar:latest ./sidecar
docker push killoscully/etcd-encryption-sidecar:latest
```

---

## A3) Create namespace
```bash
kubectl apply -f k8s/base/namespace.yaml
```

---

## A4) Deploy base components
```bash
kubectl apply -f k8s/base/etcd.yaml
kubectl apply -f k8s/base/service.yaml
kubectl apply -f k8s/base/bench-client.yaml
```

Wait for readiness:
```bash
kubectl -n etcd-bench rollout status deploy -l app=bench-client --timeout=180s
```

---

## A5) Load benchmark configs
```bash
kubectl -n etcd-bench delete configmap bench-configs --ignore-not-found
kubectl -n etcd-bench create configmap bench-configs --from-file=benchmarks/configs/
kubectl -n etcd-bench rollout restart deploy -l app=bench-client
kubectl -n etcd-bench rollout status deploy -l app=bench-client --timeout=180s
```

---

## A6) Manual smoke test
```bash
POD=$(kubectl -n etcd-bench get pod -l app=bench-client -o jsonpath='{.items[0].metadata.name}')

kubectl -n etcd-bench exec "$POD" -- \
  python -m app.run_bench \
  --run-id T01-R01 \
  --config /bench/configs/w1_put_only.yaml \
  --config /bench/configs/payload_s.yaml \
  --config /bench/configs/c1.yaml
```

Expected: one JSON object printed to stdout.

---

## A7) Run full matrix
```bash
./benchmarks/scripts/run_matrix.sh
```

---

## A8) Validate output
```bash
wc -l benchmarks/results/run_results.csv
ls benchmarks/results/raw | grep client.json | wc -l
```
