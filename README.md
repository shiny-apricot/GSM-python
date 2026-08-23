# GSM Bioinformatics Pipeline 🧬

> **Grouping–Scoring–Modeling (GSM):** A modular Python pipeline for
> identifying disease-associated gene groups from GEO expression data
> using machine learning and biological knowledge (DisGeNET).

[![Tests](https://github.com/shiny-apricot/GSM-to-python/actions/workflows/tests.yml/badge.svg)](https://github.com/shiny-apricot/GSM-to-python/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## How It Works

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
                         MODEL BUNDLE (.gsm.zip)
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                  CLI      Web UI     Python API
                    │          │          │
                    ▼          ▼          ▼
              CLINICAL INFERENCE
              (ensemble prediction + report)
```

1. **Filter** — Welch t-test + Benjamini–Hochberg FDR (α = 0.05)
2. **Group** — Project surviving genes onto DisGeNET disease-gene groups
3. **Score** — Evaluate each group with 3-fold stratified CV (Random Forest)
4. **Model** — Train final classifier on top-ranked groups (5-fold CV)
5. **Rank** — Robust Rank Aggregation across 100 iterations
6. **Validate** — Enrichr + STRING-db + DisGeNET biological enrichment
7. **Bundle** — Save top-10 models as a `.gsm.zip` for clinical inference
8. **Infer** — Diagnose new patient samples using ensemble predictions

---

## Latest Results (7 Cancer Datasets)

| Dataset | Disease | Samples | F1 | AUC | Groups | Features |
|---------|---------|--------:|----:|-----:|-------:|---------:|
| GDS1962 | Glioblastoma | 26 | 1.000 | 1.000 | 1 | 67 |
| GDS2545 | Prostate | 89 | 0.842 | 0.887 | 11 | 180 |
| GDS2547 | Prostate (Lapointe) | 89 | 0.870 | 0.911 | 9 | 108 |
| GDS2771 | Lung | 118 | 0.849 | 0.829 | 1 | 9 |
| GDS3257 | AML | 107 | 1.000 | 1.000 | 2 | 146 |
| GDS3837 | Colorectal | 70 | 1.000 | 1.000 | 2 | 442 |
| GDS5499 | Pancreatic | 140 | 1.000 | 1.000 | 5 | 51 |

**Mean F1 = 0.937 | Mean AUC = 0.947 | 4/7 datasets achieve perfect F1 = 1.00**

> Two additional datasets (GDS3268 Breast, GDS4206 HCC) were excluded due
> to severe t-test filtering issues — see [DATASET_EXCLUSIONS.md](DOCS/methods/DATASET_EXCLUSIONS.md).

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation (WSL/Linux)](DOCS/INSTALLATION.md) | Step-by-step setup for Windows (WSL2) and native Linux |
| [Running the Pipeline](DOCS/RUNNING.md) | CLI, batch runner, Streamlit UI, `screen` for long jobs |
| [Development Guide](DOCS/developer/DEVELOPMENT.md) | Project structure, testing, coding standards |
| [GitHub Workflow](DOCS/developer/GITHUB_WORKFLOW.md) | Branching, PRs, and safe collaboration |
| [Troubleshooting](DOCS/TROUBLESHOOTING.md) | Common errors and fixes |
| [GitHub Copilot Guide](DOCS/developer/COPILOT.md) | AI-assisted coding setup |
| [Project Map](.ai_context/PROJECT_MAP.md) | Complete file/folder/function reference |
| [Feature Ranking Methods](DOCS/methods/FEATURE_METHODS.md) | Explains the two methods for feature ranking |
| [Aggregated Ranking](DOCS/methods/RANKING_EXPLANATION.md) | Explains robust rank aggregation (RRA) |
| [Dataset Exclusions](DOCS/methods/DATASET_EXCLUSIONS.md) | Why GDS3268 and GDS4206 were dropped |
| [Web Deployment](DOCS/advanced/WEB_DEPLOYMENT.md) | Options for publishing inference as a website |

---

## Clinical Inference 🏥

After training, the pipeline automatically saves a **model bundle** (`.gsm.zip`)
containing the top-10 fitted models, the normalization scaler, feature names,
and full training metadata. This bundle can be used to diagnose new patient
samples via **three interfaces**.

**Multi-Bundle Inference:** Combine models from multiple datasets (e.g. prostate
+ lung + colorectal) for more robust, cross-validated predictions. Each bundle
contributes independently; the consensus is weighted by training F1.

### Quick Start — Interactive CLI (Recommended)

```bash
# Launch the interactive guided menu — no arguments needed
python run_gsm.py
```

The interactive mode walks you through dataset selection, classifier choice,
iteration count, and more — with numbered menus and color-coded output.

![GSM CLI Interactive Menu](assets/gsm_cli.png)

### Quick Start — Direct Commands

```bash
# 1. Train and produce a model bundle
python run_gsm.py train --data data/expression_data/GDS2545.csv \
                     --groups data/grouping_data/cancer-DisGeNET_gedinet.txt

# 2. Inspect the bundle
python run_gsm.py bundle-info --bundle output/.../bundles/bundle_GDS2545_*.gsm.zip

# 3. Run inference on new patient samples
python run_gsm.py infer --bundle output/.../bundles/bundle_GDS2545_*.gsm.zip \
                     --patients new_patients.csv \
                     --output results/

# 4. Multi-bundle inference (combine multiple datasets)
python run_gsm.py multi-infer \
    -b output/.../bundle_GDS2545_*.gsm.zip \
       output/.../bundle_GDS3257_*.gsm.zip \
    -p new_patients.csv
```

### Quick Start — Python API

```python
from src.inference import load_bundle, infer
from src.inference.clinical_report import save_clinical_report
import pandas as pd, logging

logger = logging.getLogger("inference")
bundle = load_bundle("output/.../bundles/bundle_GDS2545.gsm.zip", logger=logger)
patients = pd.read_csv("new_patients.csv")

summary = infer(bundle, patients, logger=logger)
for r in summary.results:
    print(f"{r.sample_id}: {r.predicted_label} "
          f"(confidence={r.confidence:.1%}, risk={r.risk_level})")

save_clinical_report(summary, Path("results/"), logger)
```

### Quick Start — Streamlit Web UI

```bash
streamlit run src/ui/app.py
# Click "🏥 Clinical Inference" → upload bundle → upload patient CSV → Run
```

### What the Report Contains

Each patient receives:
- **Predicted class** (disease / control) with mapped label
- **Confidence score** (0–100%, distance from decision boundary)
- **Risk level** — HIGH (≥ 80%), MEDIUM (≥ 55%), LOW (< 55%)
- **Model agreement** — fraction of ensemble models that concur
- **Top contributing genes** — per-sample feature importance
- **Research disclaimer** — not a clinical diagnosis

Reports are saved as both `.txt` (human-readable) and `.xlsx` (machine-readable).

### Patient Data Format

The patient CSV should have **gene names as column headers**, matching the
training data platform. Missing features are zero-filled; if >50% are
missing, inference is refused. A sample-ID column is optional.

```csv
sample_id,TP53,BRCA1,EGFR,MYC,...
patient_001,5.23,3.11,7.89,2.45,...
patient_002,4.87,2.99,6.54,3.01,...
```

---

## CLI vs Streamlit — Two Interfaces, One Pipeline

GSM ships with **two front-ends** that share the same engine:

| Feature | CLI (`python run_gsm.py`) | Streamlit (`streamlit run src/ui/app.py`) |
|---------|----------------------|------------------------------------------|
| **Best for** | Power users, automation, SSH servers | Visual exploration, demos, non-coders |
| **Training** | Foreground or background jobs | Single-click with live log streaming |
| **Advanced params** | Interactive prompts + `--flags` | Collapsible sidebar panel |
| **Batch runs** | `run_all_datasets.py` or shell scripts | Not supported (single run at a time) |
| **Output browser** | Table view with status indicators | Paginated cards with embedded figures |
| **Inference** | Works offline, scriptable | Drag-and-drop CSV upload |
| **Deployment** | Any Linux server / CI pipeline | HuggingFace Spaces / Streamlit Cloud |

**Rule of thumb:** Use the CLI for reproducible research and batch
experiments; use the Streamlit app for presentations, demos, and sharing
with collaborators who don't use the terminal.

---

## Quick Start

### Video Tutorial

[![Project Setup Tutorial](https://img.youtube.com/vi/brYpWo7VfK0/0.jpg)](https://www.youtube.com/watch?v=brYpWo7VfK0&feature=youtu.be)

### Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended)
- **Git** with [Git LFS](https://git-lfs.com/) installed
- **Linux** or **Windows with WSL2** (see [Installation Guide](DOCS/INSTALLATION.md))

### 1. Clone & Fetch Data

```bash
# Install Git LFS (once per machine)
sudo apt install git-lfs   # Ubuntu/Debian
# brew install git-lfs      # macOS

git lfs install
git clone https://github.com/shiny-apricot/GSM-to-python.git
cd GSM-to-python

# If data files are pointer stubs (< 1 KB):
git lfs pull
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r dependencies.txt
```

### 4. Run the Pipeline

```bash
# Quick test — verify everything works (~1-2 min)
python run_gsm.py train --test

# Full single-dataset run (edit config first)
python run_gsm.py train

# Batch run on all 7 datasets (100 iterations each)
python scripts/experiments/run_all_datasets.py --iterations 100

# Streamlit Web UI (training + inference)
streamlit run src/ui/app.py

# Interactive CLI (guided menu — recommended for first use)
python run_gsm.py

# Direct CLI commands
python run_gsm.py train --test --iterations 3
python run_gsm.py infer --bundle output/.../bundle.gsm.zip --patients data.csv
python run_gsm.py bundle-info --bundle output/.../bundle.gsm.zip
python run_gsm.py ui                    # Launch Streamlit dashboard
```

For detailed setup, see the [Installation Guide](DOCS/INSTALLATION.md).

---

## Running Options

### Quick Test
```bash
python run_gsm.py train --test            # Sample data, 3 iterations (~1 min)
python run_gsm.py train --test -n 5       # Custom iteration count
python run_gsm.py train                   # Real data (interactive)
```

### Single Dataset
Edit `src/workflows/GSM_workflow_config.py`, then:
```bash
python src/workflows/GSM_workflow.py
# If import errors occur:
python -m src.workflows.GSM_workflow
```

### Batch Run (Multiple Datasets)
```bash
python scripts/experiments/run_all_datasets.py                              # All 7 datasets, 100 iterations
python scripts/experiments/run_all_datasets.py --iterations 50              # Custom iterations
python scripts/experiments/run_all_datasets.py --datasets GDS2545 GDS3257   # Specific datasets
python scripts/experiments/run_all_datasets.py --list                       # List available datasets
```

For long-running jobs, use `screen` to keep them alive after disconnecting:
```bash
screen -S gsm_batch
python scripts/experiments/run_all_datasets.py --iterations 100
# Ctrl+A then D to detach — reattach later with: screen -r gsm_batch
```

### Clinical Inference (after training)
```bash
# Via CLI
python run_gsm.py infer --bundle output/.../bundles/bundle_GDS2545.gsm.zip \
                     --patients new_patients.csv --output inference_results/

# Via Streamlit
streamlit run src/ui/app.py   # Click "🏥 Clinical Inference" tab
```

---

## Output Structure

Each run creates a timestamped folder under `output/` containing:

| Category | Files |
|----------|-------|
| **Summary** | `summary_report.txt`, `modeling_results_all_iterations.json`, `modeling_results_statistics.xlsx` |
| **Rankings** | `aggregated_group_ranking_rra.xlsx`, `aggregated_feature_ranking_group_derived_rra.xlsx` ⭐, per-iteration rankings |
| **Figures** | 15+ publication-ready plots (boxplots, heatmaps, feature importance, ROC curves) in `figures/` |
| **Statistics** | Performance by group count, feature importance, CV confidence intervals in `figures/` |
| **Config** | `run_parameters.txt`, `config_used.py`, `gsm_workflow.log` |
| **Bio Validation** | Enrichr, STRING-db, DisGeNET results in `biological_validation/` (if enabled) |

---

## Project Structure

```
GSM-to-python/
├── src/                        # Core pipeline code
│   ├── data_processing/        #   Data loading, preprocessing, filtering
│   ├── feature_selection/      #   t-test, variance, RFE, SelectKBest
│   ├── grouping/               #   Phase I: gene group projection
│   ├── scoring/                #   Phase II: group evaluation
│   ├── modeling/               #   Phase III: final classifier
│   ├── machine_learning/       #   ML model factory (RF, XGBoost, etc.)
│   ├── inference/              #   Clinical inference: bundles, engine, reports
│   ├── utils/                  #   Logging, saving, visualization, RRA
│   ├── workflows/              #   Entry points & configs
│   ├── ui/                     #   Streamlit web interface
│   └── cli.py                  #   Unified CLI (train / infer / bundle-info)
├── scripts/                    # Manuscript, baselines, batch runners, analysis
├── data/                       # GEO expression matrices + DisGeNET mappings
├── tests/                      # 44 unit tests (pytest)
├── output/                     # Pipeline results + model bundles (gitignored)
├── DOCS/                       # User & developer documentation
├── gsm/                        # Package entry point (python run_gsm.py)
├── dependencies.txt            # pip requirements
└── .ai_context/PROJECT_MAP.md    # Complete file/function reference
```

See [PROJECT_MAP.md](.ai_context/PROJECT_MAP.md) for the full function-level reference.

---

## Key Parameters

| Parameter | Default |
|-----------|---------|
| Classifier | Random Forest (seed = 44) |
| Iterations | 100 per run |
| FDR threshold | α = 0.05, Welch t-test + Benjamini–Hochberg |
| Scoring CV | 3-fold stratified |
| Validation CV | 5-fold stratified |
| Feature ranking | Robust Rank Aggregation (Stuart et al.) |
| Biological validation | Enrichr + STRING-db + DisGeNET |
| Model bundle | Top-10 models by F1 in `.gsm.zip` |
| Ensemble strategy | Mean probability (also: majority vote) |
| Risk thresholds | HIGH ≥ 80%, MEDIUM ≥ 55%, LOW < 55% |

---

## Recommended VS Code Extensions

- **Python** — IntelliSense, linting, debugging
- **Remote - WSL** — Develop inside WSL from Windows
- **GitHub Copilot Chat** — AI-assisted coding and Q&A
- **Rainbow CSV** — Color-coded CSV viewing
- **vscode-pdf** — View PDF files directly in VS Code
- **TODO Highlight** — Track TODOs in code
- **GitHub Pull Requests** — Review PRs inside VS Code

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and
[DOCS/developer/GITHUB_WORKFLOW.md](DOCS/developer/GITHUB_WORKFLOW.md) for the branch/PR workflow.

---

## Troubleshooting

Common issues and fixes are documented in [DOCS/TROUBLESHOOTING.md](DOCS/TROUBLESHOOTING.md).
WSL-specific problems are covered in [DOCS/INSTALLATION.md](DOCS/INSTALLATION.md).

### Common Issues
1. **ImportError or ModuleNotFoundError**:
   - Verify your virtual environment is activated
   - Reinstall dependencies: `pip install -r dependencies.txt`

2. **Permission denied errors**:
   - Check file permissions: `chmod +x src/name_of_your_file`


## Contributing
1. Create a new branch
2. Make your changes
3. Commit your changes 
4. Push to the branch 
5. Create a new Pull Request

## License
This project is licensed under the MIT License. See the LICENSE file for more details.

## Contact
For any questions or issues, please open an issue on the repository or contact the project maintainers.
