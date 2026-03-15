import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

RESULTS_FILE = "benchmark/results/run_results.csv"
OUTPUT_DIR = Path("benchmark/results/plots")


def main():
    df = pd.read_csv(RESULTS_FILE)

    summary = (
        df.groupby(["encryption_mode", "payload_bytes", "concurrency"])
        .agg(
            write_p95_mean=("write_p95_ms", "mean"),
        )
        .reset_index()
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for payload in sorted(summary["payload_bytes"].unique()):
        subset = summary[summary["payload_bytes"] == payload].copy()
        payload_kb = payload // 1024

        pivot = subset.pivot(
            index="encryption_mode",
            columns="concurrency",
            values="write_p95_mean",
        )

        plt.figure(figsize=(8, 4))
        plt.imshow(pivot.values, aspect="auto")
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                value = pivot.values[i, j]
                plt.text(
                    j,
                    i,
                    f"{value:.0f}",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=9
                )

        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)

        plt.xlabel("Concurrency")
        plt.ylabel("Encryption Mode")
        plt.title(f"Write P95 Latency Heatmap (Payload {payload_kb} KB)")
        plt.colorbar(label="Write P95 Latency (ms)")
        plt.tight_layout()

        plt.savefig(OUTPUT_DIR / f"write_latency_heatmap_{payload_kb}kb.png", dpi=300)
        plt.close()

    print(f"Heatmaps saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()