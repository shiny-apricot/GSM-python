"""
Manuscript Results Analysis & Figure Generation 📊

Purpose:
    Analyzes GSM pipeline results across multiple datasets for manuscript tables
    and figures. Extracts performance metrics, biological validation data,
    generates cross-dataset comparison figures, and outputs structured JSON
    for the manuscript builder.

Key Functions:
    - parse_summary_report(): Parse summary reports for key metrics
    - parse_validation_summary(): Parse biological validation data
    - generate_*(): Create publication-quality matplotlib figures
    - main(): Orchestrate analysis and write manuscript_data.json

Example Usage:
    python scripts/manuscript/analyze_manuscript_results.py
"""

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

project_root = Path(__file__).resolve().parents[2]


##### DATA STRUCTURES #####

@dataclass
class PerformanceMetrics:
    """Performance metrics for a single dataset."""
    dataset_id: str
    disease: str
    f1_score: float
    f1_ci_lower: float
    f1_ci_upper: float
    accuracy: float
    precision: float
    recall: float
    auc_roc: float
    auc_ci_lower: float
    auc_ci_upper: float
    cv_f1_mean: float
    cv_f1_std: float
    groups_used: int
    features_used: int
    model_name: str


@dataclass
class BiologicalValidation:
    """Biological validation results for a single dataset."""
    dataset_id: str
    input_genes: list[str]
    top_disgenet_terms: list[dict]
    top_kegg_pathways: list[dict]
    top_reactome_pathways: list[dict]
    top_go_bp_terms: list[dict]
    top_wikipathway_terms: list[dict]
    string_interaction_count: int
    top_interactions: list[dict]


##### DATASET CONFIGURATION #####

DATASET_DISEASES = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate Cancer",
    "GDS2547": "Prostate Cancer (Lapointe)",
    "GDS2771": "Lung Cancer",
    "GDS3257": "Acute Myeloid Leukemia",
    "GDS3837": "Colorectal Cancer",
    "GDS5499": "Pancreatic Cancer",
}

DATASET_SHORT = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate",
    "GDS2547": "Prostate (2)",
    "GDS2771": "Lung",
    "GDS3257": "AML",
    "GDS3837": "Colorectal",
    "GDS5499": "Pancreatic",
}


##### PARSING FUNCTIONS #####

def parse_summary_report(file_path: Path) -> Optional[PerformanceMetrics]:
    """Parse a summary_report.txt file to extract performance metrics."""
    if not file_path.exists():
        return None

    content = file_path.read_text()

    # Extract dataset ID from parent folder name
    folder_name = file_path.parent.name
    dataset_match = re.search(r"(GDS\d+)", folder_name)
    dataset_id = dataset_match.group(1) if dataset_match else "Unknown"

    # Extract metrics using regex patterns
    f1_match = re.search(
        r"F1 Score:\s+([\d.]+)\s+\(95% CI:\s+([\d.]+)\s+-\s+([\d.]+)\)", content
    )
    acc_match = re.search(r"Accuracy:\s+([\d.]+)", content)
    prec_match = re.search(r"Precision:\s+([\d.]+)", content)
    recall_match = re.search(r"Recall:\s+([\d.]+)", content)
    auc_match = re.search(
        r"AUC-ROC:\s+([\d.]+)\s+\(95% CI:\s+([\d.]+)\s+-\s+([\d.]+)\)", content
    )
    cv_match = re.search(r"CV F1 Mean:\s+([\d.]+)\s+±\s+([\d.]+)", content)
    groups_match = re.search(r"Groups Used:\s+(\d+)", content)
    features_match = re.search(r"Features Used:\s+(\d+)", content)
    model_match = re.search(r"Model Name:\s+(\w+)", content)

    if not all([f1_match, acc_match, prec_match, recall_match, auc_match]):
        print(f"⚠️  Missing metrics in {file_path}")
        return None

    return PerformanceMetrics(
        dataset_id=dataset_id,
        disease=DATASET_DISEASES.get(dataset_id, "Unknown"),
        f1_score=float(f1_match.group(1)),
        f1_ci_lower=float(f1_match.group(2)),
        f1_ci_upper=float(f1_match.group(3)),
        accuracy=float(acc_match.group(1)),
        precision=float(prec_match.group(1)),
        recall=float(recall_match.group(1)),
        auc_roc=float(auc_match.group(1)),
        auc_ci_lower=float(auc_match.group(2)),
        auc_ci_upper=float(auc_match.group(3)),
        cv_f1_mean=float(cv_match.group(1)) if cv_match else 0.0,
        cv_f1_std=float(cv_match.group(2)) if cv_match else 0.0,
        groups_used=int(groups_match.group(1)) if groups_match else 0,
        features_used=int(features_match.group(1)) if features_match else 0,
        model_name=model_match.group(1) if model_match else "Unknown",
    )


def parse_validation_summary(
    file_path: Path, dataset_id: str
) -> Optional[BiologicalValidation]:
    """Parse validation_summary.txt for biological validation data."""
    if not file_path.exists():
        return None

    content = file_path.read_text()

    # Extract input genes
    genes_match = re.search(r"INPUT GENES:\n-+\n(.+?)\n\n", content, re.DOTALL)
    input_genes = []
    if genes_match:
        input_genes = [g.strip() for g in genes_match.group(1).split(",")]

    # Extract enrichment terms from each database
    disgenet_terms = extract_enrichment_terms(content, "DisGeNET:")
    kegg_terms = extract_enrichment_terms(content, "KEGG_2021_Human:")
    reactome_terms = extract_enrichment_terms(content, "Reactome_2022:")
    go_bp_terms = extract_enrichment_terms(content, "GO_Biological_Process_2023:")
    wiki_terms = extract_enrichment_terms(content, "WikiPathway_2023_Human:")

    # Extract STRING interaction count
    interaction_match = re.search(r"Total interactions found:\s+(\d+)", content)
    interaction_count = int(interaction_match.group(1)) if interaction_match else 0

    # Extract top interactions
    top_interactions = extract_string_interactions(content)

    return BiologicalValidation(
        dataset_id=dataset_id,
        input_genes=input_genes,
        top_disgenet_terms=disgenet_terms,
        top_kegg_pathways=kegg_terms,
        top_reactome_pathways=reactome_terms,
        top_go_bp_terms=go_bp_terms,
        top_wikipathway_terms=wiki_terms,
        string_interaction_count=interaction_count,
        top_interactions=top_interactions,
    )


def extract_enrichment_terms(content: str, section_header: str) -> list[dict]:
    """Extract enrichment terms from a section of the validation summary."""
    terms = []

    section_pattern = (
        rf"{re.escape(section_header)}\n(.+?)(?=\n\n[A-Z]|\n\nPROTEIN|\Z)"
    )
    section_match = re.search(section_pattern, content, re.DOTALL)
    if not section_match:
        return terms

    section_content = section_match.group(1)

    term_pattern = (
        r"•\s+(.+?)\n\s+P-value:\s+([\d.e+-]+),\s+Combined Score:\s+([\d.]+)"
        r"\n\s+Genes:\s+(.+?)(?=\n\s+•|\Z)"
    )
    for match in re.finditer(term_pattern, section_content, re.DOTALL):
        terms.append({
            "term": match.group(1).strip(),
            "p_value": float(match.group(2)),
            "combined_score": float(match.group(3)),
            "genes": [g.strip() for g in match.group(4).split(",")],
        })
    return terms[:3]


def extract_string_interactions(content: str) -> list[dict]:
    """Extract STRING protein-protein interactions."""
    interactions = []
    # Handle gene names with hyphens like HLA-G
    pattern = r"•\s+([\w-]+)\s+<->\s+([\w-]+)\s+\(score:\s+([\d.]+)\)"
    for match in re.finditer(pattern, content):
        interactions.append({
            "protein1": match.group(1),
            "protein2": match.group(2),
            "score": float(match.group(3)),
        })
    return interactions[:5]


##### FIGURE GENERATION #####

def setup_plot_style():
    """Set up consistent matplotlib style for all manuscript figures."""
    plt.rcParams.update({
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def generate_performance_comparison(
    results: list[PerformanceMetrics], output_dir: Path
) -> Path:
    """Generate grouped bar chart comparing F1, AUC, Accuracy across datasets.

    Args:
        results: List of PerformanceMetrics for each dataset
        output_dir: Directory to save the figure

    Returns:
        Path to the saved figure
    """
    setup_plot_style()

    labels = [
        f"{r.dataset_id}\n({DATASET_SHORT.get(r.dataset_id, '')})"
        for r in results
    ]
    f1_scores = [r.f1_score for r in results]
    auc_scores = [r.auc_roc for r in results]
    acc_scores = [r.accuracy for r in results]
    f1_lo = [r.f1_score - r.f1_ci_lower for r in results]
    f1_hi = [r.f1_ci_upper - r.f1_score for r in results]
    auc_lo = [r.auc_roc - r.auc_ci_lower for r in results]
    auc_hi = [r.auc_ci_upper - r.auc_roc for r in results]

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 5.5))

    bars1 = ax.bar(
        x - width, f1_scores, width, label="F1-Score",
        color="#2196F3", yerr=[f1_lo, f1_hi],
        capsize=3, error_kw={"lw": 0.8},
    )
    bars2 = ax.bar(
        x, auc_scores, width, label="AUC-ROC",
        color="#4CAF50", yerr=[auc_lo, auc_hi],
        capsize=3, error_kw={"lw": 0.8},
    )
    bars3 = ax.bar(
        x + width, acc_scores, width, label="Accuracy",
        color="#FF9800",
    )

    ax.set_ylabel("Score")
    ax.set_title("Classification Performance Across Cancer Datasets")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0.5, 1.08)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.1))
    ax.legend(loc="lower left", frameon=True, edgecolor="gray")
    ax.axhline(y=0.5, color="gray", linestyle=":", linewidth=0.6)

    # Add value labels on bars
    for bar_group in [bars1, bars2, bars3]:
        for bar in bar_group:
            height = bar.get_height()
            ax.annotate(
                f"{height:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha="center", va="bottom", fontsize=7,
            )

    fig.tight_layout()
    out_path = output_dir / "fig_performance_comparison.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {out_path.name}")
    return out_path


def generate_groups_features_chart(
    results: list[PerformanceMetrics], output_dir: Path
) -> Path:
    """Generate scatter plot of groups vs features, sized by F1-Score."""
    setup_plot_style()

    fig, ax = plt.subplots(figsize=(8, 5.5))

    colors = plt.cm.Set2(np.linspace(0, 1, len(results)))
    for i, r in enumerate(results):
        size = max(80, r.f1_score * 200)
        ax.scatter(
            r.groups_used, r.features_used, s=size,
            alpha=0.85, edgecolors="black", linewidth=0.5,
            color=colors[i], zorder=3,
        )
        ax.annotate(
            f"{r.dataset_id}\n({DATASET_SHORT.get(r.dataset_id, '')})",
            (r.groups_used, r.features_used),
            textcoords="offset points", xytext=(10, 4),
            fontsize=8, ha="left",
        )

    ax.set_xlabel("Number of Groups Used")
    ax.set_ylabel("Number of Features Used")
    ax.set_title(
        "Group Count vs Feature Count per Dataset\n"
        "(marker size proportional to F1-Score)"
    )
    ax.set_xlim(0, max(r.groups_used for r in results) + 1)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out_path = output_dir / "fig_groups_features_scatter.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {out_path.name}")
    return out_path


def generate_cv_stability_chart(
    results: list[PerformanceMetrics], output_dir: Path
) -> Path:
    """Generate horizontal bar chart of test-set F1 with bootstrap 95% CI."""
    setup_plot_style()

    labels = [
        f"{r.dataset_id} ({DATASET_SHORT.get(r.dataset_id, '')})"
        for r in results
    ]
    f1_scores = [r.f1_score for r in results]
    ci_lowers = [r.f1_ci_lower for r in results]
    ci_uppers = [r.f1_ci_upper for r in results]

    # Sort by F1 score for better readability
    order = np.argsort(f1_scores)
    labels = [labels[i] for i in order]
    f1_scores = [f1_scores[i] for i in order]
    ci_lowers = [ci_lowers[i] for i in order]
    ci_uppers = [ci_uppers[i] for i in order]

    # Asymmetric error bars from CI bounds
    err_low = [f - lo for f, lo in zip(f1_scores, ci_lowers)]
    err_high = [hi - f for f, hi in zip(f1_scores, ci_uppers)]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    y_pos = np.arange(len(labels))

    # Color bars by score value
    norm_scores = np.array(f1_scores)
    colors = plt.cm.RdYlGn(norm_scores)

    ax.barh(
        y_pos, f1_scores, xerr=[err_low, err_high], height=0.6,
        color=colors, edgecolor="gray", linewidth=0.5,
        capsize=3, error_kw={"lw": 0.8},
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Test-set F1 (bootstrap 95% CI)")
    ax.set_title("Classification Stability Across Datasets")
    ax.set_xlim(0, 1.15)
    ax.axvline(x=1.0, color="gray", linestyle=":", linewidth=0.6)

    # Add value labels
    for i, (f, lo, hi) in enumerate(zip(f1_scores, ci_lowers, ci_uppers)):
        ax.text(hi + 0.02, i, f"{f:.2f} [{lo:.2f}\u2013{hi:.2f}]",
                va="center", fontsize=8)

    fig.tight_layout()
    out_path = output_dir / "fig_cv_stability.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"   \u2713 {out_path.name}")
    return out_path


def generate_biological_validation_chart(
    validations: list[BiologicalValidation], output_dir: Path
) -> Path:
    """Generate dual-axis bar chart of STRING interactions and gene counts."""
    setup_plot_style()

    labels = [
        f"{v.dataset_id}\n({DATASET_SHORT.get(v.dataset_id, '')})"
        for v in validations
    ]
    interactions = [v.string_interaction_count for v in validations]
    gene_counts = [len(v.input_genes) for v in validations]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    ax2 = ax1.twinx()

    bars1 = ax1.bar(
        x - width / 2, interactions, width,
        label="STRING Interactions",
        color="#5C6BC0", alpha=0.85,
    )
    bars2 = ax2.bar(
        x + width / 2, gene_counts, width,
        label="Validated Genes",
        color="#26A69A", alpha=0.85,
    )

    ax1.set_xlabel("Dataset")
    ax1.set_ylabel("STRING Interactions", color="#5C6BC0")
    ax2.set_ylabel("Number of Validated Genes", color="#26A69A")
    ax1.set_title("Biological Validation: Interactions & Gene Counts")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.tick_params(axis="y", labelcolor="#5C6BC0")
    ax2.tick_params(axis="y", labelcolor="#26A69A")

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2, labels1 + labels2,
        loc="upper right", frameon=True, edgecolor="gray",
    )

    fig.tight_layout()
    out_path = output_dir / "fig_biological_validation.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {out_path.name}")
    return out_path


def generate_enrichment_heatmap(
    validations: list[BiologicalValidation], output_dir: Path
) -> Path:
    """Generate heatmap showing enrichment significance per database per dataset."""
    setup_plot_style()

    databases = ["DisGeNET", "KEGG", "Reactome", "GO:BP", "WikiPathway"]
    dataset_ids = [v.dataset_id for v in validations]

    # Build matrix: -log10(best p-value) per database per dataset
    matrix = np.zeros((len(dataset_ids), len(databases)))
    for i, v in enumerate(validations):
        sources = [
            v.top_disgenet_terms,
            v.top_kegg_pathways,
            v.top_reactome_pathways,
            v.top_go_bp_terms,
            v.top_wikipathway_terms,
        ]
        for j, terms in enumerate(sources):
            if terms:
                best_p = min(t["p_value"] for t in terms)
                # Cap -log10(p) at 35 for display
                matrix[i, j] = min(-np.log10(max(best_p, 1e-50)), 35)

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(np.arange(len(databases)))
    ax.set_xticklabels(databases, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(dataset_ids)))
    ax.set_yticklabels(
        [f"{d} ({DATASET_SHORT.get(d, '')})" for d in dataset_ids]
    )
    ax.set_title("Pathway Enrichment Significance\n(−log₁₀ p-value, capped at 35)")

    # Annotate cells with values
    for i in range(len(dataset_ids)):
        for j in range(len(databases)):
            val = matrix[i, j]
            color = "white" if val > 20 else "black"
            text = f"{val:.1f}" if val > 0 else "–"
            ax.text(j, i, text, ha="center", va="center", fontsize=8, color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("−log₁₀(p-value)")

    fig.tight_layout()
    out_path = output_dir / "fig_enrichment_heatmap.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {out_path.name}")
    return out_path


def generate_metrics_radar(
    results: list[PerformanceMetrics], output_dir: Path
) -> Path:
    """Generate radar/spider chart comparing all metrics for each dataset."""
    setup_plot_style()

    categories = ["F1-Score", "Accuracy", "Precision", "Recall", "AUC-ROC"]
    n_cats = len(categories)
    angles = np.linspace(0, 2 * np.pi, n_cats, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    colors = plt.cm.Set2(np.linspace(0, 1, len(results)))

    for i, r in enumerate(results):
        values = [r.f1_score, r.accuracy, r.precision, r.recall, r.auc_roc]
        values += values[:1]
        label = f"{r.dataset_id} ({DATASET_SHORT.get(r.dataset_id, '')})"
        ax.plot(angles, values, "o-", linewidth=1.5, color=colors[i], label=label)
        ax.fill(angles, values, alpha=0.08, color=colors[i])

    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
    ax.set_ylim(0.5, 1.05)
    ax.set_title("Multi-Metric Comparison Across Datasets", y=1.08)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.15, -0.15), fontsize=8)

    fig.tight_layout()
    out_path = output_dir / "fig_metrics_radar.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {out_path.name}")
    return out_path


##### MAIN ANALYSIS #####

def find_latest_output_folders(output_dir: Path) -> dict[str, Path]:
    """Find the most recent output folder for each dataset.
    
    Searches both the root output directory and organized subdirectories
    (main_runs/, sensitivity_runs/, classifier_comparison/, etc.).
    Prioritizes main_runs/ over other locations.
    """
    folders = {}
    
    # Search in main_runs/ first (preferred location for production runs)
    main_runs_dir = output_dir / "main_runs"
    search_dirs = []
    if main_runs_dir.is_dir():
        search_dirs.append(main_runs_dir)
    # Fall back to root output dir for any runs not yet organized
    search_dirs.append(output_dir)
    
    for search_dir in search_dirs:
        for folder in sorted(search_dir.iterdir(), reverse=True):
            if not folder.is_dir():
                continue
            # Skip organizational subdirectories when scanning root
            if folder.name in ("main_runs", "sensitivity_runs", "test_runs", 
                               "classifier_comparison", "archives"):
                continue
            match = re.search(r"(GDS\d+)", folder.name)
            if match:
                dataset_id = match.group(1)
                # Only include datasets that are in DATASET_DISEASES
                if dataset_id not in folders and dataset_id in DATASET_DISEASES:
                    folders[dataset_id] = folder
    return folders


def main():
    """Main analysis: extract data, generate figures, write JSON for docx builder."""
    print("=" * 70)
    print("📊 GSM Manuscript Results Analysis & Figure Generation")
    print("=" * 70)

    output_dir = project_root / "output"
    manuscript_root = project_root / "reports_ARCHIVE" / "manuscript"
    fig_dir = manuscript_root / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Discover dataset folders
    dataset_folders = find_latest_output_folders(output_dir)
    print(f"\n📁 Found {len(dataset_folders)} dataset folders")
    for dataset_id, folder in sorted(dataset_folders.items()):
        print(f"   - {dataset_id}: {folder.name}")

    # Extract performance metrics
    print("\n📈 Extracting performance metrics...")
    performance_results = []
    dataset_figure_paths = {}  # dataset_id -> { figure_name: absolute_path }
    for dataset_id, folder in sorted(dataset_folders.items()):
        summary_file = folder / "summary_report.txt"
        metrics = parse_summary_report(summary_file)
        if metrics:
            performance_results.append(metrics)
            print(
                f"   ✓ {dataset_id}: F1={metrics.f1_score:.3f}, "
                f"AUC={metrics.auc_roc:.3f}"
            )
            # Collect existing per-dataset figure paths
            fig_folder = folder / "figures"
            if fig_folder.exists():
                dataset_figure_paths[dataset_id] = {
                    f.stem: str(f) for f in fig_folder.glob("*.png")
                }

    # Extract biological validation
    print("\n🧬 Extracting biological validation...")
    validation_results = []
    for dataset_id, folder in sorted(dataset_folders.items()):
        validation_file = folder / "biological_validation" / "validation_summary.txt"
        validation = parse_validation_summary(validation_file, dataset_id)
        if validation:
            validation_results.append(validation)
            print(
                f"   ✓ {dataset_id}: {len(validation.input_genes)} genes, "
                f"{validation.string_interaction_count} interactions"
            )

    # Generate manuscript figures
    print("\n🖼️  Generating manuscript figures...")
    fig_paths = {}
    if performance_results:
        fig_paths["performance_comparison"] = str(
            generate_performance_comparison(performance_results, fig_dir)
        )
        fig_paths["groups_features_scatter"] = str(
            generate_groups_features_chart(performance_results, fig_dir)
        )
        fig_paths["cv_stability"] = str(
            generate_cv_stability_chart(performance_results, fig_dir)
        )
        fig_paths["metrics_radar"] = str(
            generate_metrics_radar(performance_results, fig_dir)
        )
    if validation_results:
        fig_paths["biological_validation"] = str(
            generate_biological_validation_chart(validation_results, fig_dir)
        )
        fig_paths["enrichment_heatmap"] = str(
            generate_enrichment_heatmap(validation_results, fig_dir)
        )

    # Write structured JSON for the docx builder
    structured_data = {
        "performance": [asdict(r) for r in performance_results],
        "validation": [asdict(v) for v in validation_results],
        "manuscript_figures": fig_paths,
        "dataset_figures": dataset_figure_paths,
    }
    json_path = manuscript_root / "data" / "manuscript_data.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(structured_data, indent=2))
    print(f"\n📦 Structured data written to: {json_path}")

    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    if performance_results:
        avg_f1 = sum(r.f1_score for r in performance_results) / len(
            performance_results
        )
        avg_auc = sum(r.auc_roc for r in performance_results) / len(
            performance_results
        )
        print(f"  Datasets with results:  {len(performance_results)}")
        print(f"  Average F1 Score:       {avg_f1:.3f}")
        print(f"  Average AUC-ROC:        {avg_auc:.3f}")
    if validation_results:
        total_int = sum(v.string_interaction_count for v in validation_results)
        print(f"  Total STRING int.:      {total_int}")
    print(f"  Figures generated:      {len(fig_paths)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
