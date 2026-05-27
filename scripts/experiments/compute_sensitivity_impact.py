#!/usr/bin/env python3
"""
Compute parameter impact from sensitivity analysis results.

Reads sensitivity_results.json and computes the F1 range
per parameter (OAT design) for the manuscript.
"""
import json
import numpy as np
from pathlib import Path


def main():
    results_path = Path(__file__).resolve().parents[2] / "output" / "sensitivity_runs" / "sensitivity_results.json"
    with open(results_path) as f:
        data = json.load(f)
    
    results = data["results"]
    baseline = data["baseline"]
    
    datasets = sorted(set(r["dataset_id"] for r in results))
    
    ##### PARAMETER IMPACT ANALYSIS #####
    param_configs = {
        "FDR Threshold": {
            "key": "fdr_threshold",
            "other_keys": {"cv_folds": baseline["cv_folds"], "max_groups": baseline["max_groups"]},
        },
        "CV Folds": {
            "key": "cv_folds",
            "other_keys": {"fdr_threshold": baseline["fdr"], "max_groups": baseline["max_groups"]},
        },
        "Max Groups": {
            "key": "max_groups",
            "other_keys": {"fdr_threshold": baseline["fdr"], "cv_folds": baseline["cv_folds"]},
        },
    }
    
    print("=" * 80)
    print("SENSITIVITY ANALYSIS — PARAMETER IMPACT")
    print("=" * 80)
    
    impact_summary = {}
    
    for param_name, cfg in param_configs.items():
        param_key = cfg["key"]
        other_keys = cfg["other_keys"]
        
        print(f"\n{param_name}:")
        ds_ranges = []
        
        for ds in datasets:
            ds_results = [r for r in results if r["dataset_id"] == ds]
            # Get results where only this param varies
            varying = [r for r in ds_results 
                      if all(r[k] == v for k, v in other_keys.items())]
            
            if len(varying) >= 2:
                f1_vals = [r["mean_f1"] for r in varying]
                rng = max(f1_vals) - min(f1_vals)
                ds_ranges.append(rng)
                detail = ", ".join(
                    f"{r[param_key]}->{r['mean_f1']:.4f}" for r in varying
                )
                print(f"  {ds}: F1 range = {rng:.4f} ({detail})")
        
        if ds_ranges:
            avg_impact = float(np.mean(ds_ranges))
            max_impact = float(np.max(ds_ranges))
            impact_summary[param_name] = {
                "avg_range": round(avg_impact, 4),
                "max_range": round(max_impact, 4),
            }
            print(f"  Average F1 range: {avg_impact:.4f}, Max: {max_impact:.4f}")
    
    # Rank parameters by impact
    print("\n" + "=" * 80)
    print("PARAMETER RANKING (by average F1 range):")
    print("=" * 80)
    ranked = sorted(impact_summary.items(), key=lambda x: x[1]["avg_range"], reverse=True)
    for i, (name, vals) in enumerate(ranked, 1):
        print(f"  {i}. {name}: avg={vals['avg_range']:.4f}, max={vals['max_range']:.4f}")
    
    # Save impact summary
    impact_path = results_path.parent / "sensitivity_impact.json"
    with open(impact_path, "w") as f:
        json.dump({"impact": impact_summary, "ranking": [r[0] for r in ranked]}, f, indent=2)
    print(f"\nSaved to {impact_path}")


if __name__ == "__main__":
    main()
