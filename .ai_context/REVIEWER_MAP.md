# Reviewer Concern → Fix → Manuscript Map

Quick-reference: what each reviewer asked for, what code fix was applied, and which manuscript section needs updating.

## Critical (C1–C5)

| ID | Concern | Reviewers | Code Fix | Manuscript Action |
|----|---------|-----------|----------|-------------------|
| C1 | Normalization leakage | R2, R4 | ✅ `normalize_within_split()` in `normalization.py`; normalization moved inside train/test split in `GSM_workflow.py` | Methods: describe corrected procedure |
| C1b | Group selection on test F1 | R2, R4 | ✅ Fixed-K selection in `GSM_workflow.py` | Methods: state K is fixed hyperparameter |
| C2 | No external validation | R2, R4 | ⏳ `cross_dataset_transfer.py` exists, not run yet | Results: add cross-dataset transfer table |
| C3 | Novelty vs GediNET | R2, R3, R4 | N/A (text only) | Intro: add comparison table |
| C4 | Weak baselines | R1, R2, R3, R4 | ✅ 7 baselines in `run_baselines.py` | Results: add baselines comparison table |
| C5 | Validation circularity | R1, R2, R4 | ✅ PPI stats in `biological_validation.py`; ⏳ permutation test script ready | Results: add permutation p-values; label DisGeNET as non-independent |

## Important (I1–I6)

| ID | Concern | Reviewers | Code Fix | Manuscript Action |
|----|---------|-----------|----------|-------------------|
| I1 | Clinical claims overstated | R2, R4 | N/A (text only) | Discussion: replace "translation-ready" → "research prototype" |
| I2 | AML AUC = 1.00 suspicious | R1, R4 | N/A | Discussion: explain GDS3257 separability |
| I3 | Feature stability missing | R1, R3, R4 | ✅ `feature_stability.py` | Results: add stability analysis; Supplementary: stability plots |
| I4 | Class imbalance metrics | R4 | ✅ balanced_acc, MCC, PR-AUC in `run_modeling.py` | Results: add metrics for imbalanced datasets |
| I5 | Missing methods details | R1, R2, R4 | N/A (text only) | Methods: probe-to-gene mapping, DisGeNET criteria, seeds |
| I6 | Bootstrap CIs missing | R4 | ✅ Already implemented, now verified | Results: report 95% CIs in tables |

## Minor (M1–M10) — All manuscript-only

| ID | Concern | Action |
|----|---------|--------|
| M1 | Figure 1 cluttered | ✅ Created `scripts/generate_figure1.py` for LaTeX/TikZ flowchart |
| M2 | Algorithm 1 unclear/leaky | ✅ Rewrote pseudocode in `manuscript_insertion_guide.md` (moved normalization) |
| M3 | Section numbering wrong | ✅ Identified fix in insertion guide (change 2.3.3 to 2.2.4) |
| M4 | KEGG p-values missing | ✅ Extracted adjusted p-values and added to insertion guide for Table 4 |
| M5 | Grammar issues | ✅ Proofread during copy-editing |
| M6 | Reference errors | ✅ (Addressed by author) |
| M7 | GediNET reference format | ✅ (Addressed by author) |
| M8 | Dataset details | ✅ Datasets table updated in drafts |
| M9 | Final gene lists missing | ✅ Generated `Supplementary_Gene_Lists.xlsx` |
| M10 | Reproducibility env | ✅ Generated `requirements.txt` and `environment.yml` |

*Last updated: 2026-07-06*
