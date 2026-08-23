"""
🧬 Data Preprocessing Module for GSM Pipeline 🧬

Purpose:
    Handles core data preprocessing tasks for gene expression analysis in the GSM pipeline.

Primary Functions:
    🔍 preprocess_data: Main preprocessing pipeline coordinator
    🎯 convert_labels_to_binary: Binary label conversion (0/1)
    📊 normalize_data: Feature normalization
    ✅ validate_input_data: Input data validation
    📑 preprocess_grouping_data: Group data preprocessing

Input Data Requirements:
    - Must contain 'class' column for labels
    - Features should be numeric
    - No duplicate indices
    - Groups data must have GENE_COLUMN_NAME and GROUP_COLUMN_NAME

Example Usage:
    ```python
    from data_processing.data_preprocess import preprocess_data
    
    processed_train, processed_test = preprocess_data(
        input_data=input_df,
        label_column_name='class',
        label_of_negative_class='healthy',
        label_of_positive_class='disease',
        logger=logger,
        test_size=0.2
    )
    ```

Note: All functions use explicit parameter names for better code readability.
"""

from typing import Any
import pandas as pd

from src.data_processing.normalization import normalize_data
from src.data_processing.handle_missing_values import drop_missing_values

# Default constants for gene grouping (used when working with GSM workflow)
DEFAULT_GENE_COLUMN_NAME = "feature_id"
DEFAULT_GROUP_COLUMN_NAME = "group_name"
DEFAULT_MIN_CLASS_BALANCE_RATIO = 0.5
DEFAULT_SAMPLING_METHOD = 'undersampling'


def validate_input_data(data: pd.DataFrame, label_column_name: str) -> None:
    """
    Validates input data structure and content.
    
    Parameters:
        data (pd.DataFrame): Input data to validate
        label_column_name (str): Name of the label column
    
    Raises:
        ValueError: With detailed message if validation fails
            - Empty DataFrame
            - Missing required columns
            - Invalid data types
    """
    if data.empty:
        raise ValueError("Input data is empty")
    
    required_columns = [label_column_name]
    missing_cols = [col for col in required_columns if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

def preprocess_data(
    input_data: pd.DataFrame,
    label_column_name: str,
    label_of_negative_class: str,
    label_of_positive_class: str,
    logger: Any,
    test_size: float = 0.2,
    normalization_method: str = 'zscore',
    random_state: int = 42,
    apply_class_balancing: bool = False,
    min_class_balance_ratio: float = DEFAULT_MIN_CLASS_BALANCE_RATIO,
    sampling_method: str = DEFAULT_SAMPLING_METHOD,
    skip_normalization: bool = False,
) -> pd.DataFrame:
    """
    Executes the complete data preprocessing pipeline.
    
    Parameters:
        input_data (pd.DataFrame): Raw input data
        label_column_name (str): Name of the label column
        label_of_negative_class (str): Label representing negative class
        label_of_positive_class (str): Label representing positive class
        logger (Any): Logger instance for tracking progress
        test_size (float, optional): Proportion of test set. Defaults to 0.2
        normalization_method (str, optional): Method for normalization. Defaults to 'zscore'
        random_state (int, optional): Random seed. Defaults to 42
        apply_class_balancing (bool, optional): Whether to apply class balancing. Defaults to False
        min_class_balance_ratio (float, optional): Minimum acceptable ratio between classes. Defaults to 0.5
        sampling_method (str, optional): Method for balancing ('undersampling', 'oversampling'). Defaults to 'undersampling'
        skip_normalization (bool, optional): If True, skip normalization here (it will be
            done inside each train/test split to prevent data leakage). Defaults to False.
    
    Returns:
        pd.DataFrame: Processed data
    
    Raises:
        ValueError: If input validation fails
    """
    # Validate
    validate_input_data(input_data, label_column_name)
    
    # Coerce object feature columns to numeric (corrupted string cells become NaN)
    features = [c for c in input_data.columns if c != label_column_name]
    object_cols = [c for c in features if input_data[c].dtype == object]
    if object_cols:
        logger.info(f"Coercing {len(object_cols)} object columns to numeric to handle corrupted data")
        for c in object_cols:
            input_data[c] = pd.to_numeric(input_data[c], errors='coerce')
    
    # handle missing values
    input_data = drop_missing_values(input_data)
    
    # Convert labels
    input_data = convert_labels_to_binary(
        input_data, 
        label_column_name,
        label_of_negative_class,
        label_of_positive_class
    )
    
    # Normalize features (skip if normalization will be done inside each split)
    if skip_normalization:
        logger.info("Normalization deferred to within-split (no leakage mode)")
        normalized_data = input_data
    else:
        normalized_data = normalize_data(input_data,
                                         label_column_name=label_column_name,
                                         logger=logger,
                                         method=normalization_method)
    
    # Apply class balancing if enabled
    if apply_class_balancing:
        sampled_data = determine_class_balance(normalized_data, 
                                               logger=logger,
                                               label_column_name=label_column_name,
                                               min_class_balance_ratio=min_class_balance_ratio,
                                               sampling_method=sampling_method)
        logger.info(f"Sampled data size: {sampled_data.shape}")
    else:
        sampled_data = normalized_data
        logger.info("Class balancing disabled")
    
    logger.info(f"Data: {sampled_data.shape}")
    
    return sampled_data

def convert_labels_to_binary(
    data: pd.DataFrame,
    label_column_name: str,
    negative_label: str,
    positive_label: str
) -> pd.DataFrame:
    """
    Converts categorical labels to binary format.
    
    Parameters:
        data (pd.DataFrame): Input data with labels
        label_column_name (str): Name of label column
        negative_label (str): Label to convert to 0
        positive_label (str): Label to convert to 1
    
    Returns:
        pd.DataFrame: Data with binary labels
    
    Raises:
        ValueError: If label column is missing or invalid labels found
    """
    if label_column_name not in data.columns:
        raise ValueError(f"Data must contain '{label_column_name}' column")
        
    label_map = {negative_label: 0, positive_label: 1}
    invalid_labels = set(data[label_column_name]) - set(label_map.keys())
    if invalid_labels:
        raise ValueError(f"Invalid labels found: {invalid_labels}")
        
    data = data.copy()
    data[label_column_name] = data[label_column_name].map(label_map)
    return data

   
def determine_class_balance(data: pd.DataFrame,
                            logger: Any,
                            label_column_name: str = 'class',
                            min_class_balance_ratio: float = 0.5,
                            sampling_method: str = 'undersampling') -> pd.DataFrame:
    """
    Determines class balance in the dataset and applies sampling if necessary.

    Parameters:
        data (pd.DataFrame): Input data with labels
        logger (Any): Logger instance
        label_column_name (str): Name of the label column (default: 'class')
        min_class_balance_ratio (float): Minimum acceptable ratio between minority and majority classes
            (0.5 means classes can be at most 1:2)
        sampling_method (str): Method for balancing classes ('undersampling', 'oversampling')
    Returns:
        pd.DataFrame: Data with balanced classes
    """
    class_label = label_column_name

    # Count occurrences of each class
    class_counts = data[class_label].value_counts()
    logger.debug(f"Class counts: {class_counts.to_dict()}")
    
    # Check if classes are balanced
    if class_counts.min() / class_counts.max() < min_class_balance_ratio:
        # Apply sampling method to balance classes
        if sampling_method == 'undersampling':
            # Find the minority and majority classes
            minority_class = class_counts.idxmin()
            majority_class = class_counts.idxmax()
            
            # Get all samples from the minority class
            minority_samples = data[data[class_label] == minority_class]
            
            # Randomly sample from the majority class to match minority class count
            # Use random_state for reproducibility across runs
            majority_samples = data[data[class_label] == majority_class].sample(
                n=class_counts.min(),
                random_state=42,
            )
            
            # Combine minority and sampled majority classes
            data = pd.concat([minority_samples, majority_samples])
        elif sampling_method == 'oversampling':
            # Find the minority class (the class with the fewest samples)
            minority_class = class_counts.idxmin()
            minority_data = data[data[class_label] == minority_class]
            
            # Sample exactly the number of additional rows needed to match majority
            n_additional = class_counts.max() - class_counts.min()
            extra = minority_data.sample(n=n_additional, replace=True, random_state=42)
            data = pd.concat([data, extra])
        else:
            raise ValueError(f"Unsupported sampling method: {sampling_method}")
    else:
        logger.debug("Classes balanced, no sampling needed")
    logger.debug(f"Final class counts: {data[class_label].value_counts().to_dict()}")
    # Check if the class balance ratio is acceptable
    ratio = data[class_label].value_counts().min() / data[class_label].value_counts().max()
    if ratio < min_class_balance_ratio:
        logger.warning(f"Class balance ratio {ratio:.2f} below threshold {min_class_balance_ratio}")
    else:
        logger.debug(f"Class balance ratio: {ratio:.2f}")
    return data

def preprocess_grouping_data(
    grouping_data: pd.DataFrame, 
    logger: Any,
    gene_column_name: str = DEFAULT_GENE_COLUMN_NAME,
    group_column_name: str = DEFAULT_GROUP_COLUMN_NAME
) -> pd.DataFrame:
    """
    Preprocesses gene grouping data by validating its structure.
    
    Parameters:
        grouping_data (pd.DataFrame): Raw grouping data
        logger (Any): Logger instance
        gene_column_name (str): Name of the gene column
        group_column_name (str): Name of the group column
    
    Returns:
        pd.DataFrame: Processed grouping data
    
    Raises:
        ValueError: If data is empty or missing required columns
    """
    try:        
        # Validate the structure
        if grouping_data.empty:
            raise ValueError("Grouping data is empty")
        
        required_columns = [gene_column_name, group_column_name]
        missing_cols = [col for col in required_columns if col not in grouping_data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        logger.info(f"Grouping data: {grouping_data.shape[0]} rows, {grouping_data.shape[1]} cols")
        
        return grouping_data

    except Exception as e:
        logger.error(f"Error processing grouping data: {e}")
        raise