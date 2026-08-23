"""Runs permutation tests across all datasets."""
import os
import subprocess
import pandas as pd
from pathlib import Path
import json
import sys

project_root = Path(__file__).resolve().parents[2]
output_dir = project_root / "output"
perm_script = project_root / "scripts" / "experiments" / "permutation_test.py"

datasets_info = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate Cancer",
    "GDS2547": "Prostate Cancer",
    "GDS2771": "Lung Cancer",
    "GDS3257": "Acute Myeloid Leukemia",
    "GDS3837": "Colorectal Cancer",
    "GDS5499": "Pancreatic Cancer"
}

for ds, disease in datasets_info.items():
    print(f"\n======================================")
    print(f"Processing {ds} ({disease})...")
    # Find the revised output dir
    matching_dirs = list(output_dir.rglob(f"gsm_*_{ds}_cancer*")) + list(output_dir.rglob(f"gsm_*_{ds}_randomforest*")) + list(output_dir.rglob(f"gsm_*_{ds}_xgboost*"))
    
    if not matching_dirs:
        print(f"No output dir found for {ds}")
        continue
    
    # Sort by modification time to get the latest
    target_dir = sorted(matching_dirs, key=os.path.getmtime)[-1]
    features_file = target_dir / "best_averaged_features.xlsx"
    
    if not features_file.exists():
        print(f"best_averaged_features.xlsx not found in {target_dir}")
        continue
        
    df = pd.read_excel(features_file)
    # The feature names are in the first column "feature"
    if "Feature Name" in df.columns:
        genes = df["Feature Name"].tolist()
    elif "feature" in df.columns:
        genes = df["feature"].tolist()
    else:
        genes = df.iloc[:, 1].tolist()
        
    genes_str = ",".join([str(g) for g in genes])
    
    cmd = [
        sys.executable, str(perm_script),
        "--dataset", ds,
        "--disease", disease,
        "--genes", genes_str,
        "--perms", "10000"
    ]
    
    out = subprocess.run(cmd, capture_output=True, text=True)
    print(out.stdout)
    if out.stderr:
        print("ERRORS:", out.stderr)
        
print("All permutations done.")
