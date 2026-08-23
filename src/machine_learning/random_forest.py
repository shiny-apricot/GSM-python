"""Random Forest Classifier Implementation."""

from sklearn.ensemble import RandomForestClassifier

def train_random_forest(X_train, y_train, n_estimators=100, random_state=None):
    """Train the Random Forest model."""
    model = RandomForestClassifier(n_estimators=n_estimators, random_state=random_state)
    model.fit(X_train, y_train)
    return model

def predict_random_forest(model, X_test):
    """Make predictions using the trained Random Forest model."""
    return model.predict(X_test)
