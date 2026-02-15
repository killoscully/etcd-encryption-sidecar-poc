# Runbook B — Narrative + Explanation (Option A)

## Purpose
Explain how and why the Option A benchmark execution model works, for debugging and thesis defense.

---

## Overview
Option A uses a single long-running benchmark client pod. Each test run is triggered using `kubectl exec`,
which ensures deterministic timing and minimal orchestration overhead.

---

## Benchmark lifecycle
1. Apply Kubernetes overlay (E0–E3)
2. Wait for deployments to stabilize
3. Execute benchmark client via `kubectl exec`
4. Client performs warmup and timed run
5. Client prints final metrics as JSON
6. Runner stores JSON and appends CSV row

---

## Why a sleeping client pod
The client pod runs `sleep infinity` so it is always available. This avoids startup noise and
ensures measurements only capture benchmark execution time.

---

## Why stdout must be pure JSON
The runner parses stdout directly. Any log output mixed with JSON will corrupt results.
All logs must go to stderr.

---

## Role of overlays
Each overlay represents a security mode:
- E0: plaintext
- E1: native etcd encryption
- E2: sidecar AES-GCM
- E3: sidecar hybrid encryption

Overlays modify infrastructure only; benchmark logic never changes.

---

## Configuration management
All workload parameters are defined in external YAML files mounted into the client pod.
This guarantees reproducibility and auditability.

---

## Data integrity rules
- Fixed duration per run
- Fixed payload sizes
- Fixed concurrency levels
- At least 5 repeats per test
- Restart deployments when switching overlays

---

## When to change execution model
Move to Kubernetes Jobs only if strict per-run isolation or parallel execution is required.
For a PoC and thesis work, Option A is sufficient and defensible.
