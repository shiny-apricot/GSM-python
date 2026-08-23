"""
Group Lasso Workflow Configuration 🧬

Purpose:
    This file defines the configuration for the Group Lasso workflow using a dataclass.
    It centralizes all the parameters, making it easy to manage and modify the workflow's behavior.
"""

from dataclasses import dataclass, field
from typing import Union, List

# --- Constants ---
# Define a constant for the random seed to ensure reproducibility across the script.
RANDOM_SEED = 44

# --- Configuration ---

@dataclass
class GroupLassoConfig:
    """Configuration for the Group Lasso workflow."""
    # --- File Paths ---
    # Path to the main dataset containing features and the target variable.
    main_data_path: str = "data/expression_data/GDS1962.csv"
    # Path to the file defining the groups for features.
    group_data_path: str = "data/grouping_data/cancer-DisGeNET_gedinet.txt"

    # --- Data Columns ---
    # Name of the column in the main data file to be used as the target variable.
    target_column: str = "class"
    # Name of the column in the group data file that defines the group names.
    group_name_column: str = "group_name"

    # --- Preprocessing ---
    # Strategy for handling missing values.
    # Options: "remove_rows", "fill_mean".
    missing_value_handling: str = "remove_rows"

    # --- Model Hyperparameters ---
    # Regularization parameter for group-level sparsity (lambda1).
    # Higher values lead to more groups being entirely removed.
    group_reg: float = 0.01
    # Regularization parameter for feature-level sparsity within groups (lambda2).
    # Higher values lead to more individual features being removed from the selected groups.
    l1_reg: float = 0.05
    
    # --- Hyperparameter Search ---
    # Whether to perform an internal grid search for regularization parameters
    enable_hyperparam_search: bool = True
    # Grid of group_reg values to search over
    group_reg_grid: List[float] = field(default_factory=lambda: [0.005, 0.01, 0.05])
    # Grid of l1_reg values to search over
    l1_reg_grid: List[float] = field(default_factory=lambda: [0.01, 0.05, 0.1])
    # The maximum number of iterations to perform.
    n_iter: int = 500
    # The convergence tolerance. The optimization will stop once the norm of the change in coefficients is less than this.
    tol: float = 1e-5
    # How to scale the group-wise regularization coefficients.
    # Options: "group_size", "none", "inverse_group_size".
    scale_reg: str = "group_size"
    # The subsampling rate for gradient and singular value computations. Can be a float (fraction), int (count), or 'sqrt'.
    subsampling_scheme: Union[None, float, int, str] = None
    # Whether to fit an intercept term in the model.
    fit_intercept: bool = True
    # If True, subsequent calls to fit will not re-initialize model parameters, speeding up hyperparameter search.
    warm_start: bool = False

    # --- General Settings ---
    # Seed for random number generators to ensure reproducibility.
    random_seed: int = RANDOM_SEED
    # Proportion of the dataset to be used for testing.
    test_size: float = 0.3
    # Number of iterations (each with a different random seed) for robust evaluation.
    n_iterations: int = 10
    # Base directory for all output files.
    output_dir: str = "output"

    # --- Overlap / Duplication Controls ---
    # Maximum number of groups a single gene can be duplicated into.
    # Genes in more than this many groups keep only their first max_groups_per_gene
    # assignments (alphabetical by group name). Set to 0 for no limit.
    max_groups_per_gene: int = 5
    # Minimum number of genes that a disease group must have in the expression data
    # for the group to be kept.  Small groups are noisy and slow down training.
    min_genes_per_group: int = 10

    # --- Biological Validation ---
    # Whether to run Enrichr / STRING-db / DisGeNET validation on top genes.
    run_biological_validation: bool = True
    # Number of top genes (by selection frequency) to validate.
    biological_validation_top_genes: int = 20
    # Optional DisGeNET API key.  If empty, DisGeNET queries are skipped.
    disgenet_api_key: str = ""
