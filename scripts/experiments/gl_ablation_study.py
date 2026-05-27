"""
Group Lasso Ablation Study 🧬🔬

Purpose:
    Compare three strategies for handling overlapping gene-disease groups:

    1. **Duplication (Latent GL)** — Our approach. Mathematically equivalent
       to the Latent Group Lasso [Obozinski et al., 2011]. Each gene in N
       groups becomes N expanded columns, each in exactly one group.

    2. **Naive (Last-Group)** — Assign each gene to a single group (the
       last one encountered). This is what a plain Python dict would do
       and silently discards ~85% of group information.

    3. **No-Group (Standard Lasso)** — Ignore groups entirely. Use
       scikit-learn's LogisticRegression with L1 penalty as a baseline.
       Shows the value of group structure.

    The study runs all three strategies on the same dataset with the
    same train/test splits, producing a side-by-side metric comparison.

Key Functions:
    - run_duplication_strategy():   Our overlap-aware Group Lasso
    - run_naive_strategy():         Single-group-assignment Group Lasso
    - run_no_group_strategy():      Standard L1 logistic regression
    - run_ablation():               Orchestrator

Example Usage:
    python scripts/experiments/gl_ablation_study.py
    python scripts/experiments/gl_ablation_study.py --dataset GDS2545
    python scripts/experiments/gl_ablation_study.py --n-iterations 5
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from group_lasso import LogisticGroupLasso
from src.data_processing.data_loader import _detect_separator
from src.utils.logger import setup_logger
from src.workflows.group_lasso_workflow import (
    build_expanded_matrix,
    load_and_prepare_data,
)
from src.workflows.group_lasso_workflow_config import GroupLassoConfig


##### DATA STRUCTURES #####

@dataclass
class StrategyResult:
    """Metrics from a single strategy across all iterations."""
    strategy: str
    description: str
    n_iterations: int = 0
    per_iteration: list = field(default_factory=list)
    mean_f1: float = 0.0
    std_f1: float = 0.0
    mean_auc: float = 0.0
    std_auc: float = 0.0
    mean_accuracy: float = 0.0
    std_accuracy: float = 0.0
    mean_n_features: float = 0.0


@dataclass
class AblationResult:
    """Complete ablation study output."""
    dataset: str
    n_iterations: int
    strategies: List[StrategyResult] = field(default_factory=list)


##### SHARED HELPERS #####

def _compute_metrics(y_true, y_pred, y_prob=None) -> dict:
    """Compute classification metrics."""
    auc = 0.0
    if y_prob is not None:
        try:
            auc = float(roc_auc_score(y_true, y_prob))
        except ValueError:
            pass
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, average="weighted")),
        "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "auc_roc": auc,
    }


def _aggregate_strategy(
    strategy_name: str,
    description: str,
    results: List[dict],
) -> StrategyResult:
    """Aggregate per-iteration results for one strategy."""
    sr = StrategyResult(
        strategy=strategy_name,
        description=description,
        n_iterations=len(results),
        per_iteration=results,
    )
    if results:
        f1s = [r["f1"] for r in results]
        aucs = [r["auc_roc"] for r in results]
        accs = [r["accuracy"] for r in results]
        feats = [r.get("n_features", 0) for r in results]
        sr.mean_f1 = float(np.mean(f1s))
        sr.std_f1 = float(np.std(f1s))
        sr.mean_auc = float(np.mean(aucs))
        sr.std_auc = float(np.std(aucs))
        sr.mean_accuracy = float(np.mean(accs))
        sr.std_accuracy = float(np.std(accs))
        sr.mean_n_features = float(np.mean(feats))
    return sr


##### STRATEGY 1: DUPLICATION (LATENT GROUP LASSO) #####

def run_duplication_strategy(
    X: pd.DataFrame,
    y: np.ndarray,
    dup_result,
    config: GroupLassoConfig,
    seeds: List[int],
    logger: logging.Logger,
) -> StrategyResult:
    """Run Group Lasso with feature duplication (our method).

    This is mathematically equivalent to the Latent Group Lasso
    (Obozinski et al., 2011) where each feature gets a latent copy
    per group assignment.
    """
    logger.info("▶ Strategy 1: Duplication (Latent Group Lasso)")
    results = []

    for i, seed in enumerate(seeds):
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=config.test_size,
                                  random_state=seed, stratify=y)

        X_tr_exp = build_expanded_matrix(X.iloc[tr], dup_result)
        X_te_exp = build_expanded_matrix(X.iloc[te], dup_result)

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr_exp)
        X_te_s = scaler.transform(X_te_exp)

        model = LogisticGroupLasso(
            groups=dup_result.groups,
            group_reg=config.group_reg,
            l1_reg=config.l1_reg,
            n_iter=config.n_iter,
            tol=config.tol,
            scale_reg=config.scale_reg,
            fit_intercept=config.fit_intercept,
            random_state=config.random_seed,
            supress_warning=True,
        )
        model.fit(X_tr_s, y[tr])
        y_pred = model.predict(X_te_s)

        y_prob = None
        try:
            proba = model.predict_proba(X_te_s)
            y_prob = proba[:, 1] if proba.ndim > 1 else proba.ravel()
        except (AttributeError, ValueError):
            pass

        m = _compute_metrics(y[te], y_pred, y_prob)
        m["n_features"] = int(np.sum(model.sparsity_mask_))
        m["seed"] = seed
        results.append(m)
        logger.info(f"  Iter {i+1}: F1={m['f1']:.4f} AUC={m['auc_roc']:.4f} Feat={m['n_features']}")

    return _aggregate_strategy(
        "Duplication (Latent GL)",
        "Feature-duplication approach equivalent to Latent Group Lasso",
        results,
    )


##### STRATEGY 2: NAIVE (SINGLE-GROUP ASSIGNMENT) #####

def _build_naive_groups(
    X: pd.DataFrame,
    config: GroupLassoConfig,
    logger: logging.Logger,
) -> np.ndarray:
    """Assign each gene to exactly one group (last-encountered).

    This is the naive approach that silently discards most group
    membership information.
    """
    sep = _detect_separator(config.group_data_path)
    gdf = pd.read_csv(config.group_data_path, sep=sep, header=0)
    for col in gdf.columns:
        if gdf[col].dtype == object:
            gdf[col] = gdf[col].str.strip().str.strip("\r")
    gdf.columns = [c.strip().strip("\r") for c in gdf.columns]

    feature_col = [c for c in gdf.columns if c != config.group_name_column][0]
    available = set(X.columns)

    # Build gene→single_group mapping (last seen wins).
    gene_to_group: Dict[str, str] = {}
    for _, row in gdf.iterrows():
        gene = row[feature_col]
        if gene in available:
            gene_to_group[gene] = row[config.group_name_column]

    # Apply same min_genes_per_group filter as duplication strategy.
    min_size = getattr(config, "min_genes_per_group", 10)
    if min_size > 0:
        from collections import Counter
        group_counts = Counter(gene_to_group.values())
        kept_groups = {g for g, c in group_counts.items() if c >= min_size}
        gene_to_group = {g: grp for g, grp in gene_to_group.items() if grp in kept_groups}

    # Map group names to integer IDs.
    unique_groups = sorted(set(gene_to_group.values()))
    group_name_to_id = {g: i for i, g in enumerate(unique_groups)}

    # Only keep genes that were assigned to a group (skip singletons).
    assigned_genes = [c for c in X.columns if c in gene_to_group]
    groups = [group_name_to_id[gene_to_group[g]] for g in assigned_genes]

    logger.info(f"  Naive: {len(assigned_genes)}/{len(X.columns)} genes assigned to {len(unique_groups)} groups")
    return np.array(groups), assigned_genes


def run_naive_strategy(
    X: pd.DataFrame,
    y: np.ndarray,
    config: GroupLassoConfig,
    seeds: List[int],
    logger: logging.Logger,
) -> StrategyResult:
    """Run Group Lasso with naive single-group assignment."""
    logger.info("▶ Strategy 2: Naive (single-group assignment)")
    groups, assigned_genes = _build_naive_groups(X, config, logger)
    X_naive = X[assigned_genes]
    results = []

    for i, seed in enumerate(seeds):
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=config.test_size,
                                  random_state=seed, stratify=y)

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_naive.iloc[tr].values)
        X_te_s = scaler.transform(X_naive.iloc[te].values)

        model = LogisticGroupLasso(
            groups=groups,
            group_reg=config.group_reg,
            l1_reg=config.l1_reg,
            n_iter=config.n_iter,
            tol=config.tol,
            scale_reg=config.scale_reg,
            fit_intercept=config.fit_intercept,
            random_state=config.random_seed,
            supress_warning=True,
        )
        model.fit(X_tr_s, y[tr])
        y_pred = model.predict(X_te_s)

        y_prob = None
        try:
            proba = model.predict_proba(X_te_s)
            y_prob = proba[:, 1] if proba.ndim > 1 else proba.ravel()
        except (AttributeError, ValueError):
            pass

        m = _compute_metrics(y[te], y_pred, y_prob)
        m["n_features"] = int(np.sum(model.sparsity_mask_))
        m["seed"] = seed
        results.append(m)
        logger.info(f"  Iter {i+1}: F1={m['f1']:.4f} AUC={m['auc_roc']:.4f} Feat={m['n_features']}")

    return _aggregate_strategy(
        "Naive (Last-Group)",
        "Each gene assigned to a single group; ~85% of group info discarded",
        results,
    )


##### STRATEGY 3: NO-GROUP (STANDARD LASSO) #####

def run_no_group_strategy(
    X: pd.DataFrame,
    y: np.ndarray,
    config: GroupLassoConfig,
    seeds: List[int],
    logger: logging.Logger,
) -> StrategyResult:
    """Run standard L1 logistic regression (no group structure)."""
    logger.info("▶ Strategy 3: No-Group (L1 Logistic Regression)")
    results = []

    for i, seed in enumerate(seeds):
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=config.test_size,
                                  random_state=seed, stratify=y)

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X.iloc[tr].values)
        X_te_s = scaler.transform(X.iloc[te].values)

        model = LogisticRegression(
            penalty="l1",
            solver="saga",
            C=1.0,  # Inverse of regularization strength.
            max_iter=2000,
            random_state=config.random_seed,
            n_jobs=-1,
        )
        model.fit(X_tr_s, y[tr])
        y_pred = model.predict(X_te_s)
        y_prob = model.predict_proba(X_te_s)[:, 1]

        m = _compute_metrics(y[te], y_pred, y_prob)
        m["n_features"] = int(np.sum(model.coef_.ravel() != 0))
        m["seed"] = seed
        results.append(m)
        logger.info(f"  Iter {i+1}: F1={m['f1']:.4f} AUC={m['auc_roc']:.4f} Feat={m['n_features']}")

    return _aggregate_strategy(
        "No-Group (L1 Lasso)",
        "Standard L1 logistic regression ignoring all group information",
        results,
    )


##### FIGURE GENERATION #####

def _generate_ablation_figures(ablation: AblationResult, output_dir: Path, logger: logging.Logger):
    """Create comparison bar charts for the ablation study."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping figures")
        return

    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    strategies = ablation.strategies
    names = [s.strategy for s in strategies]
    colors = ["#2E86AB", "#A23B72", "#F18F01"]

    # Bar chart: F1, AUC, Accuracy
    metrics = [
        ("F1 Score", [s.mean_f1 for s in strategies], [s.std_f1 for s in strategies]),
        ("AUC-ROC", [s.mean_auc for s in strategies], [s.std_auc for s in strategies]),
        ("Accuracy", [s.mean_accuracy for s in strategies], [s.std_accuracy for s in strategies]),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    for ax, (label, means, stds) in zip(axes, metrics):
        bars = ax.bar(names, means, yerr=stds, color=colors, capsize=5, edgecolor="black", linewidth=0.5)
        ax.set_ylabel(label)
        ax.set_title(label, fontweight="bold")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9)
        # Rotate labels
        ax.set_xticklabels(names, rotation=15, ha="right", fontsize=8)

    fig.suptitle(f"Ablation Study: Group Overlap Handling ({ablation.dataset})",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = fig_dir / "ablation_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"  Saved: {path.name}")

    # Feature count comparison
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    feat_means = [s.mean_n_features for s in strategies]
    bars = ax2.bar(names, feat_means, color=colors, edgecolor="black", linewidth=0.5)
    ax2.set_ylabel("Mean # Selected Features")
    ax2.set_title("Feature Selection Sparsity by Strategy", fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, feat_means):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{val:.0f}", ha="center", va="bottom", fontsize=10)
    ax2.set_xticklabels(names, rotation=15, ha="right", fontsize=9)
    plt.tight_layout()
    path2 = fig_dir / "ablation_feature_counts.png"
    fig2.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    logger.info(f"  Saved: {path2.name}")


##### SAVE & ORCHESTRATOR #####

def save_ablation(ablation: AblationResult, output_dir: Path, logger: logging.Logger):
    """Save ablation results as JSON and Excel."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    data = {
        "dataset": ablation.dataset,
        "n_iterations": ablation.n_iterations,
        "strategies": [asdict(s) for s in ablation.strategies],
    }
    json_path = output_dir / "ablation_results.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"💾 Saved: {json_path.name}")

    # Summary Excel
    rows = []
    for s in ablation.strategies:
        rows.append({
            "Strategy": s.strategy,
            "Description": s.description,
            "Mean F1": f"{s.mean_f1:.4f}±{s.std_f1:.4f}",
            "Mean AUC": f"{s.mean_auc:.4f}±{s.std_auc:.4f}",
            "Mean Accuracy": f"{s.mean_accuracy:.4f}±{s.std_accuracy:.4f}",
            "Mean #Features": f"{s.mean_n_features:.1f}",
        })
    df = pd.DataFrame(rows)
    xlsx_path = output_dir / "ablation_summary.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {xlsx_path.name}")

    # Summary table to logger
    logger.info("\n" + "=" * 75)
    logger.info("📊 ABLATION STUDY SUMMARY")
    logger.info(f"{'Strategy':<28} {'F1':>14} {'AUC':>14} {'Acc':>14} {'#Feat':>8}")
    logger.info("-" * 75)
    for s in ablation.strategies:
        logger.info(
            f"{s.strategy:<28} "
            f"{s.mean_f1:.4f}±{s.std_f1:.4f}  "
            f"{s.mean_auc:.4f}±{s.std_auc:.4f}  "
            f"{s.mean_accuracy:.4f}±{s.std_accuracy:.4f}  "
            f"{s.mean_n_features:>6.1f}"
        )
    logger.info("=" * 75)


def run_ablation(
    dataset: str = "GDS1962",
    n_iterations: int = 3,
    output_dir: Path = None,
) -> AblationResult:
    """Run the complete ablation study comparing three overlap strategies.

    Args:
        dataset: GEO dataset ID (e.g. "GDS1962").
        n_iterations: Number of train/test iterations per strategy.
        output_dir: Where to write results. Defaults to
                    output/gl_ablation_<dataset>/.
    """
    if output_dir is None:
        ts = time.strftime("%Y_%m_%d-%H_%M_%S")
        output_dir = project_root / "output" / f"gl_ablation_{dataset}_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / "ablation.log"
    logger = setup_logger(str(log_file))

    logger.info("=" * 75)
    logger.info(f"🔬 GROUP LASSO ABLATION STUDY — {dataset}")
    logger.info(f"   Iterations: {n_iterations}")
    logger.info("=" * 75)

    # Build config
    config = GroupLassoConfig()
    config.main_data_path = f"data/expression_data/{dataset}.csv"
    config.n_iterations = n_iterations

    # Load data using existing workflow loader (handles duplication).
    logger.info("📂 Loading data...")
    X, y, dup_result = load_and_prepare_data(config, logger)

    # Shared seeds for all strategies (ensures same splits).
    seeds = [config.random_seed + i * 44 for i in range(n_iterations)]

    # Run three strategies.
    start = time.time()

    s1 = run_duplication_strategy(X, y, dup_result, config, seeds, logger)
    s2 = run_naive_strategy(X, y, config, seeds, logger)
    s3 = run_no_group_strategy(X, y, config, seeds, logger)

    elapsed = time.time() - start
    logger.info(f"\n⏱ Total time: {elapsed:.0f}s")

    ablation = AblationResult(
        dataset=dataset,
        n_iterations=n_iterations,
        strategies=[s1, s2, s3],
    )

    save_ablation(ablation, output_dir, logger)
    _generate_ablation_figures(ablation, output_dir, logger)

    logger.info("✅ Ablation study complete")
    return ablation


##### CLI #####

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Group Lasso ablation study")
    parser.add_argument("--dataset", type=str, default="GDS1962",
                        help="GEO dataset ID (default: GDS1962)")
    parser.add_argument("--n-iterations", type=int, default=3,
                        help="Iterations per strategy (default: 3)")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="Output directory (default: auto)")
    args = parser.parse_args()

    od = Path(args.out_dir) if args.out_dir else None
    run_ablation(dataset=args.dataset, n_iterations=args.n_iterations, output_dir=od)
