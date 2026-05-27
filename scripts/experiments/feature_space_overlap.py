"""
Feature-space overlap analysis across expression datasets.

Computes pairwise feature overlap metrics and writes:
- feature_overlap_counts.csv
- feature_overlap_jaccard_percent.csv
- feature_overlap_coverage_percent.csv (row-wise: A->B coverage)
- feature_overlap_summary.json
- fig_feature_overlap_jaccard_heatmap.png

Usage:
  /home/yasin/GSM-to-python/venv/bin/python scripts/experiments/feature_space_overlap.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_processing.data_loader import _detect_separator

EXPR_DIR = PROJECT_ROOT / "data" / "expression_data"
OUT_DIR = PROJECT_ROOT / "output" / "feature_space_overlap"


@dataclass
class OverlapSummary:
    n_datasets: int
    dataset_ids: list[str]
    median_jaccard_percent: float
    mean_jaccard_percent: float
    min_jaccard_percent: float
    max_jaccard_percent: float
    lowest_pair: dict[str, float | str]
    highest_pair: dict[str, float | str]



def _read_dataset_columns(csv_path: Path) -> set[str]:
    sep = _detect_separator(str(csv_path))
    try:
        df = pd.read_csv(csv_path, sep=sep, low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, sep=sep, encoding="latin1", low_memory=False)
    cols = [c for c in df.columns if c != "class"]
    return set(cols)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset_paths = sorted(EXPR_DIR.glob("*.csv"))
    if not dataset_paths:
        raise FileNotFoundError(f"No CSV datasets found in {EXPR_DIR}")

    dataset_ids = [p.stem for p in dataset_paths]
    features = {p.stem: _read_dataset_columns(p) for p in dataset_paths}

    n = len(dataset_ids)
    counts = pd.DataFrame(np.zeros((n, n), dtype=int), index=dataset_ids, columns=dataset_ids)
    jaccard_pct = pd.DataFrame(np.zeros((n, n), dtype=float), index=dataset_ids, columns=dataset_ids)
    coverage_pct = pd.DataFrame(np.zeros((n, n), dtype=float), index=dataset_ids, columns=dataset_ids)

    pair_rows: list[dict[str, float | str]] = []

    for a in dataset_ids:
        for b in dataset_ids:
            fa = features[a]
            fb = features[b]
            inter = len(fa & fb)
            union = len(fa | fb)
            jaccard = (inter / union) if union else 0.0
            coverage = (inter / len(fa)) if fa else 0.0

            counts.loc[a, b] = inter
            jaccard_pct.loc[a, b] = round(jaccard * 100.0, 3)
            coverage_pct.loc[a, b] = round(coverage * 100.0, 3)

            if a != b:
                pair_rows.append({
                    "dataset_a": a,
                    "dataset_b": b,
                    "intersection_count": inter,
                    "union_count": union,
                    "jaccard_percent": jaccard * 100.0,
                    "coverage_a_to_b_percent": coverage * 100.0,
                })

    # Save matrices
    counts.to_csv(OUT_DIR / "feature_overlap_counts.csv")
    jaccard_pct.to_csv(OUT_DIR / "feature_overlap_jaccard_percent.csv")
    coverage_pct.to_csv(OUT_DIR / "feature_overlap_coverage_percent.csv")
    pd.DataFrame(pair_rows).to_csv(OUT_DIR / "feature_overlap_pairs.csv", index=False)

    # Summary stats over off-diagonal pairs
    pair_df = pd.DataFrame(pair_rows)
    min_idx = pair_df["jaccard_percent"].idxmin()
    max_idx = pair_df["jaccard_percent"].idxmax()

    summary = OverlapSummary(
        n_datasets=n,
        dataset_ids=dataset_ids,
        median_jaccard_percent=round(float(pair_df["jaccard_percent"].median()), 3),
        mean_jaccard_percent=round(float(pair_df["jaccard_percent"].mean()), 3),
        min_jaccard_percent=round(float(pair_df["jaccard_percent"].min()), 3),
        max_jaccard_percent=round(float(pair_df["jaccard_percent"].max()), 3),
        lowest_pair={
            "dataset_a": str(pair_df.loc[min_idx, "dataset_a"]),
            "dataset_b": str(pair_df.loc[min_idx, "dataset_b"]),
            "jaccard_percent": round(float(pair_df.loc[min_idx, "jaccard_percent"]), 3),
        },
        highest_pair={
            "dataset_a": str(pair_df.loc[max_idx, "dataset_a"]),
            "dataset_b": str(pair_df.loc[max_idx, "dataset_b"]),
            "jaccard_percent": round(float(pair_df.loc[max_idx, "jaccard_percent"]), 3),
        },
    )

    with open(OUT_DIR / "feature_overlap_summary.json", "w") as f:
        json.dump(asdict(summary), f, indent=2)

    # Heatmap
    plt.figure(figsize=(max(8, n * 0.7), max(6, n * 0.55)))
    sns.heatmap(
        jaccard_pct,
        annot=True,
        fmt=".1f",
        cmap="YlOrBr",
        vmin=0,
        vmax=100,
        cbar_kws={"label": "Jaccard overlap (%)"},
    )
    plt.title("Pairwise Feature-Space Overlap (Jaccard %)")
    plt.xlabel("Dataset B")
    plt.ylabel("Dataset A")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig_feature_overlap_jaccard_heatmap.png", dpi=300)
    plt.close()

    print("Feature-space overlap analysis completed")
    print(f"Datasets: {n}")
    print(f"Output dir: {OUT_DIR}")
    print(f"Median Jaccard (%): {summary.median_jaccard_percent}")


if __name__ == "__main__":
    main()
