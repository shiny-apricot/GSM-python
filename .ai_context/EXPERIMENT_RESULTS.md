# Experiment Results — Major Revision

## 1. Extended Baselines (F1 scores, 100 iterations each)

Results at: `output/baselines/baseline_results.json`

| Dataset | RF-All | RF-ttest-100 | LASSO | SVM-RBF | ElasticNet | XGB-ttest-100 | SVM-RFE |
|---------|--------|-------------|-------|---------|------------|--------------|---------|
| GDS1962 (Glioblastoma) | 0.969 | 0.977 | 0.976 | 0.963 | **0.981** | 0.968 | 0.976 |
| GDS2545 (Prostate) | 0.760 | 0.763 | 0.752 | **0.772** | 0.749 | 0.747 | 0.724 |
| GDS2547 (Prostate-L) | 0.730 | **0.746** | 0.691 | **0.746** | 0.692 | 0.721 | 0.652 |
| GDS2771 (Lung) | 0.717 | 0.716 | 0.711 | **0.743** | 0.706 | 0.711 | 0.692 |
| GDS3257 (AML) | 0.989 | **0.991** | 0.974 | 0.987 | 0.984 | 0.940 | 0.976 |
| GDS3837 (Colorectal) | 0.947 | 0.950 | 0.954 | **0.954** | 0.947 | 0.943 | 0.923 |
| GDS5499 (Pancreatic) | 0.930 | 0.945 | 0.934 | **0.946** | 0.940 | 0.943 | 0.931 |

**Bold** = best F1 per dataset. Full AUC/accuracy data in the JSON.

### AUC-ROC Table

| Dataset | RF-All | RF-ttest-100 | LASSO | SVM-RBF | ElasticNet | XGB-ttest-100 | SVM-RFE |
|---------|--------|-------------|-------|---------|------------|--------------|---------|
| GDS1962 | 0.987 | 0.987 | 0.984 | 0.984 | **0.989** | 0.984 | 0.986 |
| GDS2545 | **0.860** | 0.846 | 0.837 | 0.853 | 0.833 | 0.834 | 0.801 |
| GDS2547 | 0.838 | **0.840** | 0.799 | 0.823 | 0.800 | 0.829 | 0.769 |
| GDS2771 | 0.731 | 0.741 | 0.759 | **0.760** | 0.756 | 0.756 | 0.733 |
| GDS3257 | **1.000** | **1.000** | 0.999 | **1.000** | **1.000** | 0.932 | 0.999 |
| GDS3837 | 0.984 | 0.986 | **0.988** | 0.981 | 0.987 | 0.984 | 0.973 |
| GDS5499 | 0.943 | 0.955 | 0.938 | **0.964** | 0.945 | 0.954 | 0.933 |

---

## 2. GSM Revised Pipeline Results (6/7 complete)

Each run: 100 iterations, fixed normalization (in-split), fixed-K group selection.

| Dataset | Disease | Status | Output Path |
|---------|---------|--------|-------------|
| GDS1962 | Glioblastoma | ✅ Done (171 min) | `output/gsm_2026_07_04-09_29_56_*_revised_GDS1962/` |
| GDS2545 | Prostate Cancer | ✅ Done (101 min) | `output/gsm_2026_07_04-12_21_18_*_revised_GDS2545/` |
| GDS2547 | Prostate (Lapointe) | ✅ Done (81 min) | `output/gsm_2026_07_04-14_02_10_*_revised_GDS2547/` |
| GDS2771 | Lung Cancer | ✅ Done (70 min) | `output/gsm_2026_07_04-15_23_21_*_revised_GDS2771/` |
| GDS3257 | Acute Myeloid Leukemia | ✅ Done (199 min) | `output/gsm_2026_07_04-16_33_09_*_revised_GDS3257/` |
| GDS3837 | Colorectal Cancer | ❌ **Needs re-run** | Only 1-iter debug exists |
| GDS5499 | Pancreatic Cancer | ✅ Done (112 min) | `output/gsm_2026_07_04-19_51_50_*_revised_GDS5499/` |

**GDS3837 note:** The full 100-iteration run was killed by a server restart. The data bug (`OR10C1` in `EPHB3` column) is fixed in `data_preprocess.py`. Just needs to be re-launched.

Results JSON per run: `modeling_results_all_iterations.json` (contains all iteration metrics).

---

## 3. Not Yet Run

- **Cross-dataset transfer** (GDS2545 ↔ GDS2547) — script: `scripts/experiments/cross_dataset_transfer.py`
- **Permutation tests** — script: `scripts/experiments/permutation_test.py`
- **GSM vs baselines comparison table** — needs to be assembled from GSM results + baseline results

---

## 4. Previous Run (pre-fix, for reference)

The original run summary (before normalization fix) is at `output/revision_run_summary.json`. Those results are now **invalid** — the normalization leakage inflated all metrics.

*Last updated: 2026-07-06*
