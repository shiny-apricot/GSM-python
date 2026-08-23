#!/usr/bin/env python3
"""Generates formatted gene lists for biological validation."""
import os
import pandas as pd
from pathlib import Path

def generate_gene_lists():
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "output"
    
    datasets = ["GDS1962", "GDS2545", "GDS2547", "GDS2771", "GDS3257", "GDS3837", "GDS5499"]
    
    writer = pd.ExcelWriter(output_dir / "Supplementary_Gene_Lists.xlsx", engine="openpyxl")
    found_any = False
    
    for ds in datasets:
        matching_dirs = list(output_dir.glob(f"gsm_*_revised_{ds}"))
        if not matching_dirs:
            matching_dirs = list(output_dir.glob(f"gsm_*_{ds}*"))
            
        if matching_dirs:
            target_dir = sorted(matching_dirs, key=os.path.getmtime)[-1]
            features_path = target_dir / "best_averaged_features.xlsx"
            
            if features_path.exists():
                df = pd.read_excel(features_path)
                df.to_excel(writer, sheet_name=ds, index=False)
                found_any = True
                print(f"Added {ds} to Supplementary Gene Lists ({len(df)} features).")
            else:
                print(f"Warning: {features_path} not found for {ds}.")
        else:
            print(f"Warning: No output directory found for {ds}.")
            
    if found_any:
        writer.close()
        print(f"Saved successfully to {output_dir / 'Supplementary_Gene_Lists.xlsx'}")
    else:
        print("Failed to find any gene lists to compile.")

if __name__ == "__main__":
    generate_gene_lists()
