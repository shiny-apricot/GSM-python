#!/usr/bin/env python3
"""
Extended Classifier Comparison - Biological Validation

Purpose:
    Extend the XGBoost/RandomForest comparison with additional classifiers.
    Uses 3 representative datasets x additional classifiers x 10 iterations.
    Scoring model varies; modeling always uses XGBoost (isolates scoring effect).
    Merges results with existing classifier_comparison_results.json.

Usage:
    python scripts/experiments/extend_classifier_comparison.py
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np

from src.data_processing.data_loader import load_input_file, load_group_file
from src.workflows.GSM_workflow import gsm_run
from src.utils.biological_validation import (
    extract_top_genes,
    query_enrichr,
    query_string_db,
)


##### Configuration #####

# Representative datasets: one easy (GDS3257 AML, F1=1.0), one medium (GDS2545 Prostate),
# one hard (GDS2771 Lung). These span the performance spectrum.
DATASETS = {
    "GDS2545": "data/expression_data/GDS2545.csv",
    "GDS2771": "data/expression_data/GDS2771.csv",
    "GDS3257": "data/expression_data/GDS3257.csv",
}

GROUPING_FILE = "data/grouping_data/cancer-DisGeNET_gedinet.txt"

# Additional classifiers to test (RF and XGBoost already done)
NEW_CLASSIFIERS = ["DecisionTree", "AdaBoost", "GradientBoosting", "LogisticRegression"]

N_ITERATIONS = 10
RANDOM_SEED = 44
TOP_N_GENES = 20

EXISTING_RESULTS = project_root / "output" / "classifier_comparison" / "classifier_comparison_results.json"
OUTPUT_FILE = project_root / "output" / "classifier_comparison" / "classifier_comparison_results.json"


@dataclass
class RunResult:
    classifier: str
    dataset: str
    scoring_model: str
    modeling_model: str
    top_genes: list = field(default_factory=list)
    string_ppi_count: int = 0
    enrichr_term_count: int = 0
    top_kegg_term: str = ""
    top_kegg_pvalue: float = 1.0
    top_disgenet_term: str = ""
    top_disgenet_pvalue: float = 1.0
    mean_f1: float = 0.0
    mean_auc: float = 0.0
    elapsed_seconds: float = 0.0
    top_interactions: list = field(default_factory=list)


def setup_logger():
    logger = logging.getLogger("extended_comparison")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


def run_single(
    dataset_id: str,
    expression_path: str,
    grouping_path: str,
    scoring_model: str,
    modeling_model: str,
    logger: logging.Logger,
) -> RunResult:
    """Run pipeline with specified scoring and modeling classifiers."""
    result = RunResult(
        classifier=scoring_model,
        dataset=dataset_id,
        scoring_model=scoring_model,
        modeling_model=modeling_model,
    )

    input_data = load_input_file(Path(expression_path), separator=",")
    group_data = load_group_file(Path(grouping_path), separator=",")

    logger.info(f"  Pipeline: scoring={scoring_model}, modeling={modeling_model}")
    t0 = time.time()

    output_path = gsm_run(
        input_data,
        group_data,
        n_iterations=N_ITERATIONS,
        model_name=modeling_model,
        scoring_model=scoring_model,
        initial_seed=RANDOM_SEED,
        run_biological_validation_flag=False,
        input_data_name=f"{dataset_id}_{scoring_model.lower()}_ext",
        group_data_name="cancer-DisGeNET_gedinet",
    )

    result.elapsed_seconds = time.time() - t0
    logger.info(f"  Done in {result.elapsed_seconds:.0f}s -> {output_path.name}")

    # Extract metrics
    results_json = output_path / "modeling_results_all_iterations.json"
    if results_json.exists():
        with open(results_json) as f:
            all_res = json.load(f)
        f1s, aucs = [], []
        for payload in all_res:
            for r in payload.get("results", []):
                f1s.append(r.get("f1_score", 0))
                aucs.append(r.get("auc_roc", 0))
        result.mean_f1 = np.mean(f1s) if f1s else 0
        result.mean_auc = np.mean(aucs) if aucs else 0

    # Extract top genes
    try:
        genes = extract_top_genes(results_json, logger, top_n=TOP_N_GENES)
        result.top_genes = genes
    except Exception as e:
        logger.warning(f"  Gene extraction failed: {e}")
        return result

    # Enrichr
    try:
        enrichr_results = query_enrichr(genes, logger)
        result.enrichr_term_count = len(enrichr_results)
        kegg = [r for r in enrichr_results if "KEGG" in r.library]
        if kegg:
            best = min(kegg, key=lambda r: r.p_value)
            result.top_kegg_term = best.term
            result.top_kegg_pvalue = best.p_value
        dg = [r for r in enrichr_results if "DisGeNET" in r.library]
        if dg:
            best = min(dg, key=lambda r: r.p_value)
            result.top_disgenet_term = best.term
            result.top_disgenet_pvalue = best.p_value
    except Exception as e:
        logger.warning(f"  Enrichr failed: {e}")

    # STRING
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

    logger.info(f"  {scoring_model}: PPI={result.string_ppi_count}, "
                f"Enrichr={result.enrichr_term_count}, "
                f"F1={result.mean_f1:.3f}")

    return result


def load_existing_results():
    """Load existing results and extract per-classifier/dataset data."""
    if not EXISTING_RESULTS.exists():
        return {}

    with open(EXISTING_RESULTS) as f:
        data = json.load(f)

    # Build lookup: (classifier, dataset) -> result dict
    existing = {}
    for ds_entry in data.get("per_dataset", []):
        ds_id = ds_entry["dataset"]
        for clf_name in ["XGBoost", "RandomForest"]:
            if clf_name in ds_entry:
                existing[(clf_name, ds_id)] = ds_entry[clf_name]
    return existing


def merge_results(existing: dict, new_results: list) -> dict:
    """Merge existing and new results into the comprehensive comparison."""
    # Add new results to the lookup
    for r in new_results:
        existing[(r.classifier, r.dataset)] = {
            "top_genes": r.top_genes,
            "string_ppi": r.string_ppi_count,
            "enrichr_terms": r.enrichr_term_count,
            "top_kegg": r.top_kegg_term,
            "top_kegg_p": r.top_kegg_pvalue,
            "top_disgenet": r.top_disgenet_term,
            "top_disgenet_p": r.top_disgenet_pvalue,
            "f1": r.mean_f1,
            "auc": r.mean_auc,
            "time_s": round(r.elapsed_seconds, 1),
        }

    # Build per-dataset structure
    all_datasets = sorted(set(ds for _, ds in existing.keys()))
    all_classifiers = sorted(set(clf for clf, _ in existing.keys()))

    per_dataset = []
    for ds_id in all_datasets:
        ds_entry = {"dataset": ds_id}
        clf_data_for_overlap = {}

        for clf in all_classifiers:
            key = (clf, ds_id)
            if key in existing:
                ds_entry[clf] = existing[key]
                clf_data_for_overlap[clf] = set(existing[key].get("top_genes", []))

        # Compute pairwise overlaps (against XGBoost as reference)
        xgb_genes = clf_data_for_overlap.get("XGBoost", set())
        overlaps = {}
        for clf, genes in clf_data_for_overlap.items():
            if clf != "XGBoost" and xgb_genes:
                overlap = xgb_genes & genes
                overlaps[clf] = {
                    "count": len(overlap),
                    "pct": round(len(overlap) / TOP_N_GENES * 100, 1),
                }
        ds_entry["gene_overlaps_vs_xgboost"] = overlaps

        per_dataset.append(ds_entry)

    # Aggregate
    total_ppi = {clf: 0 for clf in all_classifiers}
    total_enrichr = {clf: 0 for clf in all_classifiers}
    mean_kegg_p = {clf: [] for clf in all_classifiers}
    mean_disgenet_p = {clf: [] for clf in all_classifiers}

    for ds_entry in per_dataset:
        for clf in all_classifiers:
            if clf in ds_entry:
                total_ppi[clf] += ds_entry[clf].get("string_ppi", 0)
                total_enrichr[clf] += ds_entry[clf].get("enrichr_terms", 0)
                kp = ds_entry[clf].get("top_kegg_p", 1.0)
                dp = ds_entry[clf].get("top_disgenet_p", 1.0)
                if kp < 1.0:
                    mean_kegg_p[clf].append(kp)
                if dp < 1.0:
                    mean_disgenet_p[clf].append(dp)

    # Geometric mean of p-values (more appropriate than arithmetic for p-values)
    geo_mean_kegg = {}
    geo_mean_disgenet = {}
    for clf in all_classifiers:
        if mean_kegg_p[clf]:
            geo_mean_kegg[clf] = float(np.exp(np.mean(np.log(mean_kegg_p[clf]))))
        if mean_disgenet_p[clf]:
            geo_mean_disgenet[clf] = float(np.exp(np.mean(np.log(mean_disgenet_p[clf]))))

    summary = {
        "total_datasets_all": len(all_datasets),
        "classifiers": all_classifiers,
        "n_iterations": N_ITERATIONS,
        "random_seed": RANDOM_SEED,
        "note": (
            "XGBoost and RandomForest ran on all 7 datasets (scoring+modeling same classifier). "
            "Additional classifiers ran on 3 representative datasets (scoring varies, modeling=XGBoost)."
        ),
        "per_dataset": per_dataset,
        "aggregate": {
            "total_string_ppi": total_ppi,
            "total_enrichr_terms": total_enrichr,
            "geo_mean_kegg_p": geo_mean_kegg,
            "geo_mean_disgenet_p": geo_mean_disgenet,
        },
    }

    return summary


def print_summary(summary: dict):
    """Print comprehensive comparison table."""
    classifiers = summary["classifiers"]
    per_dataset = summary["per_dataset"]
    agg = summary["aggregate"]

    # Datasets where additional classifiers were tested
    test_ds = set(DATASETS.keys())

    print("\n" + "=" * 100)
    print("  EXTENDED CLASSIFIER COMPARISON (3 representative datasets)")
    print("=" * 100)

    # Header
    clf_headers = " | ".join(f"{c:>14}" for c in classifiers)
    print(f"{'Dataset':<10} | {'Metric':<14} | {clf_headers}")
    print("-" * 100)

    for ds in per_dataset:
        ds_id = ds["dataset"]
        if ds_id not in test_ds:
            continue

        # STRING PPI row
        vals = []
        for c in classifiers:
            if c in ds:
                vals.append(f"{ds[c].get('string_ppi', '-'):>14}")
            else:
                vals.append(f"{'--':>14}")
        print(f"{ds_id:<10} | {'STRING PPI':<14} | {' | '.join(vals)}")

        # Enrichment p-value row (KEGG)
        vals = []
        for c in classifiers:
            if c in ds:
                p = ds[c].get("top_kegg_p", 1.0)
                vals.append(f"{p:>14.2e}")
            else:
                vals.append(f"{'--':>14}")
        print(f"{'':10} | {'KEGG p-val':<14} | {' | '.join(vals)}")

        # DisGeNET p-value row
        vals = []
        for c in classifiers:
            if c in ds:
                p = ds[c].get("top_disgenet_p", 1.0)
                vals.append(f"{p:>14.2e}")
            else:
                vals.append(f"{'--':>14}")
        print(f"{'':10} | {'DisGeNET p-val':<14} | {' | '.join(vals)}")

        # F1 row
        vals = []
        for c in classifiers:
            if c in ds:
                f1 = ds[c].get("f1", 0)
                vals.append(f"{f1:>14.3f}")
            else:
                vals.append(f"{'--':>14}")
        print(f"{'':10} | {'Mean F1':<14} | {' | '.join(vals)}")

        print("-" * 100)

    # Totals across test datasets
    print(f"\n{'TOTALS (3ds)':<10} | {'STRING PPI':<14} |", end="")
    for c in classifiers:
        ppi_sum = sum(
            ds.get(c, {}).get("string_ppi", 0)
            for ds in per_dataset if ds["dataset"] in test_ds
        )
        print(f" {ppi_sum:>14} |", end="")
    print()

    # Geo-mean p-values
    print(f"{'':10} | {'Geo-mean KEGG':<14} |", end="")
    for c in classifiers:
        gm = agg["geo_mean_kegg_p"].get(c, None)
        if gm:
            print(f" {gm:>14.2e} |", end="")
        else:
            print(f" {'--':>14} |", end="")
    print()

    print(f"{'':10} | {'Geo-mean DG':<14} |", end="")
    for c in classifiers:
        gm = agg["geo_mean_disgenet_p"].get(c, None)
        if gm:
            print(f" {gm:>14.2e} |", end="")
        else:
            print(f" {'--':>14} |", end="")
    print()

    print("=" * 100)


def main():
    logger = setup_logger()

    print("=" * 70)
    print("  EXTENDED CLASSIFIER COMPARISON")
    print(f"  New classifiers: {', '.join(NEW_CLASSIFIERS)}")
    print(f"  Datasets: {', '.join(DATASETS.keys())}")
    print(f"  Models per run: scoring=<varies>, modeling=XGBoost")
    print(f"  Total new runs: {len(DATASETS) * len(NEW_CLASSIFIERS)}")
    print("=" * 70)

    # Load existing results
    existing = load_existing_results()
    logger.info(f"Loaded {len(existing)} existing (classifier, dataset) entries")

    grouping_path = str(project_root / GROUPING_FILE)
    new_results = []

    for ds_id, ds_path in DATASETS.items():
        print(f"\n{'='*50}")
        print(f"  DATASET: {ds_id}")
        print(f"{'='*50}")

        for clf in NEW_CLASSIFIERS:
            # Skip if already done
            if (clf, ds_id) in existing:
                logger.info(f"  Skipping {clf} x {ds_id} (already exists)")
                continue

            print(f"\n  --- {clf} (scoring) + XGBoost (modeling) ---")
            try:
                result = run_single(
                    ds_id,
                    str(project_root / ds_path),
                    grouping_path,
                    scoring_model=clf,
                    modeling_model="XGBoost",
                    logger=logger,
                )
                new_results.append(result)
            except Exception as e:
                logger.error(f"  FAILED: {ds_id} + {clf}: {e}")
                import traceback
                traceback.print_exc()

    # Merge and save
    summary = merge_results(existing, new_results)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nResults saved to: {OUTPUT_FILE}")

    print_summary(summary)


if __name__ == "__main__":
    main()
