# This script generates plots based on the aggregated summary table.
# It uses pandas for data manipulation and matplotlib for plotting.

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.lines import Line2D

plt.style.use("seaborn-v0_8-whitegrid")

COLORS = {
    "NATIVE": "#000000",
    "PLAINTEXT": "#2c7bb6",
    "AES_GCM": "#888888",
    "AES_CBC": "#66bd63",
    "HYBRID_AES_GCM_RSA": "#fdae61",
    "RSA": "#d7191c",
}

MODE_ORDER = [
    "NATIVE",
    "PLAINTEXT",
    "AES_GCM",
    "AES_CBC",
    "RSA",
    "HYBRID_AES_GCM_RSA",
]

RESULTS_FILE = "results/summary_table.csv"
OUTPUT_DIR = Path("results/plots")


def load_data():
    return pd.read_csv(RESULTS_FILE)


def plot_throughput(agg: pd.DataFrame):
    for payload in sorted(agg.payload_kb.unique()):
        subset = agg[agg.payload_kb == payload]

        plt.figure(figsize=(8, 5))

        for mode in MODE_ORDER:
            if mode not in subset.encryption_mode.unique():
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency")

            plt.plot(
                data["concurrency"],
                data["throughput_mean"],
                label=mode,
                marker="o",
                color=COLORS.get(mode),
                linewidth=2,
                markersize=6,
            )

        plt.xlabel("Concurrency")
        plt.ylabel("Throughput (ops/sec)")
        plt.title(f"Throughput vs Concurrency (Payload {payload} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"throughput_{payload}kb.png", dpi=72)
        plt.close()


def plot_read_latency(agg: pd.DataFrame):
    for payload in sorted(agg.payload_kb.unique()):
        subset = agg[agg.payload_kb == payload]

        plt.figure(figsize=(8, 5))

        for mode in MODE_ORDER:
            if mode not in subset.encryption_mode.unique():
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency")

            plt.plot(
                data["concurrency"],
                data["read_p95_mean"],
                label=mode,
                marker="o",
                color=COLORS.get(mode),
                linewidth=2,
                markersize=6,
            )

        plt.xlabel("Concurrency")
        plt.ylabel("Read P95 Latency (ms)")
        plt.title(f"Read Latency vs Concurrency (Payload {payload} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"read_latency_{payload}kb.png", dpi=72)
        plt.close()


def plot_write_latency(agg: pd.DataFrame):
    for payload in sorted(agg.payload_kb.unique()):
        subset = agg[agg.payload_kb == payload]

        plt.figure(figsize=(8, 5))

        for mode in MODE_ORDER:
            if mode not in subset.encryption_mode.unique():
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency")

            plt.plot(
                data["concurrency"],
                data["write_p95_mean"],
                label=mode,
                marker="o",
                color=COLORS.get(mode),
                linewidth=2,
                markersize=6,
            )

        plt.xlabel("Concurrency")
        plt.ylabel("Write P95 Latency (ms)")
        plt.title(f"Write Latency vs Concurrency (Payload {payload} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"write_latency_{payload}kb.png", dpi=72)
        plt.close()


def plot_write_latency_overhead_vs_plaintext(agg: pd.DataFrame):
    for payload in sorted(agg.payload_kb.unique()):
        subset = agg[agg.payload_kb == payload].copy()

        baseline = (
            subset[subset.encryption_mode == "PLAINTEXT"]
            .set_index("concurrency")["write_p95_mean"]
        )

        plt.figure(figsize=(8, 5))

        for mode in MODE_ORDER:
            if mode not in subset.encryption_mode.unique():
                continue
            if mode == "PLAINTEXT":
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency").copy()
            data["baseline"] = data["concurrency"].map(baseline)
            data = data.dropna(subset=["baseline"])

            if data.empty:
                continue

            data["overhead_pct"] = (
                (data["write_p95_mean"] - data["baseline"]) / data["baseline"]
            ) * 100

            plt.plot(
                data["concurrency"],
                data["overhead_pct"],
                label=mode,
                marker="o",
                color=COLORS.get(mode),
                linewidth=2,
                markersize=6,
            )

        plt.xlabel("Concurrency")
        plt.ylabel("Write P95 Overhead (%)")
        plt.title(f"Write Latency Overhead vs PLAINTEXT (Payload {payload} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"write_overhead_vs_plaintext_{payload}kb.png", dpi=72)
        plt.close()


def plot_write_latency_overhead_vs_native(agg: pd.DataFrame):
    for payload in sorted(agg.payload_kb.unique()):
        subset = agg[agg.payload_kb == payload].copy()

        baseline = (
            subset[subset.encryption_mode == "NATIVE"]
            .set_index("concurrency")["write_p95_mean"]
        )

        plt.figure(figsize=(8, 5))

        for mode in MODE_ORDER:
            if mode not in subset.encryption_mode.unique():
                continue
            if mode == "NATIVE":
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency").copy()
            data["baseline"] = data["concurrency"].map(baseline)
            data = data.dropna(subset=["baseline"])

            if data.empty:
                continue

            data["overhead_pct"] = (
                (data["write_p95_mean"] - data["baseline"]) / data["baseline"]
            ) * 100

            plt.plot(
                data["concurrency"],
                data["overhead_pct"],
                label=mode,
                marker="o",
                color=COLORS.get(mode),
                linewidth=2,
                markersize=6,
            )

        plt.xlabel("Concurrency")
        plt.ylabel("Write P95 Overhead (%)")
        plt.title(f"Write Latency Overhead vs NATIVE (Payload {payload} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"write_overhead_vs_native_{payload}kb.png", dpi=72)
        plt.close()


def plot_cpu_utilisation(agg: pd.DataFrame):
    for payload in sorted(agg.payload_kb.unique()):
        subset = agg[agg.payload_kb == payload]

        plt.figure(figsize=(8, 5))

        for mode in MODE_ORDER:
            if mode not in subset.encryption_mode.unique():
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency")

            plt.plot(
                data["concurrency"],
                data["cpu_avg_mean"],
                label=mode,
                marker="o",
                color=COLORS.get(mode),
                linewidth=2,
                markersize=6,
            )

        plt.xlabel("Concurrency")
        plt.ylabel("Average CPU Utilisation (%)")
        plt.title(f"CPU Utilisation vs Concurrency (Payload {payload} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"cpu_utilisation_{payload}kb.png", dpi=72)
        plt.close()


def _legend_elements():
    return [
        Line2D([0], [0], color="none", label="Baselines / Modes"),
        Line2D([0], [0], color="#000000", lw=2, label="NATIVE"),
        Line2D([0], [0], color="#2c7bb6", lw=2, label="PLAINTEXT"),
        Line2D([0], [0], color="#888888", lw=2, label="AES-GCM"),
        Line2D([0], [0], color="#66bd63", lw=2, label="AES-CBC"),
        Line2D([0], [0], color="#d7191c", lw=2, label="RSA"),
        Line2D([0], [0], color="#fdae61", lw=2, label="HYBRID"),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label="Payload Size"),
        Line2D([0], [0], color="#888888", linestyle="-", lw=2, label="1 KB"),
        Line2D([0], [0], color="#888888", linestyle="--", lw=2, label="10 KB"),
        Line2D([0], [0], color="#888888", linestyle=":", lw=2, label="100 KB"),
    ]


def plot_all_in_one(agg: pd.DataFrame, value_col: str, ylabel: str, title: str, filename: str, legend_loc="best"):
    plt.figure(figsize=(10, 6))

    payload_styles = {
        1: {"linestyle": "-", "marker": "o"},
        10: {"linestyle": "--", "marker": "o"},
        100: {"linestyle": ":", "marker": "o"},
    }

    for mode in MODE_ORDER:
        if mode not in agg["encryption_mode"].unique():
            continue

        for payload in sorted(agg["payload_kb"].unique()):
            data = agg[
                (agg["encryption_mode"] == mode) &
                (agg["payload_kb"] == payload)
            ].sort_values("concurrency")

            if data.empty:
                continue

            style = payload_styles.get(payload, {"linestyle": "-", "marker": "o"})

            plt.plot(
                data["concurrency"],
                data[value_col],
                color=COLORS.get(mode),
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=2,
                markersize=5,
            )

    plt.xlabel("Concurrency")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    legend = plt.legend(
        handles=_legend_elements(),
        loc=legend_loc,
        fontsize=8,
        framealpha=0.9,
    )

    for text in legend.get_texts():
        if text.get_text() in ["Baselines / Modes", "Payload Size"]:
            text.set_weight("bold")
            text.set_ha("left")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_DIR / filename, dpi=72)
    plt.close()


def main():
    agg = load_data()

    plot_throughput(agg)
    plot_read_latency(agg)
    plot_write_latency(agg)
    plot_write_latency_overhead_vs_plaintext(agg)
    plot_write_latency_overhead_vs_native(agg)
    plot_cpu_utilisation(agg)

    plot_all_in_one(
        agg,
        "throughput_mean",
        "Throughput (QPS)",
        "Throughput vs Concurrency (All Payloads)",
        "throughput_all_in_one.png",
    )
    plot_all_in_one(
        agg,
        "read_p95_mean",
        "Read P95 Latency (ms)",
        "Read Latency vs Concurrency (All Payloads)",
        "read_latency_all_in_one.png",
        legend_loc="upper left",
    )
    plot_all_in_one(
        agg,
        "write_p95_mean",
        "Write P95 Latency (ms)",
        "Write Latency vs Concurrency (All Payloads)",
        "write_latency_all_in_one.png",
        legend_loc="upper left",
    )
    plot_all_in_one(
        agg,
        "cpu_avg_mean",
        "Average CPU Utilisation (%)",
        "CPU Utilisation vs Concurrency (All Payloads)",
        "cpu_utilisation_all_in_one.png",
        legend_loc="center left",
    )

    print("Plots saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()