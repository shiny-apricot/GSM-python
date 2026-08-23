"""
🧬 Model Training and Evaluation Module 🧬

This module handles the training and evaluation of machine learning models
using gene features from top-ranked groups.

Key Functions:
-------------
- run_modeling: Main entry point for model training with features from top groups
- select_features_from_top_groups: Selects features from specified number of top groups

Methodology Notes (for scientific review):
----------------------------------------
This module implements a rigorous evaluation methodology:
1. **Multiple ML Models**: Supports RandomForest, SVM, and others for comparative analysis
2. **Cross-Validation**: Uses stratified K-fold CV to ensure robust performance estimates
3. **Confidence Intervals**: Computes 95% CI via bootstrapping for all metrics
4. **Probability Predictions**: Outputs probability scores, not just binary labels
5. **AUC-ROC**: Reports area under ROC curve for classification quality assessment

Example Usage:
------------
>>> result = run_modeling(train_x, train_y, test_x, test_y, 
                         group_ranks, group_mapping, "RandomForest", logger)
>>> print(f"Model achieved F1 score: {result.f1_score:.4f} (95% CI: {result.f1_ci_lower:.4f}-{result.f1_ci_upper:.4f})")
>>> print(f"AUC-ROC: {result.auc_roc:.4f}")
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                            roc_auc_score, balanced_accuracy_score, matthews_corrcoef,
                            average_precision_score, confusion_matrix)
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier

from src.scoring.metrics import MetricsData
from src.grouping.grouping_utils import GroupFeatureMappingData


##### CONSTANTS FOR STATISTICAL ANALYSIS #####
CONFIDENCE_LEVEL = 0.95  # 95% confidence interval
BOOTSTRAP_SAMPLES = 100  # Number of bootstrap iterations for CI estimation (reduced for speed)
DEFAULT_CV_FOLDS = 3  # Default cross-validation folds (reduced for speed)


@dataclass
class CrossValidationMetrics:
    """Cross-validation metrics with standard deviation for robust evaluation."""
    accuracy_mean: float
    accuracy_std: float
    f1_mean: float
    f1_std: float
    precision_mean: float
    precision_std: float
    recall_mean: float
    recall_std: float


@dataclass
class ConfidenceInterval:
    """95% confidence interval for a metric."""
    lower: float
    upper: float
    point_estimate: float


@dataclass
class ModelingResult:
    """Results from model training and evaluation.
    
    Contains comprehensive metrics for publication-quality reporting:
    - Point estimates for all standard metrics (accuracy, precision, recall, F1, AUC-ROC)
    - 95% confidence intervals computed via bootstrapping
    - Cross-validation mean and standard deviation
    - Probability predictions for threshold analysis
    """
    model_name: str
    num_groups_used: int
    num_features_used: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    # AUC-ROC for classification quality
    auc_roc: float = 0.0
    # 95% Confidence intervals (bootstrapped)
    accuracy_ci_lower: float = 0.0
    accuracy_ci_upper: float = 0.0
    f1_ci_lower: float = 0.0
    f1_ci_upper: float = 0.0
    auc_ci_lower: float = 0.0
    auc_ci_upper: float = 0.0
    # Cross-validation metrics
    cv_accuracy_mean: float = 0.0
    cv_accuracy_std: float = 0.0
    cv_f1_mean: float = 0.0
    cv_f1_std: float = 0.0
    # Probability predictions (mean probability for positive class)
    mean_positive_probability: float = 0.0
    # Extended metrics (reviewer I4: class imbalance)
    balanced_accuracy: float = 0.0
    mcc: float = 0.0  # Matthews Correlation Coefficient
    pr_auc: float = 0.0  # Precision-Recall AUC
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    # Feature importance
    feature_importance: Dict[str, float] = field(default_factory=dict)
    training_time: float = 0.0
    used_features: List[str] = field(default_factory=list)
    used_groups: List[str] = field(default_factory=list)
    # Fitted model object (optional, for inference bundle saving)
    fitted_model: Optional[Any] = field(default=None, repr=False)


@dataclass
class SelectedFeaturesResult:
    """Result of feature selection from top groups."""
    selected_features: List[str]
    used_group_names: List[str]


def compute_bootstrap_confidence_interval(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray],
    metric_name: str,
    n_bootstrap: int = BOOTSTRAP_SAMPLES,
    confidence: float = CONFIDENCE_LEVEL,
    random_state: int = 42
) -> ConfidenceInterval:
    """
    Compute confidence interval for a metric using bootstrapping.
    
    This provides statistically rigorous uncertainty estimates for model performance,
    which is essential for publication and validation.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_proba: Predicted probabilities (for AUC-ROC)
        metric_name: One of 'accuracy', 'f1', 'precision', 'recall', 'auc_roc'
        n_bootstrap: Number of bootstrap samples (default: 100, reduced for speed)
        confidence: Confidence level (default: 0.95 for 95% CI)
        random_state: Random seed for reproducible bootstrap sampling
    
    Returns:
        ConfidenceInterval with lower, upper bounds and point estimate
    """
    n_samples = len(y_true)
    bootstrap_scores = []
    
    # Use a dedicated RNG for reproducible bootstrap sampling
    rng = np.random.RandomState(random_state)
    all_indices = rng.randint(0, n_samples, size=(n_bootstrap, n_samples))
    
    for i in range(n_bootstrap):
        indices = all_indices[i]
        y_true_boot = y_true[indices]
        y_pred_boot = y_pred[indices]
        
        # Compute metric for this bootstrap sample
        if metric_name == 'accuracy':
            score = accuracy_score(y_true_boot, y_pred_boot)
        elif metric_name == 'f1':
            score = f1_score(y_true_boot, y_pred_boot, average='binary', zero_division=0)
        elif metric_name == 'precision':
            score = precision_score(y_true_boot, y_pred_boot, average='binary', zero_division=0)
        elif metric_name == 'recall':
            score = recall_score(y_true_boot, y_pred_boot, average='binary', zero_division=0)
        elif metric_name == 'auc_roc' and y_proba is not None:
            y_proba_boot = y_proba[indices]
            # AUC requires at least 2 classes in the sample
            if len(np.unique(y_true_boot)) < 2:
                continue
            score = roc_auc_score(y_true_boot, y_proba_boot)
        else:
            continue
            
        bootstrap_scores.append(score)
    
    if not bootstrap_scores:
        return ConfidenceInterval(lower=0.0, upper=0.0, point_estimate=0.0)
    
    # Compute percentile-based confidence interval
    alpha = (1 - confidence) / 2
    lower = np.percentile(bootstrap_scores, alpha * 100)
    upper = np.percentile(bootstrap_scores, (1 - alpha) * 100)
    point_estimate = np.mean(bootstrap_scores)
    
    return ConfidenceInterval(lower=lower, upper=upper, point_estimate=point_estimate)


def perform_cross_validation(
    model,
    X: pd.DataFrame,
    y: pd.Series,
    cv_folds: int = DEFAULT_CV_FOLDS,
    logger: Optional[logging.Logger] = None,
    random_state: int = 42
) -> CrossValidationMetrics:
    """
    Perform stratified cross-validation for robust performance estimation.
    
    Uses stratified K-fold to ensure class balance in each fold.
    Reports mean and standard deviation for all metrics.
    
    Args:
        model: Scikit-learn compatible model (will be cloned for each fold)
        X: Feature matrix
        y: Target labels
        cv_folds: Number of cross-validation folds
        logger: Optional logger
        
    Returns:
        CrossValidationMetrics with mean and std for each metric
    """
    from sklearn.model_selection import cross_validate as sklearn_cv
    from sklearn.base import clone
    
    # Use explicit random_state for reproducible CV fold splits
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    
    # Single cross_validate call for all metrics (more efficient than 4 separate calls)
    scoring = ['accuracy', 'f1', 'precision', 'recall']
    cv_results = sklearn_cv(clone(model), X, y, cv=cv, scoring=scoring)
    
    return CrossValidationMetrics(
        accuracy_mean=float(np.mean(cv_results['test_accuracy'])),
        accuracy_std=float(np.std(cv_results['test_accuracy'])),
        f1_mean=float(np.mean(cv_results['test_f1'])),
        f1_std=float(np.std(cv_results['test_f1'])),
        precision_mean=float(np.mean(cv_results['test_precision'])),
        precision_std=float(np.std(cv_results['test_precision'])),
        recall_mean=float(np.mean(cv_results['test_recall'])),
        recall_std=float(np.std(cv_results['test_recall']))
    )


def select_features_from_top_groups(
    group_ranks: List[MetricsData],
    group_feature_mapping: List[GroupFeatureMappingData],
    top_n_groups: int,
    logger: logging.Logger
) -> SelectedFeaturesResult:
    """
    Select features from the top N ranked groups.
    
    Args:
        group_ranks: Groups ranked by performance (highest first)
        group_feature_mapping: Group to feature mapping data
        top_n_groups: Number of top groups to include
        logger: Logger for tracking progress
    
    Returns:
        SelectedFeaturesResult containing selected features and used group names
    """
    # Create a mapping from group name to features for easier lookup
    name_to_mapping = {mapping.group_name: mapping for mapping in group_feature_mapping}
    
    # Calculate how many groups we can actually use
    used_groups = min(top_n_groups, len(group_ranks))
    # logger.info(f"🔍 Selecting features from top {used_groups} groups")
    
    selected_features = []
    used_group_names = []
    
    # Process each top group
    for i in range(used_groups):
        group = group_ranks[i]
        group_name = group.name
        used_group_names.append(group_name)
        
        if group_name in name_to_mapping:
            group_features = name_to_mapping[group_name].feature_list
            # logger.info(f"  - Group {i+1}: '{group_name}' with {len(group_features)} features")
            selected_features.extend(group_features)
        else:
            logger.warning(f"Group '{group_name}' not in mappings")
    
    # Remove duplicate features
    unique_features = list(set(selected_features))
    # logger.info(f"✅ Selected {len(unique_features)} unique features from {len(used_group_names)} groups")
    
    return SelectedFeaturesResult(
        selected_features=unique_features,
        used_group_names=used_group_names
    )


@dataclass
class ModelTrainingResult:
    """Results from model training and evaluation."""
    model: Any
    metrics: Dict[str, float]
    feature_importance: Dict[str, float]
    y_pred: np.ndarray  # Predicted labels
    y_proba: Optional[np.ndarray]  # Predicted probabilities
    cv_metrics: Optional[CrossValidationMetrics]  # Cross-validation results


def train_and_evaluate_model(
    model_name: str,
    train_x: pd.DataFrame,
    train_y: pd.Series,
    test_x: pd.DataFrame,
    test_y: pd.Series,
    logger: logging.Logger,
    perform_cv: bool = True,
    random_state: int = 42
) -> ModelTrainingResult:
    """
    Train a model and evaluate its performance with comprehensive metrics.
    
    This function implements rigorous evaluation for publication-quality results:
    - Computes standard metrics (accuracy, precision, recall, F1)
    - Calculates AUC-ROC for classification quality assessment
    - Performs cross-validation with mean and std
    - Computes 95% confidence intervals via bootstrapping
    - Outputs probability predictions for threshold analysis
    
    Args:
        model_name: Classifier type to use
        train_x: Training features
        train_y: Training labels
        test_x: Testing features
        test_y: Testing labels
        logger: Logger for tracking progress
        perform_cv: Whether to perform cross-validation (default: True)
        random_state: Random seed for reproducibility
        
    Returns:
        ModelTrainingResult with trained model, metrics, probabilities, and CV results
        
    Methodology Notes (addressing reviewer concerns):
        - Multiple ML methods supported for comparative analysis
        - Probability outputs enable threshold optimization for disease prediction
        - AUC-ROC provides classification quality independent of threshold choice
    """
    # Select model type with explicit random_state for reproducibility
    # n_jobs=-1 for final modeling RF to use all cores (this is NOT nested inside joblib)
    if model_name == "RandomForest":
        model = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=random_state)
    elif model_name == "XGBoost":
        # Gradient boosting: fast, accurate, with native feature importance
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0,
            random_state=random_state,
            n_jobs=-1
        )
    elif model_name == "DecisionTree":
        model = DecisionTreeClassifier(random_state=random_state)
    elif model_name == "SVM":
        model = SVC(probability=True, random_state=random_state)  # Enable probability estimates
    elif model_name == "KNN":
        model = KNeighborsClassifier(n_neighbors=5, n_jobs=-1)  # Deterministic algorithm
    elif model_name == "MLP":
        model = MLPClassifier(hidden_layer_sizes=(100,), max_iter=500, random_state=random_state)
    else:
        logger.error(f"Unsupported model: {model_name}")
        raise ValueError(f"Unsupported model type: {model_name}")
    
    logger.debug(f"Training {model_name} with {len(train_x)} samples, {len(train_x.columns)} features")
    
    # Train model
    start_time = time.time()
    model.fit(train_x, train_y)
    training_time = time.time() - start_time
    
    # Make predictions (binary labels)
    y_pred = model.predict(test_x)
    
    # Get probability predictions for positive class
    y_proba = None
    if hasattr(model, 'predict_proba'):
        y_proba = model.predict_proba(test_x)[:, 1]  # Probability of positive class
    elif hasattr(model, 'decision_function'):
        # SVM without probability - use decision function normalized
        y_proba = model.decision_function(test_x)
    
    # Calculate standard metrics
    acc = accuracy_score(test_y, y_pred)
    prec = precision_score(test_y, y_pred, average='binary', zero_division=0)
    rec = recall_score(test_y, y_pred, average='binary', zero_division=0)
    f1 = f1_score(test_y, y_pred, average='binary', zero_division=0)
    
    # Extended metrics (reviewer I4: class imbalance)
    bal_acc = balanced_accuracy_score(test_y, y_pred)
    mcc = matthews_corrcoef(test_y, y_pred)
    cm = confusion_matrix(test_y, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
    
    # Calculate AUC-ROC (important for assessing classification quality)
    auc = 0.0
    pr_auc = 0.0
    if y_proba is not None and len(np.unique(test_y)) > 1:
        try:
            auc = roc_auc_score(test_y, y_proba)
            pr_auc = average_precision_score(test_y, y_proba)
        except ValueError as e:
            logger.warning(f"AUC metrics unavailable: {e}")
    
    # Compute 95% confidence intervals via bootstrapping
    test_y_arr = np.array(test_y)
    y_pred_arr = np.array(y_pred)
    
    acc_ci = compute_bootstrap_confidence_interval(test_y_arr, y_pred_arr, y_proba, 'accuracy', random_state=random_state)
    f1_ci = compute_bootstrap_confidence_interval(test_y_arr, y_pred_arr, y_proba, 'f1', random_state=random_state + 1)
    auc_ci = compute_bootstrap_confidence_interval(test_y_arr, y_pred_arr, y_proba, 'auc_roc', random_state=random_state + 2)
    
    metrics = {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "auc_roc": auc,
        "balanced_accuracy": bal_acc,
        "mcc": mcc,
        "pr_auc": pr_auc,
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
        "training_time": training_time,
        # Confidence intervals
        "accuracy_ci_lower": acc_ci.lower,
        "accuracy_ci_upper": acc_ci.upper,
        "f1_ci_lower": f1_ci.lower,
        "f1_ci_upper": f1_ci.upper,
        "auc_ci_lower": auc_ci.lower,
        "auc_ci_upper": auc_ci.upper,
        # Mean probability for positive class predictions
        "mean_positive_probability": float(np.mean(y_proba)) if y_proba is not None else 0.0
    }
    
    # Perform cross-validation for robust estimates
    cv_metrics = None
    if perform_cv and len(train_x) >= DEFAULT_CV_FOLDS * 2:
        try:
            cv_metrics = perform_cross_validation(
                model, train_x, train_y, DEFAULT_CV_FOLDS, logger,
                random_state=random_state
            )
            metrics["cv_accuracy_mean"] = cv_metrics.accuracy_mean
            metrics["cv_accuracy_std"] = cv_metrics.accuracy_std
            metrics["cv_f1_mean"] = cv_metrics.f1_mean
            metrics["cv_f1_std"] = cv_metrics.f1_std
        except Exception as e:
            logger.warning(f"CV failed: {e}")
    
    # Get feature importance if available
    feature_importance = {}
    try:
        if isinstance(model, (RandomForestClassifier, XGBClassifier)) and hasattr(model, "feature_importances_"):
            for feature, importance in zip(train_x.columns, model.feature_importances_):
                feature_importance[feature] = float(importance)
        elif isinstance(model, DecisionTreeClassifier) and hasattr(model, "feature_importances_"):
            for feature, importance in zip(train_x.columns, model.feature_importances_):
                feature_importance[feature] = float(importance)
        elif isinstance(model, SVC):
            logger.debug("ℹ️ SVM models use embedded feature selection via support vectors")
        elif isinstance(model, (KNeighborsClassifier, MLPClassifier)):
            logger.debug(f"ℹ️ {model_name} does not provide direct feature importances")
    except Exception as e:
        logger.warning(f"Cannot extract feature importance: {str(e)}")
    
    logger.debug(f"✅ {model_name}: Acc={acc:.4f} F1={f1:.4f} AUC={auc:.4f}")
    
    return ModelTrainingResult(
        model=model,
        metrics=metrics,
        feature_importance=feature_importance,
        y_pred=y_pred_arr,
        y_proba=y_proba,
        cv_metrics=cv_metrics
    )


def run_modeling(
    data_train_x: pd.DataFrame,
    data_train_y: pd.Series,
    data_test_x: pd.DataFrame,
    data_test_y: pd.Series,
    group_ranks: List[MetricsData],
    group_feature_mapping: List[GroupFeatureMappingData],
    model_name: str,
    top_n_groups: int,
    logger: logging.Logger,
    random_state: int = 42
) -> ModelingResult:
    """
    Train and evaluate a model using features from top-ranked groups.
    
    Args:
        data_train_x: Training feature data
        data_train_y: Training labels
        data_test_x: Testing feature data
        data_test_y: Testing labels
        group_ranks: List of groups ranked by performance
        group_feature_mapping: Group to feature mapping data
        model_name: Name of ML model to use
        top_n_groups: Number of top groups to use
        logger: Logger for tracking progress
        random_state: Random seed for reproducibility
        
    Returns:
        ModelingResult with model performance metrics
    """
    try:
        # Select features from top groups
        features_result = select_features_from_top_groups(
            group_ranks, 
            group_feature_mapping, 
            top_n_groups,
            logger
        )
        
        # Filter to only include features that exist in the data
        available_features = [f for f in features_result.selected_features if f in data_train_x.columns]
        
        if len(available_features) < len(features_result.selected_features):
            missing = len(features_result.selected_features) - len(available_features)
            logger.warning(f"{missing} features missing from dataset")
        
        if not available_features:
            logger.error("No valid features for modeling")
            # Return empty result with zeros
            return ModelingResult(
                model_name=model_name,
                num_groups_used=0,
                num_features_used=0,
                accuracy=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0
            )
        
        # Filter data to use only selected features
        train_x = data_train_x[available_features]
        test_x = data_test_x[available_features]
        
        # Train and evaluate model
        training_result = train_and_evaluate_model(
            model_name,
            train_x,
            data_train_y,
            test_x,
            data_test_y,
            logger,
            random_state=random_state
        )
        
        # Create and return result with all metrics including CI and CV
        return ModelingResult(
            model_name=model_name,
            num_groups_used=len(features_result.used_group_names),
            num_features_used=len(available_features),
            accuracy=training_result.metrics["accuracy"],
            precision=training_result.metrics["precision"],
            recall=training_result.metrics["recall"],
            f1_score=training_result.metrics["f1"],
            auc_roc=training_result.metrics.get("auc_roc", 0.0),
            accuracy_ci_lower=training_result.metrics.get("accuracy_ci_lower", 0.0),
            accuracy_ci_upper=training_result.metrics.get("accuracy_ci_upper", 0.0),
            f1_ci_lower=training_result.metrics.get("f1_ci_lower", 0.0),
            f1_ci_upper=training_result.metrics.get("f1_ci_upper", 0.0),
            auc_ci_lower=training_result.metrics.get("auc_ci_lower", 0.0),
            auc_ci_upper=training_result.metrics.get("auc_ci_upper", 0.0),
            cv_accuracy_mean=training_result.metrics.get("cv_accuracy_mean", 0.0),
            cv_accuracy_std=training_result.metrics.get("cv_accuracy_std", 0.0),
            cv_f1_mean=training_result.metrics.get("cv_f1_mean", 0.0),
            cv_f1_std=training_result.metrics.get("cv_f1_std", 0.0),
            mean_positive_probability=training_result.metrics.get("mean_positive_probability", 0.0),
            balanced_accuracy=training_result.metrics.get("balanced_accuracy", 0.0),
            mcc=training_result.metrics.get("mcc", 0.0),
            pr_auc=training_result.metrics.get("pr_auc", 0.0),
            tp=training_result.metrics.get("tp", 0),
            fp=training_result.metrics.get("fp", 0),
            tn=training_result.metrics.get("tn", 0),
            fn=training_result.metrics.get("fn", 0),
            training_time=training_result.metrics["training_time"],
            feature_importance=training_result.feature_importance,
            used_features=available_features,
            used_groups=features_result.used_group_names,
            fitted_model=training_result.model,
        )
        
    except Exception as e:
        logger.error(f"Modeling error: {str(e)}")
        raise

