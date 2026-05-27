#!/usr/bin/env python3
"""
Sensitivity Analysis for GSM Pipeline Parameters 📊

Purpose:
    Assess how sensitive the pipeline results are to choices of:
      - FDR threshold (t-test): 0.01, 0.05, 0.10
      - CV folds (scoring phase): 3, 5, 10
      - Max groups retained: 5, 10, 20
    Runs on 3 representative datasets with 10 iterations each
    (enough to capture variance, fast enough to be practical).

Output:
    - sensitivity_results.json: Machine-readable results
    - Printed summary table
    - Console-friendly Markdown table for the manuscript

Usage:
    python scripts/experiments/run_sensitivity_analysis.py
    
    # Run on specific datasets:
    python scripts/experiments/run_sensitivity_analysis.py --datasets GDS2545 GDS3257
    
    # Adjust iterations:
    python scripts/experiments/run_sensitivity_analysis.py --iterations 20
"""

import sys
import json
import time
import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from itertools import product

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
from src.data_processing.data_loader import load_input_file, load_group_file
from src.workflows.GSM_workflow import gsm_run
from src.workflows.GSM_workflow_config import (
    GROUPING_FILE_SEPARATOR,
    MAIN_DATA_FILE_SEPARATOR,
    LABEL_COLUMN_NAME,
    CLASS_LABELS_POSITIVE,
    CLASS_LABELS_NEGATIVE,
    GENE_COLUMN_NAME,
    GROUP_COLUMN_NAME,
    NORMALIZATION_METHOD,
    MODEL_NAME,
    SCORING_MODEL,
    RANDOM_SEED,
)


##### DATA STRUCTURES #####
@dataclass
class SensitivityResult:
    """Result of a single sensitivity run."""
    dataset_id: str
    fdr_threshold: float
    cv_folds: int
    max_groups: int
    mean_f1: float
    std_f1: float
    mean_auc: float
    std_auc: float
    mean_groups_used: float
    mean_features_used: float
    elapsed_seconds: float


##### CONFIGURATION #####
# Datasets representative of different sizes and difficulties
DEFAULT_DATASETS = ["GDS2545", "GDS3257", "GDS2771"]
DEFAULT_ITERATIONS = 10   # Enough for variance estimation, fast enough

# Parameter grid
FDR_VALUES = [0.01, 0.05, 0.10]
CV_FOLDS_VALUES = [3, 5, 10]
MAX_GROUPS_VALUES = [5, 10, 20]

# Default/baseline values (what the pipeline normally uses)
BASELINE = {"fdr": 0.05, "cv_folds": 3, "max_groups": 10}

EXPRESSION_DATA_DIR = project_root / "data" / "expression_data"
GROUPING_DATA_FILE = project_root / "data" / "grouping_data" / "cancer-DisGeNET_gedinet.txt"


##### HELPER FUNCTIONS #####
def extract_metrics_from_output(output_dir: Path) -> dict:
    """
    Extract F1, AUC, groups_used, features_used from a pipeline run.

    Reads the modeling_results_all_iterations.json and computes
    the best-step metrics per iteration, then averages across iterations.

    Args:
        output_dir: Path to the pipeline output folder

    Returns:
        Dict with mean_f1, std_f1, mean_auc, std_auc,
        mean_groups_used, mean_features_used
    """
    json_path = output_dir / "modeling_results_all_iterations.json"
    if not json_path.exists():
        return {"mean_f1": 0.0, "std_f1": 0.0, "mean_auc": 0.0,
                "std_auc": 0.0, "mean_groups_used": 0.0,
                "mean_features_used": 0.0}

    with open(json_path) as f:
        all_results = json.load(f)

    # For each iteration, find the best step (highest F1)
    f1_scores = []
    auc_scores = []
    groups_used_list = []
    features_used_list = []

    for iteration_data in all_results:
        results = iteration_data.get("results", [])
        if not results:
            continue
        best = max(results, key=lambda r: r.get("f1_score", 0.0))
        f1_scores.append(best.get("f1_score", 0.0))
        auc_scores.append(best.get("auc_roc", 0.0))
        groups_used_list.append(best.get("num_groups_used", 0))
        features_used_list.append(best.get("num_features_used", 0))

    return {
        "mean_f1": float(np.mean(f1_scores)) if f1_scores else 0.0,
        "std_f1": float(np.std(f1_scores)) if f1_scores else 0.0,
        "mean_auc": float(np.mean(auc_scores)) if auc_scores else 0.0,
        "std_auc": float(np.std(auc_scores)) if auc_scores else 0.0,
        "mean_groups_used": float(np.mean(groups_used_list)) if groups_used_list else 0.0,
        "mean_features_used": float(np.mean(features_used_list)) if features_used_list else 0.0,
    }


def run_single_config(
    input_data: pd.DataFrame,
    group_data: pd.DataFrame,
    dataset_id: str,
    fdr: float,
    cv_folds: int,
    max_groups: int,
    n_iterations: int,
) -> SensitivityResult:
    """
    Run the pipeline with a specific parameter configuration.

    Args:
        input_data: Loaded expression data
        group_data: Loaded grouping data
        dataset_id: Dataset identifier for logging
        fdr: FDR threshold for t-test filtering
        cv_folds: Number of CV folds for scoring
        max_groups: Maximum groups to retain
        n_iterations: Number of pipeline iterations

    Returns:
        SensitivityResult with aggregated metrics
    """
    config_label = f"fdr={fdr}_cv={cv_folds}_groups={max_groups}"
    print(f"    Running {config_label}...", end="", flush=True)

    start = time.time()
    try:
        output_path = gsm_run(
            input_data,
            group_data,
            n_iterations=n_iterations,
            model_name=MODEL_NAME,
            scoring_model=SCORING_MODEL,
            label_column=LABEL_COLUMN_NAME,
            positive_class_label=CLASS_LABELS_POSITIVE,
            negative_class_label=CLASS_LABELS_NEGATIVE,
            gene_column=GENE_COLUMN_NAME,
            group_column=GROUP_COLUMN_NAME,
            normalization_method=NORMALIZATION_METHOD,
            initial_seed=RANDOM_SEED,
            ttest_threshold=fdr,
            cross_validation_folds=cv_folds,
            best_groups_to_keep=max_groups,
            run_biological_validation_flag=False,  # Skip bio validation for speed
            input_data_name=f"{dataset_id}_sens",
            group_data_name="cancer-DisGeNET_gedinet",
        )
        elapsed = time.time() - start
        metrics = extract_metrics_from_output(output_path)

        print(f" F1={metrics['mean_f1']:.3f}±{metrics['std_f1']:.3f} "
              f"({elapsed:.0f}s)")

        return SensitivityResult(
            dataset_id=dataset_id,
            fdr_threshold=fdr,
            cv_folds=cv_folds,
            max_groups=max_groups,
            mean_f1=metrics["mean_f1"],
            std_f1=metrics["std_f1"],
            mean_auc=metrics["mean_auc"],
            std_auc=metrics["std_auc"],
            mean_groups_used=metrics["mean_groups_used"],
            mean_features_used=metrics["mean_features_used"],
            elapsed_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        print(f" FAILED: {e} ({elapsed:.0f}s)")
        return SensitivityResult(
            dataset_id=dataset_id,
            fdr_threshold=fdr,
            cv_folds=cv_folds,
            max_groups=max_groups,
            mean_f1=0.0,
            std_f1=0.0,
            mean_auc=0.0,
            std_auc=0.0,
            mean_groups_used=0.0,
            mean_features_used=0.0,
            elapsed_seconds=elapsed,
        )


def generate_one_at_a_time_configs() -> list[dict]:
    """
    Generate parameter configurations using one-at-a-time (OAT) design.

    Varies one parameter while holding others at baseline.
    This avoids the full 3×3×3 = 27 grid (× 3 datasets = 81 runs)
    and instead produces 7 unique configs (× 3 datasets = 21 runs).

    Returns:
        List of dicts with fdr, cv_folds, max_groups keys
    """
    configs = []
    seen = set()

    # Vary FDR, hold others at baseline
    for fdr in FDR_VALUES:
        key = (fdr, BASELINE["cv_folds"], BASELINE["max_groups"])
        if key not in seen:
            configs.append({"fdr": fdr, "cv_folds": BASELINE["cv_folds"],
                           "max_groups": BASELINE["max_groups"]})
            seen.add(key)

    # Vary CV folds, hold others at baseline
    for cv in CV_FOLDS_VALUES:
        key = (BASELINE["fdr"], cv, BASELINE["max_groups"])
        if key not in seen:
            configs.append({"fdr": BASELINE["fdr"], "cv_folds": cv,
                           "max_groups": BASELINE["max_groups"]})
            seen.add(key)

    # Vary max groups, hold others at baseline
    for mg in MAX_GROUPS_VALUES:
        key = (BASELINE["fdr"], BASELINE["cv_folds"], mg)
        if key not in seen:
            configs.append({"fdr": BASELINE["fdr"], "cv_folds": BASELINE["cv_folds"],
                           "max_groups": mg})
            seen.add(key)

    return configs


def print_results_table(results: list[SensitivityResult]) -> None:
    """Print a formatted results table to console."""
    print("\n" + "=" * 90)
    print("SENSITIVITY ANALYSIS RESULTS")
    print("=" * 90)
    print(f"{'Dataset':<10} {'FDR':<6} {'CV':<4} {'Groups':<7} "
          f"{'F1 Mean':<9} {'±Std':<8} {'AUC Mean':<9} {'±Std':<8} {'Time':<7}")
    print("-" * 90)

    # Group by dataset
    datasets = sorted(set(r.dataset_id for r in results))
    for ds in datasets:
        ds_results = [r for r in results if r.dataset_id == ds]
        for r in ds_results:
            # Mark baseline config
            is_baseline = (r.fdr_threshold == BASELINE["fdr"] and
                          r.cv_folds == BASELINE["cv_folds"] and
                          r.max_groups == BASELINE["max_groups"])
            marker = " *" if is_baseline else ""
            print(f"{r.dataset_id:<10} {r.fdr_threshold:<6.2f} {r.cv_folds:<4} "
                  f"{r.max_groups:<7} {r.mean_f1:<9.4f} {r.std_f1:<8.4f} "
                  f"{r.mean_auc:<9.4f} {r.std_auc:<8.4f} {r.elapsed_seconds:>5.0f}s{marker}")
        print("-" * 90)

    print("* = baseline configuration (FDR=0.05, CV=3, MaxGroups=10)")


def compute_parameter_impact(results: list[SensitivityResult]) -> dict:
    """
    Compute the impact of each parameter on F1 variance.

    For each parameter, computes the range of mean F1 (max - min)
    across its levels, averaged over datasets.

    Returns:
        Dict with parameter name -> average F1 range
    """
    datasets = sorted(set(r.dataset_id for r in results))
    impacts = {"FDR threshold": [], "CV folds": [], "Max groups": []}

    for ds in datasets:
        ds_results = [r for r in results if r.dataset_id == ds]

        # FDR impact (varied FDR, fixed cv/groups at baseline)
        fdr_results = [r for r in ds_results
                       if r.cv_folds == BASELINE["cv_folds"]
                       and r.max_groups == BASELINE["max_groups"]]
        if len(fdr_results) > 1:
            f1s = [r.mean_f1 for r in fdr_results]
            impacts["FDR threshold"].append(max(f1s) - min(f1s))

        # CV folds impact
        cv_results = [r for r in ds_results
                      if r.fdr_threshold == BASELINE["fdr"]
                      and r.max_groups == BASELINE["max_groups"]]
        if len(cv_results) > 1:
            f1s = [r.mean_f1 for r in cv_results]
            impacts["CV folds"].append(max(f1s) - min(f1s))

        # Max groups impact
        mg_results = [r for r in ds_results
                      if r.fdr_threshold == BASELINE["fdr"]
                      and r.cv_folds == BASELINE["cv_folds"]]
        if len(mg_results) > 1:
            f1s = [r.mean_f1 for r in mg_results]
            impacts["Max groups"].append(max(f1s) - min(f1s))

    return {
        param: float(np.mean(vals)) if vals else 0.0
        for param, vals in impacts.items()
    }


def save_results(results: list[SensitivityResult], output_path: Path) -> None:
    """Save sensitivity results to JSON."""
    data = {
        "baseline": BASELINE,
        "fdr_values": FDR_VALUES,
        "cv_folds_values": CV_FOLDS_VALUES,
        "max_groups_values": MAX_GROUPS_VALUES,
        "results": [asdict(r) for r in results],
        "parameter_impact": compute_parameter_impact(results),
    }
    output_path.write_text(json.dumps(data, indent=2))
    print(f"\n📦 Results saved to {output_path}")


##### MAIN #####
def main():
    parser = argparse.ArgumentParser(
        description="Run sensitivity analysis on GSM pipeline parameters"
    )
    parser.add_argument(
        "--datasets", nargs="+", default=DEFAULT_DATASETS,
        help=f"Dataset IDs to test (default: {DEFAULT_DATASETS})"
    )
    parser.add_argument(
        "--iterations", type=int, default=DEFAULT_ITERATIONS,
        help=f"Iterations per config (default: {DEFAULT_ITERATIONS})"
    )
    parser.add_argument(
        "--full-grid", action="store_true",
        help="Run full 3×3×3 grid instead of one-at-a-time design"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("📊 GSM SENSITIVITY ANALYSIS")
    print("=" * 70)

    # Load grouping data once
    print(f"Loading grouping data: {GROUPING_DATA_FILE}")
    group_data = load_group_file(GROUPING_DATA_FILE, separator=GROUPING_FILE_SEPARATOR)

    # Generate parameter configs
    if args.full_grid:
        configs = [{"fdr": f, "cv_folds": c, "max_groups": m}
                   for f, c, m in product(FDR_VALUES, CV_FOLDS_VALUES, MAX_GROUPS_VALUES)]
    else:
        configs = generate_one_at_a_time_configs()

    total_runs = len(args.datasets) * len(configs)
    print(f"Datasets: {args.datasets}")
    print(f"Configs: {len(configs)} ({'full grid' if args.full_grid else 'one-at-a-time'})")
    print(f"Iterations per config: {args.iterations}")
    print(f"Total pipeline runs: {total_runs}")
    est_minutes = total_runs * 2  # Rough estimate: ~2 min per 10-iter run
    print(f"Estimated time: ~{est_minutes} minutes")
    print("=" * 70)

    all_results: list[SensitivityResult] = []
    run_count = 0

    for dataset_id in args.datasets:
        dataset_path = EXPRESSION_DATA_DIR / f"{dataset_id}.csv"
        if not dataset_path.exists():
            print(f"⚠️  Dataset not found: {dataset_path}")
            continue

        print(f"\n🧬 Dataset: {dataset_id}")
        input_data = load_input_file(dataset_path, separator=MAIN_DATA_FILE_SEPARATOR)
        print(f"   Shape: {input_data.shape}")

        for config in configs:
            run_count += 1
            print(f"  [{run_count}/{total_runs}] ", end="")
            result = run_single_config(
                input_data=input_data,
                group_data=group_data,
                dataset_id=dataset_id,
                fdr=config["fdr"],
                cv_folds=config["cv_folds"],
                max_groups=config["max_groups"],
                n_iterations=args.iterations,
            )
            all_results.append(result)

    # Print results
    print_results_table(all_results)

    # Compute and print parameter impact
    impacts = compute_parameter_impact(all_results)
    print("\nPARAMETER IMPACT (average F1 range across datasets):")
    for param, impact in sorted(impacts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {param}: ΔF1 = {impact:.4f}")

    # Save results
    output_path = project_root / "output" / "sensitivity_runs" / "sensitivity_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(all_results, output_path)

    print("\n✅ Sensitivity analysis completed!")


if __name__ == "__main__":
    main()
