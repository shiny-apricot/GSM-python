"""Data Visualization and Plotting Utilities."""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path
import logging

def plot_histogram(data, bins=30, title='Histogram', xlabel='Value', ylabel='Frequency'):
    """Plots a histogram of the given data."""
    plt.figure(figsize=(10, 6))
    plt.hist(data, bins=bins, color='blue', alpha=0.7)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(axis='y', alpha=0.75)
    plt.show()

def plot_scatter(x, y, title='Scatter Plot', xlabel='X-axis', ylabel='Y-axis'):
    """Creates a scatter plot for two variables."""
    plt.figure(figsize=(10, 6))
    plt.scatter(x, y, color='green', alpha=0.5)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid()
    plt.show()

def plot_box(data, title='Box Plot', xlabel='Categories', ylabel='Values'):
    """Generates a box plot for visualizing data distributions."""
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=data)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(axis='y', alpha=0.75)
    plt.show()

from typing import Optional

##### FIGURE STYLE CONFIGURATION #####
def _setup_publication_style():
    """Configure matplotlib for publication-quality figures."""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'font.size': 11,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.edgecolor': '#333333',
        'axes.linewidth': 1.2,
        'grid.alpha': 0.4,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })


def visualize_f1_scores(results_df: pd.DataFrame, output_dir: Path, logger: Optional[logging.Logger] = None) -> None:
    """
    Visualize F1 scores from GSM pipeline iterations.
    
    Generates two plots saved to the figures/ subfolder:
    1. F1 Scores across Iterations (scatter + mean line)
    2. Average F1 Scores by Number of Groups (bar plot with error bars)
    
    Args:
        results_df: DataFrame containing 'Iteration', 'NumGroups', and 'F1Score' columns.
        output_dir: Base output directory (figures saved to output_dir/figures/).
        logger: Optional logger.
    """
    if logger:
        logger.debug("Generating F1 plots")
    
    # Save figures to figures/ subfolder
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    
    # Set publication-quality style
    _setup_publication_style()
    
    # Color palette
    colors = sns.color_palette("viridis", n_colors=results_df["NumGroups"].nunique())
    
    # Plot 1: F1 Scores across Iterations
    fig, ax = plt.subplots(figsize=(12, 6))
    
    scatter = sns.scatterplot(
        data=results_df,
        x="Iteration",
        y="F1Score",
        hue="NumGroups",
        palette="viridis",
        s=100,
        alpha=0.8,
        edgecolor='white',
        linewidth=0.5,
        ax=ax
    )
    
    mean_by_iteration = results_df.groupby("Iteration", as_index=False)["F1Score"].mean()
    sns.lineplot(
        data=mean_by_iteration,
        x="Iteration",
        y="F1Score",
        color="#E74C3C",
        marker="o",
        markersize=8,
        linewidth=2.5,
        label="Mean F1",
        ax=ax
    )
    
    ax.set_title("F1 Scores Across Iterations")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("F1 Score")
    ax.set_ylim(0, 1.05)
    ax.legend(title="Groups", bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)
    
    plt.tight_layout()
    fig.savefig(figures_dir / "f1_scores_across_iterations.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # Plot 2: Average F1 Scores by Number of Groups
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars = sns.barplot(
        data=results_df, 
        x="NumGroups", 
        y="F1Score", 
        errorbar="sd", 
        palette="viridis",
        capsize=0.15,
        errwidth=1.5,
        edgecolor='black',
        linewidth=1,
        ax=ax
    )
    
    # Add value labels on bars
    for container in ax.containers:
        if hasattr(container, 'datavalues'):
            ax.bar_label(container, fmt='%.2f', padding=3, fontsize=9)
    
    ax.set_title("Average F1 Score by Number of Groups")
    ax.set_xlabel("Number of Groups Used")
    ax.set_ylabel("F1 Score (Mean ± SD)")
    ax.set_ylim(0, 1.1)
    
    plt.tight_layout()
    fig.savefig(figures_dir / "average_f1_scores_by_groups.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    if logger:
        logger.debug(f"F1 plots saved")
