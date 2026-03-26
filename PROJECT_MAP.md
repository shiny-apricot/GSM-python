# GSM Project Map 🗺️

> **Living document** — Single source of truth for the project's
> file/folder layout, key functions, and current conventions.
>
> Update this file whenever files are added/removed, functions are
> renamed, or defaults change. For coding standards, see
> [`.github/copilot-instructions.md`](.github/copilot-instructions.md).

---

## Pipeline Overview

```
GEO Expression Data + DisGeNET Gene-Disease Knowledge
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 GROUPING    SCORING     MODELING
 (Phase I)  (Phase II)  (Phase III)
    │           │           │
    ▼           ▼           ▼
 Disease-gene  Group      Final classifier +
 group         ranking    ranked features +
 projection    by ML      biological validation
                               │
                               ▼
                         MODEL BUNDLE
                         (.gsm.zip)
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                  CLI      Web UI     Python API
                    │          │          │
                    ▼          ▼          ▼
              CLINICAL INFERENCE
              (ensemble prediction + report)
```

**Entry point (training):** `src/workflows/GSM_workflow.py` → `gsm_workflow()`  
**Entry point (inference):** `src/inference/inference_engine.py` → `infer()`  
**Entry point (CLI):** `gsm/__main__.py` → `src/cli.py` → `main()` / `python -m gsm`

### What each phase does (conceptually)

| Phase | Input | What happens | Output |
|-------|-------|-------------|--------|
| **Filter** | Raw expression CSV (genes × samples) | Welch t-test per gene, BH-FDR correction, keep genes with p < α | Filtered gene list |
| **Group (Phase I)** | Filtered genes + DisGeNET mapping | Project genes onto disease-gene groups; each gene may belong to multiple groups | Gene-group assignment matrix |
| **Score (Phase II)** | Grouped expression data | For each group, train a classifier (3-fold CV) and record its F1/AUC | Ranked list of groups by predictive power |
| **Model (Phase III)** | Top-ranked groups' features | Train final classifier on pooled features from top-K groups | Fitted model + feature importances |
| **Rank** | 100 iterations of the above | Robust Rank Aggregation across all iterations | Consensus feature ranking |
| **Validate** | Top features | Query Enrichr, STRING-db, DisGeNET for biological enrichment | Validation report |
| **Bundle** | Top-10 models + scaler + metadata | Serialize into a `.gsm.zip` archive | Portable model bundle |
| **Infer** | Bundle + patient CSV | Ensemble prediction → per-patient class + confidence + risk | Clinical report (`.txt` + `.xlsx`) |

### Training vs. inference split

Training and inference are **completely separated** by the `.gsm.zip`
bundle boundary.  Training-time code (`filter/`, `grouping/`, `scoring/`,
`modeling/`) is never imported during inference.  The
`src/inference/` module is self-contained: it loads the bundle, aligns
patient features, scales them, and runs ensemble prediction.

### Workflow relationships

| Workflow | File | Purpose | Relationship |
|----------|------|---------|-------------|
| **GSM** | `GSM_workflow.py` | Main GSM pipeline (filter → group → score → model → rank → validate) | Primary workflow |
| **Group Lasso** | `group_lasso_workflow.py` | GL-based feature selection with overlap-aware duplication | Alternative approach for thesis comparison |
| **GL→RF Hybrid** | `gl_rf_hybrid.py` | Stage 1: GL feature selection → Stage 2: RF classification | Experimental hybrid |
| **Stability Selection** | `stability_selection_gl.py` | Meinshausen & Bühlmann stability selection with Latent GL | Feature stability analysis |
| **Classification** | `classification_workflow.py` | Plain classification baseline (no grouping, no feature selection) | Baseline comparator |

---

## Root-Level Files

| File | Purpose |
|------|---------|
| `dependencies.txt` | pip requirements |
| `pytest.ini` | Pytest configuration |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, trailing whitespace) |
| `.gitattributes` | Git LFS tracking (`*.csv`, `models/pretrained/*.gsm.zip`) |
| `.lfsconfig` | LFS fetch-include for `data/` |
| `CONTRIBUTING.md` | Contribution guidelines |
| `README.md` | Project overview and quick-start |
| `PROJECT_MAP.md` | **This file** |
| `gsm/` | Package entry point — makes `python -m gsm` work |
| `gsm/__init__.py` | Package marker |
| `gsm/__main__.py` | `python -m gsm` — adds project root to path, calls `src.cli.main()` |
| `assets/` | Static files (screenshots, images) |
| `assets/gsm_cli.png` | CLI interactive menu screenshot |
| `assets/figures.png` | General figures image |
| `assets/gsm_logic_pseudocode.png` | GSM logic pseudocode diagram |

---

## `src/` — Core Pipeline Code

### `src/data_processing/`
| File | Key functions |
|------|---------------|
| `data_loader.py` | `load_input_file()`, `load_group_file()`, `_detect_separator()` |
| `data_preprocess.py` | `preprocess_data()` |
| `normalization.py` | `normalize_expression()`, `fit_scaler()` |
| `handle_missing_values.py` | `impute_missing()` |
| `preliminary_filtering.py` | `preliminary_filter()` |
| `train_test_splitter.py` | `stratified_split()` |

### `src/feature_selection/`
| File | Key functions |
|------|---------------|
| `ttest_filter.py` | `ttest_filter_genes()` — Welch t-test + BH-FDR |
| `variance.py` | `variance_filter()` |
| `selectkbest.py` | `selectkbest_filter()` |
| `recursive_feature_elimination.py` | `rfe_filter()` |

### `src/grouping/` — Phase I
| File | Key functions |
|------|---------------|
| `run_grouping.py` | `run_grouping()` — orchestrator |
| `grouping_utils.py` | `build_gene_group_mapping()`, `filter_groups_by_size()` |
| `input_loader.py` | `load_grouping_input()` |

### `src/scoring/` — Phase II
| File | Key functions |
|------|---------------|
| `run_scoring.py` | `run_scoring()` — orchestrator |
| `feature_scorer.py` | `score_group()` |
| `score_data.py` | `ScoreData` dataclass |
| `metrics.py` | `compute_classification_metrics()` |
| `rank_aggreg.py` | `aggregate_group_ranks()` |

### `src/modeling/` — Phase III
| File | Key functions |
|------|---------------|
| `run_modeling.py` | `run_modeling()` — orchestrator; `ModelingResult.fitted_model` propagates trained model for inference bundling |
| `evaluator.py` | `evaluate_model()` |
| `modeling_utils.py` | `select_top_groups()`, `pool_group_features()` |

### `src/machine_learning/`
| File | Key functions |
|------|---------------|
| `classification.py` | `get_classifier()` — factory |
| `random_forest.py` | `create_random_forest()` |
| `xgboost.py` | `create_xgboost_classifier()` |
| `adaboost.py` | `create_adaboost()` |
| `decision_tree.py` | `create_decision_tree()` |
| `logitboost.py` | `create_logitboost()` |

### `src/utils/`
| File | Key functions |
|------|---------------|
| `logger.py` | `setup_logger()` |
| `save_results.py` | `save_iteration_results()`, `save_summary_json()` |
| `save_ranked_features.py` | `save_ranked_features()` |
| `save_ranked_groups.py` | `save_ranked_groups()` |
| `rank_aggregation.py` | `robust_rank_aggregation()` — RRA (Stuart et al.) |
| `biological_validation.py` | `run_biological_validation()` — Enrichr + STRING-db + DisGeNET |
| `generate_figures.py` | `generate_all_figures()` |
| `visualization.py` | `plot_roc_curve()`, `plot_feature_importance()` |
| `performance_profiler.py` | `profile_pipeline()` |

### `src/workflows/`
| File | Key functions |
|------|---------------|
| `GSM_workflow.py` | `gsm_run()` — **main entry point**; accepts `progress_callback` (callable for foreground progress bar) and `progress_file` (Path for background monitoring JSON) |
| `GSM_workflow_config.py` | `GSMConfig` dataclass |
| `classification_workflow.py` | `classification_workflow()` — plain classification baseline |
| `classification_workflow_config.py` | `ClassificationConfig` dataclass |
| `group_lasso_workflow.py` | `group_lasso_workflow()` — Group Lasso with overlap-aware feature duplication, multi-iteration evaluation, and integrated biological validation (Enrichr + STRING-db) |
| `group_lasso_workflow_config.py` | `GroupLassoConfig` dataclass — includes `run_biological_validation`, `biological_validation_top_genes`, `disgenet_api_key`, `max_groups_per_gene`, `min_genes_per_group` |
| `stability_selection_gl.py` | `run_stability_selection()` — **Novel**: combines Meinshausen & Bühlmann (2010) stability selection with Latent Group Lasso; B subsamples, per-gene Π̂ probabilities, provable FDR upper bound via Theorem 1 |
| `gl_rf_hybrid.py` | `gl_rf_hybrid_workflow()` — **Novel**: Two-Stage GL→RF Hybrid Pipeline; Stage 1 = Group Lasso feature pre-selection, Stage 2 = Random Forest classification on GL-selected genes |

### `src/inference/` — Clinical Inference
| File | Key functions / classes |
|------|------------------------|
| `__init__.py` | Package exports: `ModelBundle`, `save_bundle`, `load_bundle`, `infer`, `multi_infer`, `InferenceResult`, `InferenceSummary`, `MultiBundleResult`, `MultiBundleSummary` |
| `model_bundle.py` | `ModelBundle`, `ModelArtifact`, `BundleMetadata` dataclasses; `save_bundle()` — serialize top-K models + scaler + metadata into `.gsm.zip`; `load_bundle()` — deserialize; `bundle_info()` — human-readable summary (reads only metadata from zip, no model deserialization) |
| `inference_engine.py` | `infer()` — ensemble prediction from a single bundle + patient CSV; `multi_infer()` — **NEW** combine predictions from multiple bundles (different datasets) into weighted consensus; `InferenceResult`, `InferenceSummary`, `MultiBundleResult`, `MultiBundleSummary` dataclasses; `preprocess_patient_data()` — feature alignment + scaling; `_get_per_sample_importance()` — perturbation-based local feature importance; risk classification (HIGH ≥ 0.80, MEDIUM ≥ 0.55, LOW) |
| `clinical_report.py` | `generate_clinical_report()` — formatted text report; `generate_multi_bundle_report()` — **NEW** multi-bundle consensus report; `generate_report_dataframe()` — tabular export; `save_clinical_report()`, `save_multi_bundle_report()` — write `.txt` + `.xlsx` |

### `src/ui/`
| File | Purpose |
|------|---------|
| `app.py` | Streamlit web GUI — 4 tabs: Training Pipeline (with ⚙️ Advanced Parameters expander), Clinical Inference (single-bundle, patient_data/ auto-discovery), Multi-Bundle Consensus Inference, Dataset Explorer (stats & previews for all datasets). Auto-detects HuggingFace Spaces (`SPACE_ID` env var) and hides training tabs for inference-only mode. `_is_huggingface_space()` helper. `_discover_bundles()` scans output/ + models/pretrained/. |

### `src/cli.py` — Rich Interactive CLI
| Subcommand | Purpose |
|------------|----------|
| *(no args)* | Interactive guided menu with `rich` panels & numbered choices |
| `train` | Run GSM pipeline (wraps `gsm_workflow()`) — rich iteration progress bar + result panels. `--progress-file` writes JSON for background monitoring. Advanced params: `--split-ratio`, `--normalization`, `--ttest-threshold`, `--cv-folds`, `--best-groups`, `--feature-filter-size`, `--scoring-model`, `--class-balancing`, `--sampling-method`, `--balance-ratio`, `--save-intermediate`, `--bio-top-genes` |
| `infer` | Load `.gsm.zip` bundle + patient CSV → color-coded result table |
| `multi-infer` | Combine multiple bundles from different datasets for robust consensus inference |
| `bundle-info` | Inspect a saved model bundle in a rich panel |
| `ui` | Launch Streamlit web dashboard |
| `runs` | Browse / inspect past output runs (metrics, logs, files, re-run bio validation) |
| `jobs` | Monitor background training jobs (list, view-log, stop running, clear finished) |
| `bio-validate` | Re-run biological validation on a completed run (Enrichr + STRING-db + DisGeNET) |

Key functions: `interactive_menu()`, `_prompt_choice()`, `_prompt_text()`, `_prompt_yes_no()`, `_collect_advanced_params()` (advanced parameter tuning page), `_show_runtime_estimate()`, `_build_advanced_from_args()`, `_execute_train()`, `_execute_infer()`, `_execute_multi_infer()`, `_execute_bundle_info()`, `_execute_bio_validate()`, `_discover_datasets()`, `_discover_bundles()` (scans output/ + models/pretrained/), `_bundle_label()`, `_discover_patient_files()`, `_interactive_browse_outputs()` (shows status with ✓done/⚠partial, 📦bundle, 🧬bio indicators), `_inspect_run()`, `_launch_background_train_with_config()`, `_interactive_monitor_jobs()`, `_show_bg_jobs_banner()`, `_stop_job()`, `_read_progress_file()`

---

## `scripts/` — Analysis, Batch Runners & Manuscript Tooling

| File | Purpose | Output location |
|------|---------|-----------------|
| `MANUSCRIPT_BUILD_STEPS.txt` | Build order documentation for GSM manuscript | — | CHECK THIS FILE BEFORE MAKING CHANGES TO MANUSCRIPT BUILD SCRIPTS OR RUNNING NEW ANALYSES FOR THE PAPER |
| `run_test.py` | Quick single-dataset pipeline test (legacy; prefer `python -m gsm train --test`) | `output/gsm_<ts>_test_*/` |
| `run_all_datasets.py` | Batch-run pipeline on all 7 GEO datasets | `output/gsm_<ts>_*/` |
| `analyze_manuscript_results.py` | Aggregate metrics → JSON + figures | `reports_ARCHIVE/manuscript_data.json`, `reports_ARCHIVE/manuscript_figures/` |
| `build_manuscript_docx.py` | Generate Word manuscript | `reports_ARCHIVE/manuscript_versions/v###/GSM_Manuscript_v*.docx` + per-version `build_log.txt` + auto `comparison_with_v*.md` |
| `generate_flowchart.py` | Figure 1: pipeline flowchart | `reports_ARCHIVE/manuscript_figures/` |
| `generate_baseline_comparison.py` | Baseline comparison figure | `reports_ARCHIVE/manuscript_figures/` |
| `compare_gl_vs_gsm.py` | GSM vs Group Lasso side-by-side comparison (metrics, gene overlap, figures) | `output/comparison_gl_vs_gsm/` |
| `gl_ablation_study.py` | Compare 3 overlap strategies: duplication (=Latent GL), naive single-group, no-group L1 | `output/gl_ablation_<dataset>_<ts>/` |
| `run_gl_all_datasets.py` | Run GL workflow on all 7 cancer datasets with cross-dataset summary | `output/gl_all_datasets_<ts>/` |
| `gl_hyperparameter_search.py` | Grid search over λ₁, λ₂ and filter thresholds with heatmap output | `output/gl_hyperparam_<dataset>_<ts>/` |
| `manuscript_changelog.py` | Compare two manuscript .docx versions and output a word-level diff changelog | `reports_ARCHIVE/changelog_v*_v*.txt` (with `--output`) or stdout |
| `run_baselines.py` | Non-GSM baseline classifiers | `output/baselines/baseline_results.json` |
| `run_sensitivity_analysis.py` | One-at-a-time sensitivity analysis | `output/sensitivity_runs/sensitivity_results.json` |
| `compute_sensitivity_impact.py` | Δ-F1 impact rankings | `output/sensitivity_runs/sensitivity_impact.json` |
| `benchmark_scoring_models.py` | Benchmark 11 ML models for scoring | `output/benchmark/benchmark_results.json` |
| `compare_classifiers_bio_validation.py` | XGBoost vs RF bio coherence | `output/classifier_comparison/classifier_comparison_results.json` |
| `extend_classifier_comparison.py` | Extended 4-classifier comparison | `output/classifier_comparison/classifier_comparison_results.json` |
| `seed_stability_experiment.py` | Seed stability analysis | `output/seed_stability/seed_stability_results.json` |
| `rerun_bio_validation.py` | Re-run failed bio validations | In-place in `output/<run>/biological_validation/` |
| `rerun_seed_bio_validation.py` | Re-run seed bio validations | `output/seed_stability/seed_stability_results.json` |
| `verify_gene_lists.py` | Sanity-check gene lists | stdout |
| `_rerun_bio_validation.py` | Internal helper: re-run biological validation for specific runs | In-place in `output/<run>/biological_validation/` |
| `run_publication_experiments.py` | Orchestrate all publication experiments end-to-end | Various `output/` sub-dirs |
| `run_grouping_comparison.py` | Compare 3 knowledge sources (DisGeNET, KEGG, maTE) × 3 datasets; optional Enrichr/STRING validation and export of STRING + top adjusted p-value metrics | `output/grouping_comparison_results.json` |
| `cross_dataset_transfer.py` | Evaluate bundle→dataset transfer with compatibility diagnostics and heatmaps; now supports CLI filters for bundle datasets, test datasets, and output directory | `output/cross_dataset_transfer/` (or custom via `--output-dir`) |
| `feature_space_overlap.py` | Compute pairwise feature-space overlap matrices (counts, Jaccard %, coverage %) across expression datasets and render a heatmap | `output/feature_space_overlap/` |
| `download_geo_series_matrix.py` | Download GEO GSE series matrix files and convert to GSM-compatible expression CSV (`class` + numeric features) using keyword-based label inference | `data/expression_data/<GSE>.csv` |
| `run_prostate_transfer_experiment.py` | Run prostate-focused transfer experiment (disease-matched setting) using selected bundles and test datasets | `output/cross_dataset_transfer_prostate/` |
| `finalize_publication.py` | Final checks and packaging for publication submission | — |

---

## `data/`

| Folder | Contents |
|--------|----------|
| `data/expression_data/` | GEO expression matrices (`.csv`, tracked by Git LFS) |
| `data/grouping_data/` | Gene-to-group knowledge mappings: DisGeNET disease-gene associations (`cancer-DisGeNET_gedinet.txt`), KEGG pathways (`kegg_genes_table_vFatma_pripath.csv`), miRNA targets (`mate_grouping_file.csv`) |
| `data/patient_data/` | Patient CSV files for clinical inference (auto-discovered by CLI) |
| `data/test/` | Small test fixtures for unit tests |
| `data/data_ARCHIVE/` | Archived/deprecated datasets |

---

## `models/`

| Folder | Contents |
|--------|----------|
| `models/pretrained/` | Pre-trained `.gsm.zip` bundles shipped with the repo (Git LFS). Both CLI and Streamlit auto-discover from here with `[pretrained]` label. |

### Publication Bundles (Random Forest, seed 44, 100 iterations)

| Bundle | Disease |
|--------|---------|
| `bundle_GDS1962_publication_RF.gsm.zip` | Glioblastoma |
| `bundle_GDS2545_publication_RF.gsm.zip` | Prostate Cancer |
| `bundle_GDS2547_publication_RF.gsm.zip` | Prostate Cancer (Lapointe) |
| `bundle_GDS2771_publication_RF.gsm.zip` | Lung Cancer |
| `bundle_GDS3257_publication_RF.gsm.zip` | Acute Myeloid Leukemia |
| `bundle_GDS3837_publication_RF.gsm.zip` | Colorectal Cancer |
| `bundle_GDS5499_publication_RF.gsm.zip` | Pancreatic Cancer |
| `README.md` | Bundle documentation |

---

## `tests/`

| File | Coverage |
|------|----------|
| `test_core_functions.py` | 29 tests: data loading, t-test, grouping, scoring, modeling, rank aggregation, bio validation, profiling |
| `test_inference.py` | 14 tests: model bundle save/load/info (3), inference engine correctness + missing features (4), clinical report generation (2), multi-bundle consensus inference (5) |
| `test_reproducibility.py` | 1 test: pipeline reproducibility verification (marked `@pytest.mark.slow`, excluded from default runs) |

---

## `output/` — Pipeline Outputs (gitignored)

Each pipeline run creates a timestamped folder. Organized subdirectories:

| Subfolder | Contents |
|-----------|----------|
| `main_runs/` | Production pipeline runs (7 datasets × RF) |
| `glasso_<timestamp>/` | Group Lasso runs (includes `group_lasso_results.json`, `gene_selection_frequency.xlsx`, `biological_validation/`) |
| `stability_test/` or `stability_gl_<ts>/` | Stability selection runs (`stability_results.json`, `stability_gene_probabilities.xlsx`, probability figures) |
| `gl_rf_hybrid_<dataset>_<ts>/` | GL→RF hybrid runs (`gl_rf_hybrid_results.json`, `hybrid_gene_frequency.xlsx`, comparison figures) |
| `comparison_gl_vs_gsm/` | GSM vs GL comparison (metrics, gene overlap, figures) |
| `gl_ablation_<dataset>_<ts>/` | Ablation study: duplication vs naive vs no-group L1 |
| `gl_all_datasets_<ts>/` | Multi-dataset GL evaluation with cross-dataset summary |
| `gl_hyperparam_<dataset>_<ts>/` | Hyperparameter grid search results and heatmaps |
| `classifier_comparison/` | XGBoost vs RF and extended classifier runs |
| `seed_stability/` | Seed stability experiment results |
| `cross_dataset_transfer/` | Cross-dataset transfer diagnostics (`transfer_results.csv/json`, transfer matrices, F1/AUC heatmaps, in-vs-out-domain figure) |
| `feature_space_overlap/` | Pairwise feature-space overlap diagnostics (`feature_overlap_*` CSVs, summary JSON, Jaccard heatmap figure) |
| `sensitivity_runs/` | Sensitivity analysis runs + results JSON |
| `baselines/` | Baseline comparison results |
| `benchmark/` | Scoring model benchmark results |
| `archives/` | Old compressed runs |

---

## `reports_ARCHIVE/` — Manuscript Artefacts (gitignored)

`manuscript_data.json`, `manuscript_figures/`, versioned manuscript builds,
supplementary PDFs, and related publications.

| Subfolder | Contents |
|-----------|----------|
| `manuscript_versions/` | Versioned GSM manuscripts in `v###/` folders. Each folder contains `GSM_Manuscript_v*.docx`, a `build_log.txt`, and an auto-generated `comparison_with_v*.md` against the previous version when available. |
| `group_lasso_manuscript/` | GL manuscript builder (`build_gl_manuscript.py`) and generated `GL_Manuscript_v*.docx` files. Accepts `--comparison-dir` for GSM vs GL data and reads bio validation results automatically. |

---

## `.github/` — CI & Copilot

| File | Purpose |
|------|---------|
| `copilot-instructions.md` | Coding conventions and AI agent guidelines |
| `workflows/tests.yml` | CI workflow — runs `pytest` on push/PR |

---

## `DOCS/` — Documentation

| File | Topic |
|------|-------|
| `DEVELOPMENT.md` | Project structure & coding standards |
| `RUNNING.md` | How to run the pipeline |
| `INSTALL_WSL.md` | WSL/Linux setup |
| `GITHUB_WORKFLOW.md` | Branching & PR guidelines |
| `COPILOT.md` | GitHub Copilot usage |
| `WEB_DEPLOYMENT.md` | Web deployment options, costs, and architecture for publishing inference as a website |
| `TROUBLESHOOTING.md` | Common fixes |
| `DATASET_EXCLUSIONS.md` | Rationale for excluding GDS3268 and GDS4206 |
| `CLINICAL_MODEL_SELECTION.md` | Clinician-facing guidance for disease-matched bundle selection and interpretation thresholds |
| `README.md` | Documentation index |
| `aggregated_group_ranking_explanation.txt` | Explanation of aggregated group ranking algorithm |
| `feature_ranking_methods_explanation.txt` | Explanation of feature ranking methods (RRA, etc.) |

---

## Key Conventions

| Parameter | Value | Notes |
|-----------|-------|-------|
| Default classifier | Random Forest | seed = 44, deterministic derivation per iteration |
| Iterations | 100 per run | Each iteration: new train/test split |
| FDR threshold | α = 0.05 | Welch t-test + Benjamini–Hochberg correction |
| CV folds (scoring) | 3-fold stratified | Phase II group evaluation |
| CV folds (validation) | 5-fold stratified | Phase III final model |
| Feature ranking | Robust Rank Aggregation | Stuart et al. method |
| Biological validation | Enrichr + STRING-db + DisGeNET | Optional, external APIs |
| Excluded datasets | GDS3268 (breast), GDS4206 (HCC) | See `DOCS/DATASET_EXCLUSIONS.md` |
| Supported classifiers | RF, XGBoost, DecisionTree, SVM, KNN, MLP | Via `get_classifier()` factory |
| Python version | 3.10+ | 3.11 or 3.12 recommended |
| Model bundle format | `.gsm.zip` | Top-10 models by F1 + scaler + feature names + metadata |
| Ensemble strategy | `mean_probability` (default) | Also supports `majority_vote` |
| Risk thresholds | HIGH ≥ 0.80, MEDIUM ≥ 0.55, LOW < 0.55 | Configurable in `inference_engine.py` |
| Per-sample importance | Perturbation-based local importance | Model-agnostic, ≤200 samples, top-50 candidates |

---

*Last updated: 2026-06-10*
