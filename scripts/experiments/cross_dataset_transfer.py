"""
Cross-Dataset Transfer Evaluation
=================================

Evaluates how bundles trained on one dataset generalize to other datasets.
Builds a full train-dataset (bundle) × test-dataset transfer matrix.

Outputs:
  - output/cross_dataset_transfer/transfer_results.json
  - output/cross_dataset_transfer/transfer_results.csv
  - output/cross_dataset_transfer/transfer_f1_matrix.csv
  - output/cross_dataset_transfer/transfer_auc_matrix.csv
  - output/cross_dataset_transfer/fig_transfer_f1_heatmap.png
  - output/cross_dataset_transfer/fig_transfer_auc_heatmap.png
  - output/cross_dataset_transfer/fig_transfer_in_vs_out_f1.png
  - output/cross_dataset_transfer/transfer_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.data_processing.data_loader import _detect_separator
from src.data_processing.handle_missing_values import drop_missing_values
from src.data_processing.normalization import normalize_data
from src.inference.model_bundle import load_bundle
from src.utils.logger import setup_logger


##### CONFIG #####

DEFAULT_EXPR_DIR = project_root / "data" / "expression_data"
DEFAULT_BUNDLE_DIR = project_root / "models" / "pretrained"
DEFAULT_OUTPUT_DIR = project_root / "output" / "cross_dataset_transfer"


##### DATA STRUCTURES #####

@dataclass
class TransferResult:
    bundle_dataset: str
    test_dataset: str
    n_samples: int
    n_features_required: int
    n_features_available: int
    feature_coverage: float
    n_models_total: int
    n_models_successful: int
    accuracy: float
    balanced_accuracy: float
    f1_score: float
    auc_roc: float | None
    in_domain: bool
    status: str = "OK"
    error: str = ""


##### HELPERS #####

def _load_expression(dataset_id: str, expr_dir: Path) -> pd.DataFrame:
    path = expr_dir / f"{dataset_id}.csv"
    sep = _detect_separator(str(path))
    try:
        return pd.read_csv(path, sep=sep, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=sep, encoding="latin1", low_memory=False)


def _to_binary_labels(y: pd.Series, positive_label: str, negative_label: str) -> np.ndarray:
    y_str = y.astype(str)

    if positive_label in set(y_str) and negative_label in set(y_str):
        return (y_str == positive_label).astype(int).values

    # Fallback for mixed label naming conventions
    norm = y_str.str.lower().str.strip()
    pos_tokens = {"pos", "positive", "disease", "case", "tumor", "cancer", "1", "true"}
    neg_tokens = {"neg", "negative", "control", "healthy", "normal", "0", "false"}

    mapped = []
    for val in norm:
        if val in pos_tokens:
            mapped.append(1)
        elif val in neg_tokens:
            mapped.append(0)
        else:
            mapped.append(np.nan)

    arr = np.array(mapped, dtype=float)
    if np.isnan(arr).any():
        raise ValueError(
            "Could not map all labels to binary classes. "
            f"Observed labels: {sorted(set(y_str))}"
        )
    return arr.astype(int)


def _bundle_dataset_name(bundle_path: Path) -> str:
    bundle = load_bundle(bundle_path)
    return bundle.metadata.dataset_name


def _predict_bundle_fast(bundle, X_input: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Fast bundle inference for benchmarking.

    Uses model-aligned feature matrices and skips per-sample explanation
    generation to keep transfer experiments fast.
    """
    n_samples = len(X_input)
    n_models = len(bundle.models)
    n_success = 0

    all_probabilities = np.zeros((n_samples, n_models), dtype=float)
    all_predictions = np.zeros((n_samples, n_models), dtype=int)

    f1_scores = np.array([m.f1_score for m in bundle.models], dtype=float)
    model_weights = np.maximum(f1_scores, 0.01)
    model_weights = model_weights / model_weights.sum()

    for i, model_artifact in enumerate(bundle.models):
        model = model_artifact.model
        try:
            if hasattr(model, "feature_names_in_"):
                model_cols = [c for c in model.feature_names_in_ if c in X_input.columns]
                X_model = pd.DataFrame(0.0, index=X_input.index, columns=model.feature_names_in_)
                if model_cols:
                    X_model[model_cols] = X_input[model_cols].values
            else:
                X_model = X_input

            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X_model)[:, 1]
            elif hasattr(model, "decision_function"):
                raw = model.decision_function(X_model)
                proba = 1.0 / (1.0 + np.exp(-raw))
            else:
                proba = model.predict(X_model).astype(float)

            all_probabilities[:, i] = proba
            all_predictions[:, i] = (proba >= 0.5).astype(int)
            n_success += 1
        except Exception:
            all_probabilities[:, i] = 0.5
            all_predictions[:, i] = 0

    if bundle.metadata.ensemble_strategy == "mean_probability":
        y_prob = np.dot(all_probabilities, model_weights)
        y_pred = (y_prob >= 0.5).astype(int)
    else:
        y_vote = np.dot(all_predictions, model_weights)
        y_prob = y_vote
        y_pred = (y_vote >= 0.5).astype(int)

    return y_pred, y_prob, n_success, n_models


##### MAIN #####

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate cross-dataset transfer for GSM model bundles.",
    )
    parser.add_argument(
        "--expr-dir",
        type=Path,
        default=DEFAULT_EXPR_DIR,
        help="Directory containing expression CSV files (default: data/expression_data).",
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
        help="Directory containing .gsm.zip bundles (default: models/pretrained).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for transfer artifacts.",
    )
    parser.add_argument(
        "--bundle-pattern",
        type=str,
        default="bundle_*_publication_RF.gsm.zip",
        help="Glob pattern for selecting bundles in --bundle-dir.",
    )
    parser.add_argument(
        "--bundle-datasets",
        nargs="+",
        default=None,
        help="Optional dataset IDs to keep as training bundles (e.g., GDS2545 GDS2547).",
    )
    parser.add_argument(
        "--test-datasets",
        nargs="+",
        default=None,
        help="Optional dataset IDs to use as test datasets. Defaults to bundle dataset IDs.",
    )
    return parser.parse_args()


def run_transfer(
    *,
    expr_dir: Path,
    bundle_dir: Path,
    output_dir: Path,
    bundle_pattern: str,
    bundle_datasets: list[str] | None = None,
    test_datasets: list[str] | None = None,
) -> dict[str, float | int | None | dict[str, float | str | None]]:
    warnings.filterwarnings(
        "ignore",
        message="X does not have valid feature names",
        category=UserWarning,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(str(output_dir / "cross_dataset_transfer.log"), logger_name="cross_dataset_transfer")

    bundle_paths = sorted(bundle_dir.glob(bundle_pattern))
    if bundle_datasets:
        wanted = set(bundle_datasets)
        bundle_paths = [p for p in bundle_paths if _bundle_dataset_name(p) in wanted]

    bundle_dataset_ids = sorted({_bundle_dataset_name(p) for p in bundle_paths})
    dataset_ids = sorted(test_datasets) if test_datasets else bundle_dataset_ids

    if not dataset_ids:
        raise FileNotFoundError("No test datasets selected.")
    if not bundle_paths:
        raise FileNotFoundError("No bundles matched the requested selection.")

    logger.info(f"Datasets found: {dataset_ids}")
    logger.info(f"Bundles found: {[p.name for p in bundle_paths]}")

    results: list[TransferResult] = []

    # Preload test datasets once
    test_data = {}
    for ds in dataset_ids:
        df = _load_expression(ds, expr_dir)
        df = drop_missing_values(df)
        if "class" not in df.columns:
            raise ValueError(f"Dataset {ds} missing required label column 'class'")
        test_data[ds] = df

    for bundle_path in bundle_paths:
        bundle = load_bundle(bundle_path)
        train_ds = bundle.metadata.dataset_name
        logger.info(f"\nEvaluating bundle: {bundle_path.name} (trained on {train_ds})")

        required_features = bundle.metadata.feature_names

        for test_ds in dataset_ids:
            df = test_data[test_ds]
            y_true = _to_binary_labels(
                df["class"],
                positive_label=bundle.metadata.label_mapping.get("positive", "pos"),
                negative_label=bundle.metadata.label_mapping.get("negative", "neg"),
            )

            # Match training preprocessing: labels -> binary, then feature normalization.
            df_norm = df.copy()
            df_norm["class"] = y_true
            df_norm = normalize_data(
                df_norm,
                label_column_name="class",
                logger=logger,
                method=bundle.metadata.normalization_method,
            )
            X_norm = df_norm.drop(columns=["class"])

            available_features = [f for f in required_features if f in X_norm.columns]
            feature_coverage = len(available_features) / len(required_features) if required_features else 0.0

            missing_ratio = 1.0 - feature_coverage
            if missing_ratio > 0.5:
                result = TransferResult(
                    bundle_dataset=train_ds,
                    test_dataset=test_ds,
                    n_samples=len(df_norm),
                    n_features_required=len(required_features),
                    n_features_available=len(available_features),
                    feature_coverage=round(feature_coverage, 4),
                    n_models_total=len(bundle.models),
                    n_models_successful=0,
                    accuracy=0.0,
                    balanced_accuracy=0.0,
                    f1_score=0.0,
                    auc_roc=None,
                    in_domain=(train_ds == test_ds),
                    status="INCOMPATIBLE",
                    error=(
                        f"Too many features missing ({len(required_features)-len(available_features)}/"
                        f"{len(required_features)} = {missing_ratio:.0%}). "
                        "Patient data may be from an incompatible platform."
                    ),
                )
                results.append(result)
                logger.info(
                    f"{train_ds} -> {test_ds} | F1={result.f1_score:.3f} "
                    f"AUC=NA coverage={result.feature_coverage:.1%} "
                    f"models={result.n_models_successful}/{result.n_models_total} "
                    f"status={result.status}"
                )
                continue

            try:
                y_pred, y_prob, n_success, n_total = _predict_bundle_fast(bundle, X_norm)

                try:
                    auc = float(roc_auc_score(y_true, y_prob))
                except ValueError:
                    auc = None

                result = TransferResult(
                    bundle_dataset=train_ds,
                    test_dataset=test_ds,
                    n_samples=len(df_norm),
                    n_features_required=len(required_features),
                    n_features_available=len(available_features),
                    feature_coverage=round(feature_coverage, 4),
                    n_models_total=n_total,
                    n_models_successful=n_success,
                    accuracy=round(float(accuracy_score(y_true, y_pred)), 4),
                    balanced_accuracy=round(float(balanced_accuracy_score(y_true, y_pred)), 4),
                    f1_score=round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
                    auc_roc=round(float(auc), 4) if auc is not None else None,
                    in_domain=(train_ds == test_ds),
                    status=("OK" if n_success == n_total else "PARTIAL_MODEL_MATCH"),
                )
            except Exception as exc:
                result = TransferResult(
                    bundle_dataset=train_ds,
                    test_dataset=test_ds,
                    n_samples=len(df_norm),
                    n_features_required=len(required_features),
                    n_features_available=len(available_features),
                    feature_coverage=round(feature_coverage, 4),
                    n_models_total=len(bundle.models),
                    n_models_successful=0,
                    accuracy=0.0,
                    balanced_accuracy=0.0,
                    f1_score=0.0,
                    auc_roc=None,
                    in_domain=(train_ds == test_ds),
                    status="INCOMPATIBLE",
                    error=str(exc)[:200],
                )
            results.append(result)

            logger.info(
                f"{train_ds} -> {test_ds} | F1={result.f1_score:.3f} "
                f"AUC={(result.auc_roc if result.auc_roc is not None else 'NA')} "
                f"coverage={result.feature_coverage:.1%} "
                f"models={result.n_models_successful}/{result.n_models_total} "
                f"status={result.status}"
            )

    # Save row-wise outputs
    results_json = [asdict(r) for r in results]
    with open(output_dir / "transfer_results.json", "w") as f:
        json.dump(results_json, f, indent=2)

    df = pd.DataFrame(results_json)
    df.to_csv(output_dir / "transfer_results.csv", index=False)

    # Build matrices (only successful evaluations)
    df_ok = df[df["status"].isin(["OK", "PARTIAL_MODEL_MATCH"])].copy()
    f1_matrix = df_ok.pivot(index="bundle_dataset", columns="test_dataset", values="f1_score")
    auc_matrix = df_ok.pivot(index="bundle_dataset", columns="test_dataset", values="auc_roc")

    f1_matrix.to_csv(output_dir / "transfer_f1_matrix.csv")
    auc_matrix.to_csv(output_dir / "transfer_auc_matrix.csv")

    # Plot heatmaps
    plt.figure(figsize=(8.5, 7))
    sns.heatmap(f1_matrix, annot=True, fmt=".3f", cmap="YlGnBu", vmin=0, vmax=1, cbar_kws={"label": "F1"})
    plt.title("Cross-Dataset Transfer Matrix (F1)")
    plt.xlabel("Test Dataset")
    plt.ylabel("Bundle Training Dataset")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_transfer_f1_heatmap.png", dpi=300)
    plt.close()

    plt.figure(figsize=(8.5, 7))
    sns.heatmap(auc_matrix, annot=True, fmt=".3f", cmap="PuBuGn", vmin=0, vmax=1, cbar_kws={"label": "AUC-ROC"})
    plt.title("Cross-Dataset Transfer Matrix (AUC-ROC)")
    plt.xlabel("Test Dataset")
    plt.ylabel("Bundle Training Dataset")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_transfer_auc_heatmap.png", dpi=300)
    plt.close()

    # In-domain vs out-of-domain comparison
    in_domain = df_ok[df_ok["in_domain"]]
    out_domain = df_ok[~df_ok["in_domain"]].groupby("bundle_dataset", as_index=False)["f1_score"].mean()
    out_domain = out_domain.rename(columns={"f1_score": "out_domain_f1"})
    comp = in_domain[["bundle_dataset", "f1_score"]].rename(columns={"f1_score": "in_domain_f1"})
    comp = comp.merge(out_domain, on="bundle_dataset", how="left")

    x = np.arange(len(comp))
    width = 0.38

    plt.figure(figsize=(10, 5))
    plt.bar(x - width / 2, comp["in_domain_f1"], width, label="In-domain F1", color="#2E8B57")
    plt.bar(x + width / 2, comp["out_domain_f1"], width, label="Mean out-of-domain F1", color="#6A5ACD")
    plt.xticks(x, comp["bundle_dataset"], rotation=30, ha="right")
    plt.ylim(0, 1.02)
    plt.ylabel("F1")
    plt.title("Generalization Gap: In-domain vs Out-of-domain")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "fig_transfer_in_vs_out_f1.png", dpi=300)
    plt.close()

    # Summary stats for manuscript usage
    summary = {
        "n_datasets": len(dataset_ids),
        "n_bundles": len(bundle_paths),
        "n_transfer_pairs": len(df),
        "n_successful_pairs": int(df["status"].isin(["OK", "PARTIAL_MODEL_MATCH"]).sum()),
        "n_full_model_match_pairs": int((df["status"] == "OK").sum()),
        "n_partial_model_match_pairs": int((df["status"] == "PARTIAL_MODEL_MATCH").sum()),
        "n_incompatible_pairs": int((df["status"] == "INCOMPATIBLE").sum()),
        "mean_in_domain_f1": round(float(in_domain["f1_score"].mean()), 4),
        "mean_out_domain_f1": round(float(df_ok[~df_ok["in_domain"]]["f1_score"].mean()), 4),
        "mean_in_domain_auc": round(float(in_domain["auc_roc"].dropna().mean()), 4),
        "mean_out_domain_auc": round(float(df_ok[~df_ok["in_domain"]]["auc_roc"].dropna().mean()), 4),
        "best_cross_pair": None,
        "worst_cross_pair": None,
    }

    cross = df_ok[~df_ok["in_domain"]].copy()
    if not cross.empty:
        best_idx = cross["f1_score"].idxmax()
        worst_idx = cross["f1_score"].idxmin()
        summary["best_cross_pair"] = {
            "bundle_dataset": cross.loc[best_idx, "bundle_dataset"],
            "test_dataset": cross.loc[best_idx, "test_dataset"],
            "f1_score": float(cross.loc[best_idx, "f1_score"]),
            "auc_roc": float(cross.loc[best_idx, "auc_roc"]) if pd.notna(cross.loc[best_idx, "auc_roc"]) else None,
        }
        summary["worst_cross_pair"] = {
            "bundle_dataset": cross.loc[worst_idx, "bundle_dataset"],
            "test_dataset": cross.loc[worst_idx, "test_dataset"],
            "f1_score": float(cross.loc[worst_idx, "f1_score"]),
            "auc_roc": float(cross.loc[worst_idx, "auc_roc"]) if pd.notna(cross.loc[worst_idx, "auc_roc"]) else None,
        }

    with open(output_dir / "transfer_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\nCross-dataset transfer evaluation completed")
    print(f"Results saved to: {output_dir}")
    print(f"Mean in-domain F1:  {summary['mean_in_domain_f1']:.3f}")
    print(f"Mean out-domain F1: {summary['mean_out_domain_f1']:.3f}")
    return summary


def main() -> None:
    args = _parse_args()
    run_transfer(
        expr_dir=args.expr_dir,
        bundle_dir=args.bundle_dir,
        output_dir=args.output_dir,
        bundle_pattern=args.bundle_pattern,
        bundle_datasets=args.bundle_datasets,
        test_datasets=args.test_datasets,
    )


if __name__ == "__main__":
    main()
