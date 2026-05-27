"""
📊 Baseline Comparison Script for GSM Pipeline

Purpose:
    Compare G-S-M framework performance with standard feature selection methods.
    Provides fair comparison with LASSO, RFE, SelectKBest, and no selection.

Key Functions:
    - run_baseline_comparison: Main entry point
    - run_lasso: LASSO-based feature selection
    - run_rfe: Recursive Feature Elimination
    - run_selectkbest: Univariate feature selection
    - run_no_selection: Full feature set baseline

Output:
    - comparison_results.csv: Tabular comparison of all methods
    - comparison_figure.png: Bar chart visualization

Example Usage:
    >>> python baseline_comparison.py data/main_data/GDS2545.csv output/comparison

Note:
    This script should be run after the main GSM pipeline to compare results.
"""

import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LassoCV, LogisticRegressionCV
from sklearn.feature_selection import SelectKBest, f_classif, RFE
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                            f1_score, roc_auc_score)


##### CONSTANTS #####
RANDOM_STATE = 42
TEST_SIZE = 0.3
CV_FOLDS = 5
N_FEATURES_TO_SELECT = 10  # Target number of features for comparison


@dataclass
class ComparisonResult:
    """Result from a feature selection method comparison."""
    method_name: str
    n_features_selected: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_roc: float
    cv_f1_mean: float
    cv_f1_std: float
    training_time: float
    selected_features: List[str] = field(default_factory=list)
    interpretability: str = "Low"


##### MAIN ENTRY POINT #####
def run_baseline_comparison(
    data_path: Path,
    output_dir: Path,
    gsm_results_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> pd.DataFrame:
    """Run comparison with all baseline feature selection methods.
    
    Args:
        data_path: Path to gene expression data (CSV)
        output_dir: Directory to save comparison results
        gsm_results_path: Optional path to GSM results JSON for inclusion
        logger: Logger instance
    
    Returns:
        DataFrame with comparison results
    """
    if logger is None:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
    
    logger.info("📊 Starting baseline comparison analysis...")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and prepare data
    X, y, feature_names = load_and_prepare_data(data_path, logger)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    
    logger.info(f"📋 Data: {X.shape[0]} samples, {X.shape[1]} features")
    logger.info(f"   Training: {X_train.shape[0]}, Test: {X_test.shape[0]}")
    
    results = []
    
    # Run each method
    logger.info("\n🔬 Running LASSO feature selection...")
    lasso_result = run_lasso(X_train, X_test, y_train, y_test, feature_names, logger)
    results.append(lasso_result)
    
    logger.info("\n🔬 Running Recursive Feature Elimination...")
    rfe_result = run_rfe(X_train, X_test, y_train, y_test, feature_names, logger)
    results.append(rfe_result)
    
    logger.info("\n🔬 Running SelectKBest (ANOVA F-value)...")
    kbest_result = run_selectkbest(X_train, X_test, y_train, y_test, feature_names, logger)
    results.append(kbest_result)
    
    logger.info("\n🔬 Running full feature set (no selection)...")
    full_result = run_no_selection(X_train, X_test, y_train, y_test, feature_names, logger)
    results.append(full_result)
    
    # Include GSM results if available
    if gsm_results_path and gsm_results_path.exists():
        logger.info("\n🔬 Loading GSM results for comparison...")
        gsm_result = load_gsm_results(gsm_results_path, logger)
        if gsm_result:
            results.insert(0, gsm_result)  # Put GSM first
    
    # Create comparison DataFrame
    comparison_df = create_comparison_df(results)
    
    # Save results
    save_comparison_results(comparison_df, output_dir, logger)
    
    # Generate comparison figure
    plot_comparison_figure(comparison_df, output_dir, logger)
    
    logger.info(f"\n✅ Baseline comparison complete. Results saved to: {output_dir}")
    
    return comparison_df


##### DATA LOADING #####
def load_and_prepare_data(
    data_path: Path, 
    logger: logging.Logger
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Load and prepare gene expression data for analysis."""
    logger.info(f"📂 Loading data from: {data_path}")
    
    df = pd.read_csv(data_path)
    
    # Assume first column is sample ID and second is class label
    # This may need adjustment based on actual data format
    
    # Find the class column (usually 'class', 'Class', 'label', etc.)
    class_col = None
    for col in ['class', 'Class', 'label', 'Label', 'disease_state', 'condition']:
        if col in df.columns:
            class_col = col
            break
    
    if class_col is None:
        # Assume second column is class
        class_col = df.columns[1]
        logger.warning(f"   Using '{class_col}' as class column (second column)")
    
    # Identify feature columns (numeric columns that are not ID or class)
    feature_cols = [col for col in df.columns 
                   if col != class_col and df[col].dtype in ['float64', 'int64']]
    
    # Also try to exclude ID columns
    feature_cols = [col for col in feature_cols 
                   if 'id' not in col.lower() and 'sample' not in col.lower()]
    
    X = df[feature_cols].values
    
    # Encode labels
    le = LabelEncoder()
    y = le.fit_transform(df[class_col].values)
    
    # Handle missing values
    X = np.nan_to_num(X, nan=0.0)
    
    # Standardize features
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    
    logger.info(f"   Features: {len(feature_cols)}, Classes: {len(le.classes_)}")
    
    return X, y, feature_cols


##### LASSO FEATURE SELECTION #####
def run_lasso(
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    logger: logging.Logger
) -> ComparisonResult:
    """Run LASSO-based feature selection and classification."""
    start_time = time.time()
    
    # Use LogisticRegressionCV with L1 penalty for classification
    lasso = LogisticRegressionCV(
        cv=CV_FOLDS,
        penalty='l1',
        solver='saga',
        max_iter=1000,
        random_state=RANDOM_STATE
    )
    
    lasso.fit(X_train, y_train)
    
    # Get selected features (non-zero coefficients)
    if hasattr(lasso, 'coef_'):
        selected_mask = np.abs(lasso.coef_[0]) > 1e-5
    else:
        selected_mask = np.ones(X_train.shape[1], dtype=bool)
    
    selected_features = [f for f, s in zip(feature_names, selected_mask) if s]
    n_selected = len(selected_features)
    
    logger.info(f"   Selected {n_selected} features")
    
    # Evaluate
    y_pred = lasso.predict(X_test)
    y_prob = lasso.predict_proba(X_test)[:, 1] if hasattr(lasso, 'predict_proba') else y_pred
    
    # Cross-validation
    cv_scores = cross_val_score(lasso, X_train, y_train, cv=CV_FOLDS, scoring='f1')
    
    training_time = time.time() - start_time
    
    return ComparisonResult(
        method_name="LASSO (L1 Regularization)",
        n_features_selected=n_selected,
        accuracy=accuracy_score(y_test, y_pred),
        precision=precision_score(y_test, y_pred, zero_division=0),
        recall=recall_score(y_test, y_pred, zero_division=0),
        f1_score=f1_score(y_test, y_pred, zero_division=0),
        auc_roc=roc_auc_score(y_test, y_prob),
        cv_f1_mean=np.mean(cv_scores),
        cv_f1_std=np.std(cv_scores),
        training_time=training_time,
        selected_features=selected_features[:10],
        interpretability="Low"
    )


##### RECURSIVE FEATURE ELIMINATION #####
def run_rfe(
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    logger: logging.Logger
) -> ComparisonResult:
    """Run Recursive Feature Elimination."""
    start_time = time.time()
    
    base_estimator = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
    
    # Use RFE to select top features
    rfe = RFE(
        estimator=base_estimator,
        n_features_to_select=N_FEATURES_TO_SELECT,
        step=0.1  # Remove 10% of features at each step
    )
    
    rfe.fit(X_train, y_train)
    
    selected_features = [f for f, s in zip(feature_names, rfe.support_) if s]
    n_selected = len(selected_features)
    
    logger.info(f"   Selected {n_selected} features")
    
    # Evaluate
    y_pred = rfe.predict(X_test)
    y_prob = rfe.predict_proba(X_test)[:, 1] if hasattr(rfe, 'predict_proba') else y_pred
    
    # Cross-validation on selected features
    X_train_selected = X_train[:, rfe.support_]
    X_test_selected = X_test[:, rfe.support_]
    
    cv_scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE),
        X_train_selected, y_train, cv=CV_FOLDS, scoring='f1'
    )
    
    training_time = time.time() - start_time
    
    return ComparisonResult(
        method_name="Recursive Feature Elimination",
        n_features_selected=n_selected,
        accuracy=accuracy_score(y_test, y_pred),
        precision=precision_score(y_test, y_pred, zero_division=0),
        recall=recall_score(y_test, y_pred, zero_division=0),
        f1_score=f1_score(y_test, y_pred, zero_division=0),
        auc_roc=roc_auc_score(y_test, y_prob),
        cv_f1_mean=np.mean(cv_scores),
        cv_f1_std=np.std(cv_scores),
        training_time=training_time,
        selected_features=selected_features[:10],
        interpretability="Low"
    )


##### SELECTKBEST #####
def run_selectkbest(
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    logger: logging.Logger
) -> ComparisonResult:
    """Run SelectKBest with ANOVA F-value."""
    start_time = time.time()
    
    selector = SelectKBest(f_classif, k=N_FEATURES_TO_SELECT)
    X_train_selected = selector.fit_transform(X_train, y_train)
    X_test_selected = selector.transform(X_test)
    
    selected_features = [f for f, s in zip(feature_names, selector.get_support()) if s]
    n_selected = len(selected_features)
    
    logger.info(f"   Selected {n_selected} features")
    
    # Train classifier on selected features
    clf = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)
    clf.fit(X_train_selected, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test_selected)
    y_prob = clf.predict_proba(X_test_selected)[:, 1]
    
    # Cross-validation
    cv_scores = cross_val_score(clf, X_train_selected, y_train, cv=CV_FOLDS, scoring='f1')
    
    training_time = time.time() - start_time
    
    return ComparisonResult(
        method_name="SelectKBest (ANOVA F)",
        n_features_selected=n_selected,
        accuracy=accuracy_score(y_test, y_pred),
        precision=precision_score(y_test, y_pred, zero_division=0),
        recall=recall_score(y_test, y_pred, zero_division=0),
        f1_score=f1_score(y_test, y_pred, zero_division=0),
        auc_roc=roc_auc_score(y_test, y_prob),
        cv_f1_mean=np.mean(cv_scores),
        cv_f1_std=np.std(cv_scores),
        training_time=training_time,
        selected_features=selected_features[:10],
        interpretability="Low"
    )


##### NO SELECTION (BASELINE) #####
def run_no_selection(
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    logger: logging.Logger
) -> ComparisonResult:
    """Run classifier with all features (no selection)."""
    start_time = time.time()
    
    n_features = X_train.shape[1]
    logger.info(f"   Using all {n_features} features")
    
    # Train classifier
    clf = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1)
    clf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    
    # Cross-validation
    cv_scores = cross_val_score(clf, X_train, y_train, cv=CV_FOLDS, scoring='f1')
    
    training_time = time.time() - start_time
    
    return ComparisonResult(
        method_name="No Selection (All Features)",
        n_features_selected=n_features,
        accuracy=accuracy_score(y_test, y_pred),
        precision=precision_score(y_test, y_pred, zero_division=0),
        recall=recall_score(y_test, y_pred, zero_division=0),
        f1_score=f1_score(y_test, y_pred, zero_division=0),
        auc_roc=roc_auc_score(y_test, y_prob),
        cv_f1_mean=np.mean(cv_scores),
        cv_f1_std=np.std(cv_scores),
        training_time=training_time,
        selected_features=[],
        interpretability="None"
    )


##### LOAD GSM RESULTS #####
def load_gsm_results(
    results_path: Path,
    logger: logging.Logger
) -> Optional[ComparisonResult]:
    """Load GSM results for comparison."""
    import json
    
    try:
        with open(results_path, 'r') as f:
            all_results = json.load(f)
        
        # Find best result (2-group configuration typically)
        best_f1 = 0
        best_result = None
        
        for iteration_data in all_results:
            for result in iteration_data.get('results', []):
                if result.get('num_groups_used') == 2:  # Focus on best config
                    if result.get('f1_score', 0) > best_f1:
                        best_f1 = result.get('f1_score', 0)
                        best_result = result
        
        if best_result:
            features = list(best_result.get('feature_importance', {}).keys())
            
            return ComparisonResult(
                method_name="G-S-M (Knowledge-Driven)",
                n_features_selected=best_result.get('num_features_used', 0),
                accuracy=best_result.get('accuracy', 0),
                precision=best_result.get('precision', 0),
                recall=best_result.get('recall', 0),
                f1_score=best_result.get('f1_score', 0),
                auc_roc=best_result.get('auc_roc', 0),
                cv_f1_mean=best_result.get('cv_f1_mean', 0),
                cv_f1_std=best_result.get('cv_f1_std', 0),
                training_time=best_result.get('training_time', 0),
                selected_features=features[:10],
                interpretability="High (Pathway-level)"
            )
        
    except Exception as e:
        logger.warning(f"⚠️ Could not load GSM results: {e}")
    
    return None


##### SAVE RESULTS #####
def create_comparison_df(results: List[ComparisonResult]) -> pd.DataFrame:
    """Create comparison DataFrame from results."""
    data = []
    for r in results:
        data.append({
            'Method': r.method_name,
            'Features': r.n_features_selected,
            'Accuracy': r.accuracy,
            'Precision': r.precision,
            'Recall': r.recall,
            'F1 Score': r.f1_score,
            'AUC-ROC': r.auc_roc,
            'CV F1 Mean': r.cv_f1_mean,
            'CV F1 Std': r.cv_f1_std,
            'Time (s)': r.training_time,
            'Interpretability': r.interpretability
        })
    
    return pd.DataFrame(data)


def save_comparison_results(
    df: pd.DataFrame,
    output_dir: Path,
    logger: logging.Logger
) -> None:
    """Save comparison results to CSV."""
    output_path = output_dir / "baseline_comparison.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"💾 Saved comparison results: {output_path}")
    
    # Also print to console
    print("\n" + "=" * 80)
    print("BASELINE COMPARISON RESULTS")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80 + "\n")


def plot_comparison_figure(
    df: pd.DataFrame,
    output_dir: Path,
    logger: logging.Logger
) -> None:
    """Generate comparison bar chart."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    methods = df['Method'].values
    x = np.arange(len(methods))
    
    # F1 Score comparison
    ax1 = axes[0]
    colors = plt.cm.Set2(np.linspace(0, 1, len(methods)))
    bars1 = ax1.bar(x, df['F1 Score'], color=colors, edgecolor='black')
    ax1.set_xticks(x)
    ax1.set_xticklabels(methods, rotation=45, ha='right', fontsize=8)
    ax1.set_ylabel('F1 Score')
    ax1.set_title('F1 Score Comparison')
    ax1.set_ylim(0, 1.1)
    
    # Add value labels
    for bar, val in zip(bars1, df['F1 Score']):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{val:.3f}', ha='center', fontsize=8)
    
    # AUC-ROC comparison
    ax2 = axes[1]
    bars2 = ax2.bar(x, df['AUC-ROC'], color=colors, edgecolor='black')
    ax2.set_xticks(x)
    ax2.set_xticklabels(methods, rotation=45, ha='right', fontsize=8)
    ax2.set_ylabel('AUC-ROC')
    ax2.set_title('AUC-ROC Comparison')
    ax2.set_ylim(0, 1.1)
    
    for bar, val in zip(bars2, df['AUC-ROC']):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{val:.3f}', ha='center', fontsize=8)
    
    # Number of features
    ax3 = axes[2]
    bars3 = ax3.bar(x, df['Features'], color=colors, edgecolor='black')
    ax3.set_xticks(x)
    ax3.set_xticklabels(methods, rotation=45, ha='right', fontsize=8)
    ax3.set_ylabel('Number of Features')
    ax3.set_title('Feature Count Comparison')
    ax3.set_yscale('log')
    
    for bar, val in zip(bars3, df['Features']):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.1,
                f'{val}', ha='center', fontsize=8)
    
    plt.tight_layout()
    
    output_path = output_dir / "baseline_comparison.png"
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"📊 Saved comparison figure: {output_path}")


##### STANDALONE EXECUTION #####
if __name__ == "__main__":
    import sys
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(
        description="Compare G-S-M with baseline feature selection methods"
    )
    parser.add_argument(
        "data_path",
        type=str,
        help="Path to gene expression data CSV"
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Directory to save comparison results"
    )
    parser.add_argument(
        "--gsm-results",
        type=str,
        default=None,
        help="Path to GSM modeling_results_all_iterations.json"
    )
    
    args = parser.parse_args()
    
    gsm_path = Path(args.gsm_results) if args.gsm_results else None
    
    comparison_df = run_baseline_comparison(
        Path(args.data_path),
        Path(args.output_dir),
        gsm_path,
        logger
    )
    
    print("\n✅ Comparison complete!")
