#!/usr/bin/env python3
"""
Publication Experiment Suite — Master Orchestrator

Purpose:
    Runs ALL experiments needed for the GSM manuscript in the
    correct order.  Each experiment checks whether its output
    already exists (fresh enough) and skips if so, making it
    safe to re-run after a partial failure.

Experiments (in order):
    1. Main pipeline — 7 datasets × 100 iterations (RF)
    2. Baselines     — RF-All, RF-ttest-100, LASSO, SVM-RBF
    3. Classifier comparison — RF vs XGBoost + 4 additional classifiers
    4. Sensitivity analysis  — OAT on 3 datasets
    5. Seed stability        — 7 datasets × 5 seeds × 10 iters
    6. Analyze & aggregate   — build manuscript_data.json + figures

Usage:
    python scripts/experiments/run_publication_experiments.py                 # run all
    python scripts/experiments/run_publication_experiments.py --skip-main     # skip main
    python scripts/experiments/run_publication_experiments.py --only baselines sensitivity

Note:
    This may take 12-24+ hours depending on hardware.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = project_root / "scripts" / "experiments"
MANUSCRIPT_DIR = project_root / "scripts" / "manuscript"


def _run(label: str, cmd: list[str]) -> bool:
    """Run a subprocess, print status, return success."""
    print(f"\n{'='*70}")
    print(f"🚀 {label}")
    print(f"   CMD: {' '.join(cmd[-6:])}")
    print(f"{'='*70}\n")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(project_root))
    elapsed = time.time() - t0
    ok = result.returncode == 0
    status = "✅" if ok else "❌"
    print(f"\n{status} {label} — {elapsed/60:.1f} min")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Run all publication experiments")
    parser.add_argument(
        "--only", nargs="+",
        choices=["main", "baselines", "classifiers", "sensitivity", "seed", "analyze"],
        help="Run only specific experiments",
    )
    parser.add_argument("--skip-main", action="store_true", help="Skip main pipeline runs")
    args = parser.parse_args()

    py = sys.executable
    experiments = []

    should_run = lambda name: (args.only is None or name in args.only) and not (name == "main" and args.skip_main)

    if should_run("main"):
        experiments.append((
            "Main Pipeline (7 datasets × 100 iters)",
            [py, str(EXPERIMENTS_DIR / "run_all_datasets.py"),
             "--iterations", "100", "--name", "publication-main-RF"],
        ))

    if should_run("baselines"):
        experiments.append((
            "Baselines (RF-All, RF-ttest-100, LASSO, SVM-RBF)",
            [py, str(EXPERIMENTS_DIR / "run_baselines.py")],
        ))

    if should_run("classifiers"):
        experiments.append((
            "Classifier Comparison (RF vs XGBoost on all datasets)",
            [py, str(EXPERIMENTS_DIR / "compare_classifiers_bio_validation.py")],
        ))
        experiments.append((
            "Extended Classifier Comparison (+DT, AdaBoost, GB, LR)",
            [py, str(EXPERIMENTS_DIR / "extend_classifier_comparison.py")],
        ))

    if should_run("sensitivity"):
        experiments.append((
            "Sensitivity Analysis (3 datasets × 7 configs)",
            [py, str(EXPERIMENTS_DIR / "run_sensitivity_analysis.py"),
             "--datasets", "GDS2545", "GDS2771", "GDS3257"],
        ))

    if should_run("seed"):
        experiments.append((
            "Seed Stability (7 datasets × 5 seeds)",
            [py, str(EXPERIMENTS_DIR / "seed_stability_experiment.py")],
        ))

    if should_run("analyze"):
        experiments.append((
            "Analyze Results → manuscript_data.json + figures",
            [py, str(MANUSCRIPT_DIR / "analyze_manuscript_results.py")],
        ))

    if not experiments:
        print("Nothing to run.")
        return

    total_start = time.time()
    results = []
    for label, cmd in experiments:
        ok = _run(label, cmd)
        results.append((label, ok))
        if not ok:
            print(f"\n⚠️  {label} failed — continuing with remaining experiments")

    total = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"📊 EXPERIMENT SUITE SUMMARY")
    print(f"{'='*70}")
    for label, ok in results:
        print(f"  {'✅' if ok else '❌'} {label}")
    print(f"\n⏱️  Total time: {total/3600:.1f} hours")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
