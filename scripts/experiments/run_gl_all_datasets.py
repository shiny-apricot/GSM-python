"""
Run Group Lasso on All Datasets 🧬

Purpose:
    Execute the Group Lasso workflow on all 7 cancer GEO datasets,
    producing per-dataset results and a cross-dataset summary.
    Mirrors `run_all_datasets.py` for the GSM pipeline.

    Excluded datasets: GDS3268 (breast), GDS4206 (HCC) — see
    DATASET_EXCLUSIONS.md for rationale.

Key Functions:
    - run_all():  Iterate over datasets and invoke group_lasso_workflow()
    - summarize_runs():  Aggregate metrics across datasets

Example Usage:
    python scripts/experiments/run_gl_all_datasets.py
    python scripts/experiments/run_gl_all_datasets.py --n-iterations 5
    python scripts/experiments/run_gl_all_datasets.py --datasets GDS1962 GDS2545
"""

import argparse
import json
import logging  # <-- Moved to the top so Python knows what it is!
import sys
import time
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.utils.logger import setup_logger
from src.workflows.group_lasso_workflow import group_lasso_workflow
from src.workflows.group_lasso_workflow_config import GroupLassoConfig


##### CONSTANTS #####

# The 7 datasets used in the GSM manuscript (excluding GDS3268, GDS4206).
ALL_DATASETS = [
    "GDS1962",   # Glioblastoma
    "GDS2545",   # Prostate
    "GDS2547",   # Prostate (2)
    "GDS2771",   # Lung
    "GDS3257",   # AML
    "GDS3837",   # Colorectal
    "GDS5499",   # Pancreatic
]

DATASET_NAMES = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate",
    "GDS2547": "Prostate (2)",
    "GDS2771": "Lung",
    "GDS3257": "AML",
    "GDS3837": "Colorectal",
    "GDS5499": "Pancreatic",
}


##### CORE #####

def run_all(
    datasets: List[str] = None,
    n_iterations: int = 100,
    run_bio_validation: bool = True,
    base_output: Path = None,
) -> dict:
    """Run Group Lasso on every specified dataset.

    Args:
        datasets: List of GEO IDs. Default: all 7 cancer datasets.
        n_iterations: Iterations per dataset.
        run_bio_validation: Whether to run Enrichr/STRING validation.
        base_output: Base output directory. Each dataset gets a subfolder.

    Returns:
        Dict mapping dataset ID → {output_dir, summary, error}.
    """
    if datasets is None:
        datasets = ALL_DATASETS

    if base_output is None:
        ts = time.strftime("%Y_%m_%d-%H_%M_%S")
        base_output = project_root / "output" / f"gl_all_datasets_{ts}"
    base_output.mkdir(parents=True, exist_ok=True)

    # Master logger
    master_log = base_output / "run_all.log"
    master_logger = setup_logger(str(master_log))

    master_logger.info("=" * 75)
    master_logger.info("🚀 GROUP LASSO — ALL DATASETS RUN")
    master_logger.info(f"   Datasets: {', '.join(datasets)}")
    master_logger.info(f"   Iterations per dataset: {n_iterations}")
    master_logger.info(f"   Bio validation: {run_bio_validation}")
    master_logger.info("=" * 75)

    all_results = {}
    total_start = time.time()

    for i, ds_id in enumerate(datasets, 1):
        ds_name = DATASET_NAMES.get(ds_id, ds_id)
        master_logger.info(f"\n{'━' * 65}")
        master_logger.info(f"📊 [{i}/{len(datasets)}] {ds_id} — {ds_name}")
        master_logger.info(f"{'━' * 65}")

        ds_output = base_output / ds_id
        ds_output.mkdir(parents=True, exist_ok=True)

        config = GroupLassoConfig()
        config.main_data_path = f"data/expression_data/{ds_id}.csv"
        config.n_iterations = n_iterations
        config.run_biological_validation = run_bio_validation

        ds_log = ds_output / "group_lasso_workflow.log"
        ds_logger = setup_logger(str(ds_log))

        try:
            start = time.time()
            results = group_lasso_workflow(
                config, ds_logger, ds_output, n_iterations=n_iterations,
            )
            elapsed = time.time() - start

            summary = {
                "dataset": ds_id,
                "name": ds_name,
                "gl_f1": results.mean_f1,
                "gl_auc": results.mean_auc,
                "rf_f1": results.rf_mean_f1,
                "rf_auc": results.rf_mean_auc,
                "mean_selected_features": results.mean_selected_features,
                "time_seconds": elapsed,
            }
            all_results[ds_id] = {"output_dir": str(ds_output), "summary": summary, "error": None}

            master_logger.info(
                f"  ✅ {ds_id}: F1={results.mean_f1:.4f}±{results.std_f1:.4f}  "
                f"AUC={results.mean_auc:.4f}  ({elapsed:.0f}s)"
            )

        except Exception as e:
            master_logger.error(f"  ❌ {ds_id} FAILED: {e}")
            all_results[ds_id] = {"output_dir": str(ds_output), "summary": None, "error": str(e)}

    total_elapsed = time.time() - total_start

    # Save cross-dataset summary
    summarize_runs(all_results, base_output, master_logger)

    master_logger.info(f"\n⏱ Total time: {total_elapsed / 60:.1f} minutes")
    master_logger.info("✅ All datasets complete")
    return all_results


def summarize_runs(
    all_results: dict,
    output_dir: Path,
    logger: logging.Logger,
):
    """Save a cross-dataset summary JSON and Excel table."""
    summaries = []
    for ds_id, entry in all_results.items():
        if entry["summary"]:
            summaries.append(entry["summary"])

    if not summaries:
        logger.warning("No successful runs to summarize.")
        return

    # JSON
    json_path = output_dir / "cross_dataset_summary.json"
    with open(json_path, "w") as f:
        json.dump(summaries, f, indent=2)
    logger.info(f"💾 Saved: {json_path.name}")

    # Excel
    df = pd.DataFrame(summaries)
    xlsx_path = output_dir / "cross_dataset_summary.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {xlsx_path.name}")

    # Log table
    logger.info("\n" + "=" * 85)
    logger.info("📊 CROSS-DATASET SUMMARY")
    logger.info(f"{'Dataset':<14} {'Name':<14} {'F1':>14} {'AUC':>14} {'#Feat':>8} {'Time':>8}")
    logger.info("-" * 85)
    for s in summaries:
        logger.info(
            f"{s['dataset']:<14} {s['name']:<14} "
            f"{s.get('gl_f1', 0):.4f}  "
            f"{s.get('gl_auc', 0):.4f}  "
            f"{s.get('mean_selected_features', 0):>6.1f}  "
            f"{s.get('time_seconds', 0):>6.0f}s"
        )
    logger.info("=" * 85)

    # Grand average
    avg_f1 = np.mean([s.get("gl_f1", 0) for s in summaries])
    avg_auc = np.mean([s.get("gl_auc", 0) for s in summaries])
    logger.info(f"Grand average: F1={avg_f1:.4f}  AUC={avg_auc:.4f}")


##### FIGURE #####

def _generate_all_datasets_figure(output_dir: Path, logger: logging.Logger):
    """Bar chart of F1 and AUC across datasets."""
    json_path = output_dir / "cross_dataset_summary.json"
    if not json_path.exists():
        return

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    with open(json_path) as f:
        summaries = json.load(f)

    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    datasets = [s["dataset"] for s in summaries]
    f1s = [s["mean_f1"] for s in summaries]
    aucs = [s["mean_auc"] for s in summaries]
    f1_errs = [s["std_f1"] for s in summaries]
    auc_errs = [s["std_auc"] for s in summaries]

    x = np.arange(len(datasets))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, f1s, width, yerr=f1_errs, label="F1", color="#2E86AB", capsize=4)
    ax.bar(x + width / 2, aucs, width, yerr=auc_errs, label="AUC-ROC", color="#F18F01", capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels(datasets, rotation=30, ha="right")
    ax.set_ylabel("Score")
    ax.set_title("Group Lasso Performance Across Cancer Datasets", fontweight="bold")
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    path = fig_dir / "all_datasets_performance.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"📈 Saved: {path.name}")


##### CLI #####

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Group Lasso on all datasets")
    parser.add_argument("--datasets", nargs="+", default=None,
                        help="Dataset IDs (default: all 7)")
    parser.add_argument("--n-iterations", type=int, default=100,
                        help="Iterations per dataset (default: 100)")
    parser.add_argument("--no-bio-validation", action="store_true",
                        help="Skip biological validation")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="Base output directory")
    args = parser.parse_args()

    od = Path(args.out_dir) if args.out_dir else None
    all_results = run_all(
        datasets=args.datasets,
        n_iterations=args.n_iterations,
        run_bio_validation=not args.no_bio_validation,
        base_output=od,
    )

    # Generate cross-dataset figure after all runs.
    if od:
        base = od
    else:
        # Find the most recent gl_all_datasets_ dir.
        candidates = sorted((project_root / "output").glob("gl_all_datasets_*"))
        base = candidates[-1] if candidates else None

    if base and base.exists():
        summary_logger = setup_logger(str(base / "figures.log"))
        _generate_all_datasets_figure(base, summary_logger)