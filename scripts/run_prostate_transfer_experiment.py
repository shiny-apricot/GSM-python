"""
Run a prostate-focused transfer experiment using selected bundles and test datasets.

Default behavior:
- Train bundles: GDS2545 and GDS2547
- Test datasets: GDS2545, GDS2547 (plus optional GSE datasets if present)

Example:
  python scripts/run_prostate_transfer_experiment.py

  python scripts/run_prostate_transfer_experiment.py \
      --test-datasets GDS2545 GDS2547 GSE46602 GSE6919 GSE70768
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cross_dataset_transfer import run_transfer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPR_DIR = PROJECT_ROOT / "data" / "expression_data"
BUNDLE_DIR = PROJECT_ROOT / "models" / "pretrained"
OUT_DIR = PROJECT_ROOT / "output" / "cross_dataset_transfer_prostate"

DEFAULT_BUNDLE_DATASETS = ["GDS2545", "GDS2547"]
DEFAULT_TEST_DATASETS = ["GDS2545", "GDS2547"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run prostate-focused transfer evaluation.")
    parser.add_argument(
        "--bundle-datasets",
        nargs="+",
        default=DEFAULT_BUNDLE_DATASETS,
        help="Dataset IDs for training bundles.",
    )
    parser.add_argument(
        "--test-datasets",
        nargs="+",
        default=DEFAULT_TEST_DATASETS,
        help="Dataset IDs to evaluate as test cohorts.",
    )
    parser.add_argument("--expr-dir", type=Path, default=EXPR_DIR)
    parser.add_argument("--bundle-dir", type=Path, default=BUNDLE_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def _validate_datasets(expr_dir: Path, datasets: list[str]) -> list[str]:
    available = []
    missing = []
    for ds in datasets:
        if (expr_dir / f"{ds}.csv").exists():
            available.append(ds)
        else:
            missing.append(ds)

    if missing:
        print(f"Missing dataset CSV files (skipped): {missing}")
    if not available:
        raise FileNotFoundError("No test datasets available in expression_data.")
    return available


def main() -> None:
    args = _parse_args()
    test_datasets = _validate_datasets(args.expr_dir, args.test_datasets)

    summary = run_transfer(
        expr_dir=args.expr_dir,
        bundle_dir=args.bundle_dir,
        output_dir=args.output_dir,
        bundle_pattern="bundle_*_publication_RF.gsm.zip",
        bundle_datasets=args.bundle_datasets,
        test_datasets=test_datasets,
    )

    print("\nProstate-focused transfer summary")
    print(f"  pairs:              {summary['n_transfer_pairs']}")
    print(f"  successful pairs:   {summary['n_successful_pairs']}")
    print(f"  incompatible pairs: {summary['n_incompatible_pairs']}")
    print(f"  mean in-domain F1:  {summary['mean_in_domain_f1']}")
    print(f"  mean out-domain F1: {summary['mean_out_domain_f1']}")
    print(f"  mean out-domain AUC:{summary['mean_out_domain_auc']}")


if __name__ == "__main__":
    main()
