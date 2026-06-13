
import os
import pandas as pd
import numpy as np
from pathlib import Path
import collections

# --- Configuration ---
# Replace this with the absolute path to your main output folder
BASE_DIR = Path("/home/yasin/GSM-to-python/output") 

# Dictionary mapping each dataset to its optimal group count
OPTIMAL_GROUPS = {
    "GDS3257": 1,
    "GDS3837": 4,
    "GDS5499": 13,
    "GDS2547": 14,
    "GDS1962": 15,
    "GDS2545": 5,
    "GDS2771": 11
}
def main():
    # Dictionary to hold the extracted F1 scores for each dataset
    f1_scores_dict = collections.defaultdict(list)
    
    # Recursively find all modeling_results_statistics.xlsx files
    excel_files = list(BASE_DIR.rglob("modeling_results_statistics.xlsx"))
    
    if not excel_files:
        print(f"No 'modeling_results_statistics.xlsx' files found in {BASE_DIR}")
        return

    print(f"Found {len(excel_files)} total result files. Filtering for 'seed' folders...\n")
    
    for file_path in excel_files:
        # ENFORCED RULE: The folder path must include the word "seed"
        if "seed" not in str(file_path).lower():
            continue

        # Determine which dataset this file belongs to by checking the path string
        dataset_name = None
        for ds in OPTIMAL_GROUPS.keys():
            if ds in str(file_path):
                dataset_name = ds
                break
        
        # If the file doesn't belong to our target datasets, skip it
        if not dataset_name:
            continue
            
        try:
            # Read the "Averaged Results" tab
            df = pd.read_excel(file_path, sheet_name="Averaged Results")
            
            # Clean column names just in case there are trailing spaces
            df.columns = df.columns.str.strip()
            
            # Find the target group count
            target_group = OPTIMAL_GROUPS[dataset_name]
            
            # Filter the dataframe for the optimal group row
            row = df[df['Group Count'] == target_group]
            
            if not row.empty:
                # Extract the F1 Score
                f1_val = row['F1 Score'].values[0]
                f1_scores_dict[dataset_name].append(f1_val)
            else:
                print(f"Warning: Optimal Group Count {target_group} not found in {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # --- Calculate Averages and Standard Deviations ---
    print("-" * 65)
    print(f"{'Dataset':<10} | {'Opt. Groups':<12} | {'Seeds Found':<12} | {'Avg F1 Score':<15} | {'Std Dev'}")
    print("-" * 65)
    
    final_results = []
    
    for ds, scores in f1_scores_dict.items():
        avg_f1 = np.mean(scores)
        # Calculate sample standard deviation (ddof=1)
        std_f1 = np.std(scores, ddof=1) if len(scores) > 1 else 0.0 
        
        print(f"{ds:<10} | {OPTIMAL_GROUPS[ds]:<12} | {len(scores):<12} | {avg_f1:<15.4f} | {std_f1:.4f}")
        
        final_results.append({
            "Dataset": ds,
            "Optimal Groups": OPTIMAL_GROUPS[ds],
            "Seeds Count": len(scores),
            "Average F1 Score": avg_f1,
            "Std Dev": std_f1
        })

if __name__ == "__main__":
    main()