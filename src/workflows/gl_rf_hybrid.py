"""
Two-Stage GL→RF Hybrid Pipeline v2.0 🧬🌲
(t-test Pre-filter + Optuna HP Optimization + Stability Selection)

Purpose:
    A NOVEL pipeline that combines:
    - Statistical pre-filtering (Welch t-test + BH FDR) to remove noise genes
    - Bayesian hyperparameter optimization (Optuna) for (group_reg, l1_reg)
    - Stability Selection for robust feature selection with Group Lasso
    - Random Forest for non-linear classification

    Stage 0 (Pre-filter):    Welch t-test + BH FDR → discard noise genes
    Stage 1 (HP Optimize):   Multi-objective Optuna → Pareto-optimal (group_reg, l1_reg)
    Stage 2 (Select):        Stability Selection with GL at best HP → stable gene set
    Stage 3 (Classify):      Random Forest on GL-selected original genes

Key Improvements over v1:
    - t-test removes ~90% of noise genes → GL is 5-10x faster
    - Optuna replaces fixed 5-point grid → finds optimal HP automatically
    - Multi-objective (maximize F1, minimize features) → smooth Pareto curve
    - Stability Selection: 30 subsamples (was 10) → more reliable gene selection
    - scale_reg="inverse_group_size" → reduces cliff effect
    - Warmup strategy: Optuna runs ONCE, best HPs reused across iterations

Example Usage:
    python -m src.workflows.gl_rf_hybrid
    python -m src.workflows.gl_rf_hybrid --dataset GDS2545 --n-iterations 5
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from group_lasso import LogisticGroupLasso
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

import warnings
import datetime
from sklearn.exceptions import ConvergenceWarning
warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", message=".*The FISTA iterations did not converge.*")

from src.utils.logger import setup_logger
from src.utils.biological_validation import run_biological_validation
from src.workflows.group_lasso_workflow import (
    _load_expression_data,
    _load_grouping_data,
    _build_duplication_map,
    build_expanded_matrix,
    FeatureDuplicationResult,
)
from src.workflows.group_lasso_workflow_config import GroupLassoConfig

##### DATA STRUCTURES #####

@dataclass
class ParetoPoint:
    """Result for a specific regularization level on a single train/test split."""
    group_reg: float
    l1_reg: float
    n_selected_genes: int
    n_selected_groups: int
    selected_genes: List[str]
    rf_f1: float
    rf_auc: float
    rf_accuracy: float
    rf_precision: float
    rf_recall: float
    rf_specificity: float
    model_type: str = "RF"  # "RF" or "LR" — whichever won the dual-model race

@dataclass
class HybridIterationResult:
    """Result from one iteration (train/test split) of the hybrid pipeline."""
    iteration: int
    seed: int
    n_sig_genes: int = 0
    n_expanded_features: int = 0
    pareto_points: List[ParetoPoint] = field(default_factory=list)

@dataclass
class HybridResults:
    """Aggregated results across all iterations."""
    dataset: str = ""
    n_iterations: int = 0
    optuna_hps: List[dict] = field(default_factory=list)
    iterations: List[HybridIterationResult] = field(default_factory=list)


##### STAGE 0: t-TEST PRE-FILTER #####

def _apply_ttest_prefilter(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    fdr_threshold: float,
    logger: logging.Logger,
    min_genes: int = 3000,
) -> List[str]:
    """Apply Welch t-test + BH FDR correction to select significant genes.

    This mirrors GSM's Phase I: only statistically significant genes
    (training-only) proceed to Group Lasso. Removes ~90% of noise genes,
    making GL 5-10x faster and more focused.

    Dynamic Fallback: If FDR correction yields fewer than `min_genes`,
    falls back to raw p-value < 0.05 to ensure a sufficiently large
    gene pool for Group Lasso on low-signal datasets.
    """
    from scipy.stats import ttest_ind
    from statsmodels.stats.multitest import multipletests

    genes = X_train.columns.tolist()
    pvals = np.ones(len(genes))

    mask_0 = y_train == 0
    mask_1 = y_train == 1

    for i, gene in enumerate(genes):
        vals_0 = X_train[gene].values[mask_0]
        vals_1 = X_train[gene].values[mask_1]
        # Skip constant columns
        if vals_0.std() == 0 and vals_1.std() == 0:
            continue
        try:
            _, pval = ttest_ind(vals_0, vals_1, equal_var=False)
            pvals[i] = pval if not np.isnan(pval) else 1.0
        except Exception:
            pass

    # Primary: FDR-corrected p-values
    _, adj_pvals, _, _ = multipletests(pvals, method='fdr_bh')
    sig_mask = adj_pvals < fdr_threshold
    sig_genes = [g for g, s in zip(genes, sig_mask) if s]

    # Fallback: if too few genes survive FDR, use raw p-values
    if len(sig_genes) < min_genes:
        raw_mask = pvals < 0.05
        sig_genes_raw = [g for g, s in zip(genes, raw_mask) if s]
        logger.info(
            f"  🧪 t-test filter: FDR yielded only {len(sig_genes)} genes "
            f"(< {min_genes} threshold) → falling back to raw p < 0.05: "
            f"{len(sig_genes_raw)}/{len(genes)} genes"
        )
        return sig_genes_raw

    logger.info(
        f"  🧪 t-test filter: {len(sig_genes)}/{len(genes)} genes significant "
        f"(FDR < {fdr_threshold})"
    )
    return sig_genes


##### STAGE 1: OPTUNA HP OPTIMIZATION #####

def _optuna_find_pareto_hps(
    X_exp_scaled: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    config: GroupLassoConfig,
    seed: int,
    logger: logging.Logger,
) -> List[dict]:
    """Find Pareto-optimal (group_reg, l1_reg) via multi-objective Optuna.

    Objectives:
        1. Maximize weighted F1 score (primary — classifier performance)
        2. Minimize selected feature count (secondary — interpretability)

    Uses 3-fold CV with single GL fits (no stability selection) for speed.
    Typical runtime: ~30 trials × 3 folds × 3-5s = 5-8 minutes.
    """
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    n_cv_folds = getattr(config, 'optuna_n_cv_folds', 3)

    def objective(trial):
        group_reg = trial.suggest_float("group_reg", 1e-4, 1.0, log=True)
        l1_reg = trial.suggest_float("l1_reg", 1e-4, 0.5, log=True)

        skf = StratifiedKFold(
            n_splits=n_cv_folds, shuffle=True, random_state=seed
        )
        f1_scores = []
        n_features_list = []

        for fold_train, fold_val in skf.split(X_exp_scaled, y):
            model = LogisticGroupLasso(
                groups=groups,
                group_reg=group_reg,
                l1_reg=l1_reg,
                n_iter=config.n_iter,
                tol=config.tol,
                scale_reg=config.scale_reg,
                fit_intercept=config.fit_intercept,
                random_state=seed,
                warm_start=True,
                subsampling_scheme=None,
                supress_warning=True,
            )
            model.fit(X_exp_scaled[fold_train], y[fold_train])

            n_feat = int(model.sparsity_mask_.sum())
            if n_feat == 0:
                f1_scores.append(0.0)
                n_features_list.append(0)
                continue

            y_pred = model.predict(X_exp_scaled[fold_val])
            f1_val = float(f1_score(
                y[fold_val], y_pred, average='weighted', zero_division=0
            ))
            f1_scores.append(f1_val)
            n_features_list.append(n_feat)

        return float(np.mean(f1_scores)), float(np.mean(n_features_list))

    logger.info(
        f"  🔍 Optuna: {config.optuna_n_trials} trials, "
        f"{n_cv_folds}-fold CV, multi-objective (F1↑, features↓)"
    )
    start = time.time()

    study = optuna.create_study(
        directions=["maximize", "minimize"],
        sampler=optuna.samplers.TPESampler(seed=seed),
    )
    study.optimize(objective, n_trials=config.optuna_n_trials, show_progress_bar=False)

    elapsed = time.time() - start
    logger.info(f"  🔍 Optuna completed in {elapsed:.1f}s")

    return _select_pareto_configs(
        study, config.optuna_n_pareto_configs, logger,
        feature_penalty=config.optuna_feature_penalty,
    )


def _select_pareto_configs(
    study, n_top: int, logger: logging.Logger,
    feature_penalty: float = 0.0,
) -> List[dict]:
    """Select top HP configs from multi-objective Pareto front.

    Ranks Pareto-optimal trials by:
        composite = normalized_F1 - feature_penalty × normalized_log(features)

    With feature_penalty=0.0 (default), this ranks purely by F1.
    The Pareto front already handles the sparsity-performance trade-off;
    adding a second penalty caused double-penalization (the worst-F1
    config was ranked first). See commit history for details.
    """
    pareto_trials = study.best_trials

    if not pareto_trials:
        logger.warning("  ⚠️ No Pareto-optimal trials found, using defaults")
        return [{"group_reg": 0.01, "l1_reg": 0.005}]

    # Compute composite score
    f1s = [t.values[0] for t in pareto_trials]
    feats = [t.values[1] for t in pareto_trials]

    max_f1 = max(f1s) if max(f1s) > 0 else 1.0
    max_log_feat = np.log1p(max(feats)) if max(feats) > 0 else 1.0

    scored = []
    for trial in pareto_trials:
        f1_norm = trial.values[0] / max_f1 if max_f1 > 0 else 0
        feat_norm = (
            np.log1p(trial.values[1]) / max_log_feat
            if max_log_feat > 0
            else 0
        )
        # Feature penalty: 0.0 = pure F1 ranking (recommended)
        composite = f1_norm - feature_penalty * feat_norm
        scored.append((composite, trial))

    scored.sort(key=lambda x: -x[0])
    top = scored[:n_top]

    configs = []
    for rank, (score, trial) in enumerate(top, 1):
        cfg = {
            "group_reg": trial.params["group_reg"],
            "l1_reg": trial.params["l1_reg"],
            "optuna_f1": trial.values[0],
            "optuna_features": trial.values[1],
            "composite_score": score,
        }
        configs.append(cfg)
        logger.info(
            f"    Pareto #{rank}: group_reg={cfg['group_reg']:.5f}, "
            f"l1_reg={cfg['l1_reg']:.5f}, "
            f"F1={cfg['optuna_f1']:.3f}, "
            f"features={cfg['optuna_features']:.0f}, "
            f"composite={score:.3f}"
        )

    return configs


##### STAGE 2: STABILITY SELECTION #####

def _run_stability_selection(
    X_exp_scaled: np.ndarray,
    y: np.ndarray,
    dup_result: FeatureDuplicationResult,
    group_reg: float,
    l1_reg: float,
    config: GroupLassoConfig,
    seed: int,
    logger: logging.Logger,
) -> tuple:
    """Run stability selection and return (selected_original_genes, n_groups).

    Fits Group Lasso on multiple random subsamples of the training data.
    Genes selected in ≥ stability_threshold fraction of subsamples are "stable".
    """
    n_sub = config.n_stability_subsamples
    threshold = config.stability_threshold
    selection_counts = np.zeros(X_exp_scaled.shape[1])

    start = time.time()
    for s in range(n_sub):
        sub_seed = seed + s * 100
        try:
            sub_X, _, sub_y, _ = train_test_split(
                X_exp_scaled, y, test_size=0.3,
                stratify=y, random_state=sub_seed,
            )
        except ValueError:
            sub_X, _, sub_y, _ = train_test_split(
                X_exp_scaled, y, test_size=0.3, random_state=sub_seed,
            )

        model = LogisticGroupLasso(
            groups=dup_result.groups,
            group_reg=group_reg,
            l1_reg=l1_reg,
            n_iter=config.n_iter,
            tol=config.tol,
            scale_reg=config.scale_reg,
            fit_intercept=config.fit_intercept,
            random_state=sub_seed,
            warm_start=True,
            subsampling_scheme=None,
            supress_warning=True,
        )
        model.fit(sub_X, sub_y)
        selection_counts += model.sparsity_mask_.astype(int)

    elapsed = time.time() - start

    freqs = selection_counts / n_sub
    mask = freqs >= threshold
    n_sel_expanded = int(np.sum(mask))

    if n_sel_expanded == 0:
        logger.info(
            f"      StabSel (reg={group_reg:.5f}): 0 genes "
            f"({elapsed:.1f}s, {n_sub} subs)"
        )
        return [], 0

    selected_expanded = [
        name for name, sel in zip(dup_result.expanded_names, mask) if sel
    ]
    selected_originals = sorted(set(
        dup_result.original_gene_map[name] for name in selected_expanded
    ))
    n_groups = len(np.unique(dup_result.groups[mask]))

    logger.info(
        f"      StabSel (reg={group_reg:.5f}): "
        f"{len(selected_originals)} genes, {n_groups} groups "
        f"({elapsed:.1f}s, {n_sub} subs)"
    )
    return selected_originals, n_groups


##### STAGE 3: DUAL-MODEL CLASSIFICATION (LR vs RF) #####

def _classify_best_model(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: np.ndarray,
    y_test: np.ndarray,
    selected_genes: List[str],
    seed: int,
    logger: logging.Logger,
) -> dict:
    """Train both Logistic Regression and Random Forest, pick the better one.

    Uses 3-fold stratified CV on the training set to select the model
    with higher weighted F1. This prevents the pipeline from being locked
    into RF when the data is linearly separable (where LR excels).
    """
    available = [g for g in selected_genes if g in X_train.columns]
    if not available:
        logger.warning("      No GL-selected genes found in expression data!")
        return {
            "f1": 0.0, "auc": 0.0, "accuracy": 0.0,
            "precision": 0.0, "recall": 0.0, "specificity": 0.0,
            "model_type": "none",
        }

    X_tr = X_train[available].values
    X_te = X_test[available].values

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    # --- Define candidate models ---
    candidates = {
        "LR": LogisticRegression(
            max_iter=1000, random_state=seed,
            class_weight="balanced", solver="lbfgs",
        ),
        "RF": RandomForestClassifier(
            n_estimators=200, max_depth=None,
            random_state=seed, n_jobs=-1,
            class_weight="balanced",
        ),
    }

    # --- Inner CV to pick the better model ---
    cv_scores = {}
    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    for name, model in candidates.items():
        fold_f1s = []
        for fold_tr, fold_val in skf.split(X_tr_s, y_train):
            m = type(model)(**model.get_params())
            m.fit(X_tr_s[fold_tr], y_train[fold_tr])
            y_val_pred = m.predict(X_tr_s[fold_val])
            fold_f1s.append(float(f1_score(
                y_train[fold_val], y_val_pred,
                average="weighted", zero_division=0,
            )))
        cv_scores[name] = float(np.mean(fold_f1s))

    best_name = max(cv_scores, key=cv_scores.get)
    best_model = candidates[best_name]
    logger.info(
        f"      Model race: LR CV-F1={cv_scores['LR']:.4f}, "
        f"RF CV-F1={cv_scores['RF']:.4f} → winner: {best_name}"
    )

    # --- Train winner on full training set, evaluate on test ---
    best_model.fit(X_tr_s, y_train)
    y_pred = best_model.predict(X_te_s)

    if hasattr(best_model, 'predict_proba'):
        y_prob = best_model.predict_proba(X_te_s)[:, 1]
    else:
        y_prob = best_model.decision_function(X_te_s)

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except ValueError:
        auc = 0.0

    metrics = {
        "f1": float(f1_score(y_test, y_pred, average="weighted")),
        "auc": auc,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
        "specificity": specificity,
        "model_type": best_name,
    }
    logger.info(
        f"      {best_name}: F1={metrics['f1']:.4f} AUC={metrics['auc']:.4f} "
        f"Acc={metrics['accuracy']:.4f} ({len(available)} features)"
    )
    return metrics


##### SINGLE HYBRID ITERATION #####

def run_hybrid_iteration(
    X: pd.DataFrame,
    y: np.ndarray,
    group_df: pd.DataFrame,
    config: GroupLassoConfig,
    pareto_hps: List[dict],
    iteration: int,
    seed: int,
    logger: logging.Logger,
) -> HybridIterationResult:
    """Run one iteration: t-test → StabSel (per Pareto HP) → RF.

    The t-test filter is applied per-iteration on the training set
    to prevent data leakage (same as GSM's approach).
    """
    # --- Split ---
    indices = np.arange(len(y))
    train_idx, test_idx = train_test_split(
        indices, test_size=config.test_size,
        random_state=seed, stratify=y,
    )
    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y[train_idx]
    y_test = y[test_idx]
    logger.info(f"  Split: {len(train_idx)} train / {len(test_idx)} test")

    # --- Stage 0: t-test pre-filter (training-only) ---
    if config.enable_ttest_prefilter:
        sig_genes = _apply_ttest_prefilter(
            X_train, y_train, config.fdr_threshold, logger,
            min_genes=config.min_genes_after_ttest,
        )
        if len(sig_genes) < 5:
            logger.warning(
                f"  ⚠️ Only {len(sig_genes)} significant genes — "
                f"falling back to all genes"
            )
            sig_genes = X_train.columns.tolist()
        X_train_f = X_train[sig_genes]
        X_test_f = X_test[sig_genes]
    else:
        sig_genes = X_train.columns.tolist()
        X_train_f = X_train
        X_test_f = X_test

    # --- Build duplication map for filtered genes ---
    dup_result = _build_duplication_map(X_train_f, group_df, config, logger)
    X_train_exp = build_expanded_matrix(X_train_f, dup_result)
    scaler = StandardScaler()
    X_train_exp_scaled = scaler.fit_transform(X_train_exp)

    logger.info(
        f"  📋 Filtered: {len(sig_genes)} genes → "
        f"{dup_result.n_expanded_features} expanded features, "
        f"{dup_result.n_groups_used} groups"
    )

    # --- Determine HP configs to evaluate ---
    if pareto_hps:
        hp_configs = pareto_hps
    elif not config.enable_optuna:
        # Fallback to grid
        hp_configs = [
            {"group_reg": g, "l1_reg": config.l1_reg}
            for g in config.group_reg_grid
        ]
    else:
        hp_configs = [{"group_reg": config.group_reg, "l1_reg": config.l1_reg}]

    # --- Stage 2 + 3: Stability Selection → RF for each HP config ---
    pareto_points = []
    for idx, hp in enumerate(hp_configs):
        hp_start = time.time()
        g_reg = hp["group_reg"]
        l_reg = hp["l1_reg"]

        selected_genes, n_groups = _run_stability_selection(
            X_train_exp_scaled, y_train, dup_result,
            g_reg, l_reg, config, seed, logger,
        )

        hp_elapsed = time.time() - hp_start
        hps_left = len(hp_configs) - (idx + 1)
        if hps_left > 0:
            eta_str = str(datetime.timedelta(seconds=int(hp_elapsed * hps_left)))
            logger.info(f"    ⏳ ETA for remaining {hps_left} HPs: {eta_str}")

        if not selected_genes:
            pareto_points.append(ParetoPoint(
                group_reg=g_reg, l1_reg=l_reg,
                n_selected_genes=0, n_selected_groups=0,
                selected_genes=[], rf_f1=0.0, rf_auc=0.0,
                rf_accuracy=0.0, rf_precision=0.0,
                rf_recall=0.0, rf_specificity=0.0,
            ))
            continue

        rf_metrics = _classify_best_model(
            X_train_f, X_test_f, y_train, y_test,
            selected_genes, seed, logger,
        )

        pareto_points.append(ParetoPoint(
            group_reg=g_reg, l1_reg=l_reg,
            n_selected_genes=len(selected_genes),
            n_selected_groups=n_groups,
            selected_genes=selected_genes,
            rf_f1=rf_metrics["f1"], rf_auc=rf_metrics["auc"],
            rf_accuracy=rf_metrics["accuracy"],
            rf_precision=rf_metrics["precision"],
            rf_recall=rf_metrics["recall"],
            rf_specificity=rf_metrics["specificity"],
            model_type=rf_metrics.get("model_type", "RF"),
        ))

    return HybridIterationResult(
        iteration=iteration,
        seed=seed,
        n_sig_genes=len(sig_genes),
        n_expanded_features=dup_result.n_expanded_features,
        pareto_points=pareto_points,
    )


##### MAIN WORKFLOW #####

def gl_rf_hybrid_workflow(
    dataset: str = "GDS1962",
    n_iterations: int = 5,
    output_dir: Path = None,
) -> HybridResults:
    """Main entry point for the GL→RF hybrid pipeline.

    Architecture:
        1. WARMUP PHASE (once): t-test → Optuna multi-objective → Pareto HPs
        2. ITERATION PHASE (×N): t-test → StabSel with Pareto HPs → RF → metrics
    """
    if output_dir is None:
        ts = time.strftime("%Y_%m_%d-%H_%M_%S")
        output_dir = project_root / "output" / "hybrid_runs" / f"run_{ts}"
        output_dir = output_dir / dataset
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / "gl_rf_hybrid.log"
    logger = setup_logger(str(log_file))

    config = GroupLassoConfig()
    config.main_data_path = f"data/expression_data/{dataset}.csv"

    logger.info("=" * 75)
    logger.info(f"🌲 GL→RF HYBRID PIPELINE v2.0 — {dataset}")
    logger.info(f"   Iterations: {n_iterations}")
    logger.info(f"   t-test filter: {config.enable_ttest_prefilter} (FDR={config.fdr_threshold})")
    logger.info(f"   Optuna: {config.enable_optuna} ({config.optuna_n_trials} trials)")
    logger.info(f"   Stability Selection: {config.n_stability_subsamples} subsamples")
    logger.info(f"   scale_reg: {config.scale_reg}")
    logger.info("=" * 75)

    # --- Load data ---
    X, y = _load_expression_data(config, logger)
    group_df = _load_grouping_data(config, logger)

    # ===== WARMUP PHASE: Optuna HP Optimization =====
    pareto_hps: List[dict] = []
    if config.enable_optuna:
        logger.info("\n" + "─" * 60)
        logger.info("🔥 WARMUP PHASE: Optuna HP Optimization")
        logger.info("─" * 60)

        warmup_seed = config.random_seed
        warmup_indices = np.arange(len(y))
        warmup_train_idx, _ = train_test_split(
            warmup_indices, test_size=config.test_size,
            random_state=warmup_seed, stratify=y,
        )
        X_warmup = X.iloc[warmup_train_idx]
        y_warmup = y[warmup_train_idx]

        # t-test filter for warmup
        if config.enable_ttest_prefilter:
            sig_genes_warmup = _apply_ttest_prefilter(
                X_warmup, y_warmup, config.fdr_threshold, logger,
                min_genes=config.min_genes_after_ttest,
            )
            X_warmup_f = X_warmup[sig_genes_warmup]
        else:
            X_warmup_f = X_warmup

        # Build expanded matrix
        dup_warmup = _build_duplication_map(X_warmup_f, group_df, config, logger)
        X_warmup_exp = build_expanded_matrix(X_warmup_f, dup_warmup)
        X_warmup_exp_scaled = StandardScaler().fit_transform(X_warmup_exp)

        logger.info(
            f"  Warmup matrix: {X_warmup_exp_scaled.shape[0]} samples × "
            f"{X_warmup_exp_scaled.shape[1]} expanded features"
        )

        # Multi-objective Optuna
        pareto_hps = _optuna_find_pareto_hps(
            X_warmup_exp_scaled, y_warmup, dup_warmup.groups,
            config, warmup_seed, logger,
        )

    # ===== ITERATION PHASE =====
    all_results: List[HybridIterationResult] = []
    total_start = time.time()

    from tqdm import tqdm
    for i in tqdm(range(1, n_iterations + 1), desc=f"{dataset}", leave=False):
        seed = config.random_seed + (i - 1) * 44
        logger.info(f"\n{'─' * 60}")
        logger.info(f"📊 Iteration {i}/{n_iterations}  (seed={seed})")
        logger.info(f"{'─' * 60}")

        result = run_hybrid_iteration(
            X, y, group_df, config, pareto_hps, i, seed, logger,
        )
        all_results.append(result)

    total_time = time.time() - total_start

    hybrid = HybridResults(
        dataset=dataset,
        n_iterations=n_iterations,
        optuna_hps=pareto_hps,
        iterations=all_results,
    )

    logger.info(f"\n{'=' * 75}")
    logger.info(f"📊 GL→RF HYBRID RESULTS v2.0")
    logger.info(f"   ⏱  Total time: {total_time / 60:.1f} min")

    # Log summary
    for hp_idx in range(len(pareto_hps) if pareto_hps else 1):
        f1s = []
        for r in all_results:
            if hp_idx < len(r.pareto_points):
                f1s.append(r.pareto_points[hp_idx].rf_f1)
        if f1s:
            logger.info(
                f"   HP#{hp_idx+1}: Mean F1={np.mean(f1s):.4f} ± {np.std(f1s):.4f}"
            )

    logger.info(f"{'=' * 75}")

    _save_hybrid_results(hybrid, output_dir, logger)
    _generate_hybrid_figures(hybrid, output_dir, logger)

    return hybrid


##### SAVE RESULTS #####

def _save_hybrid_results(
    hybrid: HybridResults,
    output_dir: Path,
    logger: logging.Logger,
):
    """Save results to JSON and Excel."""
    data = {
        "dataset": hybrid.dataset,
        "n_iterations": hybrid.n_iterations,
        "optuna_hps": hybrid.optuna_hps,
        "iterations": [asdict(r) for r in hybrid.iterations],
    }
    json_path = output_dir / "gl_rf_hybrid_results.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"💾 Saved: {json_path.name}")

    rows = []
    for r in hybrid.iterations:
        for p in r.pareto_points:
            rows.append({
                "iteration": r.iteration,
                "seed": r.seed,
                "n_sig_genes": r.n_sig_genes,
                "group_reg": p.group_reg,
                "l1_reg": p.l1_reg,
                "n_genes": p.n_selected_genes,
                "n_groups": p.n_selected_groups,
                "rf_f1": p.rf_f1,
                "rf_auc": p.rf_auc,
                "rf_accuracy": p.rf_accuracy,
            })
    df = pd.DataFrame(rows)
    xlsx_path = output_dir / "gl_rf_pareto_iterations.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {xlsx_path.name}")


##### FIGURES #####

def _generate_hybrid_figures(
    hybrid: HybridResults,
    output_dir: Path,
    logger: logging.Logger,
):
    """Generate Pareto front and summary figures."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        logger.warning("matplotlib/seaborn not installed — skipping figures")
        return

    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Gather data
    data = []
    for r in hybrid.iterations:
        for p in r.pareto_points:
            data.append({
                "iteration": r.iteration,
                "n_genes": p.n_selected_genes,
                "rf_f1": p.rf_f1,
                "rf_auc": p.rf_auc,
                "group_reg": p.group_reg,
                "l1_reg": p.l1_reg,
            })
    df = pd.DataFrame(data)

    if df.empty:
        return

    # --- Figure 1: Pareto Front (Features vs F1) ---
    fig, ax = plt.subplots(figsize=(10, 6))

    # Individual iteration points
    valid = df[df["rf_f1"] > 0]
    if not valid.empty:
        scatter = ax.scatter(
            valid["n_genes"], valid["rf_f1"],
            c=valid["group_reg"], cmap="viridis",
            alpha=0.6, s=60, edgecolors="white", linewidth=0.5,
        )
        plt.colorbar(scatter, ax=ax, label="group_reg")

        # Mean path per HP config
        for (greg, lreg), grp in valid.groupby(["group_reg", "l1_reg"]):
            mean_genes = grp["n_genes"].mean()
            mean_f1 = grp["rf_f1"].mean()
            ax.plot(mean_genes, mean_f1, "r*", markersize=15, zorder=5)
            ax.annotate(
                f"λ={greg:.4f}\nF1={mean_f1:.3f}",
                (mean_genes, mean_f1),
                textcoords="offset points", xytext=(10, 5),
                fontsize=7, color="red",
            )

    ax.set_xlabel("Number of Selected Genes (Sparsity)", fontsize=12)
    ax.set_ylabel("Random Forest F1 Score", fontsize=12)
    ax.set_title(
        f"Sparsity vs Performance Pareto Front ({hybrid.dataset})",
        fontweight="bold", fontsize=13,
    )
    ax.grid(True, alpha=0.3)
    if not valid.empty and valid["n_genes"].max() > 100:
        ax.set_xscale("log")

    plt.tight_layout()
    path = fig_dir / "pareto_front.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"📈 Saved: {path.name}")

    # --- Figure 2: F1 Distribution Across Iterations (best HP) ---
    if len(hybrid.iterations) > 1 and hybrid.optuna_hps:
        best_f1s = []
        for r in hybrid.iterations:
            if r.pareto_points:
                best_f1s.append(max(p.rf_f1 for p in r.pareto_points))
        if best_f1s:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.bar(range(1, len(best_f1s)+1), best_f1s, color="steelblue", alpha=0.8)
            ax.axhline(np.mean(best_f1s), color="red", linestyle="--",
                       label=f"Mean={np.mean(best_f1s):.3f}")
            ax.set_xlabel("Iteration", fontsize=12)
            ax.set_ylabel("Best RF F1 Score", fontsize=12)
            ax.set_title(f"F1 Across Iterations ({hybrid.dataset})", fontweight="bold")
            ax.legend()
            ax.grid(True, alpha=0.3, axis="y")
            plt.tight_layout()
            path = fig_dir / "f1_iterations.png"
            fig.savefig(path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info(f"📈 Saved: {path.name}")


##### CLI ENTRY POINT #####

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GL→RF Hybrid Pipeline v2.0")
    parser.add_argument("--dataset", type=str, default="GDS1962",
                        help="GEO dataset ID (default: GDS1962)")
    parser.add_argument("--n-iterations", type=int, default=5,
                        help="Number of iterations (default: 5)")
    parser.add_argument("--out-dir", type=str, default=None)
    parser.add_argument("--no-optuna", action="store_true",
                        help="Disable Optuna HP optimization (use grid fallback)")
    parser.add_argument("--no-ttest", action="store_true",
                        help="Disable t-test pre-filtering")
    args = parser.parse_args()

    od = Path(args.out_dir) if args.out_dir else None

    # Apply CLI overrides to config
    if args.no_optuna:
        GroupLassoConfig.enable_optuna = False
    if args.no_ttest:
        GroupLassoConfig.enable_ttest_prefilter = False

    gl_rf_hybrid_workflow(
        dataset=args.dataset,
        n_iterations=args.n_iterations,
        output_dir=od,
    )
