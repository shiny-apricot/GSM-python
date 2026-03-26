"""
📊 Figure Generation Module for GSM Pipeline

Purpose:
    Generate publication-quality figures for manuscript preparation.
    Creates ROC curves, confusion matrices, feature importance plots,
    performance comparison charts, and aggregated ranking visualizations.

Key Functions:
    - generate_all_figures: Main entry point to create all figures
    - plot_roc_curves: ROC curves with AUC values
    - plot_confusion_matrix: Heatmap of classification results
    - plot_feature_importance: Bar chart of top features
    - plot_performance_boxplot: F1 stability across iterations
    - plot_aggregated_group_ranking: Best averaged groups visualization
    - plot_aggregated_feature_ranking: Best averaged features visualization
    - plot_iteration_performance_summary: Per-iteration performance overview
    - plot_group_count_optimization: Optimal group count analysis

Example Usage:
    >>> from src.utils.generate_figures import generate_all_figures
    >>> generate_all_figures(output_dir, results_json_path, logger)

File Map:
        Entry point:
                - generate_all_figures(): calls all plotters for a run

        Performance plots:
                - plot_performance_boxplot(), plot_auc_roc_comparison(),
                    plot_confidence_interval_forest(), plot_iteration_performance_summary()

        Ranking plots:
                - plot_best_averaged_groups(), plot_best_averaged_features()

        Group analysis:
                - plot_group_count_optimization(), plot_group_performance_heatmap(),
                    plot_group_usage_frequency()

        Feature analysis:
                - plot_feature_importance_aggregated(), plot_feature_occurrence_frequency()
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from sklearn.metrics import confusion_matrix, roc_curve, auc


##### MATPLOTLIB CONFIGURATION #####
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


@dataclass
class FigureConfig:
    """Configuration for figure generation."""
    output_dir: Path
    format: str = 'png'
    dpi: int = 300
    figsize_single: tuple = (8, 6)
    figsize_wide: tuple = (12, 6)
    color_palette: str = 'viridis'


##### MAIN ENTRY POINT #####
def generate_all_figures(
    output_dir: Path,
    results_json_path: Path,
    logger: logging.Logger
) -> Dict[str, Path]:
    """Generate all publication figures from modeling results.
    
    Args:
        output_dir: Directory to save figures
        results_json_path: Path to modeling_results_all_iterations.json
        logger: Logger instance
    
    Returns:
        Dictionary mapping figure names to their file paths
    """
    logger.info("Generating figures...")
    
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    
    config = FigureConfig(output_dir=figures_dir)
    
    # Load results
    with open(results_json_path, 'r') as f:
        all_results = json.load(f)
    
    generated_figures = {}
    
    # Generate each figure type
    try:
        path = plot_feature_importance_aggregated(all_results, config, logger)
        generated_figures['feature_importance'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate feature importance plot: {e}")
    
    try:
        path = plot_performance_boxplot(all_results, config, logger)
        generated_figures['performance_boxplot'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate performance boxplot: {e}")
    
    try:
        path = plot_auc_roc_comparison(all_results, config, logger)
        generated_figures['auc_roc_comparison'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate AUC-ROC comparison: {e}")
    
    try:
        path = plot_confidence_interval_forest(all_results, config, logger)
        generated_figures['ci_forest_plot'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate CI forest plot: {e}")
    
    try:
        path = plot_cv_stability(all_results, config, logger)
        generated_figures['cv_stability'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate CV stability plot: {e}")
    
    try:
        path = plot_group_performance_heatmap(all_results, config, logger)
        generated_figures['group_heatmap'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate group heatmap: {e}")
    
    # New figures added
    try:
        path = plot_best_averaged_groups(all_results, config, logger)
        generated_figures['best_averaged_groups'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate best averaged groups plot: {e}")
    
    try:
        path = plot_best_averaged_features(all_results, config, logger)
        generated_figures['best_averaged_features'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate best averaged features plot: {e}")
    
    try:
        path = plot_iteration_performance_summary(all_results, config, logger)
        generated_figures['iteration_summary'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate iteration summary plot: {e}")
    
    try:
        path = plot_group_count_optimization(all_results, config, logger)
        generated_figures['group_count_optimization'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate group count optimization plot: {e}")
    
    try:
        path = plot_feature_occurrence_frequency(all_results, config, logger)
        generated_figures['feature_frequency'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate feature frequency plot: {e}")
    
    try:
        path = plot_group_usage_frequency(all_results, config, logger)
        generated_figures['group_frequency'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate group frequency plot: {e}")
    
    try:
        path = plot_metrics_correlation(all_results, config, logger)
        generated_figures['metrics_correlation'] = path
    except Exception as e:
        logger.warning(f"⚠️ Could not generate metrics correlation plot: {e}")
    
    logger.info(f"Generated {len(generated_figures)} figures")
    return generated_figures


##### FEATURE IMPORTANCE PLOT #####
def plot_feature_importance_aggregated(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger,
    top_n: int = 15
) -> Path:
    """Create aggregated feature importance bar chart across all iterations.
    
    Combines feature importances from all iterations and shows mean ± std.
    """
    logger.debug("Plotting feature importance...")
    
    # Collect feature importances across all iterations
    feature_scores = {}
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            importance = result.get('feature_importance', {})
            for gene, score in importance.items():
                if gene not in feature_scores:
                    feature_scores[gene] = []
                feature_scores[gene].append(score)
    
    # Calculate mean and std for each feature
    feature_stats = []
    for gene, scores in feature_scores.items():
        feature_stats.append({
            'Gene': gene,
            'Mean Importance': np.mean(scores),
            'Std': np.std(scores),
            'Count': len(scores)
        })
    
    df = pd.DataFrame(feature_stats)
    df = df.sort_values('Mean Importance', ascending=False).head(top_n)
    
    # Create figure
    fig, ax = plt.subplots(figsize=config.figsize_single)
    
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df)))
    
    bars = ax.barh(
        df['Gene'], 
        df['Mean Importance'], 
        xerr=df['Std'],
        color=colors,
        edgecolor='black',
        linewidth=0.5,
        capsize=3
    )
    
    ax.set_xlabel('Mean Feature Importance Score')
    ax.set_ylabel('Gene Symbol')
    ax.set_title(f'Top {top_n} Features by Aggregated Importance\n(Mean ± SD across all iterations)')
    ax.invert_yaxis()
    
    # Add value labels
    for bar, val in zip(bars, df['Mean Importance']):
        ax.text(val + 0.005, bar.get_y() + bar.get_height()/2, 
                f'{val:.3f}', va='center', fontsize=8)
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'feature_importance_aggregated.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### PERFORMANCE BOXPLOT #####
def plot_performance_boxplot(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create boxplot showing metric distributions across iterations."""
    logger.debug("Plotting performance boxplot...")
    
    # Collect metrics for best configuration (2 groups based on earlier analysis)
    metrics_data = {
        'Accuracy': [],
        'Precision': [],
        'Recall': [],
        'F1 Score': [],
        'AUC-ROC': []
    }
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            # Focus on 2-group configuration for clarity
            if result.get('num_groups_used') == 2:
                metrics_data['Accuracy'].append(result.get('accuracy', 0))
                metrics_data['Precision'].append(result.get('precision', 0))
                metrics_data['Recall'].append(result.get('recall', 0))
                metrics_data['F1 Score'].append(result.get('f1_score', 0))
                metrics_data['AUC-ROC'].append(result.get('auc_roc', 0))
    
    df = pd.DataFrame(metrics_data)
    
    fig, ax = plt.subplots(figsize=config.figsize_single)
    
    # Create boxplot with custom styling
    bp = ax.boxplot(
        [df[col].dropna() for col in df.columns],
        labels=df.columns,
        patch_artist=True,
        showmeans=True,
        meanprops={'marker': 'D', 'markerfacecolor': 'red', 'markersize': 6}
    )
    
    # Color the boxes
    colors = plt.cm.Set2(np.linspace(0, 1, len(df.columns)))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_ylabel('Score')
    ax.set_title('Classification Performance Distribution\n(Best Configuration: 2 Groups, 8 Features)')
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.8, color='gray', linestyle='--', alpha=0.5, label='0.8 threshold')
    
    # Add mean values as text
    for i, col in enumerate(df.columns):
        mean_val = df[col].mean()
        ax.text(i + 1, mean_val + 0.03, f'{mean_val:.3f}', 
                ha='center', fontsize=8, fontweight='bold')
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'performance_boxplot.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### AUC-ROC COMPARISON #####
def plot_auc_roc_comparison(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create bar chart comparing AUC-ROC across different group counts."""
    logger.debug("Plotting AUC-ROC comparison...")
    
    # Collect AUC by group count
    auc_by_groups = {}
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            n_groups = result.get('num_groups_used', 0)
            auc_val = result.get('auc_roc', 0)
            
            if n_groups not in auc_by_groups:
                auc_by_groups[n_groups] = []
            auc_by_groups[n_groups].append(auc_val)
    
    # Calculate statistics
    group_counts = sorted(auc_by_groups.keys())
    means = [np.mean(auc_by_groups[g]) for g in group_counts]
    stds = [np.std(auc_by_groups[g]) for g in group_counts]
    ci_lowers = [np.percentile(auc_by_groups[g], 2.5) for g in group_counts]
    ci_uppers = [np.percentile(auc_by_groups[g], 97.5) for g in group_counts]
    
    fig, ax = plt.subplots(figsize=config.figsize_single)
    
    x = np.arange(len(group_counts))
    colors = plt.cm.coolwarm(np.linspace(0.2, 0.8, len(group_counts)))
    
    bars = ax.bar(x, means, yerr=stds, capsize=5, color=colors, 
                  edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Number of Groups Used')
    ax.set_ylabel('AUC-ROC Score')
    ax.set_title('Classification Performance by Number of Groups\n(Mean ± SD)')
    ax.set_xticks(x)
    ax.set_xticklabels(group_counts)
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.8, color='gray', linestyle='--', alpha=0.5, label='AUC = 0.8')
    
    # Add value labels
    for bar, mean_val, ci_l, ci_u in zip(bars, means, ci_lowers, ci_uppers):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{mean_val:.3f}', ha='center', fontsize=9)
    
    # Add legend for CI
    ax.legend(loc='lower right')
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'auc_roc_by_groups.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### CONFIDENCE INTERVAL FOREST PLOT #####
def plot_confidence_interval_forest(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create forest plot showing F1 scores with 95% CI for each iteration."""
    logger.debug("Plotting CI forest...")
    
    # Collect F1 scores and CIs for 2-group configuration
    iterations = []
    f1_scores = []
    ci_lowers = []
    ci_uppers = []
    
    for i, iteration_data in enumerate(all_results):
        for result in iteration_data.get('results', []):
            if result.get('num_groups_used') == 2:
                iterations.append(f"Iter {i+1}")
                f1_scores.append(result.get('f1_score', 0))
                ci_lowers.append(result.get('f1_ci_lower', 0))
                ci_uppers.append(result.get('f1_ci_upper', 1))
    
    fig, ax = plt.subplots(figsize=(10, max(6, len(iterations) * 0.4)))
    
    y_pos = np.arange(len(iterations))
    
    # Plot points with error bars
    ax.errorbar(
        f1_scores, y_pos,
        xerr=[np.array(f1_scores) - np.array(ci_lowers), 
              np.array(ci_uppers) - np.array(f1_scores)],
        fmt='o', color='steelblue', markersize=8,
        capsize=4, capthick=1.5, elinewidth=1.5
    )
    
    # Add vertical line for pooled mean
    pooled_mean = np.mean(f1_scores)
    ax.axvline(pooled_mean, color='red', linestyle='--', linewidth=2, 
               label=f'Pooled Mean: {pooled_mean:.3f}')
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(iterations)
    ax.set_xlabel('F1 Score')
    ax.set_title('F1 Score with 95% Confidence Intervals\n(Best Configuration: 2 Groups)')
    ax.set_xlim(0, 1.1)
    ax.legend(loc='lower right')
    ax.invert_yaxis()
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'f1_confidence_intervals.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### CROSS-VALIDATION STABILITY #####
def plot_cv_stability(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create plot showing CV mean vs test performance across iterations."""
    logger.debug("Plotting CV stability...")
    
    cv_means = []
    test_scores = []
    iterations = []
    
    for i, iteration_data in enumerate(all_results):
        for result in iteration_data.get('results', []):
            if result.get('num_groups_used') == 2:
                cv_means.append(result.get('cv_f1_mean', 0))
                test_scores.append(result.get('f1_score', 0))
                iterations.append(i + 1)
    
    n_iterations = len(iterations)
    
    # For many iterations, use line plot instead of bar chart
    if n_iterations > 30:
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(iterations, cv_means, 'o-', color='steelblue', 
                linewidth=1.5, markersize=4, alpha=0.8, label='CV F1 Mean')
        ax.plot(iterations, test_scores, 's-', color='coral', 
                linewidth=1.5, markersize=4, alpha=0.8, label='Test F1')
        
        ax.set_xlabel('Iteration')
        ax.set_ylabel('F1 Score')
        ax.set_title('Cross-Validation vs Test Performance Stability')
        
        # Set x-ticks to show every Nth iteration
        tick_step = max(1, n_iterations // 20)
        ax.set_xticks(iterations[::tick_step])
        ax.set_xticklabels(iterations[::tick_step], rotation=45)
        
        ax.legend(loc='lower right')
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3)
    else:
        fig, ax = plt.subplots(figsize=config.figsize_single)
        
        x = np.arange(len(iterations))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, cv_means, width, label='CV F1 Mean', color='steelblue', alpha=0.8)
        bars2 = ax.bar(x + width/2, test_scores, width, label='Test F1', color='coral', alpha=0.8)
        
        ax.set_xlabel('Iteration')
        ax.set_ylabel('F1 Score')
        ax.set_title('Cross-Validation vs Test Performance Stability')
        ax.set_xticks(x)
        ax.set_xticklabels(iterations)
        ax.legend()
        ax.set_ylim(0, 1.1)
    
    # Add correlation coefficient
    if len(cv_means) > 1:
        correlation = np.corrcoef(cv_means, test_scores)[0, 1]
        ax.text(0.02, 0.98, f'Correlation: {correlation:.3f}', 
                transform=ax.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'cv_test_stability.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### GROUP PERFORMANCE HEATMAP #####
def plot_group_performance_heatmap(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create heatmap showing metrics across iterations and group counts."""
    logger.debug("Plotting group heatmap...")
    
    # Build matrix: rows = iterations, columns = group counts
    data = {}
    
    for i, iteration_data in enumerate(all_results):
        for result in iteration_data.get('results', []):
            n_groups = result.get('num_groups_used', 0)
            f1 = result.get('f1_score', 0)
            
            if n_groups not in data:
                data[n_groups] = {}
            data[n_groups][i + 1] = f1
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    df = df.sort_index(axis=1)  # Sort by group count
    df.index.name = 'Iteration'
    df.columns.name = 'Groups'
    
    # Determine figure size and annotation based on number of iterations
    n_iterations = len(df)
    n_groups = len(df.columns)
    
    # For many iterations, use a larger figure and smaller/no annotations
    if n_iterations > 30:
        # Large heatmap without annotations for clarity
        fig_height = max(10, n_iterations * 0.15)
        fig, ax = plt.subplots(figsize=(12, fig_height))
        
        sns.heatmap(
            df, 
            annot=False,  # No annotations for many iterations
            cmap='RdYlGn',
            center=0.7,
            linewidths=0.1,
            ax=ax,
            cbar_kws={'label': 'F1 Score', 'shrink': 0.5}
        )
        
        # Show only every Nth y-tick label for readability
        tick_step = max(1, n_iterations // 20)
        ax.set_yticks(ax.get_yticks()[::tick_step])
    else:
        fig, ax = plt.subplots(figsize=config.figsize_wide)
        
        sns.heatmap(
            df, 
            annot=True, 
            fmt='.2f',
            cmap='RdYlGn',
            center=0.7,
            linewidths=0.5,
            ax=ax,
            annot_kws={'fontsize': 8},
            cbar_kws={'label': 'F1 Score'}
        )
    
    ax.set_title('F1 Score Heatmap: Iterations × Group Counts')
    ax.set_xlabel('Number of Groups')
    ax.set_ylabel('Iteration')
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'performance_heatmap.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### BEST AVERAGED GROUPS PLOT #####
def plot_best_averaged_groups(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger,
    top_n: int = 15
) -> Path:
    """Create horizontal bar chart of best averaged groups."""
    logger.debug("Plotting averaged groups...")
    
    # Collect group usage and F1 scores
    group_stats = {}
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            used_groups = result.get('used_groups', [])
            f1_score = result.get('f1_score', 0.0)
            
            for group_name in used_groups:
                if group_name not in group_stats:
                    group_stats[group_name] = {'f1_scores': [], 'count': 0}
                group_stats[group_name]['f1_scores'].append(f1_score)
                group_stats[group_name]['count'] += 1
    
    # Calculate statistics
    groups_data = []
    for name, stats in group_stats.items():
        groups_data.append({
            'Group': name[:40] + '...' if len(name) > 40 else name,
            'Avg F1': np.mean(stats['f1_scores']),
            'Std': np.std(stats['f1_scores']),
            'Count': stats['count']
        })
    
    df = pd.DataFrame(groups_data)
    df = df.sort_values('Avg F1', ascending=False).head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(df)))
    
    bars = ax.barh(
        df['Group'], 
        df['Avg F1'], 
        xerr=df['Std'],
        color=colors,
        edgecolor='black',
        linewidth=0.5,
        capsize=3
    )
    
    ax.set_xlabel('Average F1 Score (when group is used)')
    ax.set_ylabel('Group Name')
    ax.set_title(f'Top {top_n} Groups by Average F1 Score\n(Mean ± SD across configurations)')
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    
    # Add count labels showing how many times the group was used
    for bar, count in zip(bars, df['Count']):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2, 
                f'Used {count}x', va='center', fontsize=8, color='gray')
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'best_averaged_groups.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### BEST AVERAGED FEATURES PLOT #####
def plot_best_averaged_features(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger,
    top_n: int = 25
) -> Path:
    """Create lollipop chart of best averaged features by importance."""
    logger.debug("Plotting averaged features...")
    
    # Collect feature importance scores
    feature_stats = {}
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            importance = result.get('feature_importance', {})
            for name, score in importance.items():
                if name not in feature_stats:
                    feature_stats[name] = []
                feature_stats[name].append(score)
    
    # Calculate statistics
    features_data = []
    for name, scores in feature_stats.items():
        features_data.append({
            'Feature': name,
            'Avg Importance': np.mean(scores),
            'Std': np.std(scores),
            'Count': len(scores)
        })
    
    df = pd.DataFrame(features_data)
    df = df.sort_values('Avg Importance', ascending=False).head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Lollipop chart
    y_pos = np.arange(len(df))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df)))
    
    ax.hlines(y=y_pos, xmin=0, xmax=df['Avg Importance'], color='gray', alpha=0.7, linewidth=1)
    ax.scatter(df['Avg Importance'], y_pos, color=colors, s=100, zorder=3)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df['Feature'])
    ax.set_xlabel('Average Importance Score')
    ax.set_ylabel('Feature Name')
    ax.set_title(f'Top {top_n} Features by Average Importance\n(Across all iterations)')
    ax.invert_yaxis()
    
    # Add error bars as horizontal lines
    for i, (idx, row) in enumerate(df.iterrows()):
        ax.plot([row['Avg Importance'] - row['Std'], row['Avg Importance'] + row['Std']], 
                [i, i], color='red', alpha=0.5, linewidth=2)
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'best_averaged_features.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### ITERATION PERFORMANCE SUMMARY #####
def plot_iteration_performance_summary(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create line plot showing best performance per iteration."""
    logger.debug("Plotting iteration summary...")
    
    # Collect best F1 per iteration
    best_per_iter = []
    for i, iteration_data in enumerate(all_results):
        results = iteration_data.get('results', [])
        if results:
            best_f1 = max(r.get('f1_score', 0) for r in results)
            best_auc = max(r.get('auc_roc', 0) for r in results)
            avg_f1 = np.mean([r.get('f1_score', 0) for r in results])
            best_per_iter.append({
                'Iteration': i + 1,
                'Best F1': best_f1,
                'Best AUC': best_auc,
                'Avg F1': avg_f1
            })
    
    df = pd.DataFrame(best_per_iter)
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    # Top plot: F1 scores
    ax1 = axes[0]
    ax1.plot(df['Iteration'], df['Best F1'], 'o-', color='steelblue', 
             linewidth=2, markersize=6, label='Best F1')
    ax1.plot(df['Iteration'], df['Avg F1'], 's--', color='coral', 
             linewidth=1.5, markersize=5, alpha=0.7, label='Avg F1')
    ax1.axhline(df['Best F1'].mean(), color='steelblue', linestyle=':', alpha=0.5)
    ax1.fill_between(df['Iteration'], df['Best F1'].min(), df['Best F1'], alpha=0.2)
    ax1.set_ylabel('F1 Score')
    ax1.set_title('Performance Across Iterations')
    ax1.legend(loc='lower right')
    ax1.set_ylim(0, 1.0)
    
    # Bottom plot: AUC-ROC
    ax2 = axes[1]
    ax2.plot(df['Iteration'], df['Best AUC'], 'o-', color='green', 
             linewidth=2, markersize=6, label='Best AUC-ROC')
    ax2.axhline(df['Best AUC'].mean(), color='green', linestyle=':', alpha=0.5)
    ax2.fill_between(df['Iteration'], df['Best AUC'].min(), df['Best AUC'], 
                     alpha=0.2, color='green')
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('AUC-ROC Score')
    ax2.legend(loc='lower right')
    ax2.set_ylim(0, 1.0)
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'iteration_performance_summary.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### GROUP COUNT OPTIMIZATION PLOT #####
def plot_group_count_optimization(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create plot showing optimal number of groups analysis."""
    logger.debug("Plotting group optimization...")
    
    # Collect metrics by group count
    metrics_by_groups = {}
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            n_groups = result.get('num_groups_used', 0)
            if n_groups not in metrics_by_groups:
                metrics_by_groups[n_groups] = {'f1': [], 'auc': [], 'features': []}
            metrics_by_groups[n_groups]['f1'].append(result.get('f1_score', 0))
            metrics_by_groups[n_groups]['auc'].append(result.get('auc_roc', 0))
            metrics_by_groups[n_groups]['features'].append(result.get('num_features_used', 0))
    
    group_counts = sorted(metrics_by_groups.keys())
    f1_means = [np.mean(metrics_by_groups[g]['f1']) for g in group_counts]
    f1_stds = [np.std(metrics_by_groups[g]['f1']) for g in group_counts]
    auc_means = [np.mean(metrics_by_groups[g]['auc']) for g in group_counts]
    feature_means = [np.mean(metrics_by_groups[g]['features']) for g in group_counts]
    
    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    
    # Top: F1 and AUC by group count
    ax1 = axes[0]
    x = np.arange(len(group_counts))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, f1_means, width, yerr=f1_stds, 
                    label='F1 Score', color='steelblue', capsize=3)
    bars2 = ax1.bar(x + width/2, auc_means, width, 
                    label='AUC-ROC', color='coral', capsize=3)
    
    ax1.set_ylabel('Score')
    ax1.set_title('Performance Metrics by Number of Groups')
    ax1.set_xticks(x)
    ax1.set_xticklabels(group_counts)
    ax1.legend()
    ax1.set_ylim(0, 1.0)
    
    # Highlight optimal
    best_idx = np.argmax(f1_means)
    ax1.axvline(best_idx, color='green', linestyle='--', alpha=0.5, label='Optimal')
    
    # Bottom: Total feature count by group count
    ax2 = axes[1]
    feature_totals = [sum(metrics_by_groups[g]['features']) for g in group_counts]
    ax2.bar(x, feature_totals, color='purple', alpha=0.7)
    ax2.set_xlabel('Number of Groups')
    ax2.set_ylabel('Total Feature Count (across all configs)')
    ax2.set_title('Total Features Used by Number of Groups')
    ax2.set_xticks(x)
    ax2.set_xticklabels(group_counts)
    
    # Add value labels on bars
    for i, v in enumerate(feature_totals):
        ax2.text(i, v + max(feature_totals)*0.01, f'{v:,}', ha='center', fontsize=8)
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'group_count_optimization.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### FEATURE OCCURRENCE FREQUENCY #####
def plot_feature_occurrence_frequency(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger,
    top_n: int = 30
) -> Path:
    """Create bar chart showing how often features appear across iterations."""
    logger.debug("Plotting feature frequency...")
    
    feature_counts = {}
    total_results = 0
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            total_results += 1
            importance = result.get('feature_importance', {})
            for name in importance.keys():
                feature_counts[name] = feature_counts.get(name, 0) + 1
    
    # Convert to DataFrame
    df = pd.DataFrame([
        {'Feature': name, 'Occurrences': count, 'Frequency': count / total_results * 100}
        for name, count in feature_counts.items()
    ])
    df = df.sort_values('Occurrences', ascending=False).head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(df)))
    
    bars = ax.barh(df['Feature'], df['Frequency'], color=colors, edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Occurrence Frequency (%)')
    ax.set_ylabel('Feature Name')
    ax.set_title(f'Top {top_n} Most Frequently Selected Features\n(Across all configurations)')
    ax.invert_yaxis()
    
    # Add percentage labels
    for bar, freq in zip(bars, df['Frequency']):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                f'{freq:.1f}%', va='center', fontsize=8)
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'feature_occurrence_frequency.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### GROUP USAGE FREQUENCY #####
def plot_group_usage_frequency(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger,
    top_n: int = 20
) -> Path:
    """Create bar chart showing how often groups are used across iterations."""
    logger.debug("Plotting group frequency...")
    
    group_counts = {}
    total_results = 0
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            total_results += 1
            used_groups = result.get('used_groups', [])
            for name in used_groups:
                group_counts[name] = group_counts.get(name, 0) + 1
    
    # Convert to DataFrame
    df = pd.DataFrame([
        {'Group': name[:35] + '...' if len(name) > 35 else name, 
         'Occurrences': count, 
         'Frequency': count / total_results * 100}
        for name, count in group_counts.items()
    ])
    df = df.sort_values('Occurrences', ascending=False).head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = plt.cm.Greens(np.linspace(0.4, 0.9, len(df)))
    
    bars = ax.barh(df['Group'], df['Frequency'], color=colors, edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Usage Frequency (%)')
    ax.set_ylabel('Group Name')
    ax.set_title(f'Top {top_n} Most Frequently Used Groups\n(Across all configurations)')
    ax.invert_yaxis()
    
    # Add percentage labels
    for bar, freq in zip(bars, df['Frequency']):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                f'{freq:.1f}%', va='center', fontsize=8)
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'group_usage_frequency.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### METRICS CORRELATION PLOT #####
def plot_metrics_correlation(
    all_results: List[Dict],
    config: FigureConfig,
    logger: logging.Logger
) -> Path:
    """Create scatter matrix showing correlations between metrics."""
    logger.debug("Plotting metrics correlation...")
    
    # Collect all metrics
    data = []
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            data.append({
                'F1 Score': result.get('f1_score', 0),
                'AUC-ROC': result.get('auc_roc', 0),
                'Accuracy': result.get('accuracy', 0),
                'Precision': result.get('precision', 0),
                'Recall': result.get('recall', 0),
                'Groups': result.get('num_groups_used', 0),
                'Features': result.get('num_features_used', 0)
            })
    
    df = pd.DataFrame(data)
    
    # Calculate correlation matrix
    corr_matrix = df.corr()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Create heatmap
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    sns.heatmap(
        corr_matrix, 
        mask=mask,
        annot=True, 
        fmt='.2f',
        cmap='RdBu_r',
        center=0,
        square=True,
        linewidths=0.5,
        ax=ax,
        cbar_kws={'label': 'Correlation', 'shrink': 0.8}
    )
    
    ax.set_title('Correlation Matrix of Performance Metrics')
    
    plt.tight_layout()
    
    output_path = config.output_dir / f'metrics_correlation.{config.format}'
    fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.debug(f"Saved {output_path.name}")
    return output_path


##### STANDALONE EXECUTION #####
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    if len(sys.argv) < 2:
        print("Usage: python generate_figures.py <output_directory>")
        print("Example: python generate_figures.py output/gsm_2026_01_24-08_46_49")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1])
    results_path = output_dir / "modeling_results_all_iterations.json"
    
    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}")
        sys.exit(1)
    
    figures = generate_all_figures(output_dir, results_path, logger)
    print(f"\n✅ Generated {len(figures)} figures")
    for name, path in figures.items():
        print(f"   - {name}: {path}")
