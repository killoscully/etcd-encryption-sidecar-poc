# This script is responsible for running benchmark experiments for different encryption modes.
# It interacts with a Kubernetes cluster to configure and execute benchmarks, and stores the results in CSV and JSON formats.

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path

import yaml

# Define the columns that will be used in the CSV results file
CSV_COLUMNS = [
    "run_id",  # Unique identifier for each benchmark run
    "encryption_mode",  # The encryption mode used in the benchmark
    "payload_bytes",  # Size of the payload in bytes
    "iterations",  # Number of iterations for the benchmark
    "concurrency",  # Level of concurrency during the benchmark
    "total_operations",  # Total number of operations performed
    "throughput_ops_sec",  # Throughput in operations per second
    "wall_time_sec",  # Total wall time for the benchmark
    "write_ops",  # Number of write operations
    "write_avg_ms",  # Average write latency in milliseconds
    "write_p50_ms",  # 50th percentile write latency
    "write_p95_ms",  # 95th percentile write latency
    "write_p99_ms",  # 99th percentile write latency
    "write_error_rate_pct",  # Write error rate as a percentage
    "read_ops",  # Number of read operations
    "read_avg_ms",  # Average read latency in milliseconds
    "read_p50_ms",  # 50th percentile read latency
    "read_p95_ms",  # 95th percentile read latency
    "read_p99_ms",  # 99th percentile read latency
    "read_error_rate_pct",  # Read error rate as a percentage
]

# Helper function to execute shell commands and return their output
def sh(cmd, timeout=None):
    return subprocess.check_output(
        cmd,
        text=True,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    ).strip()

# Retrieve the name of the benchmark client pod in the specified namespace
def get_client_pod(namespace: str) -> str:
    return sh([
        "kubectl", "-n", namespace, "get", "pods",
        "-l", "app=bench-client",
        "-o", "jsonpath={.items[0].metadata.name}",
    ])

# Set the encryption mode for the Kubernetes deployment and wait for the rollout to complete
def set_encryption_mode(namespace: str, mode: str):
    sh([
        "kubectl", "-n", namespace, "set", "env", "deployment/encryption-sidecar",
        f"ENCRYPTION_TYPE={mode}",
    ])
    sh([
        "kubectl", "-n", namespace, "rollout", "status",
        "deployment/encryption-sidecar", "--timeout=180s",
    ], timeout=190)

# Execute a benchmark run inside the client pod and return the results as a dictionary
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

# Append a row of benchmark data to the CSV results file, creating the file if it doesn't exist
def append_csv(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})

# Extract concurrency levels from the experiment configuration
def get_concurrency_levels(experiment: dict) -> list[int]:
    if "concurrency_levels" in experiment:
        return [int(v) for v in experiment["concurrency_levels"]]
    if "concurrency" in experiment:
        return [int(experiment["concurrency"])]
    raise RuntimeError(
        f"experiment '{experiment.get('name', 'unknown')}' is missing concurrency configuration"
    )

# Extract the number of repetitions for an experiment from the configuration
def get_repetitions(experiment: dict) -> int:
    return int(experiment.get("repetitions", 1))

# Main function to orchestrate the benchmark experiments
def main():
    start_time = time.time()
    total_runs = 0

    # Parse command-line arguments for namespace, matrix file, and results directory
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="etcd-dissertation")
    parser.add_argument("--matrix", default="benchmark/config/benchmark_matrix.yaml")
    parser.add_argument("--results-dir", default="benchmark/results")
    args = parser.parse_args()

    # Load the benchmark matrix configuration from the specified YAML file
    matrix = yaml.safe_load(Path(args.matrix).read_text(encoding="utf-8"))
    experiments = matrix.get("experiments", [])
    if not experiments:
        raise RuntimeError("benchmark matrix is empty")

    # Prepare directories for storing results
    results_dir = Path(args.results_dir)
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "run_results.csv"

    # Retrieve the name of the client pod
    pod = get_client_pod(args.namespace)

    # Iterate through each experiment in the matrix
    for experiment in experiments:
        mode = experiment["encryption"]  # Encryption mode for the experiment
        iterations = int(experiment["iterations"])  # Number of iterations
        payload_sizes = [int(v) for v in experiment["payload_sizes"]]  # Payload sizes
        concurrency_levels = get_concurrency_levels(experiment)  # Concurrency levels
        repetitions = get_repetitions(experiment)  # Number of repetitions

        # Set the encryption mode in the Kubernetes deployment
        set_encryption_mode(args.namespace, mode)
        time.sleep(3)  # Wait for the deployment to stabilize

        # Execute benchmarks for each combination of parameters
        for payload_bytes in payload_sizes:
            for concurrency in concurrency_levels:
                for repetition in range(1, repetitions + 1):
                    run_id = (
                        f"{experiment['name']}-"
                        f"{payload_bytes}b-"
                        f"c{concurrency}-"
                        f"r{repetition}"
                    )

                    # Execute the benchmark and save the results
                    data = exec_bench(
                        args.namespace,
                        pod,
                        run_id,
                        payload_bytes,
                        iterations,
                        concurrency,
                        mode,
                    )

                    # Save raw results to a JSON file
                    (raw_dir / f"{run_id}.json").write_text(
                        json.dumps(data, indent=2),
                        encoding="utf-8",
                    )
                    # Append results to the CSV file
                    append_csv(csv_path, data)
                    print(f"completed {run_id}")
                    total_runs += 1

    # Calculate and display the total execution time
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"results written to {csv_path}")
    print(f"total experiment runs: {total_runs}")
    print(f"total execution time: {minutes} min {seconds} sec")

# Entry point of the script
if __name__ == "__main__":
    main()