#!/usr/bin/env python3
"""
🧪 Quick Test Runner for GSM Pipeline

Purpose:
    Run a quick test of the GSM pipeline using test data with minimal iterations.
    Use this to verify the pipeline works before running on real data.

Usage:
    # Basic test (3 iterations)
    python run_test.py
    
    # Custom iterations
    python run_test.py --iterations 5
    
    # Test with real data (small run)
    python run_test.py --real-data --iterations 3

Output:
    Results saved to: output/gsm_<timestamp>_test_expression_data_test_grouping_data/
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_processing.data_loader import load_input_file, load_group_file
from src.workflows.GSM_workflow import gsm_run
from src.workflows.GSM_workflow_config import (
    TRAIN_TEST_SPLIT_RATIO,
    MODEL_NAME,
    LABEL_COLUMN_NAME,
    CLASS_LABELS_POSITIVE,
    CLASS_LABELS_NEGATIVE,
    GENE_COLUMN_NAME,
    GROUP_COLUMN_NAME,
    NORMALIZATION_METHOD,
)


##### Test Data Paths #####
TEST_DATA_DIR = Path("data/test")
TEST_EXPRESSION_FILE = TEST_DATA_DIR / "test_expression_data.csv"
TEST_GROUPING_FILE = TEST_DATA_DIR / "test_grouping_data.csv"

# Real data for small test runs
REAL_DATA_DIR = Path("data/expression_data")
REAL_EXPRESSION_FILE = REAL_DATA_DIR / "GDS2545.csv"
REAL_GROUPING_FILE = Path("data/grouping_data/cancer-DisGeNET_gedinet.txt")

DEFAULT_TEST_ITERATIONS = 3


def run_test(
    use_real_data: bool = False,
    n_iterations: int = DEFAULT_TEST_ITERATIONS,
) -> bool:
    """
    Run a quick test of the GSM pipeline.
    
    Args:
        use_real_data: Use real data instead of test data
        n_iterations: Number of iterations to run
    
    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("🧪 GSM PIPELINE QUICK TEST")
    print("=" * 70)
    
    # Select data files
    if use_real_data:
        expression_file = REAL_EXPRESSION_FILE
        grouping_file = REAL_GROUPING_FILE
        print("📊 Using: REAL DATA (GDS2545)")
    else:
        expression_file = TEST_EXPRESSION_FILE
        grouping_file = TEST_GROUPING_FILE
        print("📊 Using: TEST DATA")
    
    print(f"🔄 Iterations: {n_iterations}")
    print("=" * 70)
    
    # Check if files exist
    if not expression_file.exists():
        print(f"❌ Expression data not found: {expression_file}")
        return False
    
    if not grouping_file.exists():
        print(f"❌ Grouping data not found: {grouping_file}")
        return False
    
    start_time = time.time()
    
    try:
        # Load data
        print(f"\n📊 Loading expression data: {expression_file}")
        if use_real_data:
            input_data = load_input_file(expression_file, separator=",")
        else:
            input_data = load_input_file(expression_file, separator=",")
        print(f"   Shape: {input_data.shape}")
        
        print(f"\n🔗 Loading grouping data: {grouping_file}")
        if use_real_data:
            group_data = load_group_file(grouping_file, separator=",")
        else:
            group_data = load_group_file(grouping_file, separator="\t")
        print(f"   Shape: {group_data.shape}")
        
        # Run pipeline
        print(f"\n🚀 Running GSM pipeline with {n_iterations} iterations...")
        print("   This may take a few minutes...")
        
        output_path = gsm_run(
            input_data,
            group_data,
            n_iterations=n_iterations,
            sample_ratio=TRAIN_TEST_SPLIT_RATIO,
            model_name=MODEL_NAME,
            label_column=LABEL_COLUMN_NAME,
            positive_class_label=CLASS_LABELS_POSITIVE,
            negative_class_label=CLASS_LABELS_NEGATIVE,
            gene_column=GENE_COLUMN_NAME,
            group_column=GROUP_COLUMN_NAME,
            normalization_method=NORMALIZATION_METHOD,
            input_data_name=expression_file.stem,
            group_data_name=grouping_file.stem,
        )
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("✅ TEST PASSED!")
        print("=" * 70)
        print(f"⏱️  Time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"📁 Output: {output_path}")
        print()
        print("Output files:")
        for f in sorted(output_path.iterdir()):
            if f.is_file():
                print(f"   📄 {f.name}")
            elif f.is_dir():
                print(f"   📁 {f.name}/")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("❌ TEST FAILED!")
        print("=" * 70)
        print(f"⏱️  Time: {elapsed:.1f} seconds")
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        print("=" * 70)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run a quick test of the GSM pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_test.py                    # Quick test with test data (3 iterations)
  python run_test.py --iterations 5     # Test with 5 iterations
  python run_test.py --real-data        # Test with real GDS2545 data
  python run_test.py --real-data -i 2   # Real data with 2 iterations
        """
    )
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=DEFAULT_TEST_ITERATIONS,
        help=f"Number of iterations (default: {DEFAULT_TEST_ITERATIONS})"
    )
    parser.add_argument(
        "--real-data", "-r",
        action="store_true",
        help="Use real data (GDS2545) instead of test data"
    )
    
    args = parser.parse_args()
    
    success = run_test(
        use_real_data=args.real_data,
        n_iterations=args.iterations
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
