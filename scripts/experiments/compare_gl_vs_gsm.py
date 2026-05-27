"""
Group Lasso vs GSM Pipeline — Comparison Script 🧬📊

Purpose:
    Load results from both the GSM (Grouping-Scoring-Modeling) pipeline and the
    Group Lasso workflow, then produce side-by-side tables, figures, and a
    summary JSON that the GL manuscript builder can consume.

Key Functions:
    - load_gsm_results():  Parse GSM modeling_results_all_iterations.json
    - load_gl_results():   Parse GL group_lasso_results.json
    - compare_metrics():   Build a DataFrame of per-method summary metrics
    - compare_genes():     Venn-style gene overlap analysis
    - generate_figures():  Box-plots and bar-charts for visual comparison
    - build_comparison():  Orchestrator — runs all comparisons and saves output

Example Usage:
    python scripts/experiments/compare_gl_vs_gsm.py \\
        --gsm-dir output/gsm_2026_02_16-12_57_29_GDS1962_seed44_cancer-DisGeNET_gedinet \\
        --gl-dir  output/glasso_2026_03_05-07_47_34 \\
        --out-dir output/comparison_gl_vs_gsm
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# --- Project-specific imports ---
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.utils.logger import setup_logger


##### DATA STRUCTURES #####

@dataclass
class MethodMetrics:
    """Aggregated classification metrics for one method."""
    method: str
    n_iterations: int
    mean_f1: float
    std_f1: float
    mean_auc: float
    std_auc: float
    mean_accuracy: float
    std_accuracy: float
    mean_precision: float
    std_precision: float
    mean_recall: float
    std_recall: float
    mean_n_features: float
    mean_n_groups: float


@dataclass
class GeneOverlap:
    """Gene-list overlap between two methods."""
    gsm_genes: List[str]
    gl_genes: List[str]
    common_genes: List[str]
    gsm_only: List[str]
    gl_only: List[str]
    jaccard_index: float


@dataclass
class ComparisonResult:
    """Full comparison output for serialisation and manuscript consumption."""
    gsm_dir: str
    gl_dir: str
    gsm_metrics: dict = field(default_factory=dict)
    gl_metrics: dict = field(default_factory=dict)
    gene_overlap: dict = field(default_factory=dict)
    gsm_per_iteration: list = field(default_factory=list)
    gl_per_iteration: list = field(default_factory=list)


##### LOADING FUNCTIONS #####

def load_gsm_results(
    gsm_dir: Path,
    logger: logging.Logger,
) -> tuple:
    """Load GSM results and extract best-group metrics per iteration.

    For each iteration, selects the model run with the highest F1 score
    (across group-count sweeps) as the representative result.

    Returns:
        (per_iteration_list, top_gene_names)
        per_iteration_list:  list of dicts with keys
            iteration, seed, accuracy, precision, recall, f1, auc_roc,
            n_features, n_groups
        top_gene_names:  list of gene names from the RRA or averaged ranking
    """
    results_path = gsm_dir / "modeling_results_all_iterations.json"
    if not results_path.exists():
        raise FileNotFoundError(f"GSM results not found: {results_path}")

    logger.info(f"📂 Loading GSM results from: {gsm_dir.name}")
    with open(results_path) as f:
        raw = json.load(f)

    per_iteration: List[dict] = []
    for entry in raw:
        meta = entry.get("metadata", {})
        results_list = entry.get("results", [])
        if not results_list:
            continue

        # Pick the model run with the highest F1 score.
        best = max(results_list, key=lambda r: r.get("f1_score", 0))
        per_iteration.append({
            "iteration": meta.get("iteration", len(per_iteration) + 1),
            "seed": meta.get("random_seed", 0),
            "accuracy": best.get("accuracy", 0),
            "precision": best.get("precision", 0),
            "recall": best.get("recall", 0),
            "f1": best.get("f1_score", 0),
            "auc_roc": best.get("auc_roc", 0),
            "n_features": best.get("num_features_used", 0),
            "n_groups": best.get("num_groups_used", 0),
        })

    logger.info(f"  Loaded {len(per_iteration)} iterations from GSM")

    # Load top gene names from ranking files.
    top_genes = _load_gsm_top_genes(gsm_dir, logger)
    return per_iteration, top_genes


def _load_gsm_top_genes(gsm_dir: Path, logger: logging.Logger) -> List[str]:
    """Read the top gene ranking from the best available GSM file."""
    candidates = [
        "aggregated_model_feature_importance_rra.xlsx",
        "best_averaged_features.xlsx",
    ]
    for fname in candidates:
        path = gsm_dir / fname
        if path.exists():
            try:
                df = pd.read_excel(path)
                col = "Feature Name" if "Feature Name" in df.columns else df.columns[0]
                genes = df[col].dropna().tolist()
                # Clean suffixes like "(1)".
                genes = [g.split("(")[0].strip() if isinstance(g, str) else str(g) for g in genes]
                logger.info(f"  GSM top genes from: {fname} ({len(genes)} genes)")
                return genes
            except Exception as e:
                logger.warning(f"  Could not read {fname}: {e}")
    logger.warning("  No GSM gene ranking file found")
    return []


def load_gl_results(
    gl_dir: Path,
    logger: logging.Logger,
) -> tuple:
    """Load Group Lasso results JSON and gene frequency table.

    Returns:
        (per_iteration_list, top_gene_names)
    """
    results_path = gl_dir / "group_lasso_results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"GL results not found: {results_path}")

    logger.info(f"📂 Loading GL results from: {gl_dir.name}")
    with open(results_path) as f:
        raw = json.load(f)

    per_iteration: List[dict] = []
    for entry in raw.get("iterations", []):
        per_iteration.append({
            "iteration": entry["iteration"],
            "seed": entry["seed"],
            "accuracy": entry["accuracy"],
            "precision": entry["precision"],
            "recall": entry["recall"],
            "f1": entry["f1"],
            "auc_roc": entry["auc_roc"],
            "n_features": entry["n_selected_features"],
            "n_groups": entry["n_selected_groups"],
        })
    logger.info(f"  Loaded {len(per_iteration)} iterations from GL")

    # Top genes from frequency table.
    top_genes = _load_gl_top_genes(gl_dir, logger)
    return per_iteration, top_genes


def _load_gl_top_genes(gl_dir: Path, logger: logging.Logger) -> List[str]:
    """Read the gene selection frequency from the GL output."""
    freq_path = gl_dir / "gene_selection_frequency.xlsx"
    if freq_path.exists():
        try:
            df = pd.read_excel(freq_path)
            genes = df["gene"].dropna().tolist()
            logger.info(f"  GL top genes from: gene_selection_frequency.xlsx ({len(genes)} genes)")
            return genes
        except Exception as e:
            logger.warning(f"  Could not read frequency file: {e}")
    return []


##### COMPARISON FUNCTIONS #####

def compare_metrics(
    gsm_iters: List[dict],
    gl_iters: List[dict],
    logger: logging.Logger,
) -> tuple:
    """Build MethodMetrics for both pipelines.

    Returns:
        (gsm_method_metrics, gl_method_metrics)
    """
    gsm_m = _build_method_metrics("GSM (RF)", gsm_iters)
    gl_m = _build_method_metrics("Group Lasso", gl_iters)

    logger.info("\n📊 METRIC COMPARISON")
    logger.info(f"{'Metric':<20} {'GSM (RF)':>18} {'Group Lasso':>18}")
    logger.info("-" * 58)
    for name, gsm_val, gl_val in [
        ("F1", f"{gsm_m.mean_f1:.4f}±{gsm_m.std_f1:.4f}", f"{gl_m.mean_f1:.4f}±{gl_m.std_f1:.4f}"),
        ("AUC-ROC", f"{gsm_m.mean_auc:.4f}±{gsm_m.std_auc:.4f}", f"{gl_m.mean_auc:.4f}±{gl_m.std_auc:.4f}"),
        ("Accuracy", f"{gsm_m.mean_accuracy:.4f}±{gsm_m.std_accuracy:.4f}", f"{gl_m.mean_accuracy:.4f}±{gl_m.std_accuracy:.4f}"),
        ("Precision", f"{gsm_m.mean_precision:.4f}±{gsm_m.std_precision:.4f}", f"{gl_m.mean_precision:.4f}±{gl_m.std_precision:.4f}"),
        ("Recall", f"{gsm_m.mean_recall:.4f}±{gsm_m.std_recall:.4f}", f"{gl_m.mean_recall:.4f}±{gl_m.std_recall:.4f}"),
        ("#Features", f"{gsm_m.mean_n_features:.1f}", f"{gl_m.mean_n_features:.1f}"),
        ("#Groups", f"{gsm_m.mean_n_groups:.1f}", f"{gl_m.mean_n_groups:.1f}"),
    ]:
        logger.info(f"{name:<20} {gsm_val:>18} {gl_val:>18}")

    return gsm_m, gl_m


def _build_method_metrics(method: str, iters: List[dict]) -> MethodMetrics:
    """Aggregate per-iteration dicts into a MethodMetrics dataclass."""
    def _col(key: str) -> np.ndarray:
        return np.array([it[key] for it in iters], dtype=float)

    return MethodMetrics(
        method=method,
        n_iterations=len(iters),
        mean_f1=float(np.mean(_col("f1"))),
        std_f1=float(np.std(_col("f1"))),
        mean_auc=float(np.mean(_col("auc_roc"))),
        std_auc=float(np.std(_col("auc_roc"))),
        mean_accuracy=float(np.mean(_col("accuracy"))),
        std_accuracy=float(np.std(_col("accuracy"))),
        mean_precision=float(np.mean(_col("precision"))),
        std_precision=float(np.std(_col("precision"))),
        mean_recall=float(np.mean(_col("recall"))),
        std_recall=float(np.std(_col("recall"))),
        mean_n_features=float(np.mean(_col("n_features"))),
        mean_n_groups=float(np.mean(_col("n_groups"))),
    )


def compare_genes(
    gsm_genes: List[str],
    gl_genes: List[str],
    logger: logging.Logger,
    *,
    top_n: int = 20,
) -> GeneOverlap:
    """Compute overlap between top genes from both methods.

    Args:
        gsm_genes: Gene list from GSM (ranked).
        gl_genes: Gene list from GL (ranked by selection frequency).
        logger: Logger instance.
        top_n: Use the top-N genes from each list.

    Returns:
        GeneOverlap dataclass with overlap statistics.
    """
    gsm_set = set(gsm_genes[:top_n])
    gl_set = set(gl_genes[:top_n])

    common = sorted(gsm_set & gl_set)
    gsm_only = sorted(gsm_set - gl_set)
    gl_only = sorted(gl_set - gsm_set)

    union_size = len(gsm_set | gl_set)
    jaccard = len(common) / union_size if union_size > 0 else 0.0

    overlap = GeneOverlap(
        gsm_genes=gsm_genes[:top_n],
        gl_genes=gl_genes[:top_n],
        common_genes=common,
        gsm_only=gsm_only,
        gl_only=gl_only,
        jaccard_index=jaccard,
    )

    logger.info(f"\n🧬 GENE OVERLAP (top {top_n})")
    logger.info(f"   GSM genes:   {len(gsm_set)}")
    logger.info(f"   GL genes:    {len(gl_set)}")
    logger.info(f"   Common:      {len(common)}")
    logger.info(f"   Jaccard:     {jaccard:.3f}")
    if common:
        logger.info(f"   Shared genes: {', '.join(common)}")

    return overlap


##### FIGURE GENERATION #####

def generate_figures(
    gsm_iters: List[dict],
    gl_iters: List[dict],
    gene_overlap: GeneOverlap,
    output_dir: Path,
    logger: logging.Logger,
) -> None:
    """Create comparison plots and save as PNG files.

    Generates:
    1. Box-plots comparing F1, AUC, Accuracy between methods.
    2. Bar-chart of per-iteration F1 side-by-side.
    3. Venn-style overlap text summary (ASCII saved as TXT).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping figure generation")
        return

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Box-plots: F1, AUC, Accuracy ---
    _plot_metric_boxplots(gsm_iters, gl_iters, figures_dir, logger)

    # --- 2. Per-iteration F1 bar chart ---
    _plot_iteration_bars(gsm_iters, gl_iters, figures_dir, logger)

    logger.info(f"📈 Figures saved to: {figures_dir}")


def _plot_metric_boxplots(
    gsm_iters: List[dict],
    gl_iters: List[dict],
    figures_dir: Path,
    logger: logging.Logger,
) -> None:
    """Side-by-side box-plots for F1, AUC-ROC, and Accuracy."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = ["f1", "auc_roc", "accuracy"]
    labels = ["F1 Score", "AUC-ROC", "Accuracy"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    for ax, key, label in zip(axes, metrics, labels):
        gsm_vals = [it[key] for it in gsm_iters]
        gl_vals = [it[key] for it in gl_iters]

        bp = ax.boxplot(
            [gsm_vals, gl_vals],
            tick_labels=["GSM (RF)", "Group Lasso"],
            patch_artist=True,
            widths=0.5,
        )
        bp["boxes"][0].set_facecolor("#4C72B0")
        bp["boxes"][1].set_facecolor("#DD8452")
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("GSM vs Group Lasso — Metric Comparison", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = figures_dir / "metric_boxplots.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"  Saved: {path.name}")


def _plot_iteration_bars(
    gsm_iters: List[dict],
    gl_iters: List[dict],
    figures_dir: Path,
    logger: logging.Logger,
) -> None:
    """Grouped bar chart of F1 per iteration for both methods."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_gsm = len(gsm_iters)
    n_gl = len(gl_iters)
    n = max(n_gsm, n_gl)

    gsm_f1 = [it["f1"] for it in gsm_iters] + [0] * (n - n_gsm)
    gl_f1 = [it["f1"] for it in gl_iters] + [0] * (n - n_gl)

    x = np.arange(n)
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(8, n * 0.8), 5))
    ax.bar(x - width / 2, gsm_f1, width, label="GSM (RF)", color="#4C72B0")
    ax.bar(x + width / 2, gl_f1, width, label="Group Lasso", color="#DD8452")

    ax.set_xlabel("Iteration")
    ax.set_ylabel("F1 Score")
    ax.set_title("Per-Iteration F1 Score Comparison", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([str(i + 1) for i in x])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = figures_dir / "iteration_f1_bars.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"  Saved: {path.name}")


##### SAVE FUNCTIONS #####

def save_comparison(
    gsm_m: MethodMetrics,
    gl_m: MethodMetrics,
    gene_overlap: GeneOverlap,
    gsm_iters: List[dict],
    gl_iters: List[dict],
    output_dir: Path,
    logger: logging.Logger,
) -> Path:
    """Save all comparison artefacts to output_dir.

    Creates:
        - comparison_results.json   (for manuscript builder consumption)
        - comparison_metrics.xlsx   (side-by-side table)
        - gene_overlap.xlsx         (overlap gene lists)
        - comparison_summary.txt    (human-readable report)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- JSON ---
    result = ComparisonResult(
        gsm_dir=str(gsm_m.method),
        gl_dir=str(gl_m.method),
        gsm_metrics=asdict(gsm_m),
        gl_metrics=asdict(gl_m),
        gene_overlap={
            "common_genes": gene_overlap.common_genes,
            "gsm_only": gene_overlap.gsm_only,
            "gl_only": gene_overlap.gl_only,
            "jaccard_index": gene_overlap.jaccard_index,
            "n_gsm": len(gene_overlap.gsm_genes),
            "n_gl": len(gene_overlap.gl_genes),
            "n_common": len(gene_overlap.common_genes),
        },
        gsm_per_iteration=gsm_iters,
        gl_per_iteration=gl_iters,
    )
    json_path = output_dir / "comparison_results.json"
    with open(json_path, "w") as f:
        json.dump(asdict(result), f, indent=2)
    logger.info(f"💾 Saved: {json_path.name}")

    # --- Excel: side-by-side metrics ---
    rows = []
    for name, gsm_attr, gl_attr in [
        ("F1 (mean±std)", f"{gsm_m.mean_f1:.4f}±{gsm_m.std_f1:.4f}", f"{gl_m.mean_f1:.4f}±{gl_m.std_f1:.4f}"),
        ("AUC-ROC (mean±std)", f"{gsm_m.mean_auc:.4f}±{gsm_m.std_auc:.4f}", f"{gl_m.mean_auc:.4f}±{gl_m.std_auc:.4f}"),
        ("Accuracy (mean±std)", f"{gsm_m.mean_accuracy:.4f}±{gsm_m.std_accuracy:.4f}", f"{gl_m.mean_accuracy:.4f}±{gl_m.std_accuracy:.4f}"),
        ("Precision (mean±std)", f"{gsm_m.mean_precision:.4f}±{gsm_m.std_precision:.4f}", f"{gl_m.mean_precision:.4f}±{gl_m.std_precision:.4f}"),
        ("Recall (mean±std)", f"{gsm_m.mean_recall:.4f}±{gsm_m.std_recall:.4f}", f"{gl_m.mean_recall:.4f}±{gl_m.std_recall:.4f}"),
        ("Mean #Features", f"{gsm_m.mean_n_features:.1f}", f"{gl_m.mean_n_features:.1f}"),
        ("Mean #Groups", f"{gsm_m.mean_n_groups:.1f}", f"{gl_m.mean_n_groups:.1f}"),
        ("#Iterations", str(gsm_m.n_iterations), str(gl_m.n_iterations)),
    ]:
        rows.append({"Metric": name, "GSM (RF)": gsm_attr, "Group Lasso": gl_attr})
    metrics_df = pd.DataFrame(rows)
    metrics_path = output_dir / "comparison_metrics.xlsx"
    metrics_df.to_excel(metrics_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {metrics_path.name}")

    # --- Excel: gene overlap ---
    max_len = max(
        len(gene_overlap.common_genes),
        len(gene_overlap.gsm_only),
        len(gene_overlap.gl_only),
        1,
    )
    def _pad(lst: list, n: int) -> list:
        return lst + [""] * (n - len(lst))

    overlap_df = pd.DataFrame({
        "Common Genes": _pad(gene_overlap.common_genes, max_len),
        "GSM Only": _pad(gene_overlap.gsm_only, max_len),
        "GL Only": _pad(gene_overlap.gl_only, max_len),
    })
    overlap_path = output_dir / "gene_overlap.xlsx"
    overlap_df.to_excel(overlap_path, index=False, engine="openpyxl")
    logger.info(f"💾 Saved: {overlap_path.name}")

    # --- TXT: summary ---
    txt_path = output_dir / "comparison_summary.txt"
    _write_summary_txt(gsm_m, gl_m, gene_overlap, txt_path)
    logger.info(f"💾 Saved: {txt_path.name}")

    return json_path


def _write_summary_txt(
    gsm_m: MethodMetrics,
    gl_m: MethodMetrics,
    gene_overlap: GeneOverlap,
    path: Path,
) -> None:
    """Write a human-readable comparison summary."""
    lines = [
        "=" * 70,
        " GSM vs Group Lasso — Comparison Summary",
        "=" * 70,
        "",
        f"GSM iterations:          {gsm_m.n_iterations}",
        f"Group Lasso iterations:  {gl_m.n_iterations}",
        "",
        "--- Classification Metrics (mean ± std) ---",
        f"{'Metric':<20} {'GSM (RF)':>18} {'Group Lasso':>18}",
        "-" * 58,
        f"{'F1':<20} {gsm_m.mean_f1:>8.4f}±{gsm_m.std_f1:<8.4f} {gl_m.mean_f1:>8.4f}±{gl_m.std_f1:<8.4f}",
        f"{'AUC-ROC':<20} {gsm_m.mean_auc:>8.4f}±{gsm_m.std_auc:<8.4f} {gl_m.mean_auc:>8.4f}±{gl_m.std_auc:<8.4f}",
        f"{'Accuracy':<20} {gsm_m.mean_accuracy:>8.4f}±{gsm_m.std_accuracy:<8.4f} {gl_m.mean_accuracy:>8.4f}±{gl_m.std_accuracy:<8.4f}",
        f"{'Precision':<20} {gsm_m.mean_precision:>8.4f}±{gsm_m.std_precision:<8.4f} {gl_m.mean_precision:>8.4f}±{gl_m.std_precision:<8.4f}",
        f"{'Recall':<20} {gsm_m.mean_recall:>8.4f}±{gsm_m.std_recall:<8.4f} {gl_m.mean_recall:>8.4f}±{gl_m.std_recall:<8.4f}",
        "",
        f"{'Mean #Features':<20} {gsm_m.mean_n_features:>18.1f} {gl_m.mean_n_features:>18.1f}",
        f"{'Mean #Groups':<20} {gsm_m.mean_n_groups:>18.1f} {gl_m.mean_n_groups:>18.1f}",
        "",
        "--- Gene Overlap (top 20) ---",
        f"GSM unique genes:   {len(gene_overlap.gsm_only)}",
        f"GL unique genes:    {len(gene_overlap.gl_only)}",
        f"Common genes:       {len(gene_overlap.common_genes)}",
        f"Jaccard index:      {gene_overlap.jaccard_index:.3f}",
        "",
    ]
    if gene_overlap.common_genes:
        lines.append(f"Shared: {', '.join(gene_overlap.common_genes)}")
    lines += ["", "=" * 70]

    path.write_text("\n".join(lines), encoding="utf-8")


##### ORCHESTRATOR #####

def build_comparison(
    gsm_dir: Path,
    gl_dir: Path,
    output_dir: Path,
    logger: logging.Logger,
    *,
    top_n_genes: int = 20,
) -> Path:
    """Run the full comparison pipeline.

    Args:
        gsm_dir: Path to a GSM output run directory.
        gl_dir: Path to a GL output run directory.
        output_dir: Directory to write comparison artefacts.
        logger: Logger instance.
        top_n_genes: Number of top genes for overlap analysis.

    Returns:
        Path to the comparison_results.json file.
    """
    logger.info("=" * 70)
    logger.info("🔬 STARTING GSM vs GROUP LASSO COMPARISON")
    logger.info("=" * 70)

    # Step 1: Load results.
    gsm_iters, gsm_genes = load_gsm_results(gsm_dir, logger)
    gl_iters, gl_genes = load_gl_results(gl_dir, logger)

    # Step 2: Compare metrics.
    gsm_m, gl_m = compare_metrics(gsm_iters, gl_iters, logger)

    # Step 3: Compare genes.
    gene_overlap = compare_genes(gsm_genes, gl_genes, logger, top_n=top_n_genes)

    # Step 4: Generate figures.
    generate_figures(gsm_iters, gl_iters, gene_overlap, output_dir, logger)

    # Step 5: Save everything.
    json_path = save_comparison(
        gsm_m, gl_m, gene_overlap, gsm_iters, gl_iters, output_dir, logger,
    )

    logger.info("=" * 70)
    logger.info("✅ COMPARISON COMPLETE")
    logger.info(f"   Results: {output_dir}")
    logger.info("=" * 70)
    return json_path


##### CLI ENTRY POINT #####

def _find_latest_dir(pattern: str) -> Optional[Path]:
    """Find the latest output directory matching a glob pattern."""
    output_root = project_root / "output"
    matches = sorted(output_root.glob(pattern))
    return matches[-1] if matches else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare Group Lasso vs GSM pipeline results",
    )
    parser.add_argument(
        "--gsm-dir",
        type=str,
        default=None,
        help="Path to GSM output directory. Default: latest gsm_* dir.",
    )
    parser.add_argument(
        "--gl-dir",
        type=str,
        default=None,
        help="Path to GL output directory. Default: latest glasso_* dir.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Output directory. Default: output/comparison_gl_vs_gsm",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Top-N genes for overlap comparison (default: 20).",
    )
    args = parser.parse_args()

    # Resolve directories.
    gsm_dir = Path(args.gsm_dir) if args.gsm_dir else _find_latest_dir("gsm_*")
    gl_dir = Path(args.gl_dir) if args.gl_dir else _find_latest_dir("glasso_*")
    out_dir = Path(args.out_dir) if args.out_dir else project_root / "output" / "comparison_gl_vs_gsm"

    if not gsm_dir or not gsm_dir.exists():
        print(f"ERROR: GSM directory not found: {gsm_dir}")
        sys.exit(1)
    if not gl_dir or not gl_dir.exists():
        print(f"ERROR: GL directory not found: {gl_dir}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "comparison.log"
    logger = setup_logger(str(log_file))

    build_comparison(gsm_dir, gl_dir, out_dir, logger, top_n_genes=args.top_n)
