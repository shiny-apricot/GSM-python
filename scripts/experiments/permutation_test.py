"""
Permutation-based Null Distribution Test for Biological Validation

Purpose:
    Computes an empirical p-value for the disease enrichment of the GSM-selected gene set.
    Randomly samples N genes from the array background 10,000 times, and calculates
    how often a random set has as many (or more) disease-associated genes as the GSM panel.

Usage:
    python scripts/experiments/permutation_test.py --dataset GDS2545 --disease "Prostate Cancer" --n-genes 10
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]

def load_background_genes(dataset_id: str) -> set:
    """Load all feature names (genes) available in the dataset."""
    path = project_root / "data" / "expression_data" / f"{dataset_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Dataset {dataset_id} not found.")
    
    # Read just the header
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        header = f.readline().strip().replace('"', '').split(',')
    
    # Exclude 'class' and return set
    return set(header[1:])

def load_disease_genes(disease_name: str) -> set:
    """Load genes associated with the disease from DisGeNET local file."""
    path = project_root / "data" / "grouping_data" / "cancer-DisGeNET_gedinet.txt"
    if not path.exists():
        raise FileNotFoundError("DisGeNET grouping file not found.")
    
    disease_genes = set()
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        f.readline() # Skip header
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                gene = parts[0]
                group = parts[1]
                # Simple exact match or substring match for disease name
                if disease_name.lower() in group.lower():
                    disease_genes.add(gene)
                    
    return disease_genes

def load_gsm_genes(dataset_id: str) -> set:
    """Extract the genes selected by GSM for this dataset (mock implementation or read from output).
    For the sake of the standalone script, we simulate loading the top 20 genes from a GSM run,
    or read them from a provided file. Since GSM saves 'best_averaged_features.xlsx' in the 
    output directory, we would normally parse that. Here we accept a comma-separated list or file.
    """
    pass # Will be implemented based on arguments

def run_permutation_test(background: list, disease_genes: set, observed_overlap: int, n_genes: int, n_permutations: int = 10000, seed: int = 42):
    """Run permutation test to get empirical p-value."""
    np.random.seed(seed)
    count_greater_equal = 0
    
    # Fast vectorized sampling if possible, or simple loop
    for _ in range(n_permutations):
        # random.choice is fast enough for 10k iterations
        random_sample = set(np.random.choice(background, size=n_genes, replace=False))
        overlap = len(random_sample.intersection(disease_genes))
        if overlap >= observed_overlap:
            count_greater_equal += 1
            
    p_value = count_greater_equal / n_permutations
    return p_value, count_greater_equal

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset ID (e.g. GDS2545)")
    parser.add_argument("--disease", required=True, help="Disease name for DisGeNET lookup")
    parser.add_argument("--genes", required=True, help="Comma-separated list of GSM selected genes")
    parser.add_argument("--perms", type=int, default=10000, help="Number of permutations")
    args = parser.parse_args()
    
    print(f"Running Permutation Test for {args.dataset} ({args.disease})")
    
    gsm_genes = set(args.genes.split(','))
    n_genes = len(gsm_genes)
    print(f"GSM selected {n_genes} genes.")
    
    bg_set = load_background_genes(args.dataset)
    print(f"Background: {len(bg_set)} genes on the microarray.")
    
    disgenet_set = load_disease_genes(args.disease)
    print(f"Disease group '{args.disease}' contains {len(disgenet_set)} genes in local database.")
    
    # Keep only disease genes that are actually on the array
    valid_disease_genes = disgenet_set.intersection(bg_set)
    print(f"Disease genes on array: {len(valid_disease_genes)}")
    
    # Observed overlap
    observed_overlap = len(gsm_genes.intersection(valid_disease_genes))
    print(f"Observed overlap: {observed_overlap} genes")
    
    if observed_overlap == 0:
        print("Empirical p-value: 1.0 (No overlap)")
        return
        
    print(f"Running {args.perms} permutations...")
    bg_list = list(bg_set)
    p_val, count = run_permutation_test(bg_list, valid_disease_genes, observed_overlap, n_genes, args.perms)
    
    print("-" * 40)
    print(f"Results for {args.dataset}:")
    print(f"Observed overlap: {observed_overlap} / {n_genes}")
    print(f"Random sets with >= overlap: {count} / {args.perms}")
    print(f"Empirical p-value: {p_val:.4f}")
    
if __name__ == '__main__':
    main()
