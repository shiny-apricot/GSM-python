"""
Group Lasso & RF Hybrid Workflow 🧬🌲

Purpose:
    Implements a dual-engine workflow:
    1. Group Lasso: Identifies sparse, important disease-associated gene sets.
    2. Random Forest: Instantly tests those selected genes for non-linear predictive power.

Key Functions:
    - group_lasso_workflow():       Main orchestrator — multi-iteration evaluation.
    - load_and_prepare_data():      Loads data, duplicates overlapping genes.
    - run_single_iteration():       Train GL -> Extract Genes -> Train RF.
    - evaluate_model():             GL metrics.
    - evaluate_rf_hybrid():         RF metrics.
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from group_lasso import LogisticGroupLasso
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import StandardScaler

# --- Project-specific imports ---
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.utils.logger import setup_logger
from src.workflows.group_lasso_workflow_config import GroupLassoConfig
from src.data_processing.data_loader import _detect_separator
from src.utils.biological_validation import (
    query_enrichr,
    query_string_db,
    query_disgenet,
    save_enrichr_results,
    save_string_results,
    save_disgenet_results,
    save_validation_summary,
    save_biological_validation_explanation,
    ValidationReport,
)

##### CUSTOM EXCEPTIONS #####
class GroupLassoError(Exception): pass
class DataLoadError(GroupLassoError): pass
class GroupStructureError(GroupLassoError): pass

##### DATA STRUCTURES #####
@dataclass
class FeatureDuplicationResult:
    groups: np.ndarray
    expanded_names: list
    original_gene_map: dict
    id_to_group: dict
    group_to_id: dict
    n_original_features: int
    n_expanded_features: int
    n_duplicated_genes: int
    n_groups_used: int

@dataclass
class IterationMetrics:
    iteration: int
    seed: int
    # GL Metrics
    accuracy: float
    f1: float
    precision: float
    recall: float
    specificity: float
    auc_roc: float
    n_selected_features: int
    n_selected_groups: int
    # RF Metrics
    rf_accuracy: float = 0.0
    rf_f1: float = 0.0
    rf_precision: float = 0.0
    rf_recall: float = 0.0
    rf_specificity: float = 0.0
    rf_auc_roc: float = 0.0

@dataclass
class AggregatedResults:
    iterations: List[IterationMetrics] = field(default_factory=list)
    # GL Aggregates
    mean_f1: float = 0.0
    std_f1: float = 0.0
    mean_auc: float = 0.0
    std_auc: float = 0.0
    mean_accuracy: float = 0.0
    mean_selected_features: float = 0.0
    mean_selected_groups: float = 0.0
    # RF Aggregates
    rf_mean_f1: float = 0.0
    rf_std_f1: float = 0.0
    rf_mean_auc: float = 0.0
    rf_std_auc: float = 0.0
    rf_mean_accuracy: float = 0.0


##### MAIN WORKFLOW #####
def group_lasso_workflow(
    config: GroupLassoConfig,
    logger: logging.Logger,
    output_dir: Path,
    *,
    n_iterations: int = 10,
) -> AggregatedResults:

    logger.info("=" * 80)
    logger.info("🚀 STARTING DUAL-ENGINE WORKFLOW (GL + RF)")
    logger.info(f"   Iterations: {n_iterations} | Base seed: {config.random_seed}")
    logger.info("=" * 80)

    logger.info("🔄 Loading and preparing data...")
    X, y, dup_result = load_and_prepare_data(config, logger)
    _log_duplication_summary(dup_result, logger)

    all_metrics: List[IterationMetrics] = []
    all_selected_genes: List[List[str]] = []

    for i in range(n_iterations):
        iteration_seed = config.random_seed + (i * 1000)
        logger.info(f"\n{'─' * 60}")
        logger.info(f"📊 Iteration {i + 1}/{n_iterations}  (seed={iteration_seed})")
        logger.info(f"{'─' * 60}")

        metrics, selected_genes = run_single_iteration(
            X=X, y=y, dup_result=dup_result, config=config,
            iteration=i + 1, iteration_seed=iteration_seed, logger=logger,
        )
        all_metrics.append(metrics)
        all_selected_genes.append(selected_genes)

    results = _aggregate_results(all_metrics)
    _log_aggregated_results(results, logger)
    save_results(results, all_selected_genes, dup_result, output_dir, logger)

    if getattr(config, "run_biological_validation", False):
        try:
            top_genes = _get_top_genes_for_validation(all_selected_genes, config.biological_validation_top_genes)
            if top_genes:
                run_gl_biological_validation(top_genes=top_genes, output_dir=output_dir, config=config, logger=logger)
        except Exception as e:
            logger.warning(f"⚠️ Biological validation failed: {e}")

    logger.info("=" * 80)
    logger.info("🏁 DUAL-ENGINE WORKFLOW COMPLETE")
    logger.info("=" * 80)
    return results


##### DATA LOADING #####
def load_and_prepare_data(config: GroupLassoConfig, logger: logging.Logger) -> tuple:
    X, y = _load_expression_data(config, logger)
    group_df = _load_grouping_data(config, logger)
    dup_result = _build_duplication_map(X, group_df, config, logger)
    return X, y, dup_result

def _load_expression_data(config: GroupLassoConfig, logger: logging.Logger) -> tuple:
    logger.info(f"  📂 Loading main data from: {config.main_data_path}")
    sep = _detect_separator(config.main_data_path)
    main_df = pd.read_csv(config.main_data_path, sep=sep, encoding='unicode_escape')
    main_df.columns = main_df.columns.str.strip().str.strip('"').str.strip()

    y_raw = main_df[config.target_column]
    X = main_df.drop(columns=[config.target_column])
    X = X.apply(pd.to_numeric, errors='coerce')

    if config.missing_value_handling == "remove_rows":
        combined = pd.concat([X, y_raw], axis=1).dropna()
        X = combined.drop(columns=[config.target_column])
        y_raw = combined[config.target_column]
    elif config.missing_value_handling == "fill_mean":
        X = X.fillna(X.mean(numeric_only=True))

    y, uniques = pd.factorize(y_raw)
    return X, y

def _load_grouping_data(config: GroupLassoConfig, logger: logging.Logger) -> pd.DataFrame:
    sep = _detect_separator(config.group_data_path)
    group_df = pd.read_csv(config.group_data_path, sep=sep, header=0)
    for col in group_df.columns:
        if group_df[col].dtype == object:
            group_df[col] = group_df[col].str.strip().str.strip('\r')
    group_df.columns = [c.strip().strip('\r') for c in group_df.columns]
    return group_df

def _build_duplication_map(X: pd.DataFrame, group_df: pd.DataFrame, config: GroupLassoConfig, logger: logging.Logger) -> FeatureDuplicationResult:
    feature_col = [c for c in group_df.columns if c != config.group_name_column][0]
    available_genes = set(X.columns)
    relevant = group_df[group_df[feature_col].isin(available_genes)].copy()

    min_size = getattr(config, "min_genes_per_group", 0)
    if min_size > 0:
        group_sizes = relevant.groupby(config.group_name_column)[feature_col].nunique()
        kept_groups = set(group_sizes[group_sizes >= min_size].index)
        relevant = relevant[relevant[config.group_name_column].isin(kept_groups)]

    max_dup = getattr(config, "max_groups_per_gene", 0)
    if max_dup > 0:
        relevant = relevant.sort_values(config.group_name_column)
        relevant = relevant.groupby(feature_col).head(max_dup).reset_index(drop=True)

    unique_groups = relevant[config.group_name_column].unique()
    group_to_id = {name: idx for idx, name in enumerate(unique_groups)}
    id_to_group = {idx: name for name, idx in group_to_id.items()}

    expanded_names, expanded_groups = [], []
    original_gene_map = {}

    for _, row in relevant.iterrows():
        gene = row[feature_col]
        group_name = row[config.group_name_column]
        col_name = f"{gene}__{group_name}"
        expanded_names.append(col_name)
        expanded_groups.append(group_to_id[group_name])
        original_gene_map[col_name] = gene

    return FeatureDuplicationResult(
        groups=np.array(expanded_groups),
        expanded_names=expanded_names,
        original_gene_map=original_gene_map,
        id_to_group=id_to_group,
        group_to_id=group_to_id,
        n_original_features=len(available_genes),
        n_expanded_features=len(expanded_names),
        n_duplicated_genes=int((relevant.groupby(feature_col)[config.group_name_column].nunique() > 1).sum()),
        n_groups_used=len(set(expanded_groups)),
    )

def build_expanded_matrix(X: pd.DataFrame, dup_result: FeatureDuplicationResult) -> np.ndarray:
    expanded = np.empty((X.shape[0], len(dup_result.expanded_names)), dtype=np.float64)
    for j, col_name in enumerate(dup_result.expanded_names):
        expanded[:, j] = X[dup_result.original_gene_map[col_name]].values
    return expanded

def _log_duplication_summary(dup_result: FeatureDuplicationResult, logger: logging.Logger) -> None:
    logger.info(f"📋 Expanded features: {dup_result.n_expanded_features:,} | Groups used: {dup_result.n_groups_used:,}")

##### SINGLE ITERATION #####
def run_single_iteration(*, X: pd.DataFrame, y: np.ndarray, dup_result: FeatureDuplicationResult, config: GroupLassoConfig, iteration: int, iteration_seed: int, logger: logging.Logger) -> tuple:
    # Split
    indices = np.arange(len(y))
    train_idx, test_idx = train_test_split(indices, test_size=config.test_size, random_state=iteration_seed, stratify=y)
    X_train_raw, X_test_raw = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    # Expand & Scale for GL
    X_train_exp = build_expanded_matrix(X_train_raw, dup_result)
    X_test_exp = build_expanded_matrix(X_test_raw, dup_result)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_exp)
    X_test_scaled = scaler.transform(X_test_exp)

    # Train GL
    model = train_group_lasso(X_train_scaled, y_train, dup_result.groups, config, logger)
    metrics = evaluate_model(model, X_test_scaled, y_test, iteration=iteration, seed=iteration_seed, groups=dup_result.groups, logger=logger)
    selected_genes = extract_selected_genes(model, dup_result, logger)

    # Train RF on selected genes
    rf_stats = evaluate_rf_hybrid(X_train_raw, X_test_raw, y_train, y_test, selected_genes, iteration_seed, logger)
    
    # Attach RF metrics
    metrics.rf_accuracy = rf_stats["accuracy"]
    metrics.rf_f1 = rf_stats["f1"]
    metrics.rf_precision = rf_stats["precision"]
    metrics.rf_recall = rf_stats["recall"]
    metrics.rf_specificity = rf_stats["specificity"]
    metrics.rf_auc_roc = rf_stats["auc_roc"]

    return metrics, selected_genes

##### MODEL TRAINING & EVALUATION #####
def train_group_lasso(X_train: np.ndarray, y_train: np.ndarray, groups: np.ndarray, config: GroupLassoConfig, logger: logging.Logger) -> LogisticGroupLasso:
    model = LogisticGroupLasso(
        groups=groups, 
        group_reg=config.group_reg, 
        l1_reg=config.l1_reg, 
        n_iter=config.n_iter, 
        tol=config.tol, 
        scale_reg=config.scale_reg, 
        fit_intercept=config.fit_intercept, 
        random_state=config.random_seed, 
        warm_start=config.warm_start,
        subsampling_scheme=config.subsampling_scheme,
        supress_warning=True
    )
    start = time.time()
    model.fit(X_train, y_train)
    logger.info(f"  GL trained in {time.time() - start:.1f}s")
    return model

def evaluate_model(model: LogisticGroupLasso, X_test: np.ndarray, y_test: np.ndarray, *, iteration: int, seed: int, groups: np.ndarray, logger: logging.Logger) -> IterationMetrics:
    y_pred = model.predict(X_test)
    try:
        y_prob = model.predict_proba(X_test)
        auc = float(roc_auc_score(y_test, y_prob[:, 1] if y_prob.ndim > 1 else y_prob.ravel()))
    except (AttributeError, ValueError):
        auc = 0.0

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    mask = model.sparsity_mask_
    n_sel_features = int(np.sum(mask))

    m = IterationMetrics(
        iteration=iteration, seed=seed,
        accuracy=accuracy_score(y_test, y_pred),
        f1=f1_score(y_test, y_pred, average='weighted'),
        precision=precision_score(y_test, y_pred, average='weighted', zero_division=0),
        recall=recall_score(y_test, y_pred, average='weighted', zero_division=0),
        specificity=tn / (tn + fp) if (tn + fp) > 0 else 0.0,
        auc_roc=auc,
        n_selected_features=n_sel_features,
        n_selected_groups=len(np.unique(groups[mask])) if n_sel_features > 0 else 0,
    )
    logger.info(f"  ➖ GL Baseline: F1={m.f1:.3f} | AUC={m.auc_roc:.3f} | Features={m.n_selected_features}")
    return m

def evaluate_rf_hybrid(X_train: pd.DataFrame, X_test: pd.DataFrame, y_train: np.ndarray, y_test: np.ndarray, selected_genes: List[str], seed: int, logger: logging.Logger) -> dict:
    available = [g for g in selected_genes if g in X_train.columns]
    if not available:
        logger.warning("  ⚠️ No GL-selected genes found for RF. Scoring 0.0")
        return {"accuracy": 0.0, "f1": 0.0, "precision": 0.0, "recall": 0.0, "specificity": 0.0, "auc_roc": 0.0}

    X_tr, X_te = X_train[available].values, X_test[available].values
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    rf = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1, class_weight="balanced")
    rf.fit(X_tr_s, y_train)
    y_pred = rf.predict(X_te_s)
    
    try:
        y_prob = rf.predict_proba(X_te_s)
        auc = float(roc_auc_score(y_test, y_prob[:, 1] if y_prob.ndim > 1 else y_prob.ravel()))
    except ValueError:
        auc = 0.0

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred, average='weighted')),
        "precision": float(precision_score(y_test, y_pred, average='weighted', zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, average='weighted', zero_division=0)),
        "specificity": tn / (tn + fp) if (tn + fp) > 0 else 0.0,
        "auc_roc": auc
    }
    logger.info(f"  🌲 RF Hybrid:   F1={metrics['f1']:.3f} | AUC={metrics['auc_roc']:.3f} | Acc={metrics['accuracy']:.3f}")
    return metrics

def extract_selected_genes(model: LogisticGroupLasso, dup_result: FeatureDuplicationResult, logger: logging.Logger) -> List[str]:
    mask = model.sparsity_mask_
    if not np.any(mask): return []
    sel_exp = [name for name, sel in zip(dup_result.expanded_names, mask) if sel]
    return sorted(set(dup_result.original_gene_map[n] for n in sel_exp))


##### AGGREGATION & SAVING #####
def _aggregate_results(metrics_list: List[IterationMetrics]) -> AggregatedResults:
    return AggregatedResults(
        iterations=metrics_list,
        mean_f1=float(np.mean([m.f1 for m in metrics_list])),
        std_f1=float(np.std([m.f1 for m in metrics_list])),
        mean_auc=float(np.mean([m.auc_roc for m in metrics_list])),
        std_auc=float(np.std([m.auc_roc for m in metrics_list])),
        mean_accuracy=float(np.mean([m.accuracy for m in metrics_list])),
        mean_selected_features=float(np.mean([m.n_selected_features for m in metrics_list])),
        mean_selected_groups=float(np.mean([m.n_selected_groups for m in metrics_list])),
        rf_mean_f1=float(np.mean([m.rf_f1 for m in metrics_list])),
        rf_std_f1=float(np.std([m.rf_f1 for m in metrics_list])),
        rf_mean_auc=float(np.mean([m.rf_auc_roc for m in metrics_list])),
        rf_std_auc=float(np.std([m.rf_auc_roc for m in metrics_list])),
        rf_mean_accuracy=float(np.mean([m.rf_accuracy for m in metrics_list])),
    )

def _log_aggregated_results(r: AggregatedResults, logger: logging.Logger) -> None:
    logger.info("\n" + "=" * 60)
    logger.info("📊 AGGREGATED RESULTS (GL vs HYBRID)")
    logger.info("   [Group Lasso (Linear)]")
    logger.info(f"   F1:       {r.mean_f1:.4f} ± {r.std_f1:.4f}")
    logger.info(f"   AUC-ROC:  {r.mean_auc:.4f} ± {r.std_auc:.4f}")
    logger.info("   [Random Forest (Hybrid)]")
    logger.info(f"   F1:       {r.rf_mean_f1:.4f} ± {r.rf_std_f1:.4f}")
    logger.info(f"   AUC-ROC:  {r.rf_mean_auc:.4f} ± {r.rf_std_auc:.4f}")
    logger.info("=" * 60)

def save_results(results: AggregatedResults, all_selected_genes: List[List[str]], dup_result: FeatureDuplicationResult, output_dir: Path, logger: logging.Logger) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_data = {
        "summary": {
            "mean_f1": results.mean_f1, "std_f1": results.std_f1, "mean_auc": results.mean_auc,
            "rf_mean_f1": results.rf_mean_f1, "rf_std_f1": results.rf_std_f1, "rf_mean_auc": results.rf_mean_auc,
            "mean_selected_features": results.mean_selected_features
        },
        "iterations": [asdict(m) for m in results.iterations],
    }
    json_path = output_dir / "group_lasso_results.json"
    with open(json_path, "w") as f: json.dump(metrics_data, f, indent=2)
    pd.DataFrame([asdict(m) for m in results.iterations]).to_excel(output_dir / "iteration_metrics.xlsx", index=False)
    
    gene_freq = {}
    for genes in all_selected_genes:
        for g in genes: gene_freq[g] = gene_freq.get(g, 0) + 1
    if gene_freq:
        freq_df = pd.DataFrame(sorted(gene_freq.items(), key=lambda x: -x[1]), columns=["gene", "selection_count"])
        freq_df.to_excel(output_dir / "gene_selection_frequency.xlsx", index=False)

def _get_top_genes_for_validation(all_selected_genes: List[List[str]], top_n: int) -> List[str]:
    gene_freq = {}
    for genes in all_selected_genes:
        for g in genes: gene_freq[g] = gene_freq.get(g, 0) + 1
    return [gene for gene, _ in sorted(gene_freq.items(), key=lambda x: -x[1])[:top_n]]

if __name__ == "__main__":
    config = GroupLassoConfig()
    timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
    output_dir = Path(__file__).resolve().parents[2] / "output" / f"glasso_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(str(output_dir / "group_lasso_workflow.log"))
    group_lasso_workflow(config, logger, output_dir, n_iterations=10)