"""XGBoost Classifier Implementation."""

import xgboost as xgb
from sklearn.metrics import accuracy_score

def train_xgboost_classifier(X_train, y_train, params=None):
    """
    Trains an XGBoost classifier on the provided training data.

    Parameters:
    - X_train: Features for training (pandas DataFrame or numpy array).
    - y_train: Target labels for training (pandas Series or numpy array).
    - params: Dictionary of parameters for XGBoost (optional).

    Returns:
    - model: Trained XGBoost model.
    """
    if params is None:
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'learning_rate': 0.1,
            'max_depth': 6,
            'n_estimators': 100
        }
    
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train)
    
    return model
