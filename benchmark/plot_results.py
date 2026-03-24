# This script generates various plots based on benchmark results.
# It uses pandas for data manipulation and matplotlib for plotting.

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.lines import Line2D

# Set the style for the plots
plt.style.use("seaborn-v0_8-whitegrid")

# Define colors for different encryption modes
COLORS = {
    "PLAINTEXT": "#2c7bb6",
    "AES_GCM": "#888888",
    "AES_CBC": "#66bd63",
    "HYBRID_AES_GCM_RSA": "#fdae61",
    "RSA": "#d7191c",
}

# File paths for input data and output plots
RESULTS_FILE = "benchmark/results/run_results.csv"
OUTPUT_DIR = Path("benchmark/results/plots")


# Function to load benchmark data from a CSV file
def load_data():
    return pd.read_csv(RESULTS_FILE)


# Function to aggregate benchmark results
def aggregate_results(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["encryption_mode", "payload_bytes", "concurrency"])
        .agg(
            throughput_mean=("throughput_ops_sec", "mean"),
            read_p95_mean=("read_p95_ms", "mean"),
            write_p95_mean=("write_p95_ms", "mean"),
            cpu_avg_mean=("cpu_avg_pct", "mean"),
            cpu_peak_mean=("cpu_peak_pct", "mean"),
        )
        .reset_index()
    )


# Function to plot throughput vs concurrency
def plot_throughput(agg: pd.DataFrame):
    for payload in sorted(agg.payload_bytes.unique()):
        subset = agg[agg.payload_bytes == payload]
        payload_kb = payload // 1024

        plt.figure(figsize=(8, 5))

        for mode in sorted(subset.encryption_mode.unique()):
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
        plt.title(f"Throughput vs Concurrency (Payload {payload_kb} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Encryption Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"throughput_{payload_kb}kb.png", dpi=72)
        plt.close()


# Function to plot read latency vs concurrency
def plot_read_latency(agg: pd.DataFrame):
    for payload in sorted(agg.payload_bytes.unique()):
        subset = agg[agg.payload_bytes == payload]
        payload_kb = payload // 1024

        plt.figure(figsize=(8, 5))

        for mode in sorted(subset.encryption_mode.unique()):
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
        plt.title(f"Read Latency vs Concurrency (Payload {payload_kb} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Encryption Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"read_latency_{payload_kb}kb.png", dpi=72)
        plt.close()


# Function to plot write latency vs concurrency
def plot_write_latency(agg: pd.DataFrame):
    for payload in sorted(agg.payload_bytes.unique()):
        subset = agg[agg.payload_bytes == payload]
        payload_kb = payload // 1024

        plt.figure(figsize=(8, 5))

        for mode in sorted(subset.encryption_mode.unique()):
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
        plt.title(f"Write Latency vs Concurrency (Payload {payload_kb} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Encryption Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"write_latency_{payload_kb}kb.png", dpi=72)
        plt.close()


# Function to plot write latency overhead vs plaintext
def plot_write_latency_overhead(agg: pd.DataFrame):
    for payload in sorted(agg.payload_bytes.unique()):
        subset = agg[agg.payload_bytes == payload].copy()
        payload_kb = payload // 1024

        baseline = (
            subset[subset.encryption_mode == "PLAINTEXT"]
            .set_index("concurrency")["write_p95_mean"]
        )

        plt.figure(figsize=(8, 5))

        for mode in sorted(subset.encryption_mode.unique()):
            if mode == "PLAINTEXT":
                continue

            data = subset[subset.encryption_mode == mode].sort_values("concurrency").copy()
            data["baseline"] = data["concurrency"].map(baseline)
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
        plt.title(f"Write Latency Overhead vs PLAINTEXT (Payload {payload_kb} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Encryption Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"write_overhead_{payload_kb}kb.png", dpi=72)
        plt.close()


# Function to plot CPU utilisation vs concurrency
def plot_cpu_utilisation(agg: pd.DataFrame):
    for payload in sorted(agg.payload_bytes.unique()):
        subset = agg[agg.payload_bytes == payload]
        payload_kb = payload // 1024

        plt.figure(figsize=(8, 5))

        for mode in sorted(subset.encryption_mode.unique()):
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
        plt.title(f"CPU Utilisation vs Concurrency (Payload {payload_kb} KB)")
        plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        plt.legend(title="Encryption Mode")
        plt.tight_layout()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        plt.savefig(OUTPUT_DIR / f"cpu_utilisation_{payload_kb}kb.png", dpi=72)
        plt.close()


def plot_write_latency_all_in_one(agg: pd.DataFrame):
    plt.figure(figsize=(10, 6))

    # Payload styles (clean and subtle)
    payload_styles = {
        1024: {"linestyle": "-", "marker": "o", "label": "1 KB"},
        10240: {"linestyle": "--", "marker": "o", "label": "10 KB"},
        102400: {"linestyle": ":", "marker": "o", "label": "100 KB"},
    }

    for mode in sorted(agg["encryption_mode"].unique()):
        for payload in sorted(agg["payload_bytes"].unique()):
            data = agg[
                (agg["encryption_mode"] == mode) &
                (agg["payload_bytes"] == payload)
                ].sort_values("concurrency")

            if data.empty:
                continue

            style = payload_styles[payload]

            plt.plot(
                data["concurrency"],
                data["write_p95_mean"],
                label=f"{mode} ({style['label']})",
                color=COLORS.get(mode),
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=2,
                markersize=5,
            )

    plt.xlabel("Concurrency")
    plt.ylabel("Write P95 Latency (ms)")
    plt.title("Write Latency vs Concurrency (All Payloads)")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    # Keep legend readable
    plt.legend(title="Encryption Mode / Payload", ncol=2, fontsize=8)
    from matplotlib.lines import Line2D

    encryption_legend = [
        Line2D([0], [0], color="#2ca02c", lw=2, label="PLAINTEXT"),
        Line2D([0], [0], color="#1f77b4", lw=2, label="AES-GCM"),
        Line2D([0], [0], color="#17becf", lw=2, label="AES-CBC"),
        Line2D([0], [0], color="#d62728", lw=2, label="RSA"),
        Line2D([0], [0], color="#ff7f0e", lw=2, label="HYBRID"),
        Line2D([0], [0], color="#666666", linestyle="-", lw=2, label="1 KB"),
        Line2D([0], [0], color="#666666", linestyle="--", lw=2, label="10 KB"),
        Line2D([0], [0], color="#666666", linestyle=":", lw=2, label="100 KB"),
    ]

    legend_elements = [
        # --- Section: Encryption ---
        Line2D([0], [0], color="none", label="Encryption"),
        Line2D([0], [0], color="#2ca02c", lw=2, label="PLAINTEXT"),
        Line2D([0], [0], color="#1f77b4", lw=2, label="AES-GCM"),
        Line2D([0], [0], color="#17becf", lw=2, label="AES-CBC"),
        Line2D([0], [0], color="#d62728", lw=2, label="RSA"),
        Line2D([0], [0], color="#ff7f0e", lw=2, label="HYBRID"),

        # spacer
        Line2D([0], [0], color="none", label=""),

        # --- Section: Payload ---
        Line2D([0], [0], color="none", label="Payload Size"),
        Line2D([0], [0], color="#888888", linestyle="-", lw=2, label="1 KB"),
        Line2D([0], [0], color="#888888", linestyle="--", lw=2, label="10 KB"),
        Line2D([0], [0], color="#888888", linestyle=":", lw=2, label="100 KB"),
    ]

    legend = plt.legend(
        handles=legend_elements,
        loc="upper left",
        fontsize=8,
        framealpha=0.9,
    )

    # Style section headers
    for text in legend.get_texts():
        if text.get_text() in ["Encryption", "Payload Size"]:
            text.set_weight("bold")
            text.set_ha("left")  # left align

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_DIR / "write_latency_all_in_one.png", dpi=72)
    plt.close()


def plot_cpu_utilisation_all_in_one(agg: pd.DataFrame):
    plt.figure(figsize=(10, 6))

    payload_styles = {
        1024: {"linestyle": "-", "marker": "o", "label": "1 KB"},
        10240: {"linestyle": "--", "marker": "o", "label": "10 KB"},
        102400: {"linestyle": ":", "marker": "o", "label": "100 KB"},
    }

    for mode in sorted(agg["encryption_mode"].unique()):
        for payload in sorted(agg["payload_bytes"].unique()):
            data = agg[
                (agg["encryption_mode"] == mode) &
                (agg["payload_bytes"] == payload)
                ].sort_values("concurrency")

            if data.empty:
                continue

            style = payload_styles[payload]

            plt.plot(
                data["concurrency"],
                data["cpu_avg_mean"],
                color=COLORS.get(mode),
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=2,
                markersize=5,
            )

    plt.xlabel("Concurrency")
    plt.ylabel("Average CPU Utilisation (%)")
    plt.title("CPU Utilisation vs Concurrency (All Payloads)")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], color="none", label="Encryption"),
        Line2D([0], [0], color="#2ca02c", lw=2, label="PLAINTEXT"),
        Line2D([0], [0], color="#1f77b4", lw=2, label="AES-GCM"),
        Line2D([0], [0], color="#17becf", lw=2, label="AES-CBC"),
        Line2D([0], [0], color="#d62728", lw=2, label="RSA"),
        Line2D([0], [0], color="#ff7f0e", lw=2, label="HYBRID"),

        Line2D([0], [0], color="none", label=""),

        Line2D([0], [0], color="none", label="Payload Size"),
        Line2D([0], [0], color="#888888", linestyle="-", lw=2, label="1 KB"),
        Line2D([0], [0], color="#888888", linestyle="--", lw=2, label="10 KB"),
        Line2D([0], [0], color="#888888", linestyle=":", lw=2, label="100 KB"),
    ]

    legend = plt.legend(
        handles=legend_elements,
        loc="center left",
        fontsize=8,
        framealpha=0.9,
    )

    for text in legend.get_texts():
        if text.get_text() in ["Encryption", "Payload Size"]:
            text.set_weight("bold")
            text.set_ha("left")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_DIR / "cpu_utilisation_all_in_one.png", dpi=72)
    plt.close()

def plot_throughput_all_in_one(agg: pd.DataFrame):
    plt.figure(figsize=(10, 6))
    payload_styles = {
        1024: {"linestyle": "-", "marker": "o", "label": "1 KB"},
        10240: {"linestyle": "--", "marker": "o", "label": "10 KB"},
        102400: {"linestyle": ":", "marker": "o", "label": "100 KB"},
    }

    for mode in sorted(agg["encryption_mode"].unique()):
        for payload in sorted(agg["payload_bytes"].unique()):
            data = agg[
                (agg["encryption_mode"] == mode) &
                (agg["payload_bytes"] == payload)
                ].sort_values("concurrency")

            if data.empty:
                continue

            style = payload_styles[payload]

            plt.plot(
                data["concurrency"],
                data["throughput_mean"],
                color=COLORS.get(mode),
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=2,
                markersize=5,
            )

    plt.xlabel("Concurrency")
    plt.ylabel("Throughput (QPS)")
    plt.title("Throughput vs Concurrency (All Payloads)")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label=""),
        Line2D([0], [0], color="none", label="Encryption"),
        Line2D([0], [0], color="#2ca02c", lw=2, label="PLAINTEXT"),
        Line2D([0], [0], color="#1f77b4", lw=2, label="AES-GCM"),
        Line2D([0], [0], color="#17becf", lw=2, label="AES-CBC"),
        Line2D([0], [0], color="#d62728", lw=2, label="RSA"),
        Line2D([0], [0], color="#ff7f0e", lw=2, label="HYBRID"),

        Line2D([0], [0], color="none", label=""),


        Line2D([0], [0], color="none", label="Payload Size"),
        Line2D([0], [0], color="#888888", linestyle="-", lw=2, label="1 KB"),
        Line2D([0], [0], color="#888888", linestyle="--", lw=2, label="10 KB"),
        Line2D([0], [0], color="#888888", linestyle=":", lw=2, label="100 KB"),
    ]

    legend = plt.legend(
        handles=legend_elements,
        loc="best",
        fontsize=8,
        framealpha=0.9,
    )

    for text in legend.get_texts():
        if text.get_text() in ["Encryption", "Payload Size"]:
            text.set_weight("bold")
            text.set_ha("left")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_DIR / "throughput_all_in_one.png", dpi=72)
    plt.close()


def plot_read_latency_all_in_one(agg: pd.DataFrame):
    plt.figure(figsize=(10, 6))

    payload_styles = {
        1024: {"linestyle": "-", "marker": "o", "label": "1 KB"},
        10240: {"linestyle": "--", "marker": "o", "label": "10 KB"},
        102400: {"linestyle": ":", "marker": "o", "label": "100 KB"},
    }

    for mode in sorted(agg["encryption_mode"].unique()):
        for payload in sorted(agg["payload_bytes"].unique()):
            data = agg[
                (agg["encryption_mode"] == mode) &
                (agg["payload_bytes"] == payload)
                ].sort_values("concurrency")

            if data.empty:
                continue

            style = payload_styles[payload]

            plt.plot(
                data["concurrency"],
                data["read_p95_mean"],
                color=COLORS.get(mode),
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=2,
                markersize=5,
            )

    plt.xlabel("Concurrency")
    plt.ylabel("Read P95 Latency (ms)")
    plt.title("Read Latency vs Concurrency (All Payloads)")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], color="none", label="Encryption"),
        Line2D([0], [0], color="#2ca02c", lw=2, label="PLAINTEXT"),
        Line2D([0], [0], color="#1f77b4", lw=2, label="AES-GCM"),
        Line2D([0], [0], color="#17becf", lw=2, label="AES-CBC"),
        Line2D([0], [0], color="#d62728", lw=2, label="RSA"),
        Line2D([0], [0], color="#ff7f0e", lw=2, label="HYBRID"),

        Line2D([0], [0], color="none", label=""),

        Line2D([0], [0], color="none", label="Payload Size"),
        Line2D([0], [0], color="#888888", linestyle="-", lw=2, label="1 KB"),
        Line2D([0], [0], color="#888888", linestyle="--", lw=2, label="10 KB"),
        Line2D([0], [0], color="#888888", linestyle=":", lw=2, label="100 KB"),
    ]

    legend = plt.legend(
        handles=legend_elements,
        loc="upper left",
        fontsize=8,
        framealpha=0.9,
    )

    for text in legend.get_texts():
        if text.get_text() in ["Encryption", "Payload Size"]:
            text.set_weight("bold")
            text.set_ha("left")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_DIR / "read_latency_all_in_one.png", dpi=72)
    plt.close()




# Main function to execute the script
def main():
    df = load_data()
    agg = aggregate_results(df)

    plot_throughput(agg)
    plot_read_latency(agg)
    plot_write_latency(agg)
    plot_write_latency_overhead(agg)
    plot_cpu_utilisation(agg)
    plot_write_latency_all_in_one(agg)
    plot_throughput_all_in_one(agg)
    plot_write_latency_all_in_one(agg)
    plot_read_latency_all_in_one(agg)
    plot_cpu_utilisation_all_in_one(agg)

    print("Plots saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
