# Archived Tasks & Status

This file contains fully completed tasks and phases migrated from `TASKS.md` and `STATUS.md` to keep the active context window lightweight.

## From TASKS.md

### Phase 1: Code Fixes ✅ COMPLETE
- [x] 1.1 Fix normalization leakage (C1) — `data_preprocess.py`, `normalization.py`, `GSM_workflow.py`
- [x] 1.2 Fix group count selection (C1) — `GSM_workflow.py`
- [x] 1.3 Add extended metrics (I4, I6) — `run_modeling.py`
- [x] 1.4 Feature stability tracking (I3) — NEW `feature_stability.py`
- [x] 1.5 Extend baselines code (C4) — `run_baselines.py` (+3 methods)
- [x] 1.6 Enhance biological validation (C5) — STRING PPI stats + permutation script
- [x] 1.7 Fix GDS3837 data bug — coerce object columns in `data_preprocess.py`
- [x] 1.8 Unit tests pass (43/43)

### Phase 5: Narrative & Marketing Upgrades
- [x] 5.1 Rewrite Abstract (Emphasize Monte Carlo & Leakage prevention)
- [x] 5.2 Rewrite Introduction contributions (The Six Key Challenges)
- [x] 5.3 Draft "Statistical Safeguards" section for Methods
- [x] 5.4 Draft "Robust Engineering" conclusion for Discussion

### Phase 6: End-to-End Manuscript & Supplementary Rewrite
- [x] 6.1 Draft `01_Abstract_and_Introduction.md`
- [x] 6.2 Draft `02_Methods.md`
- [x] 6.3 Draft `03_Results.md`
- [x] 6.4 Draft `04_Discussion_and_Conclusion.md`
- [x] 6.5 Draft `05_Supplementary_Material.md`

### Phase 7: Academic Rigor and Scientific Tone Review
- [x] 7.1 Rewrite all 5 manuscript artifacts to ensure objective, professional scientific prose

### Phase 8: Post-Review Deliverables (2026-07-20)
- [x] 8.1 Analyze 5 pre-revision questions (DisGeNET validation, AUC 1.00, Table 1, novelties, response letter)
- [x] 8.2 Create expanded Table 1 (11-row comparison: prior G-S-M vs. proposed framework)
- [x] 8.3 Create manuscript insertion guide with corrected text
- [x] 8.4 Generate submission-ready response letter (`.md` + `.docx`)
- [x] 8.5 Update AI context files

## From STATUS.md

### Code Fixes (Phase 1)
- **Normalization leakage fix (C1):** Moved normalization inside train/test split. Verified: train mean=0.000, test mean≠0.
- **Group count selection fix (C1):** Uses fixed K (last modeling step) instead of max-F1 across all K.
- **Extended metrics (I4, I6):** Added `balanced_accuracy`, `mcc`, `pr_auc`, confusion matrix to `ModelingResult`.
- **Feature stability (I3):** New `src/utils/feature_stability.py` — per-gene frequency, Jaccard index, stable core.
- **GDS3837 data bug:** Coerce corrupted string cells (`OR10C1` in `EPHB3` column) to NaN in `data_preprocess.py`.
- **STRING PPI enrichment:** `biological_validation.py` now queries `/api/json/ppi_enrichment` for expected edges + p-value.
- **Permutation test script:** `scripts/experiments/permutation_test.py` created (not yet executed).

### Phase 7: Comprehensive Review (2026-07-14)
- **Table 2 numbers were wrong** — manuscript used pre-fix leaky pipeline numbers. All metrics updated with actual revised pipeline data.
- **Overall mean F1 corrected**: 0.87 → 0.84
- **GSM wins only 1/7 datasets on F1** — text reframed from "superior" to "competitive with biological interpretability"
- **Cross-dataset transfer results reported honestly** — F1=0.025, incompatible platforms
- **Permutation tests**: 5/7 valid (p<0.0001), GDS5499 p=1.0 (4 DB genes), GDS3837 data unavailable
- **Response letter** completely rewritten — all R3 points added, honest cross-dataset reporting
- **"Nested cross-validation" corrected** — it's internal CV within Monte Carlo iterations
- **Extended metrics added** — balanced accuracy, MCC, PR-AUC (Table 3)
- **Computational complexity added** — O(N×G×k×T_clf), 70-199 min/dataset
