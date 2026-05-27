"""
Gene List Verification Script 🧬

Purpose:
    Cross-check the hardcoded gene lists in build_manuscript_docx.py
    against the actual pipeline output files to ensure manuscript accuracy.

Usage:
    python scripts/maintenance/verify_gene_lists.py

Output:
    Console report showing matches, mismatches, and missing genes per dataset.
    Also writes reports_ARCHIVE/gene_verification_report.txt
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

##### CONFIGURATION #####

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "output"
REPORT_PATH = BASE_DIR / "reports_ARCHIVE" / "gene_verification_report.txt"

##### HARDCODED GENE LISTS FROM MANUSCRIPT SCRIPT #####
# These are copy-pasted from build_manuscript_docx.py _PER_DS dictionary.
# Update these if build_manuscript_docx.py changes.

MANUSCRIPT_GENES: dict[str, list[str]] = {
    "GDS1962": [
        "AKT1", "CDKN2A", "TP53", "VEGFA", "EGFR", "PIK3CA",
        "CCND1", "KIT", "HRAS", "MYC", "BRAF", "HIF1A", "ERBB2", "PTEN",
    ],
    "GDS2545": [
        "ACTB", "EZH2", "STAT3", "GPX3", "LGALS3", "TP63",
        "PLK1", "GSTP1", "FSCN1", "CAV1", "STMN1", "ERBB3", "HDAC1",
    ],
    "GDS2771": [
        "CDKN2A", "CDK4", "BRCA1", "HGF", "MSH2", "CDK2",
        "EGR1", "CD82", "PDGFRB", "STAT1", "FOS", "JUN",
    ],
    "GDS3257": [
        "CD34", "BCR", "FAS", "CD38", "RUNX1T1", "CDKN2A",
        "ERG", "FGFR1", "EZH2", "CBFB", "CD19", "BRCA1", "HIF1A",
        "CD33", "RUNX3",
    ],
    "GDS3268": [
        "HDAC9", "DUSP3", "CXCR4", "TIMP2", "BECN1", "LOXL1",
        "CD59", "CDCA8", "PLAU", "ADM", "AKT1", "SERPINF1", "MKI67", "MMP9",
    ],
    "GDS3837": [
        "COL10A1", "ACE", "GOLM1", "AGER", "SLIT2", "OTUD1",
        "QKI", "ROBO4", "HSPA12B", "MTA3", "CELF2", "ARHGEF19",
        "IGSF10", "XDH", "NUSAP1",
    ],
    "GDS5499": [
        "SBDSP1", "DNAJB1", "HSPA1A", "SBDS", "PVT1", "TNFAIP3",
        "TSPYL2", "SMAD7", "FXR1", "KCNJ2", "FPR2", "MYLIP",
        "IRF2BP2", "CAMK4",
    ],
}


##### DATA STRUCTURES #####

@dataclass
class DatasetVerification:
    """Result of verifying one dataset's gene list."""
    dataset: str
    output_folder: str
    source_file: str
    pipeline_genes: list[str] = field(default_factory=list)
    manuscript_genes: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    in_manuscript_only: list[str] = field(default_factory=list)
    in_pipeline_only: list[str] = field(default_factory=list)
    error: str = ""


##### HELPER FUNCTIONS #####

def find_latest_output_folder(dataset_id: str) -> Path | None:
    """Find the most recent output folder for a dataset.

    Folders follow the naming pattern:
        gsm_YYYY_MM_DD-HH_MM_SS_DATASETNAME_GROUPNAME
    We match on the dataset ID appearing anywhere in the folder name
    and pick the latest by lexicographic sort (timestamp-based names).
    """
    if not OUTPUT_DIR.exists():
        return None

    matching = [
        d for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and dataset_id in d.name
    ]
    if not matching:
        return None

    # Sort by name (timestamps sort lexicographically)
    matching.sort(key=lambda p: p.name)
    return matching[-1]


def read_genes_from_rra_excel(folder: Path) -> tuple[list[str], str]:
    """Read top-20 gene names from the aggregated RRA Excel file.

    Tries files in priority order:
        1. aggregated_feature_ranking_group_derived_rra.xlsx
        2. aggregated_feature_ranking_individual_rra.xlsx
        3. best_averaged_features.xlsx

    Returns:
        (list of gene names, source file name)
    """
    priority_files = [
        "aggregated_feature_ranking_group_derived_rra.xlsx",
        "aggregated_feature_ranking_individual_rra.xlsx",
        "best_averaged_features.xlsx",
    ]

    for fname in priority_files:
        fpath = folder / fname
        if fpath.exists():
            df = pd.read_excel(fpath)
            # The gene name column is "Feature Name" in all variants
            col = "Feature Name"
            if col not in df.columns:
                # Fallback: try the second column (first is Rank)
                col = df.columns[1]
            genes = df[col].dropna().astype(str).tolist()[:20]
            return genes, fname

    # Last resort: try validation_summary.txt INPUT GENES line
    val_file = folder / "biological_validation" / "validation_summary.txt"
    if val_file.exists():
        text = val_file.read_text()
        match = re.search(r"INPUT GENES.*?:\s*(.+)", text, re.IGNORECASE)
        if match:
            genes = [g.strip() for g in match.group(1).split(",") if g.strip()]
            return genes, "biological_validation/validation_summary.txt"

    return [], "(no ranking file found)"


def verify_dataset(dataset_id: str) -> DatasetVerification:
    """Verify gene list for a single dataset."""
    manuscript_genes = MANUSCRIPT_GENES.get(dataset_id, [])

    folder = find_latest_output_folder(dataset_id)
    if folder is None:
        return DatasetVerification(
            dataset=dataset_id,
            output_folder="(not found)",
            source_file="",
            manuscript_genes=manuscript_genes,
            error=f"No output folder found for {dataset_id}",
        )

    pipeline_genes, source_file = read_genes_from_rra_excel(folder)
    if not pipeline_genes:
        return DatasetVerification(
            dataset=dataset_id,
            output_folder=folder.name,
            source_file=source_file,
            manuscript_genes=manuscript_genes,
            error="Could not read pipeline genes from output files",
        )

    # Compare (case-insensitive)
    manuscript_set = {g.upper() for g in manuscript_genes}
    pipeline_set = {g.upper() for g in pipeline_genes}

    matched = sorted(manuscript_set & pipeline_set)
    in_manuscript_only = sorted(manuscript_set - pipeline_set)
    in_pipeline_only = sorted(pipeline_set - manuscript_set)

    return DatasetVerification(
        dataset=dataset_id,
        output_folder=folder.name,
        source_file=source_file,
        pipeline_genes=pipeline_genes,
        manuscript_genes=manuscript_genes,
        matched=matched,
        in_manuscript_only=in_manuscript_only,
        in_pipeline_only=in_pipeline_only,
    )


##### REPORTING #####

def format_report(results: list[DatasetVerification]) -> str:
    """Format the full verification report as text."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  GENE LIST VERIFICATION REPORT")
    lines.append("  Manuscript _PER_DS  vs  Pipeline Output")
    lines.append("=" * 70)
    lines.append("")

    total_match = 0
    total_manuscript = 0
    total_mismatch = 0

    for r in results:
        lines.append(f"--- {r.dataset} ---")
        lines.append(f"  Output folder : {r.output_folder}")
        lines.append(f"  Source file   : {r.source_file}")

        if r.error:
            lines.append(f"  ERROR: {r.error}")
            lines.append("")
            continue

        lines.append(f"  Manuscript genes ({len(r.manuscript_genes)}): "
                      f"{', '.join(r.manuscript_genes)}")
        lines.append(f"  Pipeline genes   ({len(r.pipeline_genes)}): "
                      f"{', '.join(r.pipeline_genes)}")
        lines.append("")

        pct = (len(r.matched) / len(r.manuscript_genes) * 100
               if r.manuscript_genes else 0)
        lines.append(f"  Matched       : {len(r.matched)}/{len(r.manuscript_genes)} "
                      f"({pct:.0f}%)  {', '.join(r.matched)}")

        if r.in_manuscript_only:
            lines.append(f"  In manuscript ONLY: {', '.join(r.in_manuscript_only)}")
        if r.in_pipeline_only:
            lines.append(f"  In pipeline ONLY  : {', '.join(r.in_pipeline_only)}")

        total_match += len(r.matched)
        total_manuscript += len(r.manuscript_genes)
        total_mismatch += len(r.in_manuscript_only)
        lines.append("")

    # Summary
    lines.append("=" * 70)
    lines.append("  SUMMARY")
    lines.append("=" * 70)
    overall_pct = (total_match / total_manuscript * 100
                   if total_manuscript else 0)
    lines.append(f"  Total matched genes : {total_match}/{total_manuscript} "
                 f"({overall_pct:.0f}%)")
    lines.append(f"  Total in manuscript only (not in pipeline top-20): "
                 f"{total_mismatch}")
    lines.append("")

    if total_mismatch > 0:
        lines.append("  ACTION NEEDED: Update _PER_DS in build_manuscript_docx.py")
        lines.append("  to match the actual pipeline output.")
    else:
        lines.append("  All manuscript gene lists match pipeline output.")

    lines.append("")
    return "\n".join(lines)


##### MAIN #####

def main() -> None:
    """Run gene list verification for all datasets."""
    datasets = sorted(MANUSCRIPT_GENES.keys())
    results = [verify_dataset(ds) for ds in datasets]

    report = format_report(results)
    print(report)

    # Also save to file
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
