# etcd Encryption Sidecar – Dissertation Experimental Platform

This repository contains the implementation of an encryption sidecar used to evaluate the performance impact of applying additional cryptographic protection to data stored in etcd.

The platform accompanies the MSc dissertation:

**“Performance Analysis of Sidecar-Based Encryption for etcd in Kubernetes Environments.”**

The system introduces an encryption layer between application workloads and the etcd datastore using the sidecar architectural pattern. A Python-based sidecar service performs encryption before data is written to etcd and decrypts data when it is retrieved.

The implementation is designed for **controlled experimental benchmarking** rather than production deployment.

---

## Research Motivation

In Kubernetes environments, etcd acts as the primary datastore for cluster state, configuration data, and secrets. While Kubernetes supports encryption at rest, this functionality typically relies on internal encryption mechanisms integrated within the control plane.

This research explores an alternative architectural approach: applying encryption externally through a **sidecar-based service**. The objective is to evaluate whether encryption can be introduced transparently without modifying etcd itself and to measure the resulting performance overhead.

---

## System Architecture

The experimental platform consists of three main components:

| Component | Description |
|-----------|-------------|
| Benchmark Client | Generates controlled read and write workload |
| Encryption Sidecar | Python service that encrypts data before storage and decrypts data during retrieval |
| etcd | Distributed key-value datastore used as the persistent storage layer |

Data flow:

```text
Benchmark Client → Encryption Sidecar → etcd