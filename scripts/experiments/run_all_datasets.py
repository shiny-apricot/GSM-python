#!/usr/bin/env python3
"""
🧬 Batch Runner for GSM Pipeline

Purpose:
    Run the GSM pipeline on all datasets in the data/expression_data folder
    with 100 iterations each.

Usage:
    python run_all_datasets.py
    
    # Or run specific datasets:
    python run_all_datasets.py --datasets GDS2545 GDS3257
    
    # Change number of iterations:
    python run_all_datasets.py --iterations 50
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from src.data_processing.data_loader import load_input_file, load_group_file
from src.workflows.GSM_workflow import gsm_run
from src.workflows.GSM_workflow_config import (
    GROUPING_FILE_SEPARATOR,
    MAIN_DATA_FILE_SEPARATOR,
    TRAIN_TEST_SPLIT_RATIO,
    MODEL_NAME,
    SCORING_MODEL,
    LABEL_COLUMN_NAME,
    CLASS_LABELS_POSITIVE,
    CLASS_LABELS_NEGATIVE,
    GENE_COLUMN_NAME,
    GROUP_COLUMN_NAME,
    NORMALIZATION_METHOD,
    BIOLOGICAL_VALIDATION_TOP_GENES,
    DISGENET_API_KEY,
)


##### Configuration #####
EXPRESSION_DATA_DIR = Path("data/expression_data")
GROUPING_DATA_FILE = Path("data/grouping_data/cancer-DisGeNET_gedinet.txt")
DEFAULT_ITERATIONS = 100
# Datasets excluded from publication experiments (see DOCS/DATASET_EXCLUSIONS.md)
EXCLUDED_DATASETS = {"GDS3268", "GDS4206"}


def get_all_datasets() -> list[Path]:
    """Get all CSV files in the expression_data directory, excluding known-bad ones."""
    return sorted(
        p for p in EXPRESSION_DATA_DIR.glob("*.csv")
        if p.stem not in EXCLUDED_DATASETS
    )


def run_single_dataset(
    dataset_path: Path,
    grouping_path: Path,
    n_iterations: int,
    run_bio: bool = True,
    run_name: str | None = None,
) -> tuple[str, float, bool]:
    """
    Run GSM pipeline on a single dataset.
    
    Returns:
        Tuple of (dataset_name, elapsed_time, success)
    """
    dataset_name = dataset_path.stem
    print(f"\n{'='*70}")
    print(f"🧬 Processing: {dataset_name}")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Load data
        print(f"📊 Loading {dataset_path}...")
        input_data = load_input_file(dataset_path, separator=MAIN_DATA_FILE_SEPARATOR)
        print(f"   Shape: {input_data.shape}")
        
        print(f"🔗 Loading {grouping_path}...")
        group_data = load_group_file(grouping_path, separator=GROUPING_FILE_SEPARATOR)
        print(f"   Shape: {group_data.shape}")
        
        # Run pipeline
        print(f"🚀 Running GSM pipeline with {n_iterations} iterations...")
        output_path = gsm_run(
            input_data,
            group_data,
            n_iterations=n_iterations,
            sample_ratio=TRAIN_TEST_SPLIT_RATIO,
            model_name=MODEL_NAME,
            scoring_model=SCORING_MODEL,
            label_column=LABEL_COLUMN_NAME,
            positive_class_label=CLASS_LABELS_POSITIVE,
            negative_class_label=CLASS_LABELS_NEGATIVE,
            gene_column=GENE_COLUMN_NAME,
            group_column=GROUP_COLUMN_NAME,
            normalization_method=NORMALIZATION_METHOD,
            input_data_name=dataset_path.stem,
            group_data_name=grouping_path.stem,
            run_biological_validation_flag=run_bio,
            biological_validation_top_genes=BIOLOGICAL_VALIDATION_TOP_GENES,
            disgenet_api_key=DISGENET_API_KEY,
            run_name=run_name,
        )
        
        elapsed = time.time() - start_time
        print(f"✅ Completed: {dataset_name} in {elapsed/60:.1f} minutes")
        print(f"   Output: {output_path}")
        
        return (dataset_name, elapsed, True)
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Failed: {dataset_name} - {str(e)}")
        return (dataset_name, elapsed, False)


def run_all_datasets(
    datasets: list[Path] | None = None,
    n_iterations: int = DEFAULT_ITERATIONS,
    run_bio: bool = True,
    run_name: str | None = None,
) -> None:
    """Run GSM pipeline on multiple datasets."""
    
    if datasets is None:
        datasets = get_all_datasets()
    
    if not datasets:
        print("❌ No datasets found in data/expression_data/")
        return
    
    grouping_path = project_root / GROUPING_DATA_FILE
    if not grouping_path.exists():
        print(f"❌ Grouping file not found: {grouping_path}")
        return
    
    print("=" * 70)
    print("🧬 GSM BATCH RUNNER")
    print("=" * 70)
    print(f"📁 Datasets to process: {len(datasets)}")
    for d in datasets:
        print(f"   - {d.stem}")
    print(f"🔗 Grouping file: {GROUPING_DATA_FILE}")
    print(f"🔄 Iterations per dataset: {n_iterations}")
    print(f"⏱️  Estimated time: {len(datasets) * 5 * n_iterations / 100:.0f}+ minutes")
    print("=" * 70)
    
    results = []
    total_start = time.time()
    
    for i, dataset_path in enumerate(datasets, 1):
        print(f"\n[{i}/{len(datasets)}] Starting {dataset_path.stem}...")
        result = run_single_dataset(
            dataset_path, grouping_path, n_iterations,
            run_bio=run_bio, run_name=run_name,
        )
        results.append(result)
    
    # Summary
    total_elapsed = time.time() - total_start
    successful = sum(1 for _, _, success in results if success)
    failed = len(results) - successful
    
    print("\n" + "=" * 70)
    print("📊 BATCH RUN SUMMARY")
    print("=" * 70)
    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    print(f"⏱️  Total time: {total_elapsed/60:.1f} minutes ({total_elapsed/3600:.2f} hours)")
    print()
    
    print("Results per dataset:")
    print("-" * 50)
    for name, elapsed, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {elapsed/60:.1f} min")
    
    print("=" * 70)
    print("🎉 Batch run completed!")


def main():
    parser = argparse.ArgumentParser(
        description="Run GSM pipeline on multiple datasets"
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        help="Specific dataset names to run (e.g., GDS2545 GDS3257). If not specified, runs all.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of iterations per dataset (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available datasets and exit",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Optional experiment name for all runs",
    )
    parser.add_argument(
        "--no-bio",
        action="store_true",
        help="Skip biological validation",
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("Available datasets:")
        for d in get_all_datasets():
            print(f"  - {d.stem}")
        return
    
    # Filter datasets if specified
    if args.datasets:
        all_datasets = {d.stem: d for d in get_all_datasets()}
        selected = []
        for name in args.datasets:
            if name in all_datasets:
                selected.append(all_datasets[name])
            else:
                print(f"⚠️ Dataset not found: {name}")
        datasets = selected
    else:
        datasets = None
    
    run_all_datasets(
        datasets=datasets,
        n_iterations=args.iterations,
        run_bio=not args.no_bio,
        run_name=args.name,
    )


if __name__ == "__main__":
    main()
