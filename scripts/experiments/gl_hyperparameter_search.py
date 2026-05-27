"""
Group Lasso Hyperparameter Search 🧬🔧

Purpose:
    Perform a grid search over the two key regularization parameters
    of the Group Lasso (group_reg λ₁ and l1_reg λ₂), plus the two
    overlap-filtering thresholds (max_groups_per_gene, min_genes_per_group).

    Uses stratified train/test splits (same seeds across parameter
    combinations) so results are directly comparable.

Key Functions:
    - run_hyperparameter_search():  Main grid search loop
    - _evaluate_params():           Single parameter combination
    - summarize_search():           Best params + heatmap

Example Usage:
    python scripts/experiments/gl_hyperparameter_search.py
    python scripts/experiments/gl_hyperparameter_search.py --dataset GDS2545 --n-iterations 3
"""

import argparse
import itertools
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.utils.logger import setup_logger
from src.workflows.group_lasso_workflow import (
    build_expanded_matrix,
    load_and_prepare_data,
    _build_duplication_map,
    _load_expression_data,
    _load_grouping_data,
)
from src.workflows.group_lasso_workflow_config import GroupLassoConfig

from group_lasso import LogisticGroupLasso
from sklearn.metrics import f1_score, roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


##### DATA STRUCTURES #####

@dataclass
class ParamComboResult:
    """Result for one hyperparameter combination."""
    group_reg: float
    l1_reg: float
    max_groups_per_gene: int
    min_genes_per_group: int
    mean_f1: float = 0.0
    std_f1: float = 0.0
    mean_auc: float = 0.0
    std_auc: float = 0.0
    mean_accuracy: float = 0.0
    mean_n_features: float = 0.0
    mean_n_groups: float = 0.0
    n_expanded_cols: int = 0
    time_seconds: float = 0.0


@dataclass
class SearchResult:
    """Full hyperparameter search output."""
    dataset: str
    n_iterations: int
    n_combos: int
    best_params: dict = field(default_factory=dict)
    all_combos: List[ParamComboResult] = field(default_factory=list)


##### DEFAULT GRIDS #####

DEFAULT_GROUP_REG = [0.005, 0.01, 0.02, 0.05]
DEFAULT_L1_REG = [0.01, 0.05, 0.1, 0.2]
DEFAULT_MAX_GROUPS = [3, 5, 10]
DEFAULT_MIN_GENES = [5, 10, 20]


##### CORE #####

def _evaluate_params(
    X: pd.DataFrame,
    y: np.ndarray,
    group_df: pd.DataFrame,
    group_reg: float,
    l1_reg: float,
    max_gpg: int,
    min_gig: int,
    seeds: List[int],
    base_config: GroupLassoConfig,
    logger: logging.Logger,
) -> ParamComboResult:
    """Evaluate a single parameter combination across all seeds."""
    # Build config variant for this combo.
    config = GroupLassoConfig()
    config.main_data_path = base_config.main_data_path
    config.group_data_path = base_config.group_data_path
    config.group_reg = group_reg
    config.l1_reg = l1_reg
    config.max_groups_per_gene = max_gpg
    config.min_genes_per_group = min_gig

    # Rebuild duplication map for this filter combination.
    try:
        dup_result = _build_duplication_map(X, group_df, config, logger)
    except Exception as e:
        logger.warning(f"  Skipped ({max_gpg},{min_gig}): {e}")
        return ParamComboResult(
            group_reg=group_reg, l1_reg=l1_reg,
            max_groups_per_gene=max_gpg, min_genes_per_group=min_gig,
        )

    n_exp = dup_result.n_expanded_features
    if n_exp == 0:
        logger.warning(f"  Skipped: 0 expanded features")
        return ParamComboResult(
            group_reg=group_reg, l1_reg=l1_reg,
            max_groups_per_gene=max_gpg, min_genes_per_group=min_gig,
        )

    f1s, aucs, accs, feats, n_grps = [], [], [], [], []
    start = time.time()

    for seed in seeds:
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=base_config.test_size,
                                  random_state=seed, stratify=y)

        X_tr_exp = build_expanded_matrix(X.iloc[tr], dup_result)
        X_te_exp = build_expanded_matrix(X.iloc[te], dup_result)

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr_exp)
        X_te_s = scaler.transform(X_te_exp)

        model = LogisticGroupLasso(
            groups=dup_result.groups,
            group_reg=group_reg,
            l1_reg=l1_reg,
            n_iter=base_config.n_iter,
            tol=base_config.tol,
            scale_reg=base_config.scale_reg,
            fit_intercept=base_config.fit_intercept,
            random_state=base_config.random_seed,
            supress_warning=True,
        )
        model.fit(X_tr_s, y[tr])
        y_pred = model.predict(X_te_s)

        f1s.append(float(f1_score(y[te], y_pred, average="weighted")))
        accs.append(float(accuracy_score(y[te], y_pred)))

        auc_val = 0.0
        try:
            proba = model.predict_proba(X_te_s)
            p = proba[:, 1] if proba.ndim > 1 else proba.ravel()
            auc_val = float(roc_auc_score(y[te], p))
        except (AttributeError, ValueError):
            pass
        aucs.append(auc_val)

        mask = model.sparsity_mask_
        feats.append(int(np.sum(mask)))
        n_grps.append(len(np.unique(dup_result.groups[mask])) if np.any(mask) else 0)

    elapsed = time.time() - start

    return ParamComboResult(
        group_reg=group_reg,
        l1_reg=l1_reg,
        max_groups_per_gene=max_gpg,
        min_genes_per_group=min_gig,
        mean_f1=float(np.mean(f1s)),
        std_f1=float(np.std(f1s)),
        mean_auc=float(np.mean(aucs)),
        std_auc=float(np.std(aucs)),
        mean_accuracy=float(np.mean(accs)),
        mean_n_features=float(np.mean(feats)),
        mean_n_groups=float(np.mean(n_grps)),
        n_expanded_cols=n_exp,
        time_seconds=elapsed,
    )


def run_hyperparameter_search(
    dataset: str = "GDS1962",
    n_iterations: int = 3,
    group_regs: List[float] = None,
    l1_regs: List[float] = None,
    max_groups_list: List[int] = None,
    min_genes_list: List[int] = None,
    output_dir: Path = None,
) -> SearchResult:
    """Run full grid search over GL hyperparameters.

    Args:
        dataset: GEO dataset ID.
        n_iterations: Iterations per parameter combination.
        group_regs: Values for λ₁ (group penalty).
        l1_regs: Values for λ₂ (within-group L1).
        max_groups_list: Values for max_groups_per_gene filter.
        min_genes_list: Values for min_genes_per_group filter.
        output_dir: Where to save results.

    Returns:
        SearchResult with all combos and best params.
    """
    if group_regs is None:
        group_regs = DEFAULT_GROUP_REG
    if l1_regs is None:
        l1_regs = DEFAULT_L1_REG
    if max_groups_list is None:
        max_groups_list = DEFAULT_MAX_GROUPS
    if min_genes_list is None:
        min_genes_list = DEFAULT_MIN_GENES

    if output_dir is None:
        ts = time.strftime("%Y_%m_%d-%H_%M_%S")
        output_dir = project_root / "output" / f"gl_hyperparam_{dataset}_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / "hyperparam_search.log"
    logger = setup_logger(str(log_file))

    combos = list(itertools.product(group_regs, l1_regs, max_groups_list, min_genes_list))
    n_combos = len(combos)

    logger.info("=" * 75)
    logger.info(f"🔧 HYPERPARAMETER SEARCH — {dataset}")
    logger.info(f"   {n_combos} combinations × {n_iterations} iterations each")
    logger.info(f"   λ₁ (group_reg): {group_regs}")
    logger.info(f"   λ₂ (l1_reg):    {l1_regs}")
    logger.info(f"   max_groups:     {max_groups_list}")
    logger.info(f"   min_genes:      {min_genes_list}")
    logger.info("=" * 75)

    # Load data once.
    config = GroupLassoConfig()
    config.main_data_path = f"data/expression_data/{dataset}.csv"
    X, y = _load_expression_data(config, logger)
    group_df = _load_grouping_data(config, logger)

    seeds = [config.random_seed + i * 44 for i in range(n_iterations)]
    total_start = time.time()

    all_results: List[ParamComboResult] = []
    for idx, (gr, l1, mg, mgig) in enumerate(combos, 1):
        logger.info(f"\n[{idx}/{n_combos}] λ₁={gr} λ₂={l1} max_gpg={mg} min_gig={mgig}")
        result = _evaluate_params(X, y, group_df, gr, l1, mg, mgig, seeds, config, logger)
        all_results.append(result)
        logger.info(
            f"  → F1={result.mean_f1:.4f}±{result.std_f1:.4f}  "
            f"AUC={result.mean_auc:.4f}  #Feat={result.mean_n_features:.0f}  "
            f"({result.time_seconds:.0f}s)"
        )

    total_elapsed = time.time() - total_start

    # Find best by F1.
    best = max(all_results, key=lambda r: r.mean_f1)
    best_params = {
        "group_reg": best.group_reg,
        "l1_reg": best.l1_reg,
        "max_groups_per_gene": best.max_groups_per_gene,
        "min_genes_per_group": best.min_genes_per_group,
        "mean_f1": best.mean_f1,
        "mean_auc": best.mean_auc,
    }

    search = SearchResult(
        dataset=dataset,
        n_iterations=n_iterations,
        n_combos=n_combos,
        best_params=best_params,
        all_combos=all_results,
    )

    _save_search(search, output_dir, logger)
    _generate_heatmap(all_results, output_dir, logger)

    logger.info(f"\n⏱  Total search time: {total_elapsed / 60:.1f} min")
    logger.info(f"🏆 Best: λ₁={best.group_reg} λ₂={best.l1_reg} "
                f"max_gpg={best.max_groups_per_gene} min_gig={best.min_genes_per_group} "
                f"→ F1={best.mean_f1:.4f}")
    return search


##### SAVE & FIGURES #####

def _save_search(search: SearchResult, output_dir: Path, logger: logging.Logger):
    """Save search results as JSON and Excel."""
    # JSON
    data = {
        "dataset": search.dataset,
        "n_iterations": search.n_iterations,
        "n_combos": search.n_combos,
        "best_params": search.best_params,
        "all_combos": [asdict(c) for c in search.all_combos],
    }
    json_path = output_dir / "hyperparam_results.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"💾 Saved: {json_path.name}")

    # Excel
    rows = [{
        "group_reg": c.group_reg,
        "l1_reg": c.l1_reg,
        "max_groups_per_gene": c.max_groups_per_gene,
        "min_genes_per_group": c.min_genes_per_group,
        "mean_f1": c.mean_f1,
        "std_f1": c.std_f1,
        "mean_auc": c.mean_auc,
        "std_auc": c.std_auc,
        "mean_accuracy": c.mean_accuracy,
        "mean_n_features": c.mean_n_features,
        "n_expanded_cols": c.n_expanded_cols,
        "time_seconds": c.time_seconds,
    } for c in search.all_combos]
    df = pd.DataFrame(rows).sort_values("mean_f1", ascending=False)
    xlsx_path = output_dir / "hyperparam_results.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {xlsx_path.name}")


def _generate_heatmap(
    all_results: List[ParamComboResult],
    output_dir: Path,
    logger: logging.Logger,
):
    """Generate a heatmap of F1 across λ₁ × λ₂ (using best filter combo)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        logger.warning("matplotlib/seaborn not installed — skipping heatmap")
        return

    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Build a pivot table: for each (group_reg, l1_reg), use the best
    # filter combination's F1.
    best_per_reg = {}
    for r in all_results:
        key = (r.group_reg, r.l1_reg)
        if key not in best_per_reg or r.mean_f1 > best_per_reg[key]:
            best_per_reg[key] = r.mean_f1

    gr_vals = sorted(set(k[0] for k in best_per_reg))
    l1_vals = sorted(set(k[1] for k in best_per_reg))

    matrix = np.zeros((len(gr_vals), len(l1_vals)))
    for i, gr in enumerate(gr_vals):
        for j, l1 in enumerate(l1_vals):
            matrix[i, j] = best_per_reg.get((gr, l1), 0)

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(
        matrix, annot=True, fmt=".3f", cmap="YlOrRd",
        xticklabels=[str(v) for v in l1_vals],
        yticklabels=[str(v) for v in gr_vals],
        ax=ax,
    )
    ax.set_xlabel("L1 Reg (λ₂)")
    ax.set_ylabel("Group Reg (λ₁)")
    ax.set_title("Best F1 Score by Regularization Parameters", fontweight="bold")
    plt.tight_layout()

    path = fig_dir / "hyperparam_heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"📈 Saved: {path.name}")


##### CLI #####

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Group Lasso hyperparameter search")
    parser.add_argument("--dataset", type=str, default="GDS1962",
                        help="GEO dataset ID (default: GDS1962)")
    parser.add_argument("--n-iterations", type=int, default=3,
                        help="Iterations per combo (default: 3)")
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()

    od = Path(args.out_dir) if args.out_dir else None
    run_hyperparameter_search(
        dataset=args.dataset,
        n_iterations=args.n_iterations,
        output_dir=od,
    )
