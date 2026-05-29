# Dataset Exclusion Report 📊

Two of the nine GEO datasets originally included in the full pipeline run were excluded from the final manuscript analysis due to severe statistical issues during the filtering (t-test) stage.

---

## Excluded Datasets

### GDS3268 — Breast Cancer (Invasive Ductal Carcinoma)

| Attribute | Value |
|-----------|-------|
| **Samples** | 171 (63 positive / 108 negative) |
| **Problem** | 100% of 100 iterations produced **zero** significant genes after Welch t-test + BH-FDR (α = 0.05) |
| **Consequence** | Pipeline fell back to all 2,156 features in every iteration, bypassing filtering entirely |
| **Runtime** | 533 minutes (longest of any dataset) |
| **Warnings** | 5,880 (mostly `ZeroSignificantGenesWarning`) |

**Interpretation:** The class labels do not produce meaningful gene-level differential expression under this statistical framework, making downstream grouping and scoring essentially arbitrary.

### GDS4206 — Hepatocellular Carcinoma (HCC)

| Attribute | Value |
|-----------|-------|
| **Samples** | 197 (40 positive / 157 negative) |
| **Problem** | 92% of iterations produced zero significant genes; remaining 8% found very few |
| **Consequence** | Average feature count = 2,156 (same fallback). Lowest performance: **F1 = 0.651, AUC = 0.774** |
| **Runtime** | 408 minutes |
| **Warnings** | 5,341 |

**Interpretation:** Severe class imbalance (40 vs 157) combined with weak differential expression made reliable feature selection impossible under default parameters.

---

## Retained Datasets (7)

| GDS ID | Disease | Samples | F1 | AUC |
|--------|---------|--------:|----:|-----:|
| GDS1962 | Glioblastoma | 26 | 1.000 | 1.000 |
| GDS2545 | Prostate Cancer | 89 | 0.842 | 0.887 |
| GDS2547 | Prostate (Lapointe) | 89 | 0.870 | 0.911 |
| GDS2771 | Lung Cancer | 118 | 0.849 | 0.829 |
| GDS3257 | AML | 107 | 1.000 | 1.000 |
| GDS3837 | Colorectal Cancer | 70 | 1.000 | 1.000 |
| GDS5499 | Pancreatic Cancer | 140 | 1.000 | 1.000 |

---

## Decision Rationale

When the t-test filtering stage produces zero significant genes across the vast majority of iterations, the pipeline's core assumption — that disease-associated gene groups carry discriminative signal — is violated. Including such datasets would:

1. **Inflate feature counts** artificially (using all genes instead of filtered subsets)
2. **Distort runtime comparisons** (5-10x longer than normal datasets)
3. **Undermine interpretability** claims of the manuscript

Both datasets are excluded from all manuscript tables, figures, and summary statistics. The raw output folders are preserved in `output/` for reproducibility.
