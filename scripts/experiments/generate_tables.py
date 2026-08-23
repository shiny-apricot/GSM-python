"""Generates LaTeX/Markdown tables for experiment results."""
import pandas as pd
import json
import os
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
output_dir = project_root / "output"

def generate_baselines_table():
    baselines_path = output_dir / "baselines" / "baseline_results.json"
    if not baselines_path.exists():
        print("Baselines results not found.")
        return ""
    
    with open(baselines_path, "r") as f:
        data = json.load(f)
        
    df = pd.DataFrame(data)
    if df.empty: return ""
    
    # We want rows to be datasets and columns to be methods, values to be F1
    df_f1 = df.pivot(index="dataset_id", columns="method", values="f1_score")
    
    md_table = "### Baselines Comparison (F1-score)\n\n"
    md_table += df_f1.to_markdown(floatfmt=".3f")
    md_table += "\n\n"
    return md_table

def generate_main_performance_table():
    datasets = ["GDS1962", "GDS2545", "GDS2547", "GDS2771", "GDS3257", "GDS3837", "GDS5499"]
    records = []
    
    for ds in datasets:
        matching_dirs = list(output_dir.glob(f"gsm_*_revised_{ds}"))
        if not matching_dirs:
            # Fallback
            matching_dirs = list(output_dir.glob(f"gsm_*_{ds}*"))
            
        if not matching_dirs:
            records.append({"Dataset": ds, "Status": "Pending"})
            continue
            
        target_dir = sorted(matching_dirs, key=os.path.getmtime)[-1]
        summary_report = target_dir / "summary_report.txt"
        
        f1_score, auc_roc = "N/A", "N/A"
        if summary_report.exists():
            with open(summary_report, "r") as f:
                for line in f:
                    if line.startswith("F1 Score:") and "(95% CI" in line:
                        f1_score = line.split()[2]
                    elif line.startswith("AUC-ROC:") and "(95% CI" in line:
                        auc_roc = line.split()[1]
            records.append({
                "Dataset": ds,
                "F1 Score": f1_score,
                "AUC-ROC": auc_roc,
                "Status": "Complete"
            })
        else:
            records.append({"Dataset": ds, "Status": "Missing Summary", "F1 Score": "N/A", "AUC-ROC": "N/A"})
            
    df_main = pd.DataFrame(records)
    md_table = "### Main Performance (100 Iterations)\n\n"
    md_table += df_main.to_markdown(floatfmt=".3f", index=False)
    md_table += "\n\n"
    return md_table

def generate_cross_dataset_table():
    transfer_path = output_dir / "cross_dataset_transfer" / "transfer_results.csv"
    if not transfer_path.exists():
        print("Cross-dataset transfer results not found.")
        return ""
        
    df = pd.read_csv(transfer_path)
    df_f1 = df.pivot(index="bundle_dataset", columns="test_dataset", values="f1_score")
    
    md_table = "### Cross-Dataset Transfer Matrix (F1-score)\n\n"
    md_table += df_f1.to_markdown(floatfmt=".3f")
    md_table += "\n\n"
    return md_table

if __name__ == "__main__":
    final_md = "# Aggregated Results Tables\n\n"
    final_md += generate_main_performance_table()
    final_md += generate_baselines_table()
    final_md += generate_cross_dataset_table()
    
    out_file = output_dir / "aggregated_manuscript_tables.md"
    with open(out_file, "w") as f:
        f.write(final_md)
        
    print(f"Tables generated at: {out_file}")
