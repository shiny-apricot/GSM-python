# Code Changes — Major Revision (July 2026)

All changes address reviewer concerns from Applied Sciences R1.

---

## 1. Normalization Leakage Fix (C1) — Critical

**Problem:** `preprocess_data()` normalized ALL data before the train/test split. Scaler saw test samples.

**Changes:**
- `src/data_processing/normalization.py` — Added `normalize_within_split()`: fits `StandardScaler` on X_train, transforms both X_train and X_test.
- `src/data_processing/data_preprocess.py` — Added `skip_normalization=True` parameter. Also added object-column coercion (fixes GDS3837 `OR10C1` bug).
- `src/workflows/GSM_workflow.py` — Normalization now inside the iteration loop, after train/test split. Inference scaler fits on full un-normalized data.

**Verified:** Train mean=0.000, test mean=0.515 (proves no leakage).

---

## 2. Group Count Selection Fix (C1) — Critical

**Problem:** `max(modeling_result, key=lambda r: r.f1_score)` selected best model across all group counts 1..K using test-set F1. This is model selection on the test set.

**Change:** `src/workflows/GSM_workflow.py` ~L540-555 — Now uses fixed-K result (last step in modeling loop). K is a hyperparameter (default=10) justified by sensitivity analysis. 1..K sweep kept for diagnostics only.

---

## 3. Extended Metrics (I4, I6)

**Change:** `src/modeling/run_modeling.py` — Added to `ModelingResult`:
- `balanced_accuracy`
- `mcc` (Matthews Correlation Coefficient)
- `pr_auc` (Precision-Recall AUC)
- `tp`, `fp`, `tn`, `fn` (confusion matrix)

---

## 4. Feature Stability (I3)

**New file:** `src/utils/feature_stability.py`
- Per-gene selection frequency across iterations
- Stable core (genes in >50% of iterations)
- Pairwise Jaccard stability index
- Saves `feature_stability_report.xlsx` (two sheets)
- Integrated into `gsm_run()` post-processing

---

## 5. Extended Baselines (C4)

**Changed:** `scripts/experiments/run_baselines.py`
- All baselines now fit scaler on train only (was leaking before)
- Added 3 new methods: Elastic Net, XGB-ttest-100, SVM-RFE
- Added object-column coercion for GDS3837 support
- Total: 7 baselines (was 4)

---

## 6. Biological Validation Enhancements (C5)

**Changed:** `src/utils/biological_validation.py`
- Added `ppi_enrichment` API call to capture expected edges + p-value
- Saves `string_ppi_stats.json`

**New:** `scripts/experiments/permutation_test.py`
- Monte-Carlo permutation test for DisGeNET enrichment significance
- Computes empirical p-value by comparing GSM panel overlap to random gene sets

---

## 7. Configuration Updates

**Changed:** `.github/copilot-instructions.md`
- Removed dead DOCX review workflow references
- Updated manuscript workflow to Google Docs
- Added Major Revision Context section

---

## Files Modified Summary

| File | Change |
|------|--------|
| `src/data_processing/normalization.py` | Added `normalize_within_split()` |
| `src/data_processing/data_preprocess.py` | `skip_normalization` param + object coercion |
| `src/workflows/GSM_workflow.py` | Normalization in-split, fixed-K, stability integration |
| `src/modeling/run_modeling.py` | MCC, balanced accuracy, PR-AUC, confusion matrix |
| `src/utils/feature_stability.py` | **NEW** — stability analysis module |
| `src/utils/biological_validation.py` | PPI enrichment stats + save |
| `scripts/experiments/run_baselines.py` | 3 new baselines, universal scaling, coercion |
| `scripts/experiments/permutation_test.py` | **NEW** — permutation test script |
| `.github/copilot-instructions.md` | Revision context, removed dead workflow |

*Last updated: 2026-07-06*
