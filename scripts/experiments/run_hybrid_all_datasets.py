"""
Run GL->RF Hybrid Workflow on all 7 datasets.
"""
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.workflows.gl_rf_hybrid import gl_rf_hybrid_workflow

def main():
    datasets = [
        "GDS1962",
        "GDS2545",
        "GDS2547",
        "GDS2771",
        "GDS3257",
        "GDS3837",
        "GDS5499"
    ]
    
    n_iters = 3
    print(f"🚀 Starting multi-dataset GL->RF Hybrid Evaluation ({n_iters} iterations each)")
    print("=" * 60)
    
    for dataset in datasets:
        print(f"\n⚙️ Running {dataset}...")
        start_time = time.time()
        try:
            # Note: We rely on the internal config which now has hyperparameter search enabled.
            # We'll use the default grid search.
            hybrid_results = gl_rf_hybrid_workflow(
                dataset=dataset,
                n_iterations=n_iters,
                output_dir=project_root / "output" / f"gl_rf_hybrid_{dataset}"
            )
            elapsed = time.time() - start_time
            print(f"✅ {dataset} completed in {elapsed/60:.1f} minutes.")
            print(f"   GL F1: {hybrid_results.gl_mean_f1:.4f} | GL->RF F1: {hybrid_results.rf_mean_f1:.4f}")
        except Exception as e:
            print(f"❌ Failed on {dataset}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
