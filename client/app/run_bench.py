import argparse
import json
import random
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from statistics import mean
from urllib import parse, request as urlrequest

MAX_SAMPLES = 20000


@dataclass
class OperationResult:
    operation: str
    ok: bool
    latency_ms: float


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    k = int((p / 100.0) * (len(ordered) - 1))
    return float(ordered[k])


def http_json(method: str, url: str, payload=None, timeout: float = 15.0):
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=body, headers=headers, method=method)
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def make_payload(payload_bytes: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(payload_bytes))


def run_pair(base_url: str, key: str, value: str, timeout: float) -> list[OperationResult]:
    results = []
    started = time.perf_counter()
    try:
        data = http_json("POST", f"{base_url}/put", {"key": key, "value": value}, timeout=timeout)
        ok = data.get("result") == "ok"
    except Exception:
        ok = False
    results.append(OperationResult("write", ok, (time.perf_counter() - started) * 1000.0))

    started = time.perf_counter()
    try:
        encoded_key = parse.quote(key, safe="")
        data = http_json("GET", f"{base_url}/get?key={encoded_key}", timeout=timeout)
        ok = data.get("found") is True and data.get("value") == value
    except Exception:
        ok = False
    results.append(OperationResult("read", ok, (time.perf_counter() - started) * 1000.0))
    return results


def summarize(operation_name: str, samples):
    latencies = [sample.latency_ms for sample in samples][:MAX_SAMPLES]
    total = len(samples)
    errors = sum(1 for sample in samples if not sample.ok)
    return {
        f"{operation_name}_ops": total,
        f"{operation_name}_avg_ms": round(mean(latencies), 3) if latencies else 0.0,
        f"{operation_name}_p50_ms": round(percentile(latencies, 50), 3),
        f"{operation_name}_p95_ms": round(percentile(latencies, 95), 3),
        f"{operation_name}_p99_ms": round(percentile(latencies, 99), 3),
        f"{operation_name}_error_rate_pct": round((errors / total) * 100.0, 3) if total else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--payload-bytes", required=True, type=int)
    parser.add_argument("--iterations", required=True, type=int)
    parser.add_argument("--concurrency", required=True, type=int)
    parser.add_argument("--encryption-mode", required=True)
    parser.add_argument("--base-url", default="http://sidecar:5000")
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    payload = make_payload(args.payload_bytes)
    key_prefix = f"bench/{args.run_id}"
    futures = []
    write_samples = []
    read_samples = []

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(args.concurrency, 1)) as executor:
        for index in range(args.iterations):
            key = f"{key_prefix}/{index}"
            futures.append(executor.submit(run_pair, args.base_url.rstrip('/'), key, payload, args.timeout_seconds))

        for future in as_completed(futures, timeout=max(args.iterations, 1) * args.timeout_seconds * 2):
            for result in future.result():
                if result.operation == "write":
                    write_samples.append(result)
                else:
                    read_samples.append(result)

    elapsed = time.perf_counter() - started
    total_operations = len(write_samples) + len(read_samples)
    output = {
        "run_id": args.run_id,
        "encryption_mode": args.encryption_mode,
        "payload_bytes": args.payload_bytes,
        "iterations": args.iterations,
        "concurrency": args.concurrency,
        "total_operations": total_operations,
        "throughput_ops_sec": round(total_operations / elapsed, 3) if elapsed > 0 else 0.0,
        "wall_time_sec": round(elapsed, 3),
    }
    output.update(summarize("write", write_samples))
    output.update(summarize("read", read_samples))
    print(json.dumps(output))


if __name__ == "__main__":
    main()
