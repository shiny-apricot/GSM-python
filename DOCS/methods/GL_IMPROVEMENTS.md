# GL→RF Hybrid Pipeline v2.0 — Improvements Documentation

> **Date**: 2026-08-25
> **Author**: AI-assisted refactoring
> **Files Modified**: `src/workflows/gl_rf_hybrid.py`, `src/workflows/group_lasso_workflow_config.py`

---

## Summary of Changes

The GL→RF hybrid pipeline has been upgraded from v1.0 (fixed grid search) to v2.0 (intelligent, adaptive optimization). These changes address the five root causes of GL's underperformance vs GSM identified in the comparative analysis.

## 1. t-test Pre-filter (Stage 0) — NEW

### Problem
The original pipeline fed ALL ~20,000+ genes to Group Lasso. Most genes are noise (not differentially expressed). This made GL slow, unfocused, and prone to selecting irrelevant features.

### Solution
Added `_apply_ttest_prefilter()` that mirrors GSM's Phase I:
1. Welch t-test (unequal variance) for each gene between class 0 and class 1
2. Benjamini-Hochberg FDR correction (threshold: 0.05)
3. Only significant genes proceed to Group Lasso

### Impact
- **Speed**: ~5-10x faster GL fitting (2,000 filtered genes vs 20,000)
- **Quality**: GL focuses on truly differentially expressed genes
- **Fairness**: Matches GSM's pre-filtering approach → fair comparison

### Config
```python
enable_ttest_prefilter: bool = True  # Enable/disable
fdr_threshold: float = 0.05          # BH FDR threshold
```

---

## 2. Multi-objective Optuna HP Optimization (Stage 1) — NEW

### Problem
The original pipeline used a fixed 5-point grid for `group_reg ∈ {0.01, 0.02, 0.05, 0.1, 0.2}`. This caused the "cliff effect": at low reg → thousands of genes (overfitting), at high reg → zero genes (underfitting). No intermediate sweet spot was found.

### Solution
Replaced the fixed grid with **Optuna Bayesian Optimization** using the Tree-structured Parzen Estimator (TPE):

**Two simultaneous objectives (multi-objective)**:
1. **Maximize** weighted F1 score (classifier performance — primary)
2. **Minimize** selected feature count (interpretability — secondary)

**F1 is ~3x more important than feature reduction**. After Optuna finds the Pareto front, the top configs are selected using:
```
composite = normalized_F1 − 0.3 × normalized_log(features)
```

**Warmup + Reuse strategy**:
- Optuna runs ONCE on the first training split (~5-10 minutes)
- Top 3 Pareto-optimal HP configs are extracted
- These are reused across all subsequent iterations (no re-optimization)

### Why Multi-objective?
A single-objective (just maximize F1) would always choose low regularization → too many features. Multi-objective naturally finds the **trade-off curve** between performance and parsimony, producing a smooth Pareto front instead of the flat 5-point line.

### Inner Evaluation (Fast)
During Optuna search, each trial uses **3-fold CV with a single GL fit per fold** (NOT stability selection). This is ~100x faster than full stability selection, making 30 trials feasible in minutes.

### Config
```python
enable_optuna: bool = True          # Enable/disable
optuna_n_trials: int = 30           # Number of search trials
optuna_n_cv_folds: int = 3          # Inner CV folds
optuna_n_pareto_configs: int = 3    # Top Pareto configs to keep
```

---

## 3. Improved Stability Selection — ENHANCED

### Problem
The original pipeline used only 10 subsamples. Literature recommends 50-100 for reliable frequency estimates.

### Solution
Increased default to 30 subsamples (configurable). Made the threshold configurable too.

### Config
```python
n_stability_subsamples: int = 30    # Was 10
stability_threshold: float = 0.5    # Genes in ≥50% of subsamples
```

---

## 4. Adaptive Group Regularization — CHANGED

### Problem
`scale_reg="group_size"` penalized large groups more heavily. In DisGeNET grouping, group sizes are very uneven (10–500+ genes). Large groups were eliminated first regardless of their informativeness, contributing to the cliff effect.

### Solution
Changed default to `scale_reg="inverse_group_size"`, which normalizes penalties so large and small groups are treated more equally.

---

## 5. Architecture Changes

### New Pipeline Flow
```
v1.0: Load → Expand → [Fixed Grid × Stability Selection] → RF → Save
v2.0: Load → [WARMUP: t-test → Optuna] → [Per-Iter: t-test → StabSel → RF] → Save
```

### New Functions
| Function | Purpose |
|----------|---------|
| `_apply_ttest_prefilter()` | Welch t-test + BH FDR gene filtering |
| `_optuna_find_pareto_hps()` | Multi-objective Bayesian HP search |
| `_select_pareto_configs()` | Extract top configs from Pareto front |
| `_run_stability_selection()` | Extracted/cleaned stability selection |

### Modified Functions
| Function | Change |
|----------|--------|
| `run_hybrid_iteration()` | Now accepts `pareto_hps` and `group_df`; applies t-test per iteration |
| `gl_rf_hybrid_workflow()` | Added warmup phase; restructured iteration loop |
| `_save_hybrid_results()` | Saves Optuna HP configs in JSON |
| `_generate_hybrid_figures()` | Improved Pareto plot with log scale and annotations |

### Data Structure Changes
| Class | Change |
|-------|--------|
| `HybridIterationResult` | Added `n_sig_genes`, `n_expanded_features` |
| `HybridResults` | Added `optuna_hps` |

---

## Expected Performance Impact

| Metric | v1.0 | v2.0 (expected) |
|--------|------|-----------------|
| Runtime (1 dataset, 5 iter) | ~105 min | ~20-30 min |
| F1 (GDS1962) | 0.680–0.948 | 0.90+ (with t-test + optimized HP) |
| Feature count | 0–5135 (bimodal) | 50-500 (smooth range) |
| Pareto curve | 5 points, flat | 3+ points, curved |

---

## CLI Usage

```bash
# Default (all improvements enabled)
python -m src.workflows.gl_rf_hybrid --dataset GDS1962 --n-iterations 5

# Without Optuna (grid fallback)
python -m src.workflows.gl_rf_hybrid --dataset GDS1962 --no-optuna

# Without t-test (for ablation study)
python -m src.workflows.gl_rf_hybrid --dataset GDS1962 --no-ttest
```
