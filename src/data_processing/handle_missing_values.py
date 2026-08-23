"""Handles missing values and imputations in datasets."""

import pandas as pd

def drop_missing_values(data: pd.DataFrame) -> pd.DataFrame:
    """
    Removes rows with any missing values from the DataFrame.

    Parameters:
    data (pd.DataFrame): The input DataFrame.

    Returns:
    pd.DataFrame: DataFrame with rows containing missing values removed.
    """
    return data.dropna()

def fill_missing_values(data: pd.DataFrame, strategy: str = 'mean') -> pd.DataFrame:
    """
    Fills missing values in the DataFrame using the specified strategy.

    Parameters:
    data (pd.DataFrame): The input DataFrame.
    strategy (str): The strategy to use for filling missing values ('mean', 'median', 'mode').

    Returns:
    pd.DataFrame: DataFrame with missing values filled.
    """
    if strategy == 'mean':
        return data.fillna(data.mean())
    elif strategy == 'median':
        return data.fillna(data.median())
    elif strategy == 'mode':
        return data.fillna(data.mode().iloc[0])
    else:
        raise ValueError("Invalid strategy. Choose 'mean', 'median', or 'mode'.")
