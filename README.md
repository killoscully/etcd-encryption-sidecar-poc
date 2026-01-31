# etcd Sidecar Encryption PoC (Kubernetes)

## Overview

This repository contains a **proof of concept (PoC)** implementation of a
**sidecar-based encryption system for etcd** running in **self-managed Kubernetes environments**.

The project is developed as part of an academic research study and follows a
**quantitative and experimental methodology** to evaluate the **performance impact**
and **security properties** of applying encryption using the **Kubernetes sidecar pattern**,
rather than relying exclusively on etcd’s native encryption mechanisms.

---

## Research Context

The primary research objectives of this project are to:

- Validate the feasibility of the **sidecar pattern** for encrypting data before persistence in etcd
- Measure the **latency, throughput, and resource overhead** introduced by sidecar-based encryption
- Compare multiple **encryption algorithms** under identical workload conditions
- Provide comparative insights against **etcd native encryption**

The application container is intentionally kept **unchanged**.
All cryptographic operations are transparently handled by the sidecar container.

---

## Architecture Overview

This system implements a **true sidecar architecture**, where encryption and decryption
are handled by a dedicated container colocated with the application container
inside the same Kubernetes Pod.

### Pod-Level Architecture

**Single Pod (Client Deployment)**

- **Application container**
  - Generates requests (benchmark or workload)
  - Communicates with the sidecar over `http://127.0.0.1:5000`

- **Encryption sidecar container**
  - Encrypts values on PUT
  - Decrypts values on GET
  - Communicates with etcd via the Kubernetes Service endpoint

### Data Path

```
Application → localhost:5000 (sidecar) → etcd Service → etcd Pod
```

> A Kubernetes Service for the sidecar is **not required** for the sidecar pattern.
> Services are created only for debugging or experimental inspection.

---

## Supported Encryption Modes

The sidecar supports multiple encryption modes, selectable at runtime
using the `ENCRYPTION_TYPE` environment variable.

| Encryption Type        | Category              | Security Properties                         |
|------------------------|-----------------------|---------------------------------------------|
| AES_GCM                | Symmetric (AEAD)      | Confidentiality + Integrity                 |
| CHACHA20_POLY1305      | Symmetric (AEAD)      | Confidentiality + Integrity                 |
| AES_CBC_HMAC           | Symmetric             | Confidentiality + Integrity (EtM)           |
| FERNET                 | Symmetric (High-level)| Authenticated encryption                    |
| JWT_SIGNED             | Token-based           | Integrity / Authentication only             |
| JWT_ENCRYPTED          | Token-based           | Confidentiality + Integrity (JWE)           |

**Note:**  
AES-CBC is implemented using an **encrypt-then-MAC** construction
(AES-CBC + HMAC-SHA256) to ensure message integrity.

---

## Multi-Client Experimental Setup

The system supports running **multiple client Pods concurrently**,
each configured with a **different encryption algorithm**.

Each client deployment:
- Runs its own encryption sidecar
- Uses a dedicated Kubernetes Service
- Writes to a unique key prefix in etcd

This design enables **side-by-side experimental comparison**
of encryption algorithms under identical cluster conditions.

---

## Verifying Encryption in etcd

Encryption at rest is verified by comparing:

1. Data returned via the sidecar API (plaintext)
2. Data stored directly in etcd using `etcdctl` (ciphertext)

### Example Encrypted Value Stored in etcd

```json
{"v":1,"alg":"AES_GCM","data":{"nonce":"...","ct":"..."}}
```

The plaintext value does **not** appear in etcd, confirming that encryption
is applied before persistence.

Integrity protection is verified by tamper testing, where modified ciphertext
fails to decrypt.

---

## Deployment and Functional Testing

### One-Command Deployment

```bash
bash deploy-poc.sh
```

The script:
1. Deploys etcd
2. Deploys multiple client Pods (one per encryption type)
3. Executes PUT/GET validation from the application containers

### Manual Test (Inside the Cluster)

```bash
kubectl exec -n etcd-poc deploy/etcd-client-aesgcm -c app --   curl -s -X POST http://127.0.0.1:5000/put   -H "Content-Type: application/json"   -d '{"key":"aesgcm/test","value":"top-secret-data"}'
```

```bash
kubectl exec -n etcd-poc deploy/etcd-client-aesgcm -c app --   curl -s "http://127.0.0.1:5000/get?key=aesgcm/test"
```

---

## Benchmarking (In Progress)

The benchmarking phase evaluates the performance impact of sidecar-based encryption.

### Metrics

- Read latency
- Write latency
- Throughput
- CPU utilization
- Memory usage

### Comparison Baselines

- No encryption
- Sidecar encryption (multiple algorithms)
- etcd native encryption

All experiments are executed under identical infrastructure and workload conditions.

---

## Non-Goals

This project does **not** aim to:

- Provide a key management system (KMS)
- Replace etcd native encryption
- Implement authentication or authorization
- Serve as a production-ready security solution

---

## License

See the LICENSE file for details.
