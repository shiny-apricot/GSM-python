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
    from tqdm import tqdm
    import datetime
    n_iters = 10
    
    ts = time.strftime("%Y_%m_%d-%H_%M_%S")
    run_dir = project_root / "output" / "hybrid_runs" / f"run_{ts}_v3_fixes"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Starting multi-dataset GL->RF Hybrid Evaluation ({n_iters} iterations each)")
    print(f"📁 Outputs will be saved to: {run_dir}")
    print("=" * 60)
    
    for dataset in tqdm(datasets, desc="Datasets Progress"):
        print(f"\n⚙️ Running {dataset}...")
        start_time = time.time()
        try:
            # Note: We rely on the internal config which now has hyperparameter search enabled.
            # We'll use the default grid search.
            dataset_out_dir = run_dir / dataset
            dataset_out_dir.mkdir(parents=True, exist_ok=True)
            
            # Skip if already completed (useful for resuming interrupted runs)
            if (dataset_out_dir / "gl_rf_hybrid_results.json").exists():
                print(f"⏭️ {dataset} already completed. Skipping.")
                continue
            
            hybrid_results = gl_rf_hybrid_workflow(
                dataset=dataset,
                n_iterations=n_iters,
                output_dir=dataset_out_dir
            )
            elapsed = time.time() - start_time
            print(f"✅ {dataset} completed in {elapsed/60:.1f} minutes.")
            print(f"   Saved Pareto curves and results to: {dataset_out_dir}")
        except Exception as e:
            print(f"❌ Failed on {dataset}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
