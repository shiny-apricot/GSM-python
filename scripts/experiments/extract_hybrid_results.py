import json
import os
import glob
import pandas as pd

datasets = ["GDS1962", "GDS2545", "GDS2547", "GDS2771", "GDS3257", "GDS3837", "GDS5499"]
base_dir = "output"

results = []

for ds in datasets:
    target_dir = os.path.join(base_dir, f"gl_rf_hybrid_{ds}")
    json_path = os.path.join(target_dir, "gl_rf_hybrid_results.json")
    
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
            results.append({
                "Dataset": ds,
                "GL_F1": data.get("gl_mean_f1", 0),
                "GL_AUC": data.get("gl_mean_auc", 0),
                "GL_RF_F1": data.get("rf_mean_f1", 0),
                "GL_RF_F1_std": data.get("rf_std_f1", 0),
                "GL_RF_AUC": data.get("rf_mean_auc", 0),
                "Avg_Genes": data.get("gl_mean_genes", 0)
            })
    else:
        print(f"Missing {json_path}")

df = pd.DataFrame(results)
print(df.to_markdown(index=False, floatfmt=".4f"))
