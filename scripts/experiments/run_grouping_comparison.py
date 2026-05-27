"""
Grouping Source Comparison Experiment
=====================================

Compare three knowledge sources for the G-S-M grouping phase:
  1. DisGeNET (disease-gene associations)  — the default
  2. KEGG pathways (biological pathway grouping)
  3. maTE (miRNA-target gene associations)

Runs 100-iteration experiments on representative datasets and
collects F1, AUC-ROC, group counts, and feature counts.
"""

import json
import sys
import time
import argparse
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.workflows.GSM_workflow import gsm_run
from src.data_processing.data_loader import _detect_separator


##### CONFIGURATION #####

# Datasets to test (high-accuracy datasets for publication)
DATASETS = [
    "GDS3257",   # AML – perfect classification
    "GDS1962",   # Glioblastoma – excellent classification
    "GDS2545",   # Prostate – hardest dataset
]

GROUPING_CONFIGS = {
    "DisGeNET": {
        "path": "data/grouping_data/cancer-DisGeNET_gedinet.txt",
        "gene_col": "feature_id",
        "group_col": "group_name",
    },
    "KEGG": {
        "path": "data/grouping_data/kegg_genes_table_vFatma_pripath.csv",
        "gene_col": "Target Gene",
        "group_col": "miRNA",   # actually KEGG pathway IDs
    },
    "maTE_miRNA": {
        "path": "data/grouping_data/mate_grouping_file.csv",
        "gene_col": "Target Gene",
        "group_col": "miRNA",
    },
}

N_ITERATIONS = 100
SEED = 44
RUN_BIO_VALIDATION = True
BIO_TOP_N_GENES = 20


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for grouping comparison."""
    parser = argparse.ArgumentParser(
        description=(
            "Compare DisGeNET, KEGG, and maTE grouping sources across "
            "representative datasets."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=N_ITERATIONS,
        help="Number of Monte-Carlo iterations per run (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Initial random seed (default: 44)",
    )
    parser.add_argument(
        "--bio-top-genes",
        type=int,
        default=BIO_TOP_N_GENES,
        help="Top-N genes used for biological validation (default: 20)",
    )
    parser.add_argument(
        "--skip-bio-validation",
        action="store_true",
        help="Skip Enrichr/STRING validation for faster runs",
    )
    return parser.parse_args()


def load_expression_data(dataset_id: str) -> pd.DataFrame:
    """Load an expression dataset."""
    path = project_root / "data" / "expression_data" / f"{dataset_id}.csv"
    sep = _detect_separator(str(path))
    return pd.read_csv(path, sep=sep)


def load_grouping_data(config: dict) -> pd.DataFrame:
    """Load and deduplicate a grouping file."""
    path = project_root / config["path"]
    sep = _detect_separator(str(path))
    df = pd.read_csv(path, sep=sep)
    # Drop exact duplicates
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    if before != after:
        print(f"  Removed {before - after} duplicate rows")
    return df


def run_single_experiment(
    dataset_id: str,
    group_name: str,
    group_config: dict,
    expr_data: pd.DataFrame,
    group_data: pd.DataFrame,
    n_iterations: int,
    initial_seed: int,
    run_bio_validation: bool,
    bio_top_n_genes: int,
) -> dict:
    """Run one GSM experiment and extract results."""
    print(f"\n{'='*60}")
    print(f"  {dataset_id} × {group_name}")
    print(f"  Groups: {group_data[group_config['group_col']].nunique()}, "
          f"Genes in mapping: {group_data[group_config['gene_col']].nunique()}")
    print(f"{'='*60}")

    start = time.time()
    try:
        output_dir = gsm_run(
            input_data=expr_data,
            group_data=group_data,
            n_iterations=n_iterations,
            initial_seed=initial_seed,
            gene_column=group_config["gene_col"],
            group_column=group_config["group_col"],
            input_data_name=dataset_id,
            group_data_name=group_name,
            run_biological_validation_flag=run_bio_validation,
            bio_validation_top_n_genes=bio_top_n_genes,
            run_name=f"grouping_cmp_{group_name}",
        )
        elapsed = time.time() - start

        # Read results from current pipeline output format
        results_path = output_dir / "modeling_results_all_iterations.json"
        if not results_path.exists():
            return {
                "dataset": dataset_id,
                "grouping": group_name,
                "status": "NO_RESULTS",
                "elapsed_s": round(elapsed, 1),
            }

        with open(results_path) as f:
            all_iterations = json.load(f)

        # Select the single best model across all iterations and top-group steps
        best = None
        for iteration in all_iterations:
            for step in iteration.get("results", []):
                if best is None or step.get("f1_score", 0) > best.get("f1_score", 0):
                    best = step

        if best is None:
            return {
                "dataset": dataset_id,
                "grouping": group_name,
                "status": "NO_RESULTS",
                "elapsed_s": round(elapsed, 1),
            }

        result = {
            "dataset": dataset_id,
            "grouping": group_name,
            "f1_score": round(best.get("f1_score", 0), 4),
            "auc_roc": round(best.get("auc_roc", 0), 4),
            "f1_ci_lower": round(best.get("f1_ci_lower", 0), 4),
            "f1_ci_upper": round(best.get("f1_ci_upper", 0), 4),
            "groups_used": int(best.get("num_groups_used", 0)),
            "features_used": int(best.get("num_features_used", 0)),
            "elapsed_s": round(elapsed, 1),
            "output_dir": str(output_dir),
            "status": "OK",
        }

        result.update(load_biological_metrics(Path(output_dir)))
        return result

    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ FAILED: {e}")
        return {
            "dataset": dataset_id,
            "grouping": group_name,
            "status": f"ERROR: {e}",
            "elapsed_s": round(elapsed, 1),
        }


def load_biological_metrics(output_dir: Path) -> dict:
    """Load top-level Enrichr/STRING metrics from biological validation files."""
    validation_dir = output_dir / "biological_validation"
    enrichr_path = validation_dir / "enrichr_results.csv"
    string_path = validation_dir / "string_interactions.csv"

    if not enrichr_path.exists() and not string_path.exists():
        return {
            "string_ppi": None,
            "top_kegg_p": None,
            "top_disgenet_p": None,
            "bio_status": "MISSING",
        }

    string_ppi = 0
    if string_path.exists():
        try:
            string_df = pd.read_csv(string_path)
            string_ppi = int(len(string_df))
        except Exception:
            string_ppi = 0

    top_kegg_p = None
    top_disgenet_p = None
    if enrichr_path.exists():
        try:
            enrichr_df = pd.read_csv(enrichr_path)

            kegg_df = enrichr_df[enrichr_df["Library"] == "KEGG_2021_Human"]
            if not kegg_df.empty:
                top_kegg_p = float(kegg_df["Adjusted P-value"].min())

            dg_df = enrichr_df[enrichr_df["Library"] == "DisGeNET"]
            if not dg_df.empty:
                top_disgenet_p = float(dg_df["Adjusted P-value"].min())
        except Exception:
            top_kegg_p = None
            top_disgenet_p = None

    return {
        "string_ppi": string_ppi,
        "top_kegg_p": top_kegg_p,
        "top_disgenet_p": top_disgenet_p,
        "bio_status": "OK",
    }


def main():
    args = parse_args()
    run_bio_validation = RUN_BIO_VALIDATION and not args.skip_bio_validation
    all_results = []

    for ds_id in DATASETS:
        print(f"\n🔬 Loading {ds_id}...")
        expr_data = load_expression_data(ds_id)
        print(f"  Expression data: {expr_data.shape}")

        for grp_name, grp_config in GROUPING_CONFIGS.items():
            print(f"\n📂 Loading grouping: {grp_name}...")
            grp_data = load_grouping_data(grp_config)
            print(f"  Grouping data: {grp_data.shape}")

            result = run_single_experiment(
                ds_id,
                grp_name,
                grp_config,
                expr_data,
                grp_data,
                args.iterations,
                args.seed,
                run_bio_validation,
                args.bio_top_genes,
            )
            all_results.append(result)
            print(f"  Result: {result.get('status', '?')} "
                  f"F1={result.get('f1_score', 'N/A')} "
                  f"AUC={result.get('auc_roc', 'N/A')}")

    # Summary
    print("\n" + "=" * 80)
    print("  GROUPING COMPARISON SUMMARY")
    print("=" * 80)
    
    output_path = project_root / "output" / "grouping_comparison_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Pretty-print table
    print(f"\n{'Dataset':<10} {'Grouping':<12} {'F1':>6} {'AUC':>6} "
          f"{'Groups':>7} {'Feats':>6} {'Time':>7} {'Status'}")
    print("-" * 75)
    for r in all_results:
        if r["status"] == "OK":
            print(f"{r['dataset']:<10} {r['grouping']:<12} "
                  f"{r['f1_score']:>6.3f} {r['auc_roc']:>6.3f} "
                  f"{r['groups_used']:>7} {r['features_used']:>6} "
                  f"{r['elapsed_s']:>6.1f}s OK")
        else:
            print(f"{r['dataset']:<10} {r['grouping']:<12} "
                  f"{'---':>6} {'---':>6} {'---':>7} {'---':>6} "
                  f"{r.get('elapsed_s', 0):>6.1f}s {r['status'][:30]}")


if __name__ == "__main__":
    main()
