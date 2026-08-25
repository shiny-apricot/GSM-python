# Code Changes — Current Active Phase

## 1. Group Lasso Pareto Sweep & Stability Selection (August 2026)

**Changes:**
- `src/workflows/gl_rf_hybrid.py`: Completely revamped the `_gl_feature_selection` and main workflow. Removed the internal 80/20 train/validation grid search. Implemented **Stability Selection** (20 subsamples) embedded inside a **Pareto Sweep** (iterating over `group_reg`). Output dataclasses updated to store Pareto points (Sparsity vs F1/AUC) for each iteration.
- `scripts/experiments/run_hybrid_all_datasets.py`: Modified output formatting and paths for the new Pareto-based hybrid experiment (`output/hybrid_runs`).
- *Previous Engineering Overhaul (Aug 23)*: Added progress tracking, reorganized output directory tree into `gsm_runs/`, `gl_runs/`, `hybrid_runs/`, `logs/`, etc.

---

*For older changes (e.g., July 2026 Applied Sciences R1 revisions), see `ARCHIVED_CODE_CHANGES.md`.*

*Last updated: 2026-08-24*

## 2026-08-25
- **`src/workflows/group_lasso_workflow_config.py`**: Added configuration parameters for v2.0 pipeline (t-test pre-filtering, Optuna multi-objective HP optimization, enhanced stability selection parameters, adaptive `scale_reg`).
- **`src/workflows/gl_rf_hybrid.py`**: Completely rewritten to implement v2.0 improvements. Added `_apply_ttest_prefilter`, `_optuna_find_pareto_hps`, and updated `run_hybrid_iteration` and `gl_rf_hybrid_workflow` to orchestrate the new multi-stage pipeline.
- **`DOCS/methods/GL_IMPROVEMENTS.md`**: Created new documentation detailing the rationale, technical details, and expected impact of the v2.0 pipeline upgrades.
