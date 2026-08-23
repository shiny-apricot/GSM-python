
"""
🧬 GSM_pipeline.py - Main Pipeline Implementation for Gene Analysis

Purpose:
    Core implementation of the Grouping-Scoring-Modeling (GSM) pipeline for gene analysis.
    This pipeline processes gene expression data through multiple stages to identify
    significant gene groups and build predictive models.

Key Components:
    1. Data Preprocessing: Normalizes and validates input data
    2. Grouping: Groups genes based on biological relationships
    3. Scoring: Evaluates gene groups using ML metrics
    4. Modeling: Trains and validates ML models on selected groups

Key Functions:
    📊 gsm_run: Main entry point - orchestrates the complete pipeline execution
    🔄 gsm_main_loop: Core processing loop implementing the GSM workflow stages

Usage Example:
    >>> # Load input data
    >>> expression_data = pd.read_csv("expression_data.csv")
    >>> group_data = pd.read_csv("group_data.csv")
    >>> logger = setup_logger()
    >>> 
    >>> # Configure and run pipeline
    >>> config = GSMConfig(sample_ratio=0.8, n_iteration_workflow=5)
    >>> gsm_run(expression_data, group_data, logger, config)

Notes:
    - Ensures reproducibility through fixed random seeds
    - Implements comprehensive error handling and logging
    - Supports both notebook and script execution modes

File Map:
    Runtime config + logging:
        - format_duration(), save_runtime_config(), build_runtime_log_items(),
          log_runtime_config()

    Group utilities:
        - count_unique_features_for_top_groups(): avoids duplicate features
        - expand_groups_until_feature_increase(): ensures feature growth

    Pipeline entry point:
        - gsm_run(): validates inputs, orchestrates Phase I–III, writes outputs
          Sub-steps inside: data load → preprocess → grouping → scoring →
          modeling → rank aggregation → validation → bundling

    Core loop:
        - gsm_main_loop(): per-iteration split, filter, group, score, model

    Seeds + CLI:
        - generate_iteration_seed(), set_random_seed(), main()
"""

##### Imports #####
import sys
import json
from pathlib import Path
import logging

# Add the project root to the Python path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.workflows.GSM_workflow_config import (INPUT_EXPRESSION_DATA, INPUT_GROUP_DATA, OUTPUT_DIR, 
                        RANDOM_SEED, CROSS_VALIDATION_FOLDS, NUMBER_OF_ITERATIONS,
                        GENE_COLUMN_NAME, GROUP_COLUMN_NAME, INITIAL_FEATURE_FILTER_SIZE,
                        TTEST_THRESHOLD,
                        SAVE_INTERMEDIATE_RESULTS, TRAIN_TEST_SPLIT_RATIO, MODEL_NAME, LABEL_COLUMN_NAME, NORMALIZATION_METHOD,
                        CLASS_LABELS_NEGATIVE, CLASS_LABELS_POSITIVE, BEST_GROUPS_TO_KEEP,
                        MAIN_DATA_FILE_SEPARATOR,
                        GROUPING_FILE_SEPARATOR,
                        APPLY_CLASS_BALANCING, MIN_CLASS_BALANCE_RATIO, SAMPLING_METHOD,
                        SCORING_MODEL,
                        RUN_BIOLOGICAL_VALIDATION, BIOLOGICAL_VALIDATION_TOP_GENES,
                        DISGENET_API_KEY)

# Import the config module itself (not only constants) so we can log where it
# was loaded from at runtime. This is critical for debugging “wrong config file
# / stale notebook kernel / wrong checkout” issues.
import src.workflows.GSM_workflow_config as gsm_workflow_config

import pandas as pd
from dataclasses import dataclass
from typing import Callable, List, Optional
import numpy as np
import random
from datetime import datetime, timedelta

# Updated imports to use correct module paths
from src.grouping.run_grouping import run_grouping
from src.scoring.run_scoring import run_scoring, score_all_features
from src.scoring.feature_scorer import FeatureScore
from src.utils.save_ranked_features import (
    save_ranked_features,
    FeatureRankingOutput,
)
from src.modeling.run_modeling import ModelingResult, run_modeling, select_features_from_top_groups
from src.data_processing.data_loader import load_input_file, load_group_file
from src.data_processing.data_preprocess import preprocess_data, preprocess_grouping_data
from src.data_processing.train_test_splitter import split_data
from src.data_processing.preliminary_filtering import preliminary_ttest_filter
from src.utils import save_results
from src.utils.visualization import visualize_f1_scores
from src.utils.logger import setup_logger  # Add this import at the top with other imports
from src.utils.generate_figures import generate_all_figures
from src.utils.rank_aggregation import (
    load_ranked_groups_from_excel,
    load_ranked_features_from_excel,
    aggregate_group_ranks_rra,
    aggregate_feature_ranks_rra,
    save_aggregated_group_ranking,
    save_aggregated_feature_ranking,
    compute_best_averaged_groups,
    compute_best_averaged_features,
    save_best_averaged_rankings,
    aggregate_model_feature_importance_rra
)
from src.utils.biological_validation import run_biological_validation
from src.utils.feature_stability import compute_feature_stability, save_feature_stability_report
from src.data_processing.normalization import fit_scaler, normalize_within_split
from src.inference.model_bundle import (
    ModelArtifact,
    save_bundle as save_model_bundle,
)
import time

##### Helper Functions #####
def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}min"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}min"


def _write_progress(
    progress_file: Path,
    *,
    phase: str,
    iteration: int = 0,
    total: int = 0,
    elapsed: float = 0.0,
    eta_seconds: float = 0.0,
) -> None:
    """Write a small JSON progress file for background job monitoring."""
    data = {
        "phase": phase,
        "iteration": iteration,
        "total": total,
        "elapsed": round(elapsed, 1),
        "eta_seconds": round(eta_seconds, 1),
    }
    progress_file.write_text(json.dumps(data))


##### Data Structures #####
@dataclass
class IterationResult:
    """Track results and metadata for each GSM iteration."""
    iteration: int
    random_seed: int
    modeling_results: List[ModelingResult]


@dataclass
class ConfigLogItem:
    """Single config item for log output."""
    name: str
    value: str


@dataclass
class FeatureCountResult:
    """Feature count result for a specific top-N group selection."""
    top_group_count: int
    unique_feature_count: int


@dataclass
class AdjustedGroupSelection:
    """Final group selection after enforcing feature diversity."""
    requested_top_groups: int
    used_top_groups: int
    requested_feature_count: int
    used_feature_count: int
    baseline_feature_count: int


def save_runtime_config(*, output_dir: Path, runtime_params: dict, logger) -> None:
    """Save the actual runtime parameters as JSON (not the static config file)."""
    try:
        config_path = output_dir / "runtime_config.json"
        with open(config_path, "w") as f:
            json.dump(runtime_params, f, indent=2, default=str)
        logger.debug("Runtime config saved")
    except Exception as exc:
        logger.warning(f"Could not save runtime config: {exc}")


def build_runtime_log_items(runtime_params: dict) -> List[ConfigLogItem]:
    """Build the list of runtime config variables for logging.
    
    Logs the ACTUAL runtime parameters passed to the pipeline,
    not the static values from the config file. This prevents
    confusion when callers override config defaults.
    """
    return [
        ConfigLogItem(name, str(value))
        for name, value in runtime_params.items()
    ]


def log_runtime_config(*, runtime_params: dict, logger) -> None:
    """Log the actual runtime configuration as a compact block."""
    items = build_runtime_log_items(runtime_params)
    config_str = " | ".join(f"{item.name}={item.value}" for item in items)
    logger.info(f"Runtime Config: {config_str}")


def count_unique_features_for_top_groups(
    *,
    group_ranks,
    group_feature_mapping,
    top_n_groups: int,
    data_columns,
    logger
) -> FeatureCountResult:
    """Count valid unique features for the top-N groups."""
    feature_result = select_features_from_top_groups(
        group_ranks,
        group_feature_mapping,
        top_n_groups,
        logger
    )
    available = [f for f in feature_result.selected_features if f in data_columns]
    return FeatureCountResult(top_group_count=top_n_groups, unique_feature_count=len(available))


def expand_groups_until_feature_increase(
    *,
    requested_top_groups: int,
    group_ranks,
    group_feature_mapping,
    data_columns,
    baseline_feature_count: int,
    logger
) -> AdjustedGroupSelection:
    """Increase top-N groups until features increase vs. the baseline or groups are exhausted."""
    max_groups = len(group_ranks)
    base = count_unique_features_for_top_groups(
        group_ranks=group_ranks,
        group_feature_mapping=group_feature_mapping,
        top_n_groups=min(requested_top_groups, max_groups),
        data_columns=data_columns,
        logger=logger
    )
    if base.unique_feature_count > baseline_feature_count:
        return AdjustedGroupSelection(
            requested_top_groups=base.top_group_count,
            used_top_groups=base.top_group_count,
            requested_feature_count=base.unique_feature_count,
            used_feature_count=base.unique_feature_count,
            baseline_feature_count=baseline_feature_count
        )
    current = base
    while current.top_group_count < max_groups:
        candidate = count_unique_features_for_top_groups(
            group_ranks=group_ranks,
            group_feature_mapping=group_feature_mapping,
            top_n_groups=current.top_group_count + 1,
            data_columns=data_columns,
            logger=logger
        )
        if candidate.unique_feature_count > baseline_feature_count:
            current = candidate
            break
        current = candidate
    return AdjustedGroupSelection(
        requested_top_groups=base.top_group_count,
        used_top_groups=current.top_group_count,
        requested_feature_count=base.unique_feature_count,
        used_feature_count=current.unique_feature_count,
        baseline_feature_count=baseline_feature_count
    )

def gsm_run(
    input_data: pd.DataFrame,
    group_data: pd.DataFrame,
    *,  # Force named parameters
    sample_ratio: float = TRAIN_TEST_SPLIT_RATIO,
    n_iterations: int = NUMBER_OF_ITERATIONS,
    model_name: str = MODEL_NAME,
    label_column: str = LABEL_COLUMN_NAME,
    positive_class_label: str = CLASS_LABELS_POSITIVE,
    negative_class_label: str = CLASS_LABELS_NEGATIVE,
    gene_column: str = GENE_COLUMN_NAME,
    group_column: str = GROUP_COLUMN_NAME,
    normalization_method: str = NORMALIZATION_METHOD,
    initial_feature_filter_size: int = INITIAL_FEATURE_FILTER_SIZE,
    initial_seed: int = RANDOM_SEED,
    ttest_threshold: float = TTEST_THRESHOLD,
    cross_validation_folds: int = CROSS_VALIDATION_FOLDS,
    best_groups_to_keep: int = BEST_GROUPS_TO_KEEP,
    save_intermediate_results: bool = SAVE_INTERMEDIATE_RESULTS,
    apply_class_balancing: bool = APPLY_CLASS_BALANCING,
    min_class_balance_ratio: float = MIN_CLASS_BALANCE_RATIO,
    sampling_method: str = SAMPLING_METHOD,
    scoring_model: str = SCORING_MODEL,
    run_biological_validation_flag: bool = RUN_BIOLOGICAL_VALIDATION,
    biological_validation_top_genes: int = BIOLOGICAL_VALIDATION_TOP_GENES,
    disgenet_api_key: str = DISGENET_API_KEY,
    logger_path: Optional[Path] = None,
    notebook_mode: bool = False,
    extra_handlers: Optional[List[logging.Handler]] = None,
    input_data_name: Optional[str] = None,
    group_data_name: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    progress_file: Optional[Path] = None,
    run_name: Optional[str] = None,
) -> Path:
    """
    Main entry point for the GSM pipeline execution.
    
    Args:
        input_data: Gene expression matrix (samples × genes)
        group_data: Gene grouping information
        sample_ratio: Train/test split ratio
        n_iterations: Number of GSM workflow iterations
        model_name: Selected ML model identifier
        label_column: Column name containing class labels
        normalization_method: Data normalization strategy
        initial_seed: Starting seed for reproducibility
        logger_path: Path where log files will be stored
        notebook_mode: Enable notebook-specific optimizations
        input_data_name: Name of input data source (for logging/output folder)
        group_data_name: Name of grouping data source (for logging/output folder)
        progress_callback: Optional callable(iteration, total, elapsed, eta_seconds)
            invoked after each iteration for live progress updates (foreground).
        progress_file: Optional path to a JSON file where iteration progress is
            written after each iteration (useful for background job monitoring).
        run_name: Optional human-readable label for this experiment.
            Appended to the output folder name and stored in runtime_config.json
            and the model bundle metadata.  Keep it short and filesystem-safe.
        
    Returns:
        Path: The directory where results were saved.
    """
    # Use provided names or fall back to config file values
    main_data_stem = input_data_name if input_data_name else Path(INPUT_EXPRESSION_DATA).stem
    group_data_stem = group_data_name if group_data_name else Path(INPUT_GROUP_DATA).stem

    # Sanitise run_name for filesystem safety (keep alphanumerics, hyphens, underscores)
    _safe_run_name = ""
    if run_name:
        import re as _re
        _safe_run_name = _re.sub(r"[^\w\-]", "_", run_name.strip())[:60]

    _folder_suffix = f"_{_safe_run_name}" if _safe_run_name else ""
    output_folder_path = Path(OUTPUT_DIR) / f"gsm_{time.strftime('%Y_%m_%d-%H_%M_%S')}_{main_data_stem}_{group_data_stem}{_folder_suffix}"
    output_folder_path.mkdir(parents=True, exist_ok=True)
    if logger_path is None:
        logger_path = output_folder_path / "gsm_workflow.log"

    logger = setup_logger(str(logger_path),
                          logger_name='GSM_workflow_logger')

    if n_iterations < 1:
        raise ValueError(f"n_iterations must be >= 1, got {n_iterations}")

    # Build runtime params dict — these are the ACTUAL values used by this run,
    # not necessarily what's in the config file. Log these to prevent confusion.
    runtime_params = {
        "run_name": run_name or "",
        "input_data": main_data_stem,
        "input_shape": list(input_data.shape),
        "grouping_data": group_data_stem,
        "grouping_shape": list(group_data.shape),
        "n_iterations": n_iterations,
        "sample_ratio": sample_ratio,
        "model_name": model_name,
        "label_column": label_column,
        "positive_class_label": positive_class_label,
        "negative_class_label": negative_class_label,
        "gene_column": gene_column,
        "group_column": group_column,
        "normalization_method": normalization_method,
        "initial_feature_filter_size": initial_feature_filter_size,
        "initial_seed": initial_seed,
        "ttest_threshold": ttest_threshold,
        "cross_validation_folds": cross_validation_folds,
        "best_groups_to_keep": best_groups_to_keep,
        "save_intermediate_results": save_intermediate_results,
        "apply_class_balancing": apply_class_balancing,
        "min_class_balance_ratio": min_class_balance_ratio,
        "sampling_method": sampling_method,
        "scoring_model": scoring_model,
        "run_biological_validation": run_biological_validation_flag,
        "biological_validation_top_genes": biological_validation_top_genes,
    }

    logger.info(
        f"GSM Pipeline | data={main_data_stem} {input_data.shape} | "
        f"groups={group_data_stem} {group_data.shape} | "
        f"iters={n_iterations} | model={model_name}"
    )
    
    # Log the actual runtime config (not the static config file values)
    log_runtime_config(runtime_params=runtime_params, logger=logger)

    save_runtime_config(
        output_dir=output_folder_path,
        runtime_params=runtime_params,
        logger=logger,
    )
    
    if extra_handlers:
        for handler in extra_handlers:
            logger.addHandler(handler)

    logger.info("🚀 Starting GSM pipeline")

    # Write initial progress (preprocessing phase)
    if progress_file is not None:
        try:
            _write_progress(progress_file, phase="preprocessing",
                            iteration=0, total=n_iterations)
        except Exception:
            pass

    # Run the GSM pipeline
    logger.info("Preprocessing data (labels + cleaning, normalization deferred to within-split)...")
    data_preprocessed = preprocess_data(
        input_data,
        label_column,
        logger=logger,
        label_of_negative_class=negative_class_label,
        label_of_positive_class=positive_class_label,
        normalization_method=normalization_method,
        apply_class_balancing=apply_class_balancing,
        min_class_balance_ratio=min_class_balance_ratio,
        sampling_method=sampling_method,
        skip_normalization=True,  # C1 fix: normalize inside each split
    )
    logger.info("Data preprocessed (un-normalized).")

    # Fit normalization scaler on the FULL un-normalized data for inference bundle.
    # This is correct: at inference time, a new patient sample needs to be
    # normalized using the population statistics, which are best estimated
    # from the full training cohort (all samples).
    inference_scaler = fit_scaler(
        data_preprocessed,
        label_column_name=label_column,
        method=normalization_method,
    )
    logger.debug("Inference scaler fitted on full un-normalized data")

    group_data_processed = preprocess_grouping_data(group_data, 
                                                    gene_column_name=gene_column,
                                                    group_column_name=group_column,
                                                    logger=logger)
    logger.info("Grouping data validated.")

    # One-time feature scoring on full preprocessed data (reporting only)
    # This is NOT used in group ranking or modeling — purely informational.
    # Normalize with the inference scaler for consistency (this is report-only,
    # so using the full-data scaler is acceptable).
    set_random_seed(initial_seed)
    logger.info("Feature scoring (one-time)...")
    X_full = data_preprocessed.drop(columns=[label_column])
    y_full = data_preprocessed[label_column]
    # Select only the features the scaler was fitted on (same order)
    scaler_features = list(inference_scaler.feature_names_in_)
    X_full_for_scoring = X_full[scaler_features].apply(pd.to_numeric, errors='coerce').fillna(0)
    X_full_normalized = pd.DataFrame(
        inference_scaler.transform(X_full_for_scoring),
        columns=scaler_features,
        index=X_full.index,
    )
    feature_scores = score_all_features(X_full_normalized, y_full, logger, random_state=initial_seed)
    logger.info("Feature scoring done")
    features_output = output_folder_path / "individual_feature_scores.csv"
    save_ranked_features(
        FeatureRankingOutput(
            output_path=features_output,
            feature_scores=feature_scores,
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            model_name=model_name,
            iteration=0,
        ),
        logger,
    )

    iteration_results: List[IterationResult] = []
    iteration_times: List[float] = []  # Track iteration durations for ETA estimation
    collected_model_artifacts: List[ModelArtifact] = []  # For inference bundle
    pipeline_start_time = time.time()
    
    # Changed from range(n_iterations) to range(1, n_iterations + 1)
    # This ensures that for n_iterations=1, it only runs once
    for i in range(1, n_iterations + 1):
        iteration_start_time = time.time()
        
        # Set random seed for reproducibility
        iteration_seed = generate_iteration_seed(initial_seed, i)
        set_random_seed(iteration_seed)
        
        logger.info(f"{'='*50}")
        logger.info(f"Iteration {i}/{n_iterations} (seed={iteration_seed})")
        
        modeling_result = gsm_main_loop(
            data=data_preprocessed, 
            grouping_data=group_data_processed, 
            model_name=model_name,
            scoring_model=scoring_model,
            output_dir=output_folder_path,
            iteration=i,
            logger=logger,
            gene_column=gene_column,
            group_column=group_column,
            label_column=label_column,
            sample_ratio=sample_ratio,
            ttest_threshold=ttest_threshold,
            initial_feature_filter_size=initial_feature_filter_size,
            best_groups_to_keep=best_groups_to_keep,
            cross_validation_folds=cross_validation_folds,
            iteration_seed=iteration_seed,
            save_group_derived_features=(i == 1),
            normalization_method=normalization_method,
        )
        
        iteration_results.append(IterationResult(
            iteration=i,
            random_seed=iteration_seed,
            modeling_results=modeling_result
        ))

        # Collect the model from the FIXED-K step (last in the loop) for the
        # inference bundle. We do NOT pick max F1 across group counts — that
        # would be model selection on the test set (C1 reviewer concern).
        # The K value is a pre-set hyperparameter justified by sensitivity analysis.
        if modeling_result:
            fixed_k_result = modeling_result[-1]  # Last step = full K groups
            if fixed_k_result.fitted_model is not None:
                collected_model_artifacts.append(ModelArtifact(
                    model=fixed_k_result.fitted_model,
                    iteration=i,
                    f1_score=fixed_k_result.f1_score,
                    auc_roc=fixed_k_result.auc_roc,
                    num_features_used=fixed_k_result.num_features_used,
                    num_groups_used=fixed_k_result.num_groups_used,
                ))
        
        # Track iteration timing and compute ETA
        iteration_duration = time.time() - iteration_start_time
        iteration_times.append(iteration_duration)
        
        avg_time_per_iteration = sum(iteration_times) / len(iteration_times)
        remaining_iterations = n_iterations - i
        estimated_remaining_seconds = avg_time_per_iteration * remaining_iterations
        elapsed_total = time.time() - pipeline_start_time
        estimated_finish_time = datetime.now() + timedelta(seconds=estimated_remaining_seconds)
        
        if remaining_iterations > 0:
            logger.info(
                f"Iter {i}/{n_iterations} done in {format_duration(iteration_duration)} | "
                f"Elapsed {format_duration(elapsed_total)} | "
                f"ETA {estimated_finish_time.strftime('%H:%M:%S')} (~{format_duration(estimated_remaining_seconds)} left)"
            )
        else:
            logger.info(f"Iter {i}/{n_iterations} done in {format_duration(iteration_duration)}")

        # ── Progress reporting ──
        # Notify callers (foreground progress bar) via callback
        if progress_callback is not None:
            try:
                progress_callback(i, n_iterations, elapsed_total,
                                  estimated_remaining_seconds)
            except Exception:
                pass  # Never let progress reporting break the pipeline

        # Write progress file (background job monitoring)
        if progress_file is not None:
            try:
                _write_progress(
                    progress_file, phase="iteration",
                    iteration=i, total=n_iterations,
                    elapsed=elapsed_total,
                    eta_seconds=estimated_remaining_seconds,
                )
            except Exception:
                pass

    # Mark post-processing phase
    if progress_file is not None:
        try:
            total_elapsed = time.time() - pipeline_start_time
            _write_progress(progress_file, phase="post-processing",
                            iteration=n_iterations, total=n_iterations,
                            elapsed=total_elapsed, eta_seconds=0)
        except Exception:
            pass
    if progress_callback is not None:
        try:
            total_elapsed = time.time() - pipeline_start_time
            progress_callback(n_iterations, n_iterations,
                              total_elapsed, 0)
        except Exception:
            pass

    # Save results
    if save_intermediate_results:
        logger.info("Saving results...")
        save_results.save_modeling_results(
            results=[r.modeling_results for r in iteration_results],
            iteration_metadata=[save_results.IterationMetadata(
                iteration=r.iteration,
                random_seed=r.random_seed
            ) for r in iteration_results],
            output_dir=str(output_folder_path),
            experiment_name="modeling_results",
            logger=logger
        )

    # Feature stability analysis (reviewer I3)
    try:
        stability_result = compute_feature_stability(iteration_results, logger)
        save_feature_stability_report(stability_result, output_folder_path, logger)
    except Exception as e:
        logger.warning(f"Feature stability analysis failed: {e}")

    # Visualize the F1 scores across different numbers of groups for all iterations
    logger.info("Generating visualizations...")
    viz_data = []
    for res in iteration_results:
        for model_res in res.modeling_results:
            viz_data.append({
                "Iteration": res.iteration,
                "NumGroups": model_res.num_groups_used,
                "F1Score": model_res.f1_score
            })
    
    if viz_data:
        viz_df = pd.DataFrame(viz_data)
        visualize_f1_scores(viz_df, output_folder_path, logger)
    else:
        logger.warning("No data available for visualization")

    # Load results JSON for aggregation
    results_json_path = output_folder_path / "modeling_results_all_iterations.json"
    all_results_data = None
    aggregated_groups = None
    aggregated_features = None
    robust_rank_groups = None
    robust_rank_features = None

    # Consolidate per-iteration ranked group CSVs into a single Excel file
    # so the RRA aggregation code can consume it.
    try:
        ranked_groups_dir = output_folder_path / "ranked_groups"
        ranked_groups_combined_path = output_folder_path / "ranked_groups_all_iterations.xlsx"
        if ranked_groups_dir.exists():
            csv_files = sorted(ranked_groups_dir.glob("iter_*_groups.csv"))
            if csv_files:
                frames = [pd.read_csv(f) for f in csv_files]
                combined_groups_df = pd.concat(frames, ignore_index=True)
                combined_groups_df.to_excel(ranked_groups_combined_path, index=False)
                logger.debug(f"Consolidated {len(csv_files)} ranked group files")
    except Exception as e:
        logger.warning(f"Failed to consolidate ranked groups: {e}")

    # Build ranked features file from modeling results (feature_importance per iteration)
    try:
        ranked_features_combined_path = output_folder_path / "ranked_features_all_iterations.xlsx"
        if results_json_path.exists():
            with open(results_json_path, 'r') as f:
                _results_for_features = json.load(f)
            feature_rows = []
            for iter_data in _results_for_features:
                iter_num = iter_data["metadata"]["iteration"]
                # Use the fixed-K result (last/largest step, consistent with C1 fix)
                results_list = iter_data.get("results", [])
                if results_list:
                    best_result = results_list[-1]  # Last step = fixed K groups
                    fi = best_result.get("feature_importance", {})
                    for feat_name, importance in fi.items():
                        feature_rows.append({
                            "feature_name": feat_name,
                            "importance_score": importance,
                            "iteration": iter_num,
                        })
            if feature_rows:
                features_df = pd.DataFrame(feature_rows)
                features_df.to_excel(ranked_features_combined_path, index=False)
                logger.debug(f"Built ranked features file: {len(feature_rows)} entries")
    except Exception as e:
        logger.warning(f"Failed to build ranked features file: {e}")
    
    if results_json_path.exists():
        with open(results_json_path, 'r') as f:
            all_results_data = json.load(f)
        
        # Compute and save best averaged groups/features
        try:
            save_best_averaged_rankings(output_folder_path, all_results_data, logger)
            aggregated_groups = compute_best_averaged_groups(all_results_data, logger)
            aggregated_features = compute_best_averaged_features(all_results_data, logger)
        except Exception as e:
            logger.warning(f"Failed to compute averaged rankings: {e}")
        
        # Perform robust rank aggregation on groups
        try:
            ranked_groups_path = output_folder_path / "ranked_groups_all_iterations.xlsx"
            ranked_groups_lists = load_ranked_groups_from_excel(ranked_groups_path, logger)
            if ranked_groups_lists:
                aggregated_group_ranking = aggregate_group_ranks_rra(ranked_groups_lists)
                save_aggregated_group_ranking(
                    aggregated_group_ranking, 
                    output_folder_path / "aggregated_group_ranking_rra.xlsx", 
                    logger
                )
                robust_rank_groups = [
                    {
                        'Group Name': item.group_name,
                        'Aggregated P-Value': item.aggregated_p_value,
                        'Aggregated Score': item.aggregated_score,
                        'Average Rank': item.average_rank,
                        'Occurrences': item.occurrences
                    }
                    for item in aggregated_group_ranking.items
                ]
        except Exception as e:
            logger.warning(f"Failed to aggregate group rankings: {e}")
        
        # Perform robust rank aggregation on features
        try:
            ranked_features_path = output_folder_path / "ranked_features_all_iterations.xlsx"
            ranked_features_lists = load_ranked_features_from_excel(ranked_features_path, logger)
            if ranked_features_lists:
                aggregated_feature_ranking = aggregate_feature_ranks_rra(ranked_features_lists)
                save_aggregated_feature_ranking(
                    aggregated_feature_ranking,
                    output_folder_path / "aggregated_feature_ranking_rra.xlsx",
                    logger
                )
                robust_rank_features = [
                    {
                        'Feature Name': item.feature_name,
                        'Aggregated P-Value': item.aggregated_p_value,
                        'Aggregated Score': item.aggregated_score,
                        'Average Rank': item.average_rank,
                        'Average Importance': item.average_importance,
                        'Occurrences': item.occurrences
                    }
                    for item in aggregated_feature_ranking.items
                ]
        except Exception as e:
            logger.warning(f"Failed to aggregate feature rankings: {e}")

        # Perform RRA on model feature importances (XGBoost gain-based)
        try:
            model_fi_rra = aggregate_model_feature_importance_rra(
                all_results_data, output_folder_path, logger
            )
        except Exception as e:
            logger.warning(f"Failed to aggregate model feature importances: {e}")

    # Identify the best performing iteration and save a summary report
    logger.info("Generating summary report...")
    save_results.save_summary_report(
        results=[r.modeling_results for r in iteration_results],
        iteration_metadata=[save_results.IterationMetadata(
            iteration=r.iteration,
            random_seed=r.random_seed
        ) for r in iteration_results],
        output_dir=output_folder_path,
        logger=logger,
        aggregated_groups=aggregated_groups,
        aggregated_features=aggregated_features,
        robust_rank_groups=robust_rank_groups,
        robust_rank_features=robust_rank_features
    )

    # Generate publication-quality figures
    try:
        if results_json_path.exists():
            generate_all_figures(output_folder_path, results_json_path, logger)
        else:
            logger.warning("Results JSON not found, skipping figures")
    except Exception as e:
        logger.warning(f"Figure generation failed: {e}")

    # Run biological validation if enabled
    if run_biological_validation_flag and results_json_path.exists():
        try:
            logger.info("🧬 Running biological validation...")
            grouping_data_path = project_root / INPUT_GROUP_DATA
            run_biological_validation(
                output_dir=output_folder_path,
                results_json_path=results_json_path,
                logger=logger,
                disgenet_api_key=disgenet_api_key or None,
                top_n_genes=biological_validation_top_genes,
                grouping_data_path=grouping_data_path if grouping_data_path.exists() else None,
                gene_column=gene_column,
                group_column=group_column,
            )
            logger.info("✅ Biological validation completed")
        except Exception as e:
            logger.warning(f"⚠️ Biological validation failed: {e}")
            logger.warning(
                "💡 You can re-run it later with:  "
                f"python run_gsm.py bio-validate --run {output_folder_path}"
            )
            logger.warning(
                "   Or use the CLI: Browse Output Runs → "
                "Re-run biological validation"
            )
    elif run_biological_validation_flag:
        logger.warning("Biological validation skipped: results JSON not found")

    # ── Save Model Bundle for Clinical Inference ──
    if collected_model_artifacts:
        try:
            # Determine feature names and group names from the best overall model
            best_overall = max(collected_model_artifacts, key=lambda m: m.f1_score)
            # Find the corresponding ModelingResult to get feature/group names
            best_features: List[str] = []
            best_groups: List[str] = []
            for res in iteration_results:
                for mr in res.modeling_results:
                    if (mr.f1_score == best_overall.f1_score
                            and mr.used_features):
                        best_features = mr.used_features
                        best_groups = mr.used_groups
                        break
                if best_features:
                    break

            if best_features:
                bundle_path = save_model_bundle(
                    models=collected_model_artifacts,
                    feature_names=best_features,
                    group_names=best_groups,
                    scaler=inference_scaler,
                    normalization_method=normalization_method,
                    label_mapping={
                        "positive": positive_class_label,
                        "negative": negative_class_label,
                    },
                    dataset_name=main_data_stem,
                    model_name=model_name,
                    n_training_samples=len(data_preprocessed),
                    n_iterations_total=n_iterations,
                    random_seed=initial_seed,
                    output_dir=output_folder_path,
                    logger=logger,
                    run_name=run_name or "",
                )
                logger.info(f"🏥 Clinical inference bundle: {bundle_path.name}")
            else:
                logger.warning("No feature names found; skipping bundle save")
        except Exception as e:
            logger.warning(f"Model bundle save failed: {e}")
    else:
        logger.warning("No models collected; skipping bundle save")

    logger.info("✅ GSM pipeline completed successfully")
    return output_folder_path

    

##### Main Pipeline Functions #####
def gsm_main_loop(data: pd.DataFrame, 
                  grouping_data: pd.DataFrame,
                  model_name: str, 
                  output_dir: Path,
                  iteration: int,
                  logger,
                  gene_column: str = GENE_COLUMN_NAME,
                  group_column: str = GROUP_COLUMN_NAME,
                  label_column: str = LABEL_COLUMN_NAME,
                  sample_ratio: float = TRAIN_TEST_SPLIT_RATIO,
                  ttest_threshold: float = TTEST_THRESHOLD,
                  initial_feature_filter_size: int = INITIAL_FEATURE_FILTER_SIZE,
                  best_groups_to_keep: int = BEST_GROUPS_TO_KEEP,
                  cross_validation_folds: int = CROSS_VALIDATION_FOLDS,
                  scoring_model: str = SCORING_MODEL,
                  iteration_seed: int = RANDOM_SEED,
                  save_group_derived_features: bool = False,
                  normalization_method: str = NORMALIZATION_METHOD) -> List[ModelingResult]:
    """
    Executes one complete iteration of the GSM workflow.

    Pipeline Stages:
    1. Data splitting (train/test) with iteration-specific seed
    2. **Normalization (fit on train only, transform both)** — prevents leakage
    3. Preliminary feature filtering (t-test on training data only)
    4. Gene grouping analysis (using filtered features)
    5. Group performance scoring (CV on training data)
    6. Model training and evaluation (on held-out test data)

    Args:
        data: Preprocessed expression data (un-normalized; labels converted, missing handled)
        grouping_data: Processed group definitions
        model_name: Selected ML model identifier
        output_dir: Directory to save results
        iteration: Current iteration number
        logger: Pipeline logging interface
        gene_column: Column name for gene identifiers
        group_column: Column name for group identifiers
        label_column: Column name for class labels
        sample_ratio: Training set proportion (e.g. 0.7 = 70% train, 30% test)
        ttest_threshold: P-value threshold for BH-corrected t-test filtering
        initial_feature_filter_size: Max features to keep (0 = disabled)
        best_groups_to_keep: Maximum number of top groups to evaluate
        cross_validation_folds: Number of folds for stratified CV scoring
        iteration_seed: Random seed for this iteration's train/test split
        save_group_derived_features: Whether to save group-derived feature scores
        normalization_method: Normalization method ('zscore', 'minmax', 'robust')

    Technical Notes:
        - Uses stratified sampling for data splitting
        - Each iteration uses a different seed for a unique train/test split
        - **Normalization is fit on training data only (C1 leakage fix)**
        - Feature scoring is computed on training data only (no data leakage)
    """
    logger.info("##### Starting GSM Main Loop #####")
    
    # Data Splitting
    test_size = round(1.0 - sample_ratio, 4)
    logger.info(f"Split {sample_ratio:.0%}/{test_size:.0%} (seed={iteration_seed})")
    train_test_split_data = split_data(
        data, label_column, test_size=test_size, stratify=True, random_state=iteration_seed
    )
    
    # ── Normalization: fit on TRAIN only, transform both (C1 leakage fix) ──
    # Reconstruct DataFrames with label column for normalize_within_split
    train_with_label = train_test_split_data.X_train.copy()
    train_with_label[label_column] = train_test_split_data.y_train.values
    test_with_label = train_test_split_data.X_test.copy()
    test_with_label[label_column] = train_test_split_data.y_test.values

    train_norm, test_norm, _split_scaler = normalize_within_split(
        train_with_label, test_with_label,
        label_column_name=label_column,
        logger=logger,
        method=normalization_method,
    )

    # Update the split data with normalized values
    train_test_split_data.X_train = train_norm.drop(columns=[label_column])
    train_test_split_data.X_test = test_norm.drop(columns=[label_column])
    # y_train / y_test remain unchanged

    # Feature Filtering (on training data only — no data leakage)
    filtered_train = preliminary_ttest_filter(train_test_split_data.X_train, 
                                        train_test_split_data.y_train,
                                        threshold=ttest_threshold,
                                        initial_feature_filter_size=initial_feature_filter_size,
                                        logger=logger)

    # Gene Grouping

    # Pass the filtered feature names to grouping
    if filtered_train.selected_feature_names is not None:
        filtered_feature_names = list(filtered_train.selected_feature_names)
    else:
        # Fallback: use the column names from the filtered data if available
        filtered_feature_names = list(train_test_split_data.X_train.columns[filtered_train.selected_features])
    
    group_feature_mappings = run_grouping(grouping_data, 
                                          gene_column_name=gene_column,
                                          group_column_name=group_column,
                                          filtered_features=filtered_feature_names,
                                          logger=logger)

    # Group Scoring
    # Use scoring_model (fast, for ranking) instead of model_name (final prediction)
    scoring_results = run_scoring(data_x=train_test_split_data.X_train, 
                                labels=train_test_split_data.y_train,
                                model_name=scoring_model, 
                                groups=group_feature_mappings,
                                output_dir=output_dir,
                                iteration=iteration,
                                logger=logger,
                                cross_validation_folds=cross_validation_folds,
                                should_save_group_features=save_group_derived_features,
                                random_state=iteration_seed)

    # Get ranked groups from scoring results
    ranked_groups = scoring_results.ranked_groups

    # Model Training with decreasing numbers of top groups
    modeling_result_list = []
    
    # Start with top 1 group and increase to best_groups_to_keep
    if not ranked_groups:
        logger.warning("No ranked groups available for modeling")
        return modeling_result_list

    max_group_count = min(best_groups_to_keep, len(ranked_groups))
    previous_feature_count = 0
    for requested_groups in range(1, max_group_count + 1):
        selection = expand_groups_until_feature_increase(
            requested_top_groups=requested_groups,
            group_ranks=ranked_groups,
            group_feature_mapping=group_feature_mappings,
            data_columns=train_test_split_data.X_train.columns,
            baseline_feature_count=previous_feature_count,
            logger=logger
        )

        step_label = f"Step {requested_groups}/{max_group_count}"
        if selection.used_top_groups == selection.requested_top_groups:
            logger.debug(
                f"{step_label}: using top {selection.used_top_groups} groups. "
                f"Unique features: {selection.baseline_feature_count} → {selection.used_feature_count}."
            )
        elif selection.used_feature_count > selection.baseline_feature_count:
            logger.debug(
                f"{step_label}: top {selection.requested_top_groups} groups added no new features "
                f"(still {selection.baseline_feature_count}). Expanded to top "
                f"{selection.used_top_groups} groups to reach {selection.used_feature_count} unique features."
            )
        else:
            logger.debug(
                f"{step_label}: top {selection.requested_top_groups} groups added no new features "
                f"(still {selection.baseline_feature_count}). Even after expanding to "
                f"{selection.used_top_groups} groups, the feature count stayed the same."
            )

        # Run modeling with selected top groups
        modeling_result = run_modeling(
            data_train_x=train_test_split_data.X_train,
            data_train_y=train_test_split_data.y_train, 
            data_test_x=train_test_split_data.X_test,
            data_test_y=train_test_split_data.y_test,
            group_ranks=ranked_groups,
            group_feature_mapping=group_feature_mappings,
            model_name=model_name,
            top_n_groups=selection.used_top_groups,
            logger=logger,
            random_state=iteration_seed
        )
        modeling_result_list.append(modeling_result)

        if modeling_result.num_features_used > previous_feature_count:
            previous_feature_count = modeling_result.num_features_used

    # Emit a single compact modeling summary
    if modeling_result_list:
        best = max(modeling_result_list, key=lambda r: r.f1_score)
        logger.info(
            f"✅ Modeling completed: {len(modeling_result_list)} steps | "
            f"Best F1={best.f1_score:.4f} (top {best.num_groups_used} groups, "
            f"{best.num_features_used} features)"
        )
    else:
        logger.info("Modeling completed (no results)")
    return modeling_result_list

def generate_iteration_seed(initial_seed: int, iteration: int) -> int:
    """Generate a deterministic seed for each iteration based on initial seed."""
    return initial_seed + (iteration * 1000)

def set_random_seed(seed: int) -> None:
    """Set random seed for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)

##### Main Execution Function #####
def main() -> None:
    """
    Main execution function for the GSM pipeline.
    
    This function orchestrates the complete GSM workflow by:
    1. Resolving project folder and file paths
    2. Loading input expression and group data
    3. Executing the GSM pipeline
    
    Example:
        >>> main()  # Runs the complete pipeline with default configuration
    """
    # Resolve project folder path
    project_folder = Path().resolve()
    print(f"🏠 Project Folder: {project_folder}")
    
    # Set up file paths
    input_file = project_folder / INPUT_EXPRESSION_DATA
    group_file = project_folder / INPUT_GROUP_DATA
    
    print(f"📊 Loading expression data from: {input_file}")
    print(f"🔗 Loading group data from: {group_file}")
    
    # Load input data
    input_data = load_input_file(input_file, separator=MAIN_DATA_FILE_SEPARATOR)
    group_data = load_group_file(group_file, separator=GROUPING_FILE_SEPARATOR)
    
    print(f"✅ Expression data loaded: {input_data.shape}")
    print(f"✅ Group data loaded: {group_data.shape}")
    
    # Execute GSM pipeline
    print("🚀 Starting GSM workflow execution...")
    gsm_run(input_data, group_data)
    print("🎉 GSM workflow completed successfully!")

##### Script Execution Entry Point #####
if __name__ == '__main__':
    """Enable direct script execution from command line."""
    main()
