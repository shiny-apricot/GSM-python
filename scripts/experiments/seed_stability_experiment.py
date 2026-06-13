#!/usr/bin/env python3
"""
Seed Stability Experiment for Biological Coherence

Purpose:
    Test whether the choice of initial random seed affects the biological
    coherence (PPI count, pathway enrichment) of the selected gene panels.
    This answers the question: "If we re-run the pipeline with a different
    seed, do we get similar biological validation results?"

Procedure:
    For each seed x each dataset:
      1. Run the G-S-M pipeline (10 iterations, Random Forest)
      2. Extract the top 20 genes
      3. Run biological validation (Enrichr + STRING)
      4. Record PPI count, top pathways, gene overlap between seeds

Output:
    - output/seed_stability/seed_stability_results.json
    - Console summary table

Usage:
    python scripts/experiments/seed_stability_experiment.py
    python scripts/experiments/seed_stability_experiment.py --datasets GDS2545 GDS3257
    python scripts/experiments/seed_stability_experiment.py --seeds 44 88 132 176

Note:
    This experiment takes several hours to complete (each seed x dataset
    combination runs 10 pipeline iterations).  Consider running on a
    subset of datasets first to estimate total time.
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from itertools import combinations
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_processing.data_loader import load_input_file, load_group_file
from src.workflows.GSM_workflow import gsm_run
from src.utils.biological_validation import (
    extract_top_genes,
    query_enrichr,
    query_string_db,
)


##### Configuration #####

DATASETS = {
    "GDS1962": "data/expression_data/GDS1962.csv",
    "GDS2545": "data/expression_data/GDS2545.csv",
    "GDS2547": "data/expression_data/GDS2547.csv",
    "GDS2771": "data/expression_data/GDS2771.csv",
    "GDS3257": "data/expression_data/GDS3257.csv",
    "GDS3837": "data/expression_data/GDS3837.csv",
    "GDS5499": "data/expression_data/GDS5499.csv",
}

GROUPING_FILE = "data/grouping_data/cancer-DisGeNET_gedinet.txt"

DEFAULT_SEEDS = [44, 88, 132, 176, 220]
N_ITERATIONS = 10
TOP_N_GENES = 20
CLASSIFIER = "RandomForest"


##### Data structures #####

@dataclass
class SeedRunResult:
    """Result for a single seed x dataset combination."""
    seed: int
    dataset: str
    top_genes: list = field(default_factory=list)
    string_ppi_count: int = 0
    top_interactions: list = field(default_factory=list)
    top_kegg_term: str = ""
    top_kegg_pvalue: float = 1.0
    top_disgenet_term: str = ""
    top_disgenet_pvalue: float = 1.0
    f1_score: float = 0.0
    mean_f1: float = 0.0
    auc_roc: float = 0.0
    output_dir: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class DatasetSeedComparison:
    """Aggregated comparison of seed results for one dataset."""
    dataset: str
    seed_results: list = field(default_factory=list)
    pairwise_gene_overlaps: list = field(default_factory=list)
    mean_gene_overlap_pct: float = 0.0
    ppi_range: str = ""
    f1_range: str = ""
    core_genes: list = field(default_factory=list)


def setup_logger():
    """Create a simple logger for the experiment."""
    logger = logging.getLogger("seed_stability")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter(
            "%(asctime)s - %(message)s", datefmt="%H:%M:%S"
        )
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


##### Pipeline runner #####

def run_pipeline_with_seed(
    dataset_id: str,
    expression_path: str,
    grouping_path: str,
    seed: int,
    logger: logging.Logger,
) -> SeedRunResult:
    """Run the G-S-M pipeline with a specific seed and collect results."""

    result = SeedRunResult(seed=seed, dataset=dataset_id)

    logger.info(f"  Loading {dataset_id}...")
    input_data = load_input_file(Path(expression_path), separator=",")
    group_data = load_group_file(Path(grouping_path), separator=",")

    logger.info(
        f"  Running pipeline (seed={seed}, {N_ITERATIONS} iters)..."
    )
    t0 = time.time()

    output_path = gsm_run(
        input_data,
        group_data,
        n_iterations=N_ITERATIONS,
        model_name=CLASSIFIER,
        scoring_model=CLASSIFIER,
        initial_seed=seed,
        run_biological_validation_flag=False,
        input_data_name=f"{dataset_id}_seed{seed}",
        group_data_name="cancer-DisGeNET_gedinet",
    )

    result.elapsed_seconds = time.time() - t0
    result.output_dir = str(output_path)
    logger.info(
        f"  Pipeline done in {result.elapsed_seconds:.0f}s -> "
        f"{output_path.name}"
    )

    # Extract metrics
    results_json = output_path / "modeling_results_all_iterations.json"
    if results_json.exists():
        with open(results_json) as f:
            all_results = json.load(f)

        f1_scores = []
        auc_scores = []
        for payload in all_results:
            for r in payload.get("results", []):
                f1_scores.append(r.get("f1_score", 0))
                auc_scores.append(r.get("auc_roc", 0))

        # if f1_scores:
        #     result.f1_score = max(f1_scores)
        #     result.mean_f1 = sum(f1_scores) / len(f1_scores)
        # if auc_scores:
        #     result.auc_roc = max(auc_scores)
        if f1_scores:
            # Calculate the consistent average rather than the peak anomaly
            result.f1_score = sum(f1_scores) / len(f1_scores)
            result.mean_f1 = result.f1_score  # Kept in sync just in case it's referenced later
            
        if auc_scores:
            # Calculate average AUC-ROC across iterations
            result.auc_roc = sum(auc_scores) / len(auc_scores)

    # Extract top genes
    logger.info(f"  Extracting top {TOP_N_GENES} genes...")
    try:
        genes = extract_top_genes(results_json, logger, top_n=TOP_N_GENES)
        result.top_genes = genes
        logger.info(f"  Top genes: {', '.join(genes[:5])}...")
    except Exception as e:
        logger.warning(f"  Could not extract genes: {e}")
        return result

    # Biological validation - Enrichr
    logger.info(f"  Querying Enrichr ({len(genes)} genes)...")
    try:
        enrichr_results = query_enrichr(genes, logger)

        kegg_terms = [r for r in enrichr_results if "KEGG" in r.library]
        if kegg_terms:
            best = min(kegg_terms, key=lambda r: r.p_value)
            result.top_kegg_term = best.term
            result.top_kegg_pvalue = best.p_value

        dg_terms = [
            r for r in enrichr_results if "DisGeNET" in r.library
        ]
        if dg_terms:
            best = min(dg_terms, key=lambda r: r.p_value)
            result.top_disgenet_term = best.term
            result.top_disgenet_pvalue = best.p_value
    except Exception as e:
        logger.warning(f"  Enrichr failed: {e}")

    # Biological validation - STRING
    logger.info(f"  Querying STRING-db ({len(genes)} genes)...")
    try:
        string_data = query_string_db(genes, logger)
        interactions = string_data.get("interactions", [])
        result.string_ppi_count = len(interactions)
        result.top_interactions = [
            {
                "protein1": i["preferredName_A"],
                "protein2": i["preferredName_B"],
                "score": i["score"],
            }
            for i in sorted(
                interactions, key=lambda x: x["score"], reverse=True
            )[:5]
        ]
        logger.info(f"  STRING: {result.string_ppi_count} interactions")
    except Exception as e:
        logger.warning(f"  STRING failed: {e}")

    return result


##### Analysis #####

def compute_gene_overlap(genes_a: list, genes_b: list) -> tuple[int, float]:
    """Compute overlap count and percentage between two gene lists."""
    set_a = set(genes_a)
    set_b = set(genes_b)
    overlap = set_a & set_b
    union = set_a | set_b
    pct = len(overlap) / len(union) * 100 if union else 0.0
    return len(overlap), pct


def analyse_dataset_results(
    dataset_id: str, results: list[SeedRunResult]
) -> DatasetSeedComparison:
    """Compare all seed results for a single dataset."""
    comparison = DatasetSeedComparison(
        dataset=dataset_id, seed_results=results
    )

    # Pairwise gene overlaps
    overlaps = []
    for (r1, r2) in combinations(results, 2):
        if r1.top_genes and r2.top_genes:
            count, pct = compute_gene_overlap(r1.top_genes, r2.top_genes)
            overlaps.append({
                "seed_a": r1.seed,
                "seed_b": r2.seed,
                "overlap_count": count,
                "overlap_pct": round(pct, 1),
            })
    comparison.pairwise_gene_overlaps = overlaps

    if overlaps:
        comparison.mean_gene_overlap_pct = round(
            sum(o["overlap_pct"] for o in overlaps) / len(overlaps), 1
        )

    # PPI range
    ppis = [r.string_ppi_count for r in results]
    if ppis:
        comparison.ppi_range = f"{min(ppis)}-{max(ppis)}"

    # F1 range
    f1s = [r.f1_score for r in results if r.f1_score > 0]
    if f1s:
        comparison.f1_range = f"{min(f1s):.3f}-{max(f1s):.3f}"

    # Core genes (present in ALL seed runs)
    if all(r.top_genes for r in results):
        gene_sets = [set(r.top_genes) for r in results]
        core = gene_sets[0]
        for gs in gene_sets[1:]:
            core = core & gs
        comparison.core_genes = sorted(core)

    return comparison


##### Main #####

def main():
    """Run the seed stability experiment."""
    parser = argparse.ArgumentParser(
        description="Seed stability experiment for biological coherence"
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=list(DATASETS.keys()),
        help="Dataset IDs to test (default: all)",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=DEFAULT_SEEDS,
        help=f"Seeds to test (default: {DEFAULT_SEEDS})",
    )
    args = parser.parse_args()

    logger = setup_logger()
    grouping_path = str(project_root / GROUPING_FILE)

    selected_datasets = {
        k: v for k, v in DATASETS.items() if k in args.datasets
    }
    seeds = args.seeds

    total_runs = len(selected_datasets) * len(seeds)
    logger.info("=" * 70)
    logger.info(f"  Seed Stability Experiment")
    logger.info(f"  Datasets: {list(selected_datasets.keys())}")
    logger.info(f"  Seeds: {seeds}")
    logger.info(f"  Total runs: {total_runs}")
    logger.info(f"  Classifier: {CLASSIFIER}")
    logger.info(f"  Iterations per run: {N_ITERATIONS}")
    logger.info("=" * 70)

    all_comparisons = []
    run_count = 0

    for ds_id, ds_path in selected_datasets.items():
        logger.info(f"\n{'─' * 50}")
        logger.info(f"Dataset: {ds_id}")
        logger.info(f"{'─' * 50}")

        expression_path = str(project_root / ds_path)
        ds_results = []

        for seed in seeds:
            run_count += 1
            logger.info(
                f"\n[{run_count}/{total_runs}] {ds_id} seed={seed}"
            )
            result = run_pipeline_with_seed(
                ds_id, expression_path, grouping_path, seed, logger
            )
            ds_results.append(result)

        comparison = analyse_dataset_results(ds_id, ds_results)
        all_comparisons.append(comparison)

        # Print dataset summary
        logger.info(f"\n  --- {ds_id} Summary ---")
        logger.info(f"  PPI range: {comparison.ppi_range}")
        logger.info(f"  F1 range: {comparison.f1_range}")
        logger.info(
            f"  Mean gene overlap: {comparison.mean_gene_overlap_pct}%"
        )
        logger.info(
            f"  Core genes (all seeds): "
            f"{', '.join(comparison.core_genes) if comparison.core_genes else 'none'}"
        )

    # Save results
    output_dir = project_root / "output" / "seed_stability"
    output_dir.mkdir(parents=True, exist_ok=True)

    results_data = {
        "config": {
            "seeds": seeds,
            "datasets": list(selected_datasets.keys()),
            "classifier": CLASSIFIER,
            "iterations_per_run": N_ITERATIONS,
            "top_n_genes": TOP_N_GENES,
        },
        "comparisons": [
            {
                "dataset": c.dataset,
                "ppi_range": c.ppi_range,
                "f1_range": c.f1_range,
                "mean_gene_overlap_pct": c.mean_gene_overlap_pct,
                "core_genes": c.core_genes,
                "pairwise_overlaps": c.pairwise_gene_overlaps,
                "seed_results": [asdict(r) for r in c.seed_results],
            }
            for c in all_comparisons
        ],
    }

    out_path = output_dir / "seed_stability_results.json"
    with open(out_path, "w") as f:
        json.dump(results_data, f, indent=2)

    logger.info(f"\n{'=' * 70}")
    logger.info(f"  Results saved to: {out_path}")
    logger.info(f"{'=' * 70}")

    # Print final summary table
    print("\n" + "=" * 80)
    print("  SEED STABILITY SUMMARY")
    print("=" * 80)
    print(
        f"{'Dataset':<10} {'PPI Range':<12} {'F1 Range':<16} "
        f"{'Gene Overlap':<14} {'Core Genes'}"
    )
    print("-" * 80)
    for c in all_comparisons:
        core_str = (
            ", ".join(c.core_genes[:5])
            + ("..." if len(c.core_genes) > 5 else "")
            if c.core_genes
            else "none"
        )
        print(
            f"{c.dataset:<10} {c.ppi_range:<12} {c.f1_range:<16} "
            f"{c.mean_gene_overlap_pct:>5.1f}%         {core_str}"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()
