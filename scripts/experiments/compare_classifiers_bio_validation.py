#!/usr/bin/env python3
"""
Classifier Impact on Biological Validation - Comparison Experiment

Purpose:
    Compare RandomForest vs XGBoost (scoring + modeling) to determine
    whether the choice of classifier affects the biological coherence
    of selected gene sets, specifically STRING PPI counts and Enrichr
    pathway enrichment.

Procedure:
    For each dataset x each classifier:
      1. Run the G-S-M pipeline (10 iterations, same random seed)
      2. Extract the top 20 genes
      3. Run biological validation (Enrichr + STRING)
      4. Record PPI count, top pathways, and gene overlap

Output:
    - scripts/classifier_comparison_results.json
    - Console summary table
    - Per-dataset breakdown

Usage:
    python scripts/experiments/compare_classifiers_bio_validation.py
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd

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

CLASSIFIERS = ["XGBoost", "RandomForest"]

N_ITERATIONS = 10        # enough per run for gene ranking to stabilise
RANDOM_SEED = 44         # same seed across classifiers for fair comparison
TOP_N_GENES = 20


##### Data structures #####

@dataclass
class ClassifierResult:
    classifier: str
    dataset: str
    top_genes: list = field(default_factory=list)
    string_ppi_count: int = 0
    top_interactions: list = field(default_factory=list)
    enrichr_term_count: int = 0
    top_kegg_term: str = ""
    top_kegg_pvalue: float = 1.0
    top_disgenet_term: str = ""
    top_disgenet_pvalue: float = 1.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    output_dir: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class DatasetComparison:
    dataset: str
    results: dict = field(default_factory=dict)  # classifier -> ClassifierResult
    gene_overlap_count: int = 0
    gene_overlap_pct: float = 0.0
    ppi_delta: int = 0
    enrichr_delta: int = 0


def setup_simple_logger():
    logger = logging.getLogger("classifier_comparison")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


def run_pipeline_for_classifier(
    dataset_id: str,
    expression_path: str,
    grouping_path: str,
    classifier: str,
    logger: logging.Logger,
) -> ClassifierResult:
    """Run the G-S-M pipeline with a specific classifier and collect results."""
    
    result = ClassifierResult(classifier=classifier, dataset=dataset_id)
    
    logger.info(f"  Loading {dataset_id}...")
    input_data = load_input_file(Path(expression_path), separator=",")
    group_data = load_group_file(Path(grouping_path), separator=",")
    
    logger.info(f"  Running pipeline ({classifier}, {N_ITERATIONS} iters)...")
    t0 = time.time()
    
    output_path = gsm_run(
        input_data,
        group_data,
        n_iterations=N_ITERATIONS,
        model_name=classifier,
        scoring_model=classifier,
        initial_seed=RANDOM_SEED,
        run_biological_validation_flag=False,  # we do it ourselves below
        input_data_name=f"{dataset_id}_{classifier.lower()}_cmp",
        group_data_name="cancer-DisGeNET_gedinet",
    )
    
    result.elapsed_seconds = time.time() - t0
    result.output_dir = str(output_path)
    logger.info(f"  Pipeline done in {result.elapsed_seconds:.0f}s -> {output_path.name}")
    
    # Extract metrics from results JSON
    results_json = output_path / "modeling_results_all_iterations.json"
    if results_json.exists():
        with open(results_json) as f:
            all_results = json.load(f)
        
        # Structure: list of {metadata: {...}, results: [{f1_score, auc_roc, ...}]}
        f1_scores = []
        auc_scores = []
        for payload in all_results:
            for r in payload.get("results", []):
                f1_scores.append(r.get("f1_score", 0))
                auc_scores.append(r.get("auc_roc", 0))
        
        if f1_scores:
            result.f1_score = sum(f1_scores) / len(f1_scores)
        if auc_scores:
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
    
    # Run biological validation
    logger.info(f"  Querying Enrichr ({len(genes)} genes)...")
    try:
        enrichr_results = query_enrichr(genes, logger)
        result.enrichr_term_count = len(enrichr_results)
        
        # Find top KEGG term
        kegg_terms = [r for r in enrichr_results if "KEGG" in r.library]
        if kegg_terms:
            best = min(kegg_terms, key=lambda r: r.p_value)
            result.top_kegg_term = best.term
            result.top_kegg_pvalue = best.p_value
        
        # Find top DisGeNET term
        dg_terms = [r for r in enrichr_results if "DisGeNET" in r.library]
        if dg_terms:
            best = min(dg_terms, key=lambda r: r.p_value)
            result.top_disgenet_term = best.term
            result.top_disgenet_pvalue = best.p_value
    except Exception as e:
        logger.warning(f"  Enrichr failed: {e}")
    
    logger.info(f"  Querying STRING-db ({len(genes)} genes)...")
    try:
        string_data = query_string_db(genes, logger)
        interactions = string_data.get("interactions", [])
        result.string_ppi_count = len(interactions)
        result.top_interactions = [
            {"p1": i.protein1, "p2": i.protein2, "score": i.score}
            for i in interactions[:10]
        ]
    except Exception as e:
        logger.warning(f"  STRING failed: {e}")
    
    logger.info(f"  {classifier}: PPI={result.string_ppi_count}, "
                f"Enrichr terms={result.enrichr_term_count}")
    
    return result


def compute_comparison(comparisons: list) -> dict:
    """Compute summary statistics across all comparisons."""
    summary = {
        "total_datasets": len(comparisons),
        "classifiers": CLASSIFIERS,
        "n_iterations": N_ITERATIONS,
        "random_seed": RANDOM_SEED,
        "per_dataset": [],
        "aggregate": {},
    }
    
    total_ppi = {c: 0 for c in CLASSIFIERS}
    total_enrichr = {c: 0 for c in CLASSIFIERS}
    total_overlap = 0
    
    for cmp in comparisons:
        ds_data = {
            "dataset": cmp.dataset,
            "gene_overlap_count": cmp.gene_overlap_count,
            "gene_overlap_pct": round(cmp.gene_overlap_pct, 1),
        }
        for clf_name, res in cmp.results.items():
            ds_data[clf_name] = {
                "top_genes": res.top_genes,
                "string_ppi": res.string_ppi_count,
                "enrichr_terms": res.enrichr_term_count,
                "top_kegg": res.top_kegg_term,
                "top_kegg_p": res.top_kegg_pvalue,
                "top_disgenet": res.top_disgenet_term,
                "top_disgenet_p": res.top_disgenet_pvalue,
                "f1": res.f1_score,
                "auc": res.auc_roc,
                "time_s": round(res.elapsed_seconds, 1),
            }
            total_ppi[clf_name] += res.string_ppi_count
            total_enrichr[clf_name] += res.enrichr_term_count
        total_overlap += cmp.gene_overlap_count
        summary["per_dataset"].append(ds_data)
    
    n = len(comparisons)
    summary["aggregate"] = {
        "mean_gene_overlap_pct": round(total_overlap / (n * TOP_N_GENES) * 100, 1) if n else 0,
        "total_string_ppi": total_ppi,
        "total_enrichr_terms": total_enrichr,
        "ppi_difference": total_ppi.get("RandomForest", 0) - total_ppi.get("XGBoost", 0),
    }
    
    return summary


def print_summary(comparisons: list, summary: dict):
    """Print a formatted comparison table."""
    print("\n" + "=" * 90)
    print("  CLASSIFIER COMPARISON: BIOLOGICAL VALIDATION RESULTS")
    print("=" * 90)
    
    header = f"{'Dataset':<10} | {'Metric':<14} | {'XGBoost':>10} | {'RandomForest':>12} | {'Delta':>8}"
    print(header)
    print("-" * 90)
    
    for cmp in comparisons:
        xgb = cmp.results.get("XGBoost")
        rf = cmp.results.get("RandomForest")
        if not xgb or not rf:
            continue
        
        print(f"{cmp.dataset:<10} | {'STRING PPI':<14} | {xgb.string_ppi_count:>10} | "
              f"{rf.string_ppi_count:>12} | {rf.string_ppi_count - xgb.string_ppi_count:>+8}")
        print(f"{'':10} | {'Enrichr terms':<14} | {xgb.enrichr_term_count:>10} | "
              f"{rf.enrichr_term_count:>12} | {rf.enrichr_term_count - xgb.enrichr_term_count:>+8}")
        print(f"{'':10} | {'Gene overlap':<14} | {cmp.gene_overlap_count:>10}/{TOP_N_GENES} "
              f"({cmp.gene_overlap_pct:.0f}%)")
        print(f"{'':10} | {'F1 score':<14} | {xgb.f1_score:>10.3f} | "
              f"{rf.f1_score:>12.3f} | {rf.f1_score - xgb.f1_score:>+8.3f}")
        print(f"{'':10} | {'Runtime (s)':<14} | {xgb.elapsed_seconds:>10.0f} | "
              f"{rf.elapsed_seconds:>12.0f} | {rf.elapsed_seconds - xgb.elapsed_seconds:>+8.0f}")
        print("-" * 90)
    
    agg = summary["aggregate"]
    print(f"\n{'TOTALS':<10} | {'STRING PPI':<14} | "
          f"{agg['total_string_ppi'].get('XGBoost', 0):>10} | "
          f"{agg['total_string_ppi'].get('RandomForest', 0):>12} | "
          f"{agg['ppi_difference']:>+8}")
    print(f"{'':10} | {'Mean gene overlap':>14} | {agg['mean_gene_overlap_pct']:.1f}%")
    print("=" * 90)


def main():
    logger = setup_simple_logger()
    
    print("=" * 70)
    print("  CLASSIFIER COMPARISON EXPERIMENT")
    print(f"  Classifiers: {', '.join(CLASSIFIERS)}")
    print(f"  Datasets: {len(DATASETS)}")
    print(f"  Iterations per run: {N_ITERATIONS}")
    print(f"  Total runs: {len(DATASETS) * len(CLASSIFIERS)}")
    print("=" * 70)
    
    grouping_path = str(project_root / GROUPING_FILE)
    comparisons = []
    
    for ds_id, ds_path in DATASETS.items():
        print(f"\n{'='*50}")
        print(f"  DATASET: {ds_id}")
        print(f"{'='*50}")
        
        cmp = DatasetComparison(dataset=ds_id)
        
        for clf in CLASSIFIERS:
            print(f"\n  --- {clf} ---")
            try:
                result = run_pipeline_for_classifier(
                    ds_id,
                    str(project_root / ds_path),
                    grouping_path,
                    clf,
                    logger,
                )
                cmp.results[clf] = result
            except Exception as e:
                logger.error(f"  FAILED: {ds_id} + {clf}: {e}")
                import traceback
                traceback.print_exc()
        
        # Compute gene overlap between classifiers
        if len(cmp.results) == 2:
            genes_a = set(cmp.results[CLASSIFIERS[0]].top_genes)
            genes_b = set(cmp.results[CLASSIFIERS[1]].top_genes)
            overlap = genes_a & genes_b
            cmp.gene_overlap_count = len(overlap)
            cmp.gene_overlap_pct = len(overlap) / TOP_N_GENES * 100 if TOP_N_GENES else 0
            logger.info(f"  Gene overlap: {len(overlap)}/{TOP_N_GENES} "
                       f"({cmp.gene_overlap_pct:.0f}%)")
            if overlap:
                logger.info(f"  Shared genes: {', '.join(sorted(overlap))}")
        
        comparisons.append(cmp)
    
    # Compute summary
    summary = compute_comparison(comparisons)
    
    # Save results
    out_path = project_root / "output" / "classifier_comparison" / "classifier_comparison_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")
    
    # Print summary table
    print_summary(comparisons, summary)
    
    # Print conclusion
    ppi_diff = summary["aggregate"]["ppi_difference"]
    if ppi_diff > 0:
        print(f"\n  CONCLUSION: RandomForest selects genes with {ppi_diff} more STRING "
              "interactions than XGBoost.")
    elif ppi_diff < 0:
        print(f"\n  CONCLUSION: XGBoost selects genes with {-ppi_diff} more STRING "
              "interactions than RandomForest.")
    else:
        print("\n  CONCLUSION: Both classifiers produce similar STRING interaction counts.")
    
    print(f"  Mean gene overlap: {summary['aggregate']['mean_gene_overlap_pct']:.1f}%")


if __name__ == "__main__":
    main()
