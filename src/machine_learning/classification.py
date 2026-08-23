"""Standardized Classification Interface for ML Models."""

from typing import Tuple
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import GradientBoostingClassifier, AdaBoostClassifier, ExtraTreesClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.svm import LinearSVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from xgboost import XGBClassifier


def train_model(model_name: str, data_x: pd.DataFrame, data_y: pd.Series):
    """
    Train a specified machine learning model on the provided data.

    Args:
        model: The name of the machine learning model to use ('RandomForest' or 'GradientBoosting').
        data_x: Feature DataFrame.
        data_y: Target Series.

    Returns:
        Tuple containing:
        - Trained model
    """

    # Initialize the model
    if model_name == 'RandomForest':
        classifier = RandomForestClassifier()
    elif model_name == 'GradientBoosting':
        classifier = GradientBoostingClassifier()
    else:
        raise ValueError(f"Model '{model_name}' is not supported.")

    # Train the model
    classifier.fit(data_x, data_y)

    return classifier

def predict(model, X_test: pd.DataFrame):
    """
    Generate predictions using the trained model.

    Args:
        model: The trained machine learning model.
        X_test: Testing features DataFrame.

    Returns:
        Predictions for the test set.
    """
    return model.predict(X_test)

def get_classifier_object(model_name: str, n_estimators: int = 50, random_state: int = 42):
    """
    Get the classifier object based on the model name.

    Args:
        model_name: The name of the machine learning model to use ('RandomForest' or 'GradientBoosting').
        n_estimators: Number of trees/estimators (default: 50, reduced for faster scoring)
        random_state: Random seed for reproducibility. Must be set explicitly
            because joblib worker processes do not inherit the global np.random.seed().

    Returns:
        The classifier object.
    """
    if model_name == 'RandomForest':
        # Use fewer trees (50 vs 100 default) - sufficient for group ranking
        # n_jobs=1 to avoid nested parallelism (groups are already parallelized)
        return RandomForestClassifier(n_estimators=n_estimators, n_jobs=1, random_state=random_state)
    elif model_name == 'DecisionTree':
        # Very fast — ideal for group scoring/ranking
        return DecisionTreeClassifier(random_state=random_state)
    elif model_name == 'XGBoost':
        # Fast gradient boosting — good balance of speed and accuracy
        # n_jobs=1 to avoid nested parallelism (groups are already parallelized)
        return XGBClassifier(
            n_estimators=n_estimators,
            max_depth=4,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0,
            random_state=random_state,
            n_jobs=1
        )
    elif model_name == 'GradientBoosting':
        return GradientBoostingClassifier(n_estimators=n_estimators, random_state=random_state)
    elif model_name == 'ExtraTrees':
        # Extremely randomized trees — fast and robust
        return ExtraTreesClassifier(n_estimators=n_estimators, n_jobs=1, random_state=random_state)
    elif model_name == 'AdaBoost':
        # Adaptive boosting with decision stumps
        return AdaBoostClassifier(n_estimators=n_estimators, random_state=random_state)
    elif model_name == 'LogisticRegression':
        # Fast linear model — good baseline
        return LogisticRegression(max_iter=500, solver='lbfgs', random_state=random_state)
    elif model_name == 'KNN':
        # k-nearest neighbours (k=5) — no random_state (deterministic algorithm)
        return KNeighborsClassifier(n_neighbors=5, n_jobs=1)
    elif model_name == 'NaiveBayes':
        # Gaussian Naive Bayes — very fast, no random_state (deterministic algorithm)
        return GaussianNB()
    elif model_name == 'LinearSVM':
        # Linear SVM — fast on high-dimensional data
        return LinearSVC(max_iter=2000, dual=True, random_state=random_state)
    elif model_name == 'SGD':
        # Stochastic Gradient Descent classifier — very fast
        return SGDClassifier(loss='hinge', max_iter=1000, random_state=random_state)
    else:
        raise ValueError(f"Model '{model_name}' is not supported for scoring.")
