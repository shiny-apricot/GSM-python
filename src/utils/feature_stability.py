"""
Feature Stability Analysis 📊

Purpose:
    Analyze how consistently genes are selected across multiple iterations
    of the GSM pipeline. This addresses reviewer concern I3 about feature
    stability and reproducibility of the selected biomarker panels.

Key Functions:
    - compute_feature_stability: Compute per-gene selection frequency
    - compute_jaccard_stability: Pairwise Jaccard index across iterations
    - save_feature_stability_report: Export results to Excel

Usage:
    Called automatically at the end of gsm_run() after all iterations complete.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import numpy as np
import pandas as pd
import logging


@dataclass
class FeatureStabilityResult:
    """Results from feature stability analysis."""
    # Per-gene: how often each gene was selected across iterations
    gene_frequencies: Dict[str, float]  # gene_name -> proportion (0..1)
    # Summary statistics
    total_iterations: int
    total_unique_genes: int
    mean_stability: float  # Average selection frequency
    median_stability: float
    # Genes selected in >50% of iterations (stable core)
    stable_core_genes: List[str]
    stable_core_size: int
    # Pairwise Jaccard stability (mean across all iteration pairs)
    mean_jaccard_index: float


def compute_feature_stability(
    iteration_results,
    logger: logging.Logger,
) -> FeatureStabilityResult:
    """Compute how consistently each gene is selected across iterations.

    Args:
        iteration_results: List of IterationResult from gsm_run()
        logger: Logger instance

    Returns:
        FeatureStabilityResult with per-gene frequencies and summary stats
    """
    n_iterations = len(iteration_results)
    if n_iterations == 0:
        return FeatureStabilityResult(
            gene_frequencies={}, total_iterations=0, total_unique_genes=0,
            mean_stability=0.0, median_stability=0.0,
            stable_core_genes=[], stable_core_size=0, mean_jaccard_index=0.0,
        )

    # Collect selected gene sets from each iteration
    # Use the fixed-K result (last modeling step) for each iteration
    iteration_gene_sets: List[set] = []
    for res in iteration_results:
        if res.modeling_results:
            fixed_k = res.modeling_results[-1]  # Last step = fixed K
            gene_set = set(fixed_k.used_features) if fixed_k.used_features else set()
            iteration_gene_sets.append(gene_set)

    if not iteration_gene_sets:
        logger.warning("No gene sets found for stability analysis")
        return FeatureStabilityResult(
            gene_frequencies={}, total_iterations=n_iterations, total_unique_genes=0,
            mean_stability=0.0, median_stability=0.0,
            stable_core_genes=[], stable_core_size=0, mean_jaccard_index=0.0,
        )

    # Count how often each gene appears
    gene_counts: Dict[str, int] = {}
    for gene_set in iteration_gene_sets:
        for gene in gene_set:
            gene_counts[gene] = gene_counts.get(gene, 0) + 1

    n_with_genes = len(iteration_gene_sets)
    gene_frequencies = {
        gene: count / n_with_genes
        for gene, count in gene_counts.items()
    }

    # Summary statistics
    freqs = list(gene_frequencies.values())
    mean_stability = float(np.mean(freqs)) if freqs else 0.0
    median_stability = float(np.median(freqs)) if freqs else 0.0

    # Stable core: genes in >50% of iterations
    stable_core = sorted(
        [g for g, f in gene_frequencies.items() if f > 0.5],
        key=lambda g: gene_frequencies[g],
        reverse=True,
    )

    # Pairwise Jaccard index
    jaccard_values = []
    for i in range(len(iteration_gene_sets)):
        for j in range(i + 1, len(iteration_gene_sets)):
            a, b = iteration_gene_sets[i], iteration_gene_sets[j]
            if a or b:  # Avoid division by zero
                jaccard = len(a & b) / len(a | b)
                jaccard_values.append(jaccard)
    mean_jaccard = float(np.mean(jaccard_values)) if jaccard_values else 0.0

    logger.info(
        f"📊 Feature stability: {len(gene_frequencies)} unique genes, "
        f"{len(stable_core)} stable core (>50%), "
        f"mean Jaccard={mean_jaccard:.3f}"
    )

    return FeatureStabilityResult(
        gene_frequencies=gene_frequencies,
        total_iterations=n_with_genes,
        total_unique_genes=len(gene_frequencies),
        mean_stability=mean_stability,
        median_stability=median_stability,
        stable_core_genes=stable_core,
        stable_core_size=len(stable_core),
        mean_jaccard_index=mean_jaccard,
    )


def save_feature_stability_report(
    stability: FeatureStabilityResult,
    output_dir: Path,
    logger: logging.Logger,
) -> Path:
    """Save feature stability results to Excel.

    Creates two sheets:
    1. Gene Frequencies: per-gene selection frequency across iterations
    2. Summary: overall stability statistics

    Returns:
        Path to the saved Excel file
    """
    output_path = output_dir / "feature_stability_report.xlsx"

    # Sheet 1: Per-gene frequencies
    freq_df = pd.DataFrame([
        {"Gene": gene, "Selection_Frequency": freq, "Iterations_Selected": int(freq * stability.total_iterations)}
        for gene, freq in sorted(stability.gene_frequencies.items(), key=lambda x: x[1], reverse=True)
    ])

    # Sheet 2: Summary
    summary_df = pd.DataFrame([
        {"Metric": "Total Iterations", "Value": stability.total_iterations},
        {"Metric": "Total Unique Genes", "Value": stability.total_unique_genes},
        {"Metric": "Stable Core Size (>50%)", "Value": stability.stable_core_size},
        {"Metric": "Mean Selection Frequency", "Value": f"{stability.mean_stability:.4f}"},
        {"Metric": "Median Selection Frequency", "Value": f"{stability.median_stability:.4f}"},
        {"Metric": "Mean Pairwise Jaccard Index", "Value": f"{stability.mean_jaccard_index:.4f}"},
    ])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        freq_df.to_excel(writer, sheet_name="Gene_Frequencies", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

    logger.info(f"📊 Feature stability report saved: {output_path.name}")
    return output_path
