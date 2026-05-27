#!/usr/bin/env python3
"""Re-run biological validation for all publication output folders."""

import logging
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.utils.biological_validation import (
    extract_top_genes,
    query_enrichr,
    query_string_db,
    query_disgenet,
    save_enrichr_results,
    save_string_results,
    save_disgenet_results,
    save_validation_summary,
    ValidationReport,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bio_rerun")

DISGENET_API_KEY = os.environ.get("DISGENET_API_KEY", "")

main_runs_dir = project_root / "output" / "main_runs"
folders = sorted(main_runs_dir.iterdir())

for folder in folders:
    if not folder.is_dir():
        continue

    # Extract dataset ID
    import re
    match = re.search(r"(GDS\d+)", folder.name)
    if not match:
        continue
    dataset_id = match.group(1)

    print(f"\n{'='*60}")
    print(f"  Re-running bio-validation for {dataset_id}")
    print(f"  Folder: {folder.name}")
    print(f"{'='*60}")

    # Extract top genes from the RRA ranking file directly
    import pandas as pd
    rra_path = folder / "aggregated_feature_ranking_rra.xlsx"
    avg_path = folder / "best_averaged_features.xlsx"
    
    genes = []
    try:
        if rra_path.exists():
            df = pd.read_excel(rra_path)
            genes = df["Feature Name"].head(20).tolist()
            genes = [g.split("(")[0].strip() if "(" in g else g.strip() for g in genes]
            print(f"  Genes from RRA ranking: {len(genes)}")
        elif avg_path.exists():
            df = pd.read_excel(avg_path)
            genes = df["Feature Name"].head(20).tolist()
            genes = [g.split("(")[0].strip() if "(" in g else g.strip() for g in genes]
            print(f"  Genes from averaged features: {len(genes)}")
        else:
            logger.error(f"No ranking file found for {dataset_id}")
            continue
    except Exception as e:
        logger.error(f"Failed to extract genes for {dataset_id}: {e}")
        continue

    print(f"  Top genes: {', '.join(genes[:5])}... ({len(genes)} total)")

    bio_dir = folder / "biological_validation"
    bio_dir.mkdir(exist_ok=True)

    # Query Enrichr
    enrichr_results = query_enrichr(genes, logger)
    if enrichr_results:
        save_enrichr_results(enrichr_results, bio_dir, logger)
        print(f"  Enrichr: {len(enrichr_results)} results")
    else:
        print(f"  Enrichr: No results")

    time.sleep(1)  # Rate limit

    # Query STRING-db
    string_data = query_string_db(genes, logger)
    n_interactions = 0
    if string_data and string_data.get("interactions"):
        save_string_results(string_data, bio_dir, logger)
        n_interactions = len(string_data["interactions"])
        print(f"  STRING: {n_interactions} interactions")
    else:
        print(f"  STRING: No interactions")

    time.sleep(1)

    # Query DisGeNET (if API key available)
    disgenet_results = []
    if DISGENET_API_KEY:
        disgenet_results = query_disgenet(genes, logger, api_key=DISGENET_API_KEY)
        if disgenet_results:
            save_disgenet_results(disgenet_results, bio_dir, logger)
            print(f"  DisGeNET: {len(disgenet_results)} results")

    time.sleep(1)

    # Save validation summary
    # Build string interactions list from raw data
    string_interactions = []
    if string_data and string_data.get("interactions"):
        from src.utils.biological_validation import StringInteraction
        for item in string_data["interactions"]:
            if isinstance(item, str):
                # Parse "StringInteraction(protein1='X', protein2='Y', score=0.9)"
                import ast
                # Use a simpler approach: extract fields
                p1 = item.split("protein1='")[1].split("'")[0] if "protein1=" in item else ""
                p2 = item.split("protein2='")[1].split("'")[0] if "protein2=" in item else ""
                sc = float(item.split("score=")[1].rstrip(")")) if "score=" in item else 0.0
                string_interactions.append(StringInteraction(protein1=p1, protein2=p2, score=sc))
            else:
                string_interactions.append(item)

    report = ValidationReport(
        input_genes=genes,
        enrichr_results=enrichr_results if enrichr_results else [],
        string_interactions=string_interactions,
        disease_associations=disgenet_results if disgenet_results else [],
        string_network_url=string_data.get("network_url", "") if string_data else "",
    )
    save_validation_summary(report, bio_dir, logger)
    print(f"  ✓ Summary saved to {bio_dir / 'validation_summary.txt'}")

print(f"\n{'='*60}")
print("  Bio-validation re-run complete!")
print(f"{'='*60}")
