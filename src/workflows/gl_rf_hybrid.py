"""
Two-Stage GL→RF Hybrid Pipeline 🧬🌲

Purpose:
    A NOVEL pipeline that combines the strengths of Group Lasso (convex,
    principled feature selection with group structure) and Random Forest
    (non-linear classification, interaction capture).

    Stage 1 (GL Filter):  Fit the Logistic Group Lasso on the training data
                          using overlapping-group duplication.  Extract the
                          set of genes with non-zero coefficients.
    Stage 2 (RF Classify): Train a Random Forest classifier using ONLY the
                          GL-selected original genes as features.

    Why this is novel:
    - Group Lasso provides provably sparse, convex feature selection that
      respects the group structure from DisGeNET.
    - Random Forest can capture non-linear decision boundaries and
      gene-gene interactions that the linear GL model cannot.
    - The hybrid inherits GL's principled sparsity (no need for heuristic
      group ranking as in GSM) while gaining RF's non-linear power.
    - Comparable to GSM's 3-phase pipeline but replaces the heuristic
      scoring phase with a single convex optimization.

Key Functions:
    - gl_rf_hybrid_workflow():  Main pipeline (multi-iteration).
    - run_hybrid_iteration():   One train/test split.
    - _gl_feature_selection():  Stage 1 — GL feature extraction.
    - _rf_classification():     Stage 2 — RF on selected genes.

Example Usage:
    python -m src.workflows.gl_rf_hybrid
    python -m src.workflows.gl_rf_hybrid --dataset GDS2545 --n-iterations 10
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List

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
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.utils.logger import setup_logger
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
class HybridIterationResult:
    """Result from one iteration of the hybrid pipeline."""
    iteration: int
    seed: int
    # Stage 1 (GL) metrics — linear model on expanded features.
    gl_f1: float
    gl_auc: float
    gl_accuracy: float
    gl_n_expanded_features: int
    gl_n_original_genes: int
    gl_n_groups: int
    gl_selected_genes: List[str] = field(default_factory=list)
    # Stage 2 (RF) metrics — non-linear model on GL-selected genes.
    rf_f1: float = 0.0
    rf_auc: float = 0.0
    rf_accuracy: float = 0.0
    rf_precision: float = 0.0
    rf_recall: float = 0.0
    rf_specificity: float = 0.0


@dataclass
class HybridResults:
    """Aggregated results across all iterations."""
    dataset: str = ""
    n_iterations: int = 0
    # GL standalone summary.
    gl_mean_f1: float = 0.0
    gl_mean_auc: float = 0.0
    gl_mean_genes: float = 0.0
    # RF on GL-selected features summary.
    rf_mean_f1: float = 0.0
    rf_std_f1: float = 0.0
    rf_mean_auc: float = 0.0
    rf_std_auc: float = 0.0
    rf_mean_accuracy: float = 0.0
    # Comparison: improvement from RF over GL.
    f1_improvement: float = 0.0
    auc_improvement: float = 0.0
    iterations: List[HybridIterationResult] = field(default_factory=list)


##### STAGE 1: GROUP LASSO FEATURE SELECTION #####

def _gl_feature_selection(
    X_train_exp: np.ndarray,
    y_train: np.ndarray,
    dup_result: FeatureDuplicationResult,
    config: GroupLassoConfig,
    logger: logging.Logger,
) -> tuple:
    """Fit Group Lasso and extract selected original gene names.

    Returns:
        (selected_genes, model, gl_metrics_dict)
    """
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_exp)

    if getattr(config, "enable_hyperparam_search", False):
        logger.info("    Running internal hyperparameter search...")
        try:
            X_tr, X_val, y_tr, y_val = train_test_split(
                X_train_scaled, y_train, test_size=0.2, stratify=y_train, random_state=config.random_seed
            )
        except ValueError:
            X_tr, X_val, y_tr, y_val = train_test_split(
                X_train_scaled, y_train, test_size=0.2, random_state=config.random_seed
            )
            
        best_f1 = -1.0
        best_params = {"group_reg": config.group_reg, "l1_reg": config.l1_reg}
        g_grid = sorted(getattr(config, "group_reg_grid", [0.005, 0.01, 0.05]))
        l_grid = sorted(getattr(config, "l1_reg_grid", [0.01, 0.05, 0.1]))
        
        search_model = LogisticGroupLasso(
            groups=dup_result.groups,
            group_reg=g_grid[0],
            l1_reg=l_grid[0],
            n_iter=config.n_iter,
            tol=config.tol,
            scale_reg=config.scale_reg,
            fit_intercept=config.fit_intercept,
            random_state=config.random_seed,
            warm_start=True,
            subsampling_scheme=config.subsampling_scheme,
            supress_warning=True,
        )
        
        for g_reg in g_grid:
            for l_reg in l_grid:
                search_model.group_reg = g_reg
                search_model.l1_reg = l_reg
                search_model.fit(X_tr, y_tr)
                
                preds = search_model.predict(X_val)
                f1 = float(f1_score(y_val, preds, average="weighted"))
                
                if np.sum(search_model.sparsity_mask_) == 0:
                    f1 = -1.0
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_params = {"group_reg": g_reg, "l1_reg": l_reg}
                    
        logger.info(f"    Best params found: group_reg={best_params['group_reg']}, l1_reg={best_params['l1_reg']} (Val F1={best_f1:.4f})")
        final_group_reg = best_params["group_reg"]
        final_l1_reg = best_params["l1_reg"]
    else:
        final_group_reg = config.group_reg
        final_l1_reg = config.l1_reg

    model = LogisticGroupLasso(
        groups=dup_result.groups,
        group_reg=final_group_reg,
        l1_reg=final_l1_reg,
        n_iter=config.n_iter,
        tol=config.tol,
        scale_reg=config.scale_reg,
        fit_intercept=config.fit_intercept,
        random_state=config.random_seed,
        warm_start=config.warm_start,
        subsampling_scheme=config.subsampling_scheme,
        supress_warning=True,
    )

    start = time.time()
    model.fit(X_train_scaled, y_train)
    elapsed = time.time() - start
    logger.info(f"    GL trained in {elapsed:.1f}s")

    # Extract selected genes.
    mask = model.sparsity_mask_
    n_sel_expanded = int(np.sum(mask))
    selected_expanded = [
        name for name, sel in zip(dup_result.expanded_names, mask) if sel
    ]
    selected_originals = sorted(set(
        dup_result.original_gene_map[name] for name in selected_expanded
    ))
    n_groups = len(np.unique(dup_result.groups[mask])) if n_sel_expanded > 0 else 0

    logger.info(
        f"    GL selected: {n_sel_expanded} expanded → "
        f"{len(selected_originals)} genes in {n_groups} groups"
    )

    return selected_originals, model, scaler, n_sel_expanded, n_groups


##### STAGE 2: RANDOM FOREST CLASSIFICATION #####

def _rf_classification(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: np.ndarray,
    y_test: np.ndarray,
    selected_genes: List[str],
    seed: int,
    logger: logging.Logger,
) -> dict:
    """Train Random Forest on only the GL-selected original genes.

    Args:
        X_train: Original (non-expanded) training data.
        X_test: Original (non-expanded) test data.
        y_train: Training labels.
        y_test: Test labels.
        selected_genes: Gene names selected by GL (Stage 1).
        seed: Random seed for RF.
        logger: Logger instance.

    Returns:
        Dict with RF classification metrics.
    """
    # Filter to only GL-selected genes that exist in the expression data.
    available = [g for g in selected_genes if g in X_train.columns]
    if not available:
        logger.warning("    No GL-selected genes found in expression data!")
        return {
            "f1": 0.0, "auc": 0.0, "accuracy": 0.0,
            "precision": 0.0, "recall": 0.0, "specificity": 0.0,
        }

    X_tr = X_train[available].values
    X_te = X_test[available].values

    # Scale the original features (not expanded).
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        random_state=seed,
        n_jobs=-1,
        class_weight="balanced",
    )
    rf.fit(X_tr_s, y_train)
    y_pred = rf.predict(X_te_s)
    y_prob = rf.predict_proba(X_te_s)[:, 1]

    # Metrics.
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
    }
    logger.info(
        f"    RF: F1={metrics['f1']:.4f} AUC={metrics['auc']:.4f} "
        f"Acc={metrics['accuracy']:.4f} ({len(available)} features)"
    )
    return metrics


##### SINGLE HYBRID ITERATION #####

def run_hybrid_iteration(
    X: pd.DataFrame,
    y: np.ndarray,
    dup_result: FeatureDuplicationResult,
    config: GroupLassoConfig,
    iteration: int,
    seed: int,
    logger: logging.Logger,
) -> HybridIterationResult:
    """Run one iteration of the GL→RF hybrid pipeline.

    Steps:
    1. Split data into train/test (stratified).
    2. Stage 1: Fit GL on expanded training data → extract selected genes.
    3. Evaluate GL on expanded test data (linear baseline).
    4. Stage 2: Train RF on original training data using only GL genes.
    5. Evaluate RF on original test data.
    """
    # Train/test split on original data.
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

    # Stage 1: Group Lasso feature selection.
    X_train_exp = build_expanded_matrix(X_train, dup_result)
    X_test_exp = build_expanded_matrix(X_test, dup_result)

    selected_genes, gl_model, gl_scaler, n_exp, n_grps = _gl_feature_selection(
        X_train_exp, y_train, dup_result, config, logger,
    )

    # Evaluate GL on test set (linear baseline).
    X_test_scaled = gl_scaler.transform(X_test_exp)
    gl_pred = gl_model.predict(X_test_scaled)
    gl_f1 = float(f1_score(y_test, gl_pred, average="weighted"))
    try:
        gl_proba = gl_model.predict_proba(X_test_scaled)
        gl_p = gl_proba[:, 1] if gl_proba.ndim > 1 else gl_proba.ravel()
        gl_auc = float(roc_auc_score(y_test, gl_p))
    except (AttributeError, ValueError):
        gl_auc = 0.0
    gl_acc = float(accuracy_score(y_test, gl_pred))

    logger.info(f"    GL baseline: F1={gl_f1:.4f} AUC={gl_auc:.4f}")

    # Stage 2: Random Forest on GL-selected genes.
    rf_metrics = _rf_classification(
        X_train, X_test, y_train, y_test, selected_genes, seed, logger,
    )

    return HybridIterationResult(
        iteration=iteration,
        seed=seed,
        gl_f1=gl_f1,
        gl_auc=gl_auc,
        gl_accuracy=gl_acc,
        gl_n_expanded_features=n_exp,
        gl_n_original_genes=len(selected_genes),
        gl_n_groups=n_grps,
        gl_selected_genes=selected_genes,
        rf_f1=rf_metrics["f1"],
        rf_auc=rf_metrics["auc"],
        rf_accuracy=rf_metrics["accuracy"],
        rf_precision=rf_metrics["precision"],
        rf_recall=rf_metrics["recall"],
        rf_specificity=rf_metrics["specificity"],
    )


##### MAIN WORKFLOW #####

def gl_rf_hybrid_workflow(
    dataset: str = "GDS1962",
    n_iterations: int = 10,
    output_dir: Path = None,
) -> HybridResults:
    """Run the full GL→RF hybrid pipeline across multiple iterations.

    Args:
        dataset: GEO dataset ID.
        n_iterations: Number of train/test iterations.
        output_dir: Where to save results.

    Returns:
        HybridResults with per-iteration and aggregated metrics.
    """
    if output_dir is None:
        ts = time.strftime("%Y_%m_%d-%H_%M_%S")
        output_dir = project_root / "output" / f"gl_rf_hybrid_{dataset}_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / "gl_rf_hybrid.log"
    logger = setup_logger(str(log_file))

    logger.info("=" * 75)
    logger.info(f"🌲 GL→RF HYBRID PIPELINE — {dataset}")
    logger.info(f"   Iterations: {n_iterations}")
    logger.info(f"   Stage 1: Logistic Group Lasso (feature selection)")
    logger.info(f"   Stage 2: Random Forest (classification)")
    logger.info("=" * 75)

    # Load data (once).
    config = GroupLassoConfig()
    config.main_data_path = f"data/expression_data/{dataset}.csv"
    X, y = _load_expression_data(config, logger)
    group_df = _load_grouping_data(config, logger)
    dup_result = _build_duplication_map(X, group_df, config, logger)

    # Run iterations.
    all_results: List[HybridIterationResult] = []
    total_start = time.time()

    for i in range(n_iterations):
        seed = config.random_seed + i * 44
        logger.info(f"\n{'─' * 60}")
        logger.info(f"📊 Iteration {i+1}/{n_iterations}  (seed={seed})")
        logger.info(f"{'─' * 60}")

        result = run_hybrid_iteration(X, y, dup_result, config, i + 1, seed, logger)
        all_results.append(result)

    total_time = time.time() - total_start

    # Aggregate.
    gl_f1s = [r.gl_f1 for r in all_results]
    gl_aucs = [r.gl_auc for r in all_results]
    gl_genes = [r.gl_n_original_genes for r in all_results]
    rf_f1s = [r.rf_f1 for r in all_results]
    rf_aucs = [r.rf_auc for r in all_results]
    rf_accs = [r.rf_accuracy for r in all_results]

    hybrid = HybridResults(
        dataset=dataset,
        n_iterations=n_iterations,
        gl_mean_f1=float(np.mean(gl_f1s)),
        gl_mean_auc=float(np.mean(gl_aucs)),
        gl_mean_genes=float(np.mean(gl_genes)),
        rf_mean_f1=float(np.mean(rf_f1s)),
        rf_std_f1=float(np.std(rf_f1s)),
        rf_mean_auc=float(np.mean(rf_aucs)),
        rf_std_auc=float(np.std(rf_aucs)),
        rf_mean_accuracy=float(np.mean(rf_accs)),
        f1_improvement=float(np.mean(rf_f1s)) - float(np.mean(gl_f1s)),
        auc_improvement=float(np.mean(rf_aucs)) - float(np.mean(gl_aucs)),
        iterations=all_results,
    )

    # Log summary.
    logger.info(f"\n{'=' * 75}")
    logger.info(f"📊 GL→RF HYBRID RESULTS")
    logger.info(f"   ⏱  Total time: {total_time / 60:.1f} min")
    logger.info(f"   GL alone:  F1={hybrid.gl_mean_f1:.4f}  AUC={hybrid.gl_mean_auc:.4f}")
    logger.info(f"   GL→RF:     F1={hybrid.rf_mean_f1:.4f}±{hybrid.rf_std_f1:.4f}  "
                f"AUC={hybrid.rf_mean_auc:.4f}±{hybrid.rf_std_auc:.4f}")
    logger.info(f"   F1 gain from RF: {hybrid.f1_improvement:+.4f}")
    logger.info(f"   AUC gain from RF: {hybrid.auc_improvement:+.4f}")
    logger.info(f"   Avg GL-selected genes: {hybrid.gl_mean_genes:.1f}")
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
    """Save hybrid results as JSON and Excel."""
    # JSON
    data = {
        "dataset": hybrid.dataset,
        "n_iterations": hybrid.n_iterations,
        "gl_mean_f1": hybrid.gl_mean_f1,
        "gl_mean_auc": hybrid.gl_mean_auc,
        "gl_mean_genes": hybrid.gl_mean_genes,
        "rf_mean_f1": hybrid.rf_mean_f1,
        "rf_std_f1": hybrid.rf_std_f1,
        "rf_mean_auc": hybrid.rf_mean_auc,
        "rf_std_auc": hybrid.rf_std_auc,
        "rf_mean_accuracy": hybrid.rf_mean_accuracy,
        "f1_improvement": hybrid.f1_improvement,
        "auc_improvement": hybrid.auc_improvement,
        "iterations": [asdict(r) for r in hybrid.iterations],
    }
    json_path = output_dir / "gl_rf_hybrid_results.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"💾 Saved: {json_path.name}")

    # Excel
    rows = []
    for r in hybrid.iterations:
        rows.append({
            "iteration": r.iteration,
            "seed": r.seed,
            "gl_f1": r.gl_f1,
            "gl_auc": r.gl_auc,
            "rf_f1": r.rf_f1,
            "rf_auc": r.rf_auc,
            "rf_accuracy": r.rf_accuracy,
            "rf_precision": r.rf_precision,
            "rf_recall": r.rf_recall,
            "gl_n_genes": r.gl_n_original_genes,
            "gl_n_groups": r.gl_n_groups,
        })
    df = pd.DataFrame(rows)
    xlsx_path = output_dir / "gl_rf_hybrid_iterations.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {xlsx_path.name}")

    # Gene frequency across iterations.
    gene_freq: Dict[str, int] = {}
    for r in hybrid.iterations:
        for g in r.gl_selected_genes:
            gene_freq[g] = gene_freq.get(g, 0) + 1

    if gene_freq:
        freq_rows = sorted(gene_freq.items(), key=lambda x: -x[1])
        freq_df = pd.DataFrame(freq_rows, columns=["gene", "selection_count"])
        freq_df["selection_fraction"] = freq_df["selection_count"] / hybrid.n_iterations
        freq_path = output_dir / "hybrid_gene_frequency.xlsx"
        freq_df.to_excel(freq_path, index=False, engine="openpyxl")
        logger.info(f"💾 Saved: {freq_path.name}")


##### FIGURES #####

def _generate_hybrid_figures(
    hybrid: HybridResults,
    output_dir: Path,
    logger: logging.Logger,
):
    """Generate hybrid comparison figures."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping figures")
        return

    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    iters = hybrid.iterations

    # --- Per-iteration GL vs RF F1 comparison ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    x = range(1, len(iters) + 1)
    gl_f1s = [r.gl_f1 for r in iters]
    rf_f1s = [r.rf_f1 for r in iters]
    gl_aucs = [r.gl_auc for r in iters]
    rf_aucs = [r.rf_auc for r in iters]

    # F1 comparison.
    axes[0].plot(x, gl_f1s, "o-", color="#A23B72", label="GL (linear)", markersize=6)
    axes[0].plot(x, rf_f1s, "s-", color="#2E86AB", label="GL→RF (hybrid)", markersize=6)
    axes[0].set_xlabel("Iteration")
    axes[0].set_ylabel("Weighted F1")
    axes[0].set_title("F1 Score: GL vs GL→RF Hybrid", fontweight="bold")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # AUC comparison.
    axes[1].plot(x, gl_aucs, "o-", color="#A23B72", label="GL (linear)", markersize=6)
    axes[1].plot(x, rf_aucs, "s-", color="#2E86AB", label="GL→RF (hybrid)", markersize=6)
    axes[1].set_xlabel("Iteration")
    axes[1].set_ylabel("AUC-ROC")
    axes[1].set_title("AUC-ROC: GL vs GL→RF Hybrid", fontweight="bold")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    path = fig_dir / "hybrid_gl_vs_rf.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"📈 Saved: {path.name}")

    # --- Summary bar chart: GL vs RF vs (optionally) GSM ---
    fig2, ax = plt.subplots(figsize=(8, 5))
    methods = ["GL (linear)", "GL→RF (hybrid)"]
    f1_means = [hybrid.gl_mean_f1, hybrid.rf_mean_f1]
    f1_stds = [0, hybrid.rf_std_f1]
    colors = ["#A23B72", "#2E86AB"]

    bars = ax.bar(methods, f1_means, yerr=f1_stds, color=colors,
                  capsize=5, edgecolor="white", linewidth=1.5)
    ax.set_ylabel("Mean Weighted F1")
    ax.set_title("Group Lasso vs GL→RF Hybrid", fontweight="bold")
    ax.set_ylim(0, 1.05)

    for bar, val in zip(bars, f1_means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.4f}", ha="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    path2 = fig_dir / "hybrid_summary.png"
    fig2.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    logger.info(f"📈 Saved: {path2.name}")


##### CLI #####

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GL→RF Hybrid Pipeline")
    parser.add_argument("--dataset", type=str, default="GDS1962",
                        help="GEO dataset ID (default: GDS1962)")
    parser.add_argument("--n-iterations", type=int, default=10,
                        help="Number of iterations (default: 10)")
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    od = Path(args.out_dir) if args.out_dir else None
    gl_rf_hybrid_workflow(
        dataset=args.dataset,
        n_iterations=args.n_iterations,
        output_dir=od,
    )
