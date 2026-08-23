#!/usr/bin/env python3
"""Extracts KEGG enrichment p-values for biological validation."""
import os
import pandas as pd
from pathlib import Path

def extract_kegg_pvalues():
    project_root = Path(__file__).resolve().parents[1]
    main_runs_dir = project_root / "output" / "main_runs"
    
    print("Dataset | Top KEGG Term | P-value | Adjusted P-value")
    print("-" * 60)
    
    for d in main_runs_dir.iterdir():
        if d.is_dir():
            csv_path = d / "biological_validation" / "enrichr_results.csv"
            if csv_path.exists():
                dataset_name = d.name.split("_")[6]
                df = pd.read_csv(csv_path, header=None)
                # Filter for KEGG rows
                kegg_rows = df[df[0].str.contains("KEGG", na=False)]
                if not kegg_rows.empty:
                    # Sort by p-value (column 2)
                    top_kegg = kegg_rows.sort_values(by=2).iloc[0]
                    term = top_kegg[1]
                    pval = float(top_kegg[2])
                    adj_pval = float(top_kegg[3])
                    print(f"{dataset_name:7} | {term[:25]:25} | {pval:.2e} | {adj_pval:.2e}")
                else:
                    print(f"{dataset_name:7} | No KEGG terms found")

if __name__ == "__main__":
    extract_kegg_pvalues()
