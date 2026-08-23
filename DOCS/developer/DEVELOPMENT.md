# Development Guide 🛠️

This guide explains how to *safely* make changes to the project.

If you are new to programming, think of this repo as:
- A **protocol** (the code)
- A **lab notebook** (the history in Git)
- A **shared freezer** (GitHub, where everyone stores the latest version)

---

## 1) Open the Project (WSL)

Make sure you are working inside Ubuntu/WSL, not directly on Windows paths.

### VS Code (recommended)

1. Open VS Code
2. `Ctrl+Shift+P` → **WSL: New WSL Window**
3. **File → Open Folder** → `~/GSM-to-python`
4. Verify: bottom-left should show `WSL: Ubuntu`

### Terminal

```bash
cd ~/GSM-to-python
code .
```

---

## 2) Use the Correct Python Environment

### VS Code

`Ctrl+Shift+P` → **Python: Select Interpreter** → choose the `venv` (or `.venv`) interpreter.

### Terminal

```bash
source venv/bin/activate
```

---

## 3) Project Structure

```
src/
├── data_processing/       # Data loading, preprocessing, normalization
├── feature_selection/     # t-test, variance, RFE, SelectKBest filters
├── grouping/              # Phase I: gene group projection (DisGeNET)
├── scoring/               # Phase II: group evaluation (3-fold CV)
├── modeling/              # Phase III: final classifier (5-fold CV)
├── machine_learning/      # ML model factory (RF, XGBoost, SVM, etc.)
├── utils/                 # Logging, saving, visualization, RRA, bio validation
├── workflows/             # Entry points + config dataclasses
└── ui/                    # Streamlit web interface

data/                      # Input datasets (GEO + DisGeNET)
output/                    # Pipeline results (timestamped folders)
tests/                     # Unit tests (pytest)
scripts/                   # Manuscript, experiments, maintenance
DOCS/                      # This documentation
```

For a complete function-level map, see [PROJECT_MAP.md](../../.ai_context/PROJECT_MAP.md).

### Data Flow

```
GSM_workflow.py (entry point)
  │
  ├── Load data (data_loader.py)
  ├── Preprocess (data_preprocess.py)
  ├── Filter genes (ttest_filter.py)          ← Phase I begins
  ├── Group genes (run_grouping.py)
  ├── Score groups (run_scoring.py)            ← Phase II
  ├── Model top groups (run_modeling.py)        ← Phase III
  ├── Aggregate rankings (rank_aggregation.py)
  ├── Generate figures (generate_figures.py)
  └── Biological validation (biological_validation.py)
```

---

## 4) Making Changes Safely

When you change code, avoid breaking the main branch for others.

**The safe pattern:**
1. Pull latest changes
2. Create a new branch for your work
3. Make small changes (one idea at a time)
4. Run tests to verify nothing broke
5. Commit and push
6. Open a Pull Request (PR)

The full Git workflow is in [GITHUB_WORKFLOW.md](GITHUB_WORKFLOW.md).

---

## 5) Running Tests

Tests verify that core functions still work after your edits.
Think of tests as an **automated checklist** that says "everything still works" or "something broke here".

### Run All Tests

```bash
# From the project root:
pytest
```

This runs **29+ unit tests** in about 2 seconds. You'll see green `PASSED` / red `FAILED` next to each test.

### Run a Specific Test

```bash
pytest tests/test_core_functions.py::test_my_function -v
```

### What Runs Automatically

| Trigger | What Runs | How |
|---------|-----------|-----|
| `git push` to `main` or `develop` | Full test suite | GitHub Actions |
| Pull Request | Full test suite | GitHub Actions |
| `git push` (local, if pre-commit installed) | Full test suite | Pre-commit hook |

**GitHub Actions:** Every push and PR runs tests automatically. Failed tests show a red ✗ on the PR. Check the "Actions" tab on GitHub for details.

**Pre-commit hook (optional):** Runs tests before every push so broken code never reaches GitHub:

```bash
pip install pre-commit
pre-commit install --hook-type pre-push
```

### Writing New Tests

Tests live in `tests/test_core_functions.py`:

```python
def test_my_new_function():
    """Describe what you are testing."""
    result = my_function(input_data)
    assert result == expected, "Helpful message if it fails"
```

Guidelines:
- Test name must start with `test_`
- Keep each test short and focused on one thing
- Use small, synthetic data (not real datasets)
- Run `pytest` after every change

---

## 6) Data & Large File Storage (LFS)

Because this pipeline works with biological datasets and generates machine learning bundles (`.gsm.zip`), we **must** use Git LFS to keep the repository lightweight. If you commit a 50MB CSV without LFS, it breaks GitHub pushes for everyone.
- Always run `git lfs install` on your system.
- Before committing any `.csv`, `.zip`, `.xlsx`, or `.txt` in the `data/` folder, ensure it is covered by the `.gitattributes` file.
- If you're adding a new large file format, track it explicitly: `git lfs track "*.xyz"`

---

## 7) Coding Standards

This project aims to be understandable by researchers who are not Python experts.

### Keep It Simple

- **One function = one task**, max 20 lines
- **Clear names** over short names (`calculate_gene_score` not `calc_gs`)
- **Type hints** on all function signatures
- **Docstrings** on all public functions
- **Max 2 levels of nesting** (avoid deep if/else/for chains)

### Use Dataclasses for Data Structures

```python
from dataclasses import dataclass

@dataclass
class GeneGroup:
    name: str
    genes: list[str]
    score: float = 0.0
```

**Never** use plain dicts, tuples, or named tuples for structured data.

### Comments and Section Separators

```python
##### DATA PREPROCESSING #####

def preprocess_data(raw_data: pd.DataFrame, *, logger: Logger) -> pd.DataFrame:
    """Transform raw gene data into analysis-ready format.

    Args:
        raw_data: Raw expression matrix
        logger: Logger instance

    Returns:
        Cleaned and normalized DataFrame
    """
    logger.info("Starting data preprocessing...")
```

### Error Handling

```python
class GeneAnalysisError(Exception):
    """Base exception for gene analysis errors."""
    pass

def analyze_genes(genes: list[str], *, logger: Logger) -> GeneResults:
    try:
        logger.info(f"Analyzing {len(genes)} genes...")
        # ...
    except ValueError as e:
        logger.error(f"Analysis failed: {e}")
        raise GeneAnalysisError(f"Gene analysis failed: {e}")
```

---

## 8) Testing Your Changes

After editing code, always verify:

### Quick Smoke Test

```bash
python run_test.py
```

### Full Test Suite

```bash
pytest
```

### Streamlit UI

```bash
streamlit run src/ui/app.py
```

### Full Pipeline

```bash
python -m src.workflows.GSM_workflow
```

---

## 9) Share Your Changes

See [GITHUB_WORKFLOW.md](GITHUB_WORKFLOW.md) for the complete guide on branching, committing, and submitting Pull Requests.

**TL;DR:**
1. Create a branch (`yourname-short-task`)
2. Make changes + run tests
3. Commit with a clear message
4. Push to GitHub
5. Open a Pull Request
6. Wait for review + merge

---

## 10) Getting Help

If you get stuck:
1. Copy the **exact command** you ran
2. Copy the **full error message**
3. Note whether you're in **WSL** or **Windows**
4. Ask a colleague, open a GitHub issue, or ask GitHub Copilot

> **Important:** Avoid pasting sensitive patient data into AI tools.

See also:
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common fixes
- [INSTALLATION.md](INSTALLATION.md) — WSL-specific issues
