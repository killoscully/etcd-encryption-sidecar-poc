# driver placeholder
import argparse
import csv
import json
import subprocess
import time
from pathlib import Path

import yaml  # pip install pyyaml


def sh(cmd: list[str], timeout: int | None = None) -> str:
    """Run a shell command and return stdout. Raises on non-zero exit."""
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()


def get_client_pod(namespace: str) -> str:
    pod = sh([
        "kubectl", "-n", namespace, "get", "pods",
        "-l", "app=bench-client",
        "-o", "jsonpath={.items[0].metadata.name}"
    ])
    if not pod:
        raise RuntimeError("No bench-client pod found (label app=bench-client).")
    return pod


def exec_bench(namespace: str, pod: str, run_id: str, config_paths: list[str]) -> dict:
    # IMPORTANT: stdout must be JSON only.
    cmd = ["kubectl", "-n", namespace, "exec", pod, "--",
           "python", "-m", "app.run_bench", "--run-id", run_id]
    for p in config_paths:
        cmd += ["--config", p]

    out = sh(cmd, timeout=60 * 10)  # 10 min guard; adjust later if needed
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Client did not return valid JSON. Output was:\n{out}") from e


CSV_HEADER = [
    "run_id", "test_id", "encryption_mode",
    "payload_bytes", "workload_mix", "concurrency", "duration_seconds",
    "ops_total", "ops_per_sec",
    "lat_avg_ms", "lat_p50_ms", "lat_p95_ms", "lat_p99_ms",
    "error_rate_pct",
    "notes"
]


def append_csv(csv_path: Path, row: dict) -> None:
    exists = csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not exists:
            w.writeheader()
        # Keep only the columns we define; anything missing becomes blank.
        w.writerow({k: row.get(k, "") for k in CSV_HEADER})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--results-dir", required=True)
    args = ap.parse_args()

    namespace = args.namespace
    matrix_path = Path(args.matrix)
    results_dir = Path(args.results_dir)
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Load matrix
    matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    repeats = int(matrix.get("repeats", 1))
    tests = matrix.get("tests", [])
    if not tests:
        raise RuntimeError(f"No tests found in {matrix_path}")

    # Ensure bench-client exists
    pod = get_client_pod(namespace)
    print(f"[bench] using pod: {pod}")

    csv_path = results_dir / "run_results.csv"

    # Execute tests
    for t in tests:
        test_id = t["test_id"]
        # overlay is ignored for now (Option A without overlays)
        workload = t["workload"]
        payload = t["payload"]
        concurrency = t["concurrency"]

        # These paths must exist INSIDE the pod via the ConfigMap mount
        config_paths = [
            f"/bench/configs/{workload}",
            f"/bench/configs/{payload}",
            f"/bench/configs/{concurrency}",
        ]

        for r in range(1, repeats + 1):
            run_id = f"{test_id}-R{r:02d}"
            print(f"[bench] run={run_id} configs={workload},{payload},{concurrency}")

            # Execute benchmark in the pod
            start = time.time()
            data = exec_bench(namespace, pod, run_id, config_paths)
            elapsed = time.time() - start

            # Persist raw JSON
            (raw_dir / f"{run_id}-client.json").write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )

            # Append CSV
            row = dict(data)
            row["notes"] = f"ok (wall={elapsed:.1f}s)"
            append_csv(csv_path, row)

    print(f"[bench] wrote: {csv_path}")


if __name__ == "__main__":
    main()
