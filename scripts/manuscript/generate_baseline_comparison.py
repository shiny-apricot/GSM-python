"""
Baseline Comparison Figure Generator 🧬

Purpose:
    Creates a publication-quality grouped bar chart comparing the G-S-M
    framework against four standard baselines (RF-All, RF-ttest-100,
    LASSO, SVM-RBF) across all eight cancer datasets.

Key Functions:
    - generate_baseline_comparison(): Produces the comparison figure

Output:
    reports_ARCHIVE/manuscript/figures/fig_baseline_comparison.png

Usage:
    python scripts/manuscript/generate_baseline_comparison.py
"""

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

project_root = Path(__file__).resolve().parents[2]
import matplotlib.patches as mpatches
import numpy as np


##### DATA STRUCTURES #####

@dataclass
class MethodResult:
    """Performance result for one method on one dataset."""
    dataset_id: str
    disease: str
    method: str
    f1_score: float
    f1_ci_lower: float
    f1_ci_upper: float
    auc_roc: float
    n_features: int


##### CONSTANTS #####

OUTPUT_PATH = (
    project_root / "reports_ARCHIVE" / "manuscript" / "figures"
    / "fig_baseline_comparison.png"
)

BASELINE_PATH = (
    project_root / "output" / "baselines" / "baseline_results.json"
)

GSM_DATA_PATH = (
    project_root / "reports_ARCHIVE" / "manuscript" / "data"
    / "manuscript_data.json"
)

# Short labels for datasets
DATASET_SHORT = {
    "GDS1962": "GBM",
    "GDS2545": "Prostate",
    "GDS2547": "Prostate (2)",
    "GDS2771": "Lung",
    "GDS3257": "AML",
    "GDS3837": "Colorectal",
    "GDS5499": "Pancreatic",
}

# Dataset ordering (same as manuscript)
DATASET_ORDER = [
    "GDS1962", "GDS2545", "GDS2547", "GDS2771", "GDS3257",
    "GDS3837", "GDS5499",
]

# Method display names and colours
METHOD_META = {
    "G-S-M":         {"color": "#C0392B", "hatch": ""},
    "RF-All":        {"color": "#3498DB", "hatch": ""},
    "RF-ttest-100":  {"color": "#2ECC71", "hatch": ""},
    "LASSO":         {"color": "#F39C12", "hatch": ""},
    "SVM-RBF":       {"color": "#9B59B6", "hatch": ""},
}

METHODS_ORDER = ["G-S-M", "RF-All", "RF-ttest-100", "LASSO", "SVM-RBF"]


##### HELPER FUNCTIONS #####

def _load_data() -> dict[str, list[MethodResult]]:
    """Load GSM and baseline results, grouped by dataset.

    Returns:
        dict mapping dataset_id → list[MethodResult]
    """
    # Load baselines
    baselines = json.loads(BASELINE_PATH.read_text())

    # Load GSM performance
    gsm_data = json.loads(GSM_DATA_PATH.read_text())
    gsm_perf = gsm_data["performance"]

    # Build results dict
    results: dict[str, list[MethodResult]] = {}

    for ds_id in DATASET_ORDER:
        results[ds_id] = []

        # GSM result
        gsm = next((p for p in gsm_perf if p["dataset_id"] == ds_id), None)
        if gsm is None:
            print(f"⚠️  No GSM result for {ds_id}, skipping")
            continue
        results[ds_id].append(MethodResult(
            dataset_id=ds_id,
            disease=DATASET_SHORT.get(ds_id, ds_id),
            method="G-S-M",
            f1_score=gsm["f1_score"],
            f1_ci_lower=gsm["f1_ci_lower"],
            f1_ci_upper=gsm["f1_ci_upper"],
            auc_roc=gsm["auc_roc"],
            n_features=gsm["features_used"],
        ))

        # Baseline results
        for bl in baselines:
            if bl["dataset_id"] == ds_id:
                results[ds_id].append(MethodResult(
                    dataset_id=ds_id,
                    disease=DATASET_SHORT.get(ds_id, ds_id),
                    method=bl["method"],
                    f1_score=bl["f1_score"],
                    f1_ci_lower=bl["f1_ci_lower"],
                    f1_ci_upper=bl["f1_ci_upper"],
                    auc_roc=bl["auc_roc"],
                    n_features=bl["n_features"],
                ))

    return results


##### FIGURE GENERATION #####

def generate_baseline_comparison() -> str:
    """Create a grouped bar chart comparing G-S-M vs baselines.

    Returns:
        Path to the saved figure.
    """
    results = _load_data()

    n_datasets = len(DATASET_ORDER)
    n_methods = len(METHODS_ORDER)
    bar_width = 0.15
    gap = 0.08  # gap between dataset groups

    # x positions for each dataset cluster
    group_width = n_methods * bar_width
    x_centers = np.arange(n_datasets) * (group_width + gap)

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.patch.set_facecolor("#FAFAFA")

    metrics = [("f1_score", "F1 Score"), ("auc_roc", "AUC-ROC")]

    for ax_idx, (metric_key, metric_label) in enumerate(metrics):
        ax = axes[ax_idx]
        ax.set_facecolor("#FAFAFA")

        for m_idx, method in enumerate(METHODS_ORDER):
            x_positions = x_centers + m_idx * bar_width
            values = []
            ci_lower = []
            ci_upper = []

            for ds_id in DATASET_ORDER:
                # Find this method's result for this dataset
                match = [r for r in results[ds_id] if r.method == method]
                if match:
                    r = match[0]
                    val = getattr(r, metric_key)
                    values.append(val)
                    if metric_key == "f1_score":
                        # Only show CI if bounds are real (not placeholder 1.0)
                        has_real_ci = (
                            r.f1_ci_lower < r.f1_ci_upper
                            and r.f1_ci_lower <= val <= r.f1_ci_upper
                        )
                        if has_real_ci:
                            lo = val - r.f1_ci_lower
                            hi = r.f1_ci_upper - val
                        else:
                            lo, hi = 0, 0
                        ci_lower.append(lo)
                        ci_upper.append(hi)
                    else:
                        ci_lower.append(0)
                        ci_upper.append(0)
                else:
                    values.append(0)
                    ci_lower.append(0)
                    ci_upper.append(0)

            meta = METHOD_META[method]
            bars = ax.bar(
                x_positions, values, bar_width,
                label=method if ax_idx == 0 else "",
                color=meta["color"],
                edgecolor="white",
                linewidth=0.5,
                alpha=0.88,
                zorder=3,
            )

            # Error bars only for F1 (we have CIs for that)
            if metric_key == "f1_score":
                ax.errorbar(
                    x_positions, values,
                    yerr=[ci_lower, ci_upper],
                    fmt="none", ecolor="#333333", elinewidth=0.8,
                    capsize=2, capthick=0.8, zorder=4,
                )

        # Formatting
        ax.set_ylabel(metric_label, fontsize=12, fontweight="bold")
        ax.set_ylim(0.45, 1.08)
        ax.set_yticks(np.arange(0.5, 1.05, 0.1))
        ax.axhline(y=1.0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=1)
        ax.grid(axis="y", alpha=0.3, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Highlight G-S-M as best for each dataset
        for d_idx, ds_id in enumerate(DATASET_ORDER):
            gsm_val = next(
                getattr(r, metric_key) for r in results[ds_id]
                if r.method == "G-S-M"
            )
            best_baseline = max(
                getattr(r, metric_key) for r in results[ds_id]
                if r.method != "G-S-M"
            )
            # Small star above GSM bar if it beats all baselines
            if gsm_val > best_baseline:
                star_x = x_centers[d_idx] + 0 * bar_width
                ax.text(
                    star_x + bar_width / 2,
                    gsm_val + 0.015,
                    "★",
                    ha="center", va="bottom",
                    fontsize=8, color="#C0392B",
                    zorder=5,
                )

    # X-axis labels on bottom subplot only
    tick_x = x_centers + (n_methods - 1) * bar_width / 2
    tick_labels = [
        f"{DATASET_SHORT[ds]}\n({ds})" for ds in DATASET_ORDER
    ]
    axes[1].set_xticks(tick_x)
    axes[1].set_xticklabels(tick_labels, fontsize=9, ha="center")

    # Legend at the top
    axes[0].legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.22),
        ncol=n_methods,
        fontsize=10,
        frameon=True,
        fancybox=True,
        shadow=False,
        edgecolor="#cccccc",
    )

    # Title
    fig.suptitle(
        "G-S-M Framework vs Standard Baselines",
        fontsize=14, fontweight="bold", y=0.98, color="#1A237E",
    )

    fig.tight_layout(rect=[0, 0.0, 1, 0.93])

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        str(OUTPUT_PATH), dpi=300,
        bbox_inches="tight", facecolor="#FAFAFA", edgecolor="none",
    )
    plt.close(fig)
    print(f"Baseline comparison figure saved to: {OUTPUT_PATH}")
    return str(OUTPUT_PATH)


if __name__ == "__main__":
    generate_baseline_comparison()
