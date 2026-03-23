# This script is responsible for running benchmark experiments for different encryption modes.
# It interacts with a Kubernetes cluster to configure and execute benchmarks, and stores the results in CSV and JSON formats.

import argparse
import csv
import json
import subprocess
import time
import threading
from pathlib import Path

import yaml

# ================================
# CPU MONITOR
# ================================
class CPUMonitor:
    def __init__(self, container_name: str):
        self.container = container_name
        self.values = []
        self.running = False

    def _get_cpu(self):
        try:
            result = subprocess.run(
                ["docker", "stats", self.container, "--no-stream", "--format", "{{.CPUPerc}}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                print(f"[WARN] docker stats failed for container '{self.container}': {result.stderr.strip()}")
                return 0.0

            value = result.stdout.strip().replace('%', '')
            if not value:
                print(f"[WARN] no CPU value returned for container '{self.container}'")
                return 0.0

            return float(value)

        except Exception as exc:
            print(f"[WARN] failed to read CPU for container '{self.container}': {exc}")
            return 0.0

    def _collect(self):
        while self.running:
            cpu = self._get_cpu()
            self.values.append(cpu)
            time.sleep(1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._collect)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def average(self):
        return sum(self.values) / len(self.values) if self.values else 0.0

    def peak(self):
        return max(self.values) if self.values else 0.0


# ================================
# CSV COLUMNS
# ================================
CSV_COLUMNS = [
    "run_id",
    "encryption_mode",
    "payload_bytes",
    "iterations",
    "concurrency",
    "total_operations",
    "throughput_ops_sec",
    "wall_time_sec",
    "write_ops",
    "write_avg_ms",
    "write_p50_ms",
    "write_p95_ms",
    "write_p99_ms",
    "write_error_rate_pct",
    "read_ops",
    "read_avg_ms",
    "read_p50_ms",
    "read_p95_ms",
    "read_p99_ms",
    "read_error_rate_pct",
    # NEW CPU METRICS
    "cpu_avg_pct",
    "cpu_peak_pct",
]

# ================================
# HELPERS
# ================================
def sh(cmd, timeout=None):
    return subprocess.check_output(
        cmd,
        text=True,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    ).strip()

def get_client_pod(namespace: str) -> str:
    return sh([
        "kubectl", "-n", namespace, "get", "pods",
        "-l", "app=bench-client",
        "-o", "jsonpath={.items[0].metadata.name}",
    ])

def set_encryption_mode(namespace: str, mode: str):
    sh([
        "kubectl", "-n", namespace, "set", "env", "deployment/encryption-sidecar",
        f"ENCRYPTION_TYPE={mode}",
    ])
    sh([
        "kubectl", "-n", namespace, "rollout", "status",
        "deployment/encryption-sidecar", "--timeout=180s",
    ], timeout=190)

def exec_bench(
    namespace: str,
    pod: str,
    run_id: str,
    payload_bytes: int,
    iterations: int,
    concurrency: int,
    encryption_mode: str,
):
    cmd = [
        "kubectl", "-n", namespace, "exec", pod, "--",
        "python", "-m", "app.run_bench",
        "--run-id", run_id,
        "--payload-bytes", str(payload_bytes),
        "--iterations", str(iterations),
        "--concurrency", str(concurrency),
        "--encryption-mode", encryption_mode,
        "--base-url", "http://sidecar:5000",
    ]
    out = sh(cmd, timeout=1800)
    return json.loads(out)

def append_csv(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})

def get_concurrency_levels(experiment: dict) -> list[int]:
    if "concurrency_levels" in experiment:
        return [int(v) for v in experiment["concurrency_levels"]]
    if "concurrency" in experiment:
        return [int(experiment["concurrency"])]
    raise RuntimeError("missing concurrency configuration")

def get_repetitions(experiment: dict) -> int:
    return int(experiment.get("repetitions", 1))


def get_sidecar_container_name(namespace: str) -> str:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
    )

    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    candidates = [
        name for name in names
        if name.startswith("k8s_encryption-sidecar_") and f"_{namespace}_" in name
    ]

    if not candidates:
        raise RuntimeError(
            f"no running encryption-sidecar container found for namespace '{namespace}'"
        )

    if len(candidates) > 1:
        # Keep deterministic behaviour
        candidates.sort()

    return candidates[0]

# ================================
# MAIN
# ================================
def main():
    start_time = time.time()
    total_runs = 0

    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="etcd-dissertation")
    parser.add_argument("--matrix", default="benchmark/config/benchmark_matrix.yaml")
    parser.add_argument("--results-dir", default="benchmark/results")
    parser.add_argument("--sidecar-container", default="encryption-sidecar")  # NEW
    args = parser.parse_args()

    matrix = yaml.safe_load(Path(args.matrix).read_text(encoding="utf-8"))
    experiments = matrix.get("experiments", [])
    if not experiments:
        raise RuntimeError("benchmark matrix is empty")

    results_dir = Path(args.results_dir)
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "run_results.csv"

    pod = get_client_pod(args.namespace)

    for experiment in experiments:
        mode = experiment["encryption"]
        iterations = int(experiment["iterations"])
        payload_sizes = [int(v) for v in experiment["payload_sizes"]]
        concurrency_levels = get_concurrency_levels(experiment)
        repetitions = get_repetitions(experiment)

        set_encryption_mode(args.namespace, mode)
        time.sleep(3)

        for payload_bytes in payload_sizes:
            for concurrency in concurrency_levels:
                for repetition in range(1, repetitions + 1):

                    run_id = (
                        f"{experiment['name']}-"
                        f"{payload_bytes}b-"
                        f"c{concurrency}-"
                        f"r{repetition}"
                    )

                    # ================================
                    # START CPU MONITOR
                    # ================================
                    sidecar_container_name = get_sidecar_container_name(args.namespace)
                    # print(f"monitoring sidecar container: {sidecar_container_name}")
                    cpu_monitor = CPUMonitor(sidecar_container_name)
                    cpu_monitor.start()

                    # Run benchmark
                    data = exec_bench(
                        args.namespace,
                        pod,
                        run_id,
                        payload_bytes,
                        iterations,
                        concurrency,
                        mode,
                    )

                    # ================================
                    # STOP CPU MONITOR
                    # ================================
                    cpu_monitor.stop()

                    # Add CPU metrics
                    data["cpu_avg_pct"] = round(cpu_monitor.average(), 2)
                    data["cpu_peak_pct"] = round(cpu_monitor.peak(), 2)

                    # Save JSON
                    (raw_dir / f"{run_id}.json").write_text(
                        json.dumps(data, indent=2),
                        encoding="utf-8",
                    )

                    # Save CSV
                    append_csv(csv_path, data)

                    print(f"completed {run_id} | CPU avg: {data['cpu_avg_pct']}%")

                    total_runs += 1

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"results written to {csv_path}")
    print(f"total experiment runs: {total_runs}")
    print(f"total execution time: {minutes} min {seconds} sec")


if __name__ == "__main__":
    main()