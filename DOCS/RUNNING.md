# Running the GSM Pipeline 🚀

This project can be run in multiple ways:

| Method | Best For | Time |
|--------|----------|------|
| **Quick Test** | Verifying setup works | ~1-2 min |
| **Single Dataset** | Full analysis on one dataset | 10-30 min |
| **Batch Runner** | All 7 datasets | 2-6 hours |
| **Streamlit UI** | Interactive exploration | Variable |
| **CLI (train)** | Scriptable training + bundle | 10-30 min |
| **CLI (infer)** | Diagnose new patients | ~10 sec |

---

## Before You Run Anything

### VS Code (recommended)

Make sure VS Code is connected to WSL:
1. Bottom-left should show `WSL: Ubuntu`
2. If not: `Ctrl+Shift+P` → **WSL: New WSL Window** → open the project folder
3. Select the Python environment: `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.venv` or `venv`

### Terminal

```bash
cd ~/GSM-to-python
source venv/bin/activate      # Adjust to .venv if that's what you used
```

If you don't have an environment yet, see [INSTALLATION.md](INSTALLATION.md).

---

## 1) Quick Test (Start Here!)

Before running on real data, verify everything works:

```bash
# Quick test with sample data (3 iterations, ~1-2 minutes)
python run_test.py

# Test with more iterations
python run_test.py --iterations 5

# Test with real data (small run)
python run_test.py --real-data --iterations 3
```

**Expected output:** A summary showing F1/AUC scores. If you see that, you're ready!

---

## 2) Single Dataset Run

Edit the configuration file first:

```bash
# Open in VS Code or any editor
code src/workflows/GSM_workflow_config.py
```

Key settings to check:
- `expression_file` — path to your GEO expression CSV
- `grouping_file` — path to DisGeNET grouping data
- `n_iterations` — number of iterations (default: 100)
- `classifier_type` — "random_forest" (default), "xgboost", etc.

Then run:

```bash
python src/workflows/GSM_workflow.py

# If import errors occur, use module form:
python -m src.workflows.GSM_workflow
```

---

## 3) Batch Run (Multiple Datasets)

Process multiple datasets in one go:

```bash
# All 7 datasets, 100 iterations each
python run_all_datasets.py

# Custom iterations
python run_all_datasets.py --iterations 50

# Specific datasets only
python run_all_datasets.py --datasets GDS2545 GDS3257

# List available datasets
python run_all_datasets.py --list
```

### Keeping Jobs Running (Advanced Trick)

For long jobs (2+ hours), you might want to learn a terminal trick called `screen`. This lets the job keep running even if you accidentally close your terminal window. *If you run the pipeline directly inside VS Code integrated terminal and keep VS Code open, you don't need this.*

```bash
# 1. Create a named background session
screen -S gsm_batch

# 2. Start the job as usual
cd ~/GSM-to-python
source venv/bin/activate
python run_all_datasets.py --iterations 100

# 3. Leave it running in the background (Detach)
#    Press [Ctrl+A], let go, then press [D].
#    You can now safely close the window.

# 4. Check on it later
screen -r gsm_batch
```

**Quick reference:**

| Action | Command |
|--------|---------|
| Create session | `screen -S name` |
| Detach (leave running) | `Ctrl+A`, then `D` |
| List sessions | `screen -ls` |
| Reattach | `screen -r name` |
| Kill session (from inside) | `exit` |

**Common mistake:** Closing the terminal without detaching kills the job. Always `Ctrl+A, D` first!

**Alternative (simpler, less control):**

```bash
nohup python run_all_datasets.py --iterations 100 > batch_run.log 2>&1 &

# Monitor progress:
tail -f batch_run.log

# Find/kill the process:
ps aux | grep run_all_datasets
pkill -f run_all_datasets
```

---

## 4) Streamlit Web UI

```bash
streamlit run src/ui/app.py
```

Open the URL it prints (usually `http://localhost:8501`) in your browser.

**In the UI you can:**
- Upload expression data (CSV)
- Upload group definitions (CSV/TXT)
- Configure pipeline parameters
- Run the pipeline and view plots + summary
- **Run clinical inference** on new patient samples (🏥 tab)

> **WSL tip:** If the URL doesn't auto-open, manually paste it into your Windows browser.
> If `localhost` doesn't work, try `http://127.0.0.1:8501`.
> See [INSTALLATION.md](INSTALLATION.md#cannot-connect-to-localhost--streamlit-url-doesnt-open) for more network fixes.

---

## 5) Unified CLI (`python -m gsm`)

The CLI supports an **interactive guided menu** (no arguments) and **direct
subcommands** (`train`, `infer`, `bundle-info`, `ui`). Uses `rich` for
color-coded output, panels, and tables.

### Interactive Mode (Recommended for First Use)

```bash
# Launch the guided menu — walks you through every step
python -m gsm
```

The menu lets you:
- Select a dataset from `data/expression_data/`
- Pick a classifier (RandomForest, XGBoost, etc.)
- Configure iterations, seed, and biological validation
- Review a summary table before starting
- After training: inspect bundles and run inference

### Train and Save Model Bundle

```bash
# Quick test run (3 iterations, test data)
python -m gsm train --test --iterations 3

# Full run on real data
python -m gsm train --data data/expression_data/GDS2545.csv \
                     --groups data/grouping_data/cancer-DisGeNET_gedinet.txt \
                     --iterations 100

# With custom options
python -m gsm train --data data/expression_data/GDS2545.csv \
                     --groups data/grouping_data/cancer-DisGeNET_gedinet.txt \
                     --model XGBoost --seed 88 --iterations 50 --no-bio-validation
```

After training, a `.gsm.zip` model bundle is automatically saved in `output/<run>/bundles/`. 

> **What is a `.gsm.zip` bundle?** Think of it as a "save file" that freezes the fully trained AI model and all biological group rules into a single zip file. You can share this file with other labs or clinicians so they can predict disease on their own patients without needing to retrain anything.

### Inspect a Model Bundle

```bash
python -m gsm bundle-info --bundle output/.../bundles/bundle_GDS2545_*.gsm.zip
```

Shows: dataset, classifier, number of models, features, groups,
ensemble F1/AUC, per-model metrics, and file size — without
loading the heavy model files.

### Run Clinical Inference

```bash
# Basic usage
python -m gsm infer --bundle output/.../bundles/bundle_GDS2545.gsm.zip \
                     --patients new_patients.csv

# With output directory and sample ID column
python -m gsm infer --bundle output/.../bundles/bundle_GDS2545.gsm.zip \
                     --patients new_patients.csv \
                     --output inference_results/ \
                     --sample-id-column sample_id
```

**Output:** Per-patient predictions printed to console + saved as
`clinical_report_*.txt` and `clinical_report_*.xlsx`.

### Multi-Bundle Inference (Cross-Dataset Consensus)

Combine models trained on different datasets for more robust predictions:

```bash
python -m gsm multi-infer \
    -b output/.../bundle_GDS2545_*.gsm.zip \
       output/.../bundle_GDS3257_*.gsm.zip \
       output/.../bundle_GDS3837_*.gsm.zip \
    -p new_patients.csv
```

Each bundle independently preprocesses the patient data using its own
scaler and feature set, then the predictions are merged into a weighted
consensus (weighted by each bundle's training F1 score).

**Output:** `multi_bundle_report_*.txt` and `multi_bundle_report_*.xlsx`
with per-bundle breakdowns and consensus predictions.

Each patient receives:
| Field | Description |
|-------|-------------|
| Predicted Class | `positive` / `negative` |
| Predicted Label | Mapped label (e.g. `disease` / `control`) |
| Confidence | 0–100% (distance from decision boundary) |
| Risk Level | HIGH (≥80%), MEDIUM (≥55%), LOW (<55%) |
| Model Agreement | Fraction of ensemble models that concur |
| Top Genes | Per-sample feature importance |

### Patient Data Format

Your patient CSV should have **gene names as column headers**
matching the training data platform:

```csv
sample_id,TP53,BRCA1,EGFR,MYC,...
patient_001,5.23,3.11,7.89,2.45,...
patient_002,4.87,2.99,6.54,3.01,...
```

- A `sample_id` column is optional (use `--sample-id-column` to specify)
- Missing features are auto-filled with zeros
- If >50% of features are missing, inference is refused (platform mismatch)
- Label columns (`class`, `label`, `target`) are automatically dropped

---

## Where Results Are Saved

Each run creates a **timestamped folder** under `output/`:

```
output/
└── gsm_2026_02_18-10_30_00_GDS2545_seed44_cancer-DisGeNET_gedinet/
    ├── summary_report.txt                    # Human-readable summary
    ├── modeling_results_all_iterations.json   # Detailed JSON results
    ├── modeling_results_statistics.xlsx       # Performance statistics
    ├── aggregated_group_ranking_rra.xlsx      # RRA group rankings
    ├── aggregated_feature_ranking_*.xlsx      # RRA feature rankings
    ├── run_parameters.txt                    # Config used
    ├── gsm_workflow.log                      # Detailed logs
    ├── bundles/                              # Model bundles for inference
    │   └── bundle_GDS2545_2026_02_18-10_30_00.gsm.zip
    ├── figures/                              # 15+ plots
    │   ├── performance_boxplot.png
    │   ├── feature_importance.png
    │   └── statistics_*.xlsx
    └── biological_validation/                # If enabled
        ├── enrichr_results.xlsx
        ├── string_network.xlsx
        └── disgenet_results.xlsx
```

---

## Where Input Data Lives

The repository includes example data under `data/`:

| Folder | Contents |
|--------|----------|
| `data/expression_data/` | GEO expression matrices (CSV, tracked by Git LFS) |
| `data/grouping_data/` | DisGeNET gene-disease group mappings |
| `data/test/` | Small test fixtures |

For your own experiments, place raw input files under `data/`.

---

## If Something Goes Wrong

| Problem | Quick Fix |
|---------|-----------|
| Import errors | Use `python -m src.workflows.GSM_workflow` |
| "No module named X" | `pip install -r dependencies.txt` |
| Streamlit won't open | Try `http://127.0.0.1:8501` |
| Port already in use | `streamlit run src/ui/app.py --server.port 8502` |
| Job killed on disconnect | Use `screen` (see above) |
| "No matching features" in inference | Patient data uses different gene naming — check platform |
| "Too many features missing" | Patient CSV may be from a different microarray platform |
| Bundle not found after training | Check `output/<run>/bundles/` for `.gsm.zip` files |
| sklearn version warning | Bundle was saved with a different sklearn; may still work |

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more fixes.
