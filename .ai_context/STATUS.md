# Status

**Active Phase:** Evaluating the "Group Lasso → Random Forest" hybrid model across all 7 cancer datasets to compare against the published G-S-M framework.

**Recent Work:**
- Analyzed initial GL vs GSM performance and identified 5 key areas for improvement.
- Upgraded the `gl_rf_hybrid.py` pipeline to v2.0 by introducing a t-test pre-filter, multi-objective Optuna Bayesian optimization (warmup strategy), and enhanced stability selection (30 subsamples).
- Added `optuna` dependency to the project.
- Documented the changes in `DOCS/methods/GL_IMPROVEMENTS.md`.
