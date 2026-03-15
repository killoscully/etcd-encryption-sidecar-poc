import argparse
import csv
import json
import subprocess
import time
from pathlib import Path

import yaml

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
]


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
    raise RuntimeError(
        f"experiment '{experiment.get('name', 'unknown')}' is missing concurrency configuration"
    )


def get_repetitions(experiment: dict) -> int:
    return int(experiment.get("repetitions", 1))


def main():
    start_time = time.time()
    total_runs = 0

    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="etcd-dissertation")
    parser.add_argument("--matrix", default="benchmark/config/benchmark_matrix.yaml")
    parser.add_argument("--results-dir", default="benchmark/results")
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

                    data = exec_bench(
                        args.namespace,
                        pod,
                        run_id,
                        payload_bytes,
                        iterations,
                        concurrency,
                        mode,
                    )

                    (raw_dir / f"{run_id}.json").write_text(
                        json.dumps(data, indent=2),
                        encoding="utf-8",
                    )
                    append_csv(csv_path, data)
                    print(f"completed {run_id}")
                    total_runs += 1

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"results written to {csv_path}")
    print(f"total experiment runs: {total_runs}")
    print(f"total execution time: {minutes} min {seconds} sec")


if __name__ == "__main__":
    main()