import pandas as pd
from pathlib import Path

RESULTS_FILE = "benchmark/results/run_results.csv"
OUTPUT_FILE = "benchmark/results/summary_table.csv"


def main():
    df = pd.read_csv(RESULTS_FILE)

    summary = (
        df.groupby(["encryption_mode", "payload_bytes", "concurrency"])
        .agg(
            throughput_mean=("throughput_ops_sec", "mean"),
            throughput_std=("throughput_ops_sec", "std"),
            write_p95_mean=("write_p95_ms", "mean"),
            write_p95_std=("write_p95_ms", "std"),
            read_p95_mean=("read_p95_ms", "mean"),
            read_p95_std=("read_p95_ms", "std"),
        )
        .reset_index()
    )

    summary["payload_kb"] = summary["payload_bytes"] // 1024

    summary = summary[
        [
            "encryption_mode",
            "payload_kb",
            "concurrency",
            "throughput_mean",
            "write_p95_mean",
            "read_p95_mean",
        ]
    ]

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)

    print("Summary table written to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()