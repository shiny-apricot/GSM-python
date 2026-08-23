"""
Full Re-Run Script for Major Revision (Post-Normalization Fix)

Purpose:
    Re-runs the GSM pipeline on all 7 datasets with 100 iterations each,
    using the fixed normalization (fit on train only) and fixed-K group
    selection. This produces the new results needed for the revised manuscript.

Usage:
    python scripts/experiments/run_all_datasets_revised.py

    To run a subset or fewer iterations:
    python scripts/experiments/run_all_datasets_revised.py --datasets GDS2545 GDS2547 --iterations 10

Estimated Runtime:
    ~4-6 hours for all 7 datasets × 100 iterations (depends on hardware)
"""

import sys
import os
import time
import argparse
import json
from pathlib import Path
from datetime import datetime

# Ensure project root is on path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from src.data_processing.data_loader import load_input_file, load_group_file
from src.workflows.GSM_workflow import gsm_run


##### DATASETS #####
DATASETS = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate Cancer",
    "GDS2547": "Prostate Cancer (Lapointe)",
    "GDS2771": "Lung Cancer",
    "GDS3257": "Acute Myeloid Leukemia",
    "GDS3837": "Colorectal Cancer",
    "GDS5499": "Pancreatic Cancer",
}

GROUPING_FILE = "data/grouping_data/cancer-DisGeNET_gedinet.txt"
DATA_DIR = project_root / "data" / "expression_data"


def run_single_dataset(dataset_id: str, disease: str, n_iterations: int, run_bio: bool):
    """Run the GSM pipeline on a single dataset."""
    csv_path = DATA_DIR / f"{dataset_id}.csv"
    if not csv_path.exists():
        print(f"  ⚠ {dataset_id}: file not found at {csv_path}, skipping")
        return None

    print(f"\n{'='*70}")
    print(f"  {dataset_id} — {disease}")
    print(f"{'='*70}")

    input_data = load_input_file(str(csv_path))
    group_data = load_group_file(str(project_root / GROUPING_FILE))
    
    print(f"  Data: {input_data.shape[0]} samples × {input_data.shape[1]} features")

    t0 = time.time()
    run_name = f"revised_{dataset_id}"
    
    try:
        result = gsm_run(
            input_data, group_data,
            n_iterations=n_iterations,
            run_biological_validation_flag=run_bio,
            run_name=run_name,
        )
        elapsed = time.time() - t0
        print(f"  ✅ {dataset_id} completed in {elapsed/60:.1f} minutes")
        return {"dataset": dataset_id, "disease": disease, "status": "success", "elapsed_min": round(elapsed/60, 1)}
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ❌ {dataset_id} FAILED after {elapsed/60:.1f} min: {e}")
        return {"dataset": dataset_id, "disease": disease, "status": "failed", "error": str(e), "elapsed_min": round(elapsed/60, 1)}


def main():
    parser = argparse.ArgumentParser(description="Re-run GSM pipeline on all datasets (post-revision fix)")
    parser.add_argument("--datasets", nargs="+", default=list(DATASETS.keys()),
                        help="Dataset IDs to run (default: all 7)")
    parser.add_argument("--iterations", type=int, default=100,
                        help="Number of iterations per dataset (default: 100)")
    parser.add_argument("--bio", action="store_true",
                        help="Run biological validation (adds time, requires API keys)")
    args = parser.parse_args()

    print("=" * 70)
    print("  GSM Major Revision — Full Re-Run")
    print(f"  Datasets: {len(args.datasets)} | Iterations: {args.iterations}")
    print(f"  Normalization: within-split (fixed) | Group selection: fixed-K")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = []
    total_start = time.time()

    for dataset_id in args.datasets:
        disease = DATASETS.get(dataset_id, "Unknown")
        result = run_single_dataset(dataset_id, disease, args.iterations, args.bio)
        if result:
            results.append(result)

    total_elapsed = time.time() - total_start

    # Save summary
    summary_path = project_root / "output" / "revision_run_summary.json"
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_elapsed_min": round(total_elapsed / 60, 1),
        "n_iterations": args.iterations,
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    # Print summary
    print(f"\n{'='*70}")
    print(f"  COMPLETE — Total time: {total_elapsed/60:.1f} minutes")
    print(f"{'='*70}")
    for r in results:
        status = "✅" if r["status"] == "success" else "❌"
        print(f"  {status} {r['dataset']:8s} ({r['disease']:30s}) — {r['elapsed_min']:.1f} min")
    print(f"\n  Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
