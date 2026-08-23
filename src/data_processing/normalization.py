"""
Normalization Module
-------------------
This module handles data normalization operations in the GSM pipeline.

Key Functions:
- normalize_data: Main function for normalizing input data
- fit_scaler: Fit and return a scaler for inference model bundles
- _minmax_normalize: Min-max normalization implementation
- _zscore_normalize: Z-score normalization implementation
- _robust_normalize: Robust scaling implementation

Usage Example:
    >>> import pandas as pd
    >>> data = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    >>> normalized = normalize_data(data, method='zscore')
"""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler


def _validate_input(data: pd.DataFrame) -> None:
    """Validate input data for normalization."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame")
    if data.empty:
        raise ValueError("Input DataFrame is empty")
    if data.isnull().any().any():
        raise ValueError("Input DataFrame contains missing values")


def _coerce_to_numeric(data: pd.DataFrame, logger) -> pd.DataFrame:
    """Coerce all columns to numeric, replacing non-convertible values with NaN then 0.

    Some datasets (e.g. GDS3837) contain stray non-numeric values in a few cells.
    Instead of rejecting the whole dataset, coerce and log warnings.
    """
    non_numeric_cols = data.select_dtypes(exclude=[np.number]).columns.tolist()
    if not non_numeric_cols:
        return data

    logger.warning(
        f"⚠️ Found {len(non_numeric_cols)} non-numeric column(s): {non_numeric_cols}. "
        "Coercing to numeric (non-convertible values will be set to 0)."
    )
    data = data.copy()
    for col in non_numeric_cols:
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    return data

def _minmax_normalize(data: pd.DataFrame) -> pd.DataFrame:
    """Apply min-max normalization."""
    scaler = MinMaxScaler()
    return pd.DataFrame(
        scaler.fit_transform(data),
        columns=data.columns,
        index=data.index
    )

def _zscore_normalize(data: pd.DataFrame) -> pd.DataFrame:
    """Apply z-score normalization."""
    scaler = StandardScaler()
    return pd.DataFrame(
        scaler.fit_transform(data),
        columns=data.columns,
        index=data.index
    )

def _robust_normalize(data: pd.DataFrame) -> pd.DataFrame:
    """Apply robust scaling using median and IQR."""
    scaler = RobustScaler()
    return pd.DataFrame(
        scaler.fit_transform(data),
        columns=data.columns,
        index=data.index
    )

def fit_scaler(
    data: pd.DataFrame,
    label_column_name: str,
    method: str = 'zscore',
) -> object:
    """Fit a normalization scaler on the data and return it.

    Used by the inference pipeline to save the scaler alongside
    trained models, ensuring identical preprocessing at inference time.

    Args:
        data: Input DataFrame (will use all columns except label)
        label_column_name: Column to exclude from fitting
        method: 'zscore', 'minmax', or 'robust'

    Returns:
        Fitted sklearn scaler object (StandardScaler, MinMaxScaler, or RobustScaler)
    """
    cols = data.columns.difference([label_column_name])
    numeric_data = data[cols]

    scaler_map = {
        'zscore': StandardScaler,
        'minmax': MinMaxScaler,
        'robust': RobustScaler,
    }
    if method not in scaler_map:
        raise ValueError(f"Unknown method: {method}. Choose from {list(scaler_map)}")

    scaler = scaler_map[method]()
    scaler.fit(numeric_data)
    return scaler


def normalize_data(
    data: pd.DataFrame,
    label_column_name: str,
    logger,
    method: str = 'zscore',
    subset_cols: Optional[list] = None,
) -> pd.DataFrame:
    """
    Normalize the input data using the specified method.

    Args:
        data (pd.DataFrame): Input data to normalize
        label_column_name (str): Name of the label column to exclude from normalization
        method (str): Normalization method ('minmax', 'zscore', or 'robust')
        subset_cols (list, optional): Specific columns to normalize. If None, normalize all columns except the label

    Returns:
        pd.DataFrame: Normalized data
    """
    logger.debug(f"Normalizing with {method} method")
    
    # Coerce any non-numeric columns before validation
    data = _coerce_to_numeric(data, logger)
    
    # Input validation
    _validate_input(data)
    
    # Create a copy to avoid modifying the original data
    data_to_normalize = data.copy()
    
    # Select columns to normalize
    if subset_cols is None:
        cols_to_normalize = data.columns.difference([label_column_name])  # Exclude label column
    else:
        cols_to_normalize = [col for col in subset_cols if col != label_column_name]  # Exclude label column if in subset
    
    # Validate selected columns
    if not all(col in data.columns for col in cols_to_normalize):
        raise ValueError("One or more specified columns not found in DataFrame")
    
    try:
        # Apply normalization based on method
        normalization_methods = {
            'minmax': _minmax_normalize,
            'zscore': _zscore_normalize,
            'robust': _robust_normalize
        }
        
        if method not in normalization_methods:
            raise ValueError(
                f"Invalid normalization method. Choose from: {', '.join(normalization_methods.keys())}"
            )
        
        # Normalize selected columns
        data_to_normalize[cols_to_normalize] = normalization_methods[method](
            data_to_normalize[cols_to_normalize]
        )
        
        logger.info(f"Normalized ({method})")
        return data_to_normalize
        
    except Exception as e:
        logger.error(f"Error during normalization: {str(e)}")
        raise


def normalize_within_split(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    label_column_name: str,
    logger,
    method: str = 'zscore',
) -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Fit normalization on TRAINING data only, transform both splits.

    This prevents data leakage by ensuring the test set never influences
    scaler parameters (mean, std, min, max, etc.).

    Args:
        train_data: Training split (samples × features + label column)
        test_data:  Test split (same columns as train_data)
        label_column_name: Column to exclude from normalization
        logger:     Logger instance
        method:     'zscore', 'minmax', or 'robust'

    Returns:
        (normalized_train, normalized_test, fitted_scaler)
    """
    scaler_map = {
        'zscore': StandardScaler,
        'minmax': MinMaxScaler,
        'robust': RobustScaler,
    }
    if method not in scaler_map:
        raise ValueError(f"Unknown normalization method: {method}. Choose from {list(scaler_map)}")

    feature_cols = train_data.columns.difference([label_column_name])

    # Coerce non-numeric columns (some GEO datasets have stray values)
    train_features = _coerce_to_numeric(train_data[feature_cols].copy(), logger)
    test_features = _coerce_to_numeric(test_data[feature_cols].copy(), logger)

    # Fit on train only
    scaler = scaler_map[method]()
    scaler.fit(train_features)

    # Transform both
    train_normalized = pd.DataFrame(
        scaler.transform(train_features),
        columns=feature_cols,
        index=train_data.index,
    )
    test_normalized = pd.DataFrame(
        scaler.transform(test_features),
        columns=feature_cols,
        index=test_data.index,
    )

    # Re-attach the label column
    train_out = train_normalized.copy()
    train_out[label_column_name] = train_data[label_column_name].values
    test_out = test_normalized.copy()
    test_out[label_column_name] = test_data[label_column_name].values

    logger.debug(f"Normalized within split ({method}): train={train_out.shape}, test={test_out.shape}")
    return train_out, test_out, scaler