import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
OUTPUT_FILE = "results/summary_table.csv"
LATEST_FILES_TO_USE = 5


def get_latest_result_files(results_dir: Path, limit: int = 3) -> list[Path]:
    files = sorted(
        results_dir.glob("run_results_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(f"No run_results_*.csv files found in {results_dir}")

    return files[:limit]


def load_and_merge_results(files: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(file) for file in files]
    return pd.concat(frames, ignore_index=True)


def main():
    latest_files = get_latest_result_files(RESULTS_DIR, LATEST_FILES_TO_USE)

    print("Using result files:")
    for file in latest_files:
        print(f" - {file.name}")

    df = load_and_merge_results(latest_files)

    summary = (
        df.groupby(["encryption_mode", "payload_bytes", "concurrency"])
        .agg(
            throughput_mean=("throughput_ops_sec", "mean"),
            throughput_std=("throughput_ops_sec", "std"),
            write_p95_mean=("write_p95_ms", "mean"),
            write_p95_std=("write_p95_ms", "std"),
            read_p95_mean=("read_p95_ms", "mean"),
            read_p95_std=("read_p95_ms", "std"),
            cpu_avg_mean=("cpu_avg_pct", "mean"),
            cpu_avg_std=("cpu_avg_pct", "std"),
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
            "cpu_avg_mean",
        ]
    ].sort_values(["payload_kb", "concurrency", "encryption_mode"])

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)

    print("Summary table written to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()