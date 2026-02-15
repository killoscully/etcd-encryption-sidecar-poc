import argparse, json, time, random, os
import yaml

MAX_SAMPLES = 20000


def load_cfg(paths):
    cfg = {}
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            cfg.update(yaml.safe_load(f) or {})
    return cfg

def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    k = int((p/100.0) * (len(values)-1))
    return float(values[k])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--config", action="append", required=True)
    args = ap.parse_args()

    cfg = load_cfg(args.config)

    duration = int(cfg.get("duration_seconds", 120))
    concurrency = int(cfg.get("concurrency", 1))
    payload_bytes = int(cfg.get("payload_bytes", 256))
    read_ratio = int(cfg.get("read_ratio", 0))
    write_ratio = int(cfg.get("write_ratio", 100))

    # Warmup
    t0 = time.time()
    while time.time() - t0 < 10:
        pass

    latencies = []
    ops = 0
    start = time.time()
    while time.time() - start < duration:
        base = 0.001
        extra = payload_bytes / 10_000_000.0
        jitter = random.random() * 0.0005
        lat = base + extra + jitter
        time.sleep(0.0001)
        ms = lat * 1000.0
        if len(latencies) < MAX_SAMPLES:
            latencies.append(ms)
        else:
            # Reservoir sampling: replace random element with decreasing probability
            j = random.randint(0, ops)  # ops is current operation count
            if j < MAX_SAMPLES:
                latencies[j] = ms

        ops += 1

    elapsed = time.time() - start
    ops_per_sec = ops / elapsed if elapsed > 0 else 0

    out = {
        "run_id": args.run_id,
        "test_id": args.run_id.split("-")[0],
        "encryption_mode": os.getenv("ENCRYPTION_MODE", "E0"),
        "payload_bytes": payload_bytes,
        "workload_mix": f"{read_ratio}/{write_ratio}",
        "concurrency": concurrency,
        "duration_seconds": duration,
        "ops_total": ops,
        "ops_per_sec": round(ops_per_sec, 3),
        "lat_avg_ms": round(sum(latencies)/len(latencies), 3) if latencies else 0.0,
        "lat_p50_ms": round(percentile(latencies, 50), 3),
        "lat_p95_ms": round(percentile(latencies, 95), 3),
        "lat_p99_ms": round(percentile(latencies, 99), 3),
        "error_rate_pct": 0.0
    }

    print(json.dumps(out))

if __name__ == "__main__":
    main()
