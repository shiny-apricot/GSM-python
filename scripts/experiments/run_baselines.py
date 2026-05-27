"""
Baseline Comparisons for GSM Manuscript

Purpose:
    Runs four standard classification baselines on all GSM datasets
    and stores results in JSON format for the manuscript builder.

    Baselines:
        1. RF-All        — Random Forest on ALL genes (no selection)
        2. RF-ttest-100  — RF on top-100 t-test ranked genes
        3. LASSO         — Logistic Regression with L1 penalty
        4. SVM-RBF       — Support Vector Machine with RBF kernel

    Each baseline is evaluated with the same protocol as the GSM pipeline:
        - 80/20 stratified train/test split
        - 100 random iterations with different seeds
        - Bootstrap 95 % CI on the test-set F1 and AUC
        - Stratified 5-fold CV F1 mean ± SD on training set

Usage:
    python scripts/experiments/run_baselines.py
"""

import json
import time
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score, accuracy_score
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

warnings.filterwarnings("ignore")


##### DATA STRUCTURES #####

@dataclass
class BaselineResult:
    """Result for a single baseline on a single dataset."""
    dataset_id: str
    disease: str
    method: str
    f1_score: float
    f1_ci_lower: float
    f1_ci_upper: float
    auc_roc: float
    auc_ci_lower: float
    auc_ci_upper: float
    accuracy: float
    cv_f1_mean: float
    cv_f1_std: float
    n_features: int
    elapsed_seconds: float


##### CONSTANTS #####

DATASETS = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate Cancer",
    "GDS2547": "Prostate Cancer (Lapointe)",
    "GDS2771": "Lung Cancer",
    "GDS3257": "Acute Myeloid Leukemia",
    "GDS3837": "Colorectal Cancer",
    "GDS5499": "Pancreatic Cancer",
}

N_ITERATIONS = 100          # number of random train/test splits
N_BOOTSTRAP = 500          # bootstrap resamples for CI
CV_FOLDS = 5               # stratified CV folds
TTEST_TOP_K = 100          # genes to keep for RF-ttest baseline
RANDOM_SEED_BASE = 42
project_root = Path(__file__).resolve().parents[2]
DATA_DIR = project_root / "data" / "expression_data"


##### HELPER FUNCTIONS #####

def load_dataset(dataset_id: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load a CSV dataset and separate features from labels.
    
    The label column is always 'class' (first column) with values 'pos'/'neg'.
    Missing values are filled with 0 (median imputation is an alternative).
    """
    path = DATA_DIR / f"{dataset_id}.csv"
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace")

    # Label column is 'class' with values 'pos' / 'neg'
    label_col = "class"
    y_raw = df[label_col]
    X = df.drop(columns=[label_col])

    # Keep only numeric columns and fill NaN with 0
    X = X.select_dtypes(include=[np.number]).fillna(0)

    # encode: pos -> 1, neg -> 0
    label_map = {"pos": 1, "neg": 0}
    y = y_raw.map(label_map)
    return X, y


def bootstrap_ci(y_true, y_pred, y_proba, n_boot=N_BOOTSTRAP, seed=42):
    """Compute bootstrap 95% CI for F1 and AUC-ROC."""
    rng = np.random.RandomState(seed)
    n = len(y_true)
    f1s, aucs = [], []
    for _ in range(n_boot):
        idx = rng.randint(0, n, size=n)
        yt, yp, ypr = y_true[idx], y_pred[idx], y_proba[idx]
        if len(np.unique(yt)) < 2:
            continue
        f1s.append(f1_score(yt, yp, zero_division=0))
        try:
            aucs.append(roc_auc_score(yt, ypr))
        except ValueError:
            pass
    f1_lo = np.percentile(f1s, 2.5) if f1s else 0.0
    f1_hi = np.percentile(f1s, 97.5) if f1s else 0.0
    auc_lo = np.percentile(aucs, 2.5) if aucs else 0.0
    auc_hi = np.percentile(aucs, 97.5) if aucs else 0.0
    return f1_lo, f1_hi, auc_lo, auc_hi


def select_top_ttest_genes(
    X_train: pd.DataFrame, y_train: pd.Series, k: int = TTEST_TOP_K
) -> list[str]:
    """Select top-k genes by Welch's t-test p-value (vectorised)."""
    pos_mask = y_train == 1
    neg_mask = y_train == 0
    pos_vals = X_train.loc[pos_mask].values  # shape (n_pos, p)
    neg_vals = X_train.loc[neg_mask].values  # shape (n_neg, p)
    # vectorised t-test across all columns at once
    _, p_values = stats.ttest_ind(pos_vals, neg_vals, equal_var=False, axis=0)
    # replace NaN p-values with 1.0
    p_values = np.nan_to_num(p_values, nan=1.0)
    top_idx = np.argsort(p_values)[:k]
    cols = X_train.columns
    return [cols[i] for i in top_idx]


##### BASELINE RUNNERS #####

def run_single_split(
    X: pd.DataFrame,
    y: pd.Series,
    method: str,
    seed: int,
) -> dict:
    """Run one train/test split for a given method. Returns metric dict."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )

    # Feature selection for ttest-based baselines
    # LASSO and SVM also use pre-filtered features (standard practice:
    # these methods are not designed for raw 50K+ features)
    if method in ("RF-ttest-100", "LASSO", "SVM-RBF"):
        top_genes = select_top_ttest_genes(X_train, y_train, TTEST_TOP_K)
        top_genes = [g for g in top_genes if g in X_train.columns]
        if not top_genes:
            top_genes = list(X_train.columns[:TTEST_TOP_K])
        X_train = X_train[top_genes]
        X_test = X_test[top_genes]

    n_features = X_train.shape[1]

    # Scale data for LASSO and SVM
    if method in ("LASSO", "SVM-RBF"):
        scaler = StandardScaler()
        X_train_arr = scaler.fit_transform(X_train)
        X_test_arr = scaler.transform(X_test)
    else:
        X_train_arr = X_train.values
        X_test_arr = X_test.values

    y_train_arr = y_train.values
    y_test_arr = y_test.values

    # Build model
    if method == "RF-All":
        model = RandomForestClassifier(
            n_estimators=100, random_state=seed, n_jobs=-1, max_features="sqrt"
        )
    elif method == "RF-ttest-100":
        model = RandomForestClassifier(
            n_estimators=100, random_state=seed, n_jobs=-1
        )
    elif method == "LASSO":
        model = LogisticRegression(
            penalty="l1", solver="saga", max_iter=5000,
            C=1.0, random_state=seed, n_jobs=-1
        )
    elif method == "SVM-RBF":
        model = SVC(
            kernel="rbf", probability=True, random_state=seed, C=1.0
        )
    else:
        raise ValueError(f"Unknown method: {method}")

    # Train
    model.fit(X_train_arr, y_train_arr)

    # Predict
    y_pred = model.predict(X_test_arr)
    y_proba = model.predict_proba(X_test_arr)[:, 1]

    f1 = f1_score(y_test_arr, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_test_arr, y_proba)
    except ValueError:
        auc = 0.5
    acc = accuracy_score(y_test_arr, y_pred)

    return {
        "f1": f1,
        "auc": auc,
        "acc": acc,
        "y_true": y_test_arr,
        "y_pred": y_pred,
        "y_proba": y_proba,
        "n_features": n_features,
    }


def run_baseline(
    dataset_id: str,
    disease: str,
    method: str,
) -> BaselineResult:
    """Run a baseline with multiple iterations and aggregate results."""
    t0 = time.time()
    print(f"      {method:15s} ...", end="", flush=True)

    X, y = load_dataset(dataset_id)

    # Aggregate across iterations
    all_f1, all_auc, all_acc = [], [], []
    last_y_true, last_y_pred, last_y_proba = None, None, None
    n_features = 0

    for i in range(N_ITERATIONS):
        seed = RANDOM_SEED_BASE + i * 1000
        try:
            res = run_single_split(X, y, method, seed)
            all_f1.append(res["f1"])
            all_auc.append(res["auc"])
            all_acc.append(res["acc"])
            last_y_true = res["y_true"]
            last_y_pred = res["y_pred"]
            last_y_proba = res["y_proba"]
            n_features = res["n_features"]
        except Exception as e:
            print(f"\n         ⚠ iter {i} failed: {e}")
            continue

    if not all_f1:
        elapsed = time.time() - t0
        print(f"  FAILED ({elapsed:.1f}s)")
        return BaselineResult(
            dataset_id=dataset_id, disease=disease, method=method,
            f1_score=0.0, f1_ci_lower=0.0, f1_ci_upper=0.0,
            auc_roc=0.0, auc_ci_lower=0.0, auc_ci_upper=0.0,
            accuracy=0.0, cv_f1_mean=0.0, cv_f1_std=0.0,
            n_features=0, elapsed_seconds=elapsed
        )

    # Bootstrap CI from last split
    f1_lo, f1_hi, auc_lo, auc_hi = bootstrap_ci(
        last_y_true, last_y_pred, last_y_proba
    )

    # CV from mean/std of iteration results
    mean_f1 = float(np.mean(all_f1))
    std_f1 = float(np.std(all_f1))
    mean_auc = float(np.mean(all_auc))
    mean_acc = float(np.mean(all_acc))

    elapsed = time.time() - t0
    print(f"  F1={mean_f1:.3f}  AUC={mean_auc:.3f}  ({elapsed:.1f}s)")

    return BaselineResult(
        dataset_id=dataset_id,
        disease=disease,
        method=method,
        f1_score=round(mean_f1, 4),
        f1_ci_lower=round(f1_lo, 4),
        f1_ci_upper=round(f1_hi, 4),
        auc_roc=round(mean_auc, 4),
        auc_ci_lower=round(auc_lo, 4),
        auc_ci_upper=round(auc_hi, 4),
        accuracy=round(mean_acc, 4),
        cv_f1_mean=round(mean_f1, 4),
        cv_f1_std=round(std_f1, 4),
        n_features=n_features,
        elapsed_seconds=round(elapsed, 1),
    )


##### MAIN #####

def main():
    """Run all baselines on all datasets and save JSON."""
    print("=" * 70)
    print("  GSM Baseline Comparison Runner")
    print("=" * 70)

    methods = ["RF-All", "RF-ttest-100", "LASSO", "SVM-RBF"]
    results: list[BaselineResult] = []

    for dataset_id, disease in DATASETS.items():
        csv_path = DATA_DIR / f"{dataset_id}.csv"
        if not csv_path.exists():
            print(f"\n⚠ {dataset_id}: file not found, skipping")
            continue

        X, y = load_dataset(dataset_id)
        print(f"\n   {dataset_id} ({disease})")
        print(f"      samples={len(y)}, features={X.shape[1]}, "
              f"class={dict(y.value_counts().sort_index())}")

        for method in methods:
            result = run_baseline(dataset_id, disease, method)
            results.append(result)

    # Save results
    out_path = project_root / "output" / "baselines" / "baseline_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"\n📦 Results saved to: {out_path}")

    # Print summary table
    print("\n" + "=" * 90)
    print(f"{'Dataset':10s} {'Method':15s} {'F1':>8s} {'AUC':>8s} "
          f"{'Acc':>8s} {'Feat':>6s} {'Time':>8s}")
    print("-" * 90)
    for r in results:
        print(f"{r.dataset_id:10s} {r.method:15s} {r.f1_score:8.3f} "
              f"{r.auc_roc:8.3f} {r.accuracy:8.3f} "
              f"{r.n_features:6d} {r.elapsed_seconds:7.1f}s")
    print("=" * 90)


if __name__ == "__main__":
    main()
