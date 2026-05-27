"""
🏎️ Scoring Model Benchmark Script

Purpose:
    Compare multiple classifiers for the GROUP SCORING phase.
    Measures speed, F1, accuracy, and ranking quality (rank correlation).
    Results are used to justify the default scoring model in the manuscript.

Usage:
    python scripts/experiments/benchmark_scoring_models.py

Output:
    Prints a table with timing, accuracy, and rank correlation for each model.
    Saves results to scripts/benchmark_results.json for manuscript inclusion.
"""

import sys
import time
import copy
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_processing.data_loader import load_input_file, load_group_file
from src.data_processing.data_preprocess import preprocess_data, preprocess_grouping_data
from src.grouping.run_grouping import run_grouping
from src.scoring.run_scoring import run_scoring
from src.data_processing.train_test_splitter import split_data


##### CONFIGURATION #####
# All models to benchmark (comprehensive comparison)
MODELS_TO_BENCHMARK = [
    "DecisionTree",
    "RandomForest",
    "ExtraTrees",
    "XGBoost",
    "GradientBoosting",
    "AdaBoost",
    "LogisticRegression",
    "KNN",
    "NaiveBayes",
    "LinearSVM",
    "SGD",
]

# Use real data for meaningful benchmarks
EXPRESSION_FILE = str(PROJECT_ROOT / "data" / "expression_data" / "GDS2545.csv")
GROUPING_FILE = str(PROJECT_ROOT / "data" / "grouping_data" / "cancer-DisGeNET_gedinet.txt")

# Pipeline settings (match production config)
CROSS_VALIDATION_FOLDS = 3
TTEST_THRESHOLD = 0.05
RANDOM_SEED = 44
TRAIN_TEST_SPLIT_RATIO = 0.7
NORMALIZATION_METHOD = "zscore"
N_JOBS = -1  # Use all CPUs


@dataclass
class BenchmarkResult:
    """Results from benchmarking a single scoring model."""
    model_name: str
    elapsed_seconds: float
    num_groups_scored: int
    mean_accuracy: float
    mean_f1: float
    std_accuracy: float = 0.0
    std_f1: float = 0.0
    group_rankings: list = None  # Ordered list of group names (best to worst)


##### LOGGING SETUP #####
def setup_logger() -> logging.Logger:
    """Create a logger for benchmark output."""
    logger = logging.getLogger("benchmark")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S"))
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


##### DATA PREPARATION #####
def prepare_benchmark_data(logger: logging.Logger):
    """
    Load and preprocess data once so all models benchmark on identical data.
    Mirrors the exact steps from gsm_run() + gsm_main_loop().

    Returns:
        Tuple of (train_x, train_labels, groups, output_dir)
    """
    logger.info("📂 Loading expression data...")
    input_data = load_input_file(EXPRESSION_FILE, separator=",")
    logger.info(f"   Loaded {input_data.shape[0]} samples × {input_data.shape[1] - 1} genes")

    # Load grouping data
    logger.info("📂 Loading grouping data...")
    group_data = load_group_file(GROUPING_FILE, separator=",")
    logger.info(f"   Loaded {group_data.shape[0]} gene-group mappings")

    # Preprocess (normalize, convert labels, balance)
    logger.info("🔄 Preprocessing (normalize + balance)...")
    data_preprocessed = preprocess_data(
        input_data,
        "class",
        logger=logger,
        label_of_negative_class="neg",
        label_of_positive_class="pos",
        normalization_method=NORMALIZATION_METHOD,
    )

    # Validate grouping data
    group_data_processed = preprocess_grouping_data(
        group_data,
        gene_column_name="feature_id",
        group_column_name="group_name",
        logger=logger,
    )

    # Train/test split (same as iteration 1 in actual pipeline)
    logger.info("✂️  Splitting train/test...")
    np.random.seed(RANDOM_SEED)
    iteration_seed = RANDOM_SEED + 1  # Same as generate_iteration_seed for iteration 1
    test_size = round(1.0 - TRAIN_TEST_SPLIT_RATIO, 4)
    split_result = split_data(
        data_preprocessed, "class",
        test_size=test_size, stratify=True,
        random_state=iteration_seed,
    )
    train_x = split_result.X_train
    train_labels = split_result.y_train
    logger.info(f"   Train: {train_x.shape[0]} samples × {train_x.shape[1]} features")

    # T-test filtering (on training data only)
    logger.info("🔬 Filtering genes by t-test...")
    from src.data_processing.preliminary_filtering import preliminary_ttest_filter
    filter_result = preliminary_ttest_filter(
        train_x, train_labels,
        threshold=TTEST_THRESHOLD,
        initial_feature_filter_size=0,
        logger=logger,
    )
    if filter_result.selected_feature_names is not None:
        filtered_feature_names = list(filter_result.selected_feature_names)
    else:
        filtered_feature_names = list(train_x.columns[filter_result.selected_features])
    logger.info(f"   {len(filtered_feature_names)} genes passed t-test filter")

    # Gene grouping
    logger.info("🗂️  Preparing gene groups...")
    groups = run_grouping(
        group_data_processed,
        filtered_features=filtered_feature_names,
        gene_column_name="feature_id",
        group_column_name="group_name",
        logger=logger,
    )
    logger.info(f"   {len(groups)} groups prepared")

    # Create temporary output directory for benchmark
    output_dir = PROJECT_ROOT / "output" / "_benchmark_temp"
    output_dir.mkdir(parents=True, exist_ok=True)

    return train_x, train_labels, groups, output_dir


##### BENCHMARK RUNNER #####
def benchmark_single_model(
    model_name: str,
    data_x: pd.DataFrame,
    labels: pd.Series,
    groups,
    output_dir: Path,
    logger: logging.Logger,
) -> BenchmarkResult:
    """
    Benchmark a single scoring model.

    Args:
        model_name: Name of the classifier to use
        data_x: Training feature matrix
        labels: Training labels
        groups: Gene group mappings
        output_dir: Directory for intermediate results
        logger: Logger instance

    Returns:
        BenchmarkResult with timing and quality metrics
    """
    logger.info(f"⏱️  Benchmarking {model_name}...")

    # Set seed for reproducibility
    np.random.seed(RANDOM_SEED)

    # Deep copy groups to avoid mutation between benchmarks
    groups_copy = copy.deepcopy(groups)

    start_time = time.perf_counter()

    scoring_results = run_scoring(
        data_x=data_x,
        labels=labels,
        model_name=model_name,
        groups=groups_copy,
        output_dir=output_dir / model_name,
        iteration=1,
        logger=logger,
        cross_validation_folds=CROSS_VALIDATION_FOLDS,
        n_jobs=N_JOBS,
    )

    elapsed = time.perf_counter() - start_time

    ranked = scoring_results.ranked_groups
    group_names = [m.name for m in ranked]
    accuracies = [m.accuracy for m in ranked]
    f1_scores = [m.f1 for m in ranked]

    return BenchmarkResult(
        model_name=model_name,
        elapsed_seconds=elapsed,
        num_groups_scored=len(ranked),
        mean_accuracy=float(np.mean(accuracies)) if accuracies else 0.0,
        mean_f1=float(np.mean(f1_scores)) if f1_scores else 0.0,
        std_accuracy=float(np.std(accuracies)) if accuracies else 0.0,
        std_f1=float(np.std(f1_scores)) if f1_scores else 0.0,
        group_rankings=group_names,
    )


##### RANKING COMPARISON #####
def compare_rankings(
    results: list[BenchmarkResult],
    logger: logging.Logger,
) -> list[dict]:
    """
    Compute rank correlation between all model pairs.

    Uses Spearman and Kendall-tau on the top-200 groups.
    Returns a list of dicts with pairwise correlation data.
    """
    logger.info("\n📊 RANKING CORRELATION (top 200 groups)")
    logger.info("=" * 65)

    rank_maps = {}
    for r in results:
        rank_maps[r.model_name] = {name: i for i, name in enumerate(r.group_rankings)}

    common_groups = set(results[0].group_rankings)
    for r in results[1:]:
        common_groups &= set(r.group_rankings)

    reference = results[0]
    top_common = [g for g in reference.group_rankings if g in common_groups][:200]

    logger.info(f"   Common groups: {len(common_groups)}, comparing top {len(top_common)}")

    correlations = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            name_a = results[i].model_name
            name_b = results[j].model_name

            ranks_a = [rank_maps[name_a][g] for g in top_common]
            ranks_b = [rank_maps[name_b][g] for g in top_common]

            spearman_corr, spearman_p = spearmanr(ranks_a, ranks_b)
            kendall_corr, kendall_p = kendalltau(ranks_a, ranks_b)

            logger.info(f"   {name_a} vs {name_b}:")
            logger.info(f"     Spearman ρ = {spearman_corr:.4f} (p={spearman_p:.2e})")
            logger.info(f"     Kendall  τ = {kendall_corr:.4f} (p={kendall_p:.2e})")

            correlations.append({
                "model_a": name_a,
                "model_b": name_b,
                "spearman_rho": round(spearman_corr, 4),
                "spearman_p": float(spearman_p),
                "kendall_tau": round(kendall_corr, 4),
                "kendall_p": float(kendall_p),
            })

    return correlations


##### RESULTS TABLE #####
def print_results_table(results: list[BenchmarkResult], logger: logging.Logger):
    """Print a formatted comparison table sorted by F1 descending."""
    logger.info("\n" + "=" * 90)
    logger.info("🏎️  SCORING MODEL BENCHMARK RESULTS")
    logger.info("=" * 90)

    header = (
        f"{'Model':<22} {'Time (s)':>10} {'Speedup':>10} {'Groups':>8} "
        f"{'Mean F1':>10} {'Std F1':>10} {'Mean Acc':>10}"
    )
    logger.info(header)
    logger.info("-" * 90)

    # Use RandomForest as speedup baseline
    rf_time = next((r.elapsed_seconds for r in results if r.model_name == "RandomForest"), None)
    baseline_time = rf_time if rf_time else max(r.elapsed_seconds for r in results)

    # Sort by F1 descending for readability
    sorted_results = sorted(results, key=lambda r: r.mean_f1, reverse=True)

    for r in sorted_results:
        speedup = baseline_time / r.elapsed_seconds if r.elapsed_seconds > 0 else float('inf')
        speedup_str = f"{speedup:.1f}×"
        row = (
            f"{r.model_name:<22} {r.elapsed_seconds:>10.2f} {speedup_str:>10} "
            f"{r.num_groups_scored:>8} {r.mean_f1:>10.4f} {r.std_f1:>10.4f} "
            f"{r.mean_accuracy:>10.4f}"
        )
        logger.info(row)

    logger.info("=" * 90)


def save_results_json(
    results: list[BenchmarkResult],
    correlations: list[dict],
    output_path: Path,
    logger: logging.Logger,
):
    """Save benchmark results to JSON for manuscript use."""
    data = {
        "dataset": EXPRESSION_FILE,
        "cv_folds": CROSS_VALIDATION_FOLDS,
        "random_seed": RANDOM_SEED,
        "models": [],
    }

    rf_time = next((r.elapsed_seconds for r in results if r.model_name == "RandomForest"), None)
    baseline_time = rf_time if rf_time else max(r.elapsed_seconds for r in results)

    for r in sorted(results, key=lambda x: x.mean_f1, reverse=True):
        speedup = baseline_time / r.elapsed_seconds if r.elapsed_seconds > 0 else 0
        data["models"].append({
            "model": r.model_name,
            "time_s": round(r.elapsed_seconds, 2),
            "speedup_vs_rf": round(speedup, 1),
            "groups_scored": r.num_groups_scored,
            "mean_f1": round(r.mean_f1, 4),
            "std_f1": round(r.std_f1, 4),
            "mean_accuracy": round(r.mean_accuracy, 4),
            "std_accuracy": round(r.std_accuracy, 4),
        })

    data["correlations"] = correlations

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"   Saved results to {output_path}")


##### MAIN #####
def main():
    """Run the complete benchmark."""
    logger = setup_logger()

    logger.info("=" * 90)
    logger.info("🏎️  GSM SCORING MODEL BENCHMARK (COMPREHENSIVE)")
    logger.info(f"   Models: {', '.join(MODELS_TO_BENCHMARK)}")
    logger.info(f"   CV Folds: {CROSS_VALIDATION_FOLDS}")
    logger.info(f"   Parallel Jobs: {N_JOBS}")
    logger.info("=" * 90)

    # Load data once
    data_x, labels, groups, output_dir = prepare_benchmark_data(logger)

    # Benchmark each model
    results: list[BenchmarkResult] = []
    for model_name in MODELS_TO_BENCHMARK:
        try:
            result = benchmark_single_model(
                model_name=model_name,
                data_x=data_x,
                labels=labels,
                groups=groups,
                output_dir=output_dir,
                logger=logger,
            )
            results.append(result)
            logger.info(
                f"   ✅ {model_name}: {result.elapsed_seconds:.2f}s, "
                f"{result.num_groups_scored} groups, "
                f"mean F1={result.mean_f1:.4f}"
            )
        except Exception as e:
            logger.error(f"   ❌ {model_name} failed: {e}")

    # Print comparison table
    print_results_table(results, logger)

    # Compare rankings
    correlations = []
    if len(results) >= 2:
        correlations = compare_rankings(results, logger)

    # Save results to JSON for manuscript
    results_path = PROJECT_ROOT / "output" / "benchmark" / "benchmark_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    save_results_json(results, correlations, results_path, logger)

    # Cleanup temp directory
    import shutil
    shutil.rmtree(output_dir, ignore_errors=True)

    logger.info("\n✅ Benchmark complete!")


if __name__ == "__main__":
    main()
