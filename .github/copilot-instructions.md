# GSM Bioinformatics Pipeline — Development Guide 🧬

> **Stable conventions only** — This file contains coding standards,
> design principles, and documentation rules that rarely change.
>
> For the **project map** (every file, folder, key function, and current
> defaults) see **[`PROJECT_MAP.md`](../PROJECT_MAP.md)** in the repo root.
> That file is the living document that AI agents and contributors should
> update whenever files are added, removed, or renamed.
> Check and analyze `PROJECT_MAP.md` before making any code changes to understand the current structure and conventions.

---

## How the AI Agent Should Think 🧠

These are the general principles for how AI coding assistants (Copilot,
Cursor, Claude, etc.) should approach work on this project.  They apply
to every file, every prompt, every task — not just GSM-specific code.

### Intent over instruction
Do not strictly and blindly follow the instructions in a prompt.
Instead, use your judgement, creativity, and knowledge to decide how
to best respond while still adhering to the overall goals and
principles of the project.  If the user asks for X but X would break
the architecture, propose a better alternative.  If the prompt is
ambiguous, choose the interpretation that produces the most useful
result — then mention what you assumed.

### Think holistically
Before making any change, ask yourself:
- **Why** does this change exist?  What problem does it solve?
- **Where** does it fit in the architecture?  (See Big-Picture
  Architecture below.)
- **What else** will it affect?  Other modules, tests, docs,
  deployment?
- **Could it be simpler?**  The best code is the code you don't write.

### Progressive refinement
Large tasks should follow a plan → implement → verify loop:
1. **Plan** — Write a temporary roadmap file (`.roadmap_<name>.md`)
   with concrete steps.  This is more reliable than mental to-do
   lists because the agent's to-do step limit is small.
2. **Implement** — Work through the plan one step at a time.
3. **Verify** — After each meaningful change, run `pytest` and fix
   any failures before moving on.  Never hand back broken code.
4. **Clean up** — Delete the roadmap file.  Update `PROJECT_MAP.md`
   if the change added/removed/renamed files or functions.

### Testing discipline
- At the end of **every** response that modifies code, run
  `pytest` and fix any failures.
- If a new function is non-trivial, add a test.
- If a bug is fixed, add a regression test.
- Never skip tests to save time — broken tests invalidate
  everything built on top.

### Communication style
- Be concise.  The user is a researcher, not a tourist.
- Show what you did (file names, line numbers), not just what you
  plan to do.
- When multiple valid approaches exist, pick the best one and
  explain why in one sentence — don't present a menu unless the
  choice genuinely matters.
- At the end, give a short summary of what changed and confirm
  tests pass.

### When to ask vs. act
- **Act** when the intent is clear, even if details are missing —
  fill in sensible defaults and mention them.
- **Ask** only when the choice is genuinely ambiguous and has
  irreversible consequences (e.g. deleting data, changing a public
  API).
- Never ask for permission to continue after an intermediate step.
  Just continue.

---

## Big-Picture Architecture 🗺️

Before touching any code, understand the **three concentric layers**:

```
┌─────────────────────────────────────────────────────┐
│                  USER INTERFACES                     │
│   CLI (src/cli.py)  ·  Streamlit (src/ui/app.py)   │
│   ─── both call the same engine, never each other ──│
├─────────────────────────────────────────────────────┤
│                 WORKFLOW ENGINE                       │
│   gsm_run()  in  src/workflows/GSM_workflow.py      │
│   ─── single entry point for the full pipeline ──── │
│   config defaults  in  GSM_workflow_config.py       │
├─────────────────────────────────────────────────────┤
│               DOMAIN MODULES                         │
│   filter → group → score → model → rank → validate  │
│   src/filter/  src/grouping/  src/scoring/           │
│   src/modeling/  src/ranking/  src/biological_valid/ │
│   src/inference/  (post-training prediction)         │
└─────────────────────────────────────────────────────┘
```

**Golden rule:** Data flows **downward** through the layers.
A UI never imports from another UI. A domain module never imports
from the workflow engine. The workflow engine orchestrates domain
modules only. Shared utilities live in `src/utils/`.

### Data lifecycle in one sentence

Raw CSV → t-test filter → DisGeNET group projection → per-group
CV scoring → aggregated model → rank features → biological
validation → `.gsm.zip` bundle → clinical inference.

### Module communication patterns

1. **Workflow → Domain:** The workflow engine calls domain functions
   with explicit arguments + a logger. It never stores global state.
2. **Domain → Domain:** Domain modules should NOT import each other.
   If module A needs output from module B, the workflow engine passes
   it as a parameter.
3. **UI → Workflow:** Both CLI and Streamlit call `gsm_run()` with
   keyword arguments. Neither accesses domain modules directly (except
   `src/inference/` for post-training inference).
4. **Bundle boundary:** A `.gsm.zip` bundle is the serialization
   boundary. Everything needed for inference lives inside the zip.
   Inference code must NEVER depend on training-time globals.

---

## Core Development Principles

### 1. Code Organization 🏗️
- Write modular, single-responsibility components
- Follow top-down development approach:
  1. Start with main pipeline function (gsm_pipeline.py)
  2. Implement major stage functions (filter.py, group.py, score.py, model.py)
  3. Break down each stage into smaller helper functions
  4. Create utility functions last
- Prefer pure functions over classes
- Use dataclasses for data structures and results (not for configuration)
- NEVER use dictionaries, tuples, or named tuples for data - always use dataclasses instead
- Do not create additional file for dataclasses, define them in the same file where they are used
- If a function returns multiple values, use a dataclass to encapsulate them.

Additional guardrails:
- Keep functions short (<= 20 lines) with minimal nesting.
- Use clear, non-technical comments when explaining pipeline logic.
- Keep output files stable and backward-compatible unless stated.

Example of top-down hierarchy:
```python
# Level 1: Main Pipeline (gsm_pipeline.py)
def gsm_pipeline(input_data: GeneData, logger: Logger) -> Results:
    """Main pipeline orchestrating the entire GSM analysis."""
    filtered_data = filter_genes(input_data, logger)
    groups = group_genes(filtered_data, logger)
    scores = score_groups(groups, logger)
    return train_model(scores, logger)

# Level 2: Major Stage (group.py)
def group_genes(filtered_data: FilteredData, logger: Logger) -> list[GeneGroup]:
    """Major stage function for gene grouping."""
    normalized_data = normalize_expression(filtered_data)
    clusters = perform_clustering(normalized_data)
    return create_gene_groups(clusters)

# Level 3: Helper Functions (grouping/cluster_utils.py)
def perform_clustering(normalized_data: np.ndarray) -> np.ndarray:
    """Helper function for specific clustering logic."""
    # Implementation details
```

```python
from dataclasses import dataclass

@dataclass
class GeneGroup:
    name: str
    genes: list[str]
    score: float = 0.0
```

### 2. Code Clarity for Non-Python Experts
- Write self-documenting code
- Include detailed comments in plain English
- Add visual separators for code sections
```python
##### DATA PREPROCESSING #####
def preprocess_gene_data(data: GeneData, logger: Logger) -> ProcessedData:
    """Transform raw gene data into analysis-ready format.
    
    Example:
        raw_data = load_data("genes.csv")
        processed = preprocess_gene_data(raw_data, logger)
    """
    logger.info("🔄 Starting data preprocessing...")
```

### 3. Function Design Rules
- One function = one task
- Maximum 20 lines per function
- Maximum 2 levels of nesting
- Always use type hints
```python
def calculate_gene_score(
    gene_id: str,
    expression_data: np.ndarray,
    *,  # Force keyword arguments
    threshold: float = 0.05,
    logger: Logger
) -> float:
```

### 4. Error Handling & Logging
- Log all critical operations
- Use custom exceptions for domain-specific errors
```python
class GeneAnalysisError(Exception):
    """Base exception for gene analysis errors."""
    pass

def analyze_genes(genes: list[str], logger: Logger) -> GeneResults:
    try:
        logger.info(f"📊 Analyzing {len(genes)} genes...")
        # Analysis code here
    except ValueError as e:
        logger.error(f"❌ Analysis failed: {str(e)}")
        raise GeneAnalysisError(f"Gene analysis failed: {str(e)}")
```

### 5. Performance Optimization
- Use numpy for numerical operations
- Implement dask for large datasets
- Profile code regularly
```python
import dask.dataframe as dd

def process_large_dataset(file_path: str) -> dd.DataFrame:
    """Process gene expression data using dask for memory efficiency."""
    return dd.read_csv(file_path).map_partitions(process_partition)
```

### 6. File & Folder Naming Conventions
- Python source files: `snake_case.py` — never camelCase
- Test files: `test_<module_name>.py` in `tests/`
- Output run directories: `gsm_<YYYY_MM_DD-HH_MM_SS>/` (auto-generated)
- Model bundles: `bundle_<dataset>_<classifier>_<seed>.gsm.zip`
- Pre-trained bundles: placed in `models/pretrained/`
- Data files: kept in `data/<subfolder>/` (LFS-tracked if large)
- Docs: Markdown in `DOCS/`, presentation in `reports_ARCHIVE/presentation/`

---

## Documentation Standards

### File Maps for Long Files
When a Python file grows beyond ~500 lines, add a **File Map** section near the
top docstring (or module header) in the same style as `PROJECT_MAP.md`:
- Use grouped headings (e.g., "Data loading", "Core loop", "Entry points").
- Include 1-line purpose explanations for each function or sub-function.
- If a function is long or multi-purpose, list its major sub-steps.
- Keep it compact and human-scannable; avoid duplicating full docstrings.

### File Headers
```python
"""
Gene Group Analysis Module 🧬

Purpose:
    Implements gene grouping algorithms based on expression patterns.

File Map:
    - group_genes(): Creates gene groups from expression data
    - score_groups(): Evaluates group significance
    - optimize_groups(): Refines group assignments

Example Usage:
    groups = group_genes(expression_data, logger)
    scores = score_groups(groups, logger)
"""
```

### Function Documentation
```python
def group_genes(
    expression_data: np.ndarray,
    *,
    min_size: int = 10,
    logger: Logger
) -> list[GeneGroup]:
    """Group genes based on expression patterns.

    Args:
        expression_data: Gene expression matrix (genes × samples)
        min_size: Minimum genes per group (default: 10)
        logger: Logger instance for tracking

    Returns:
        List of GeneGroup objects

    Example:
        >>> data = load_expression_data("data.csv")
        >>> groups = group_genes(data, min_size=15, logger=logger)
        >>> print(f"Found {len(groups)} gene groups")
    """
```

---

## Testing Requirements
- Write tests for all core functions
- Include edge cases
- Test with small datasets first
- Tests live in `tests/` and follow naming `test_<thing>.py`
- Tests must pass before any PR merge — `pytest` from repo root
- After every code change, run `pytest` and fix failures before proceeding

```python
def test_gene_grouping():
    """Test gene grouping with a small dataset."""
    test_data = load_test_data()
    groups = group_genes(test_data, min_size=5, logger=test_logger)
    assert len(groups) > 0, "Should create at least one group"
    assert all(len(g.genes) >= 5 for g in groups), "Groups should meet size requirement"
```

---

## Deployment Awareness

The codebase serves **two deployment targets** simultaneously:

1. **Local research** — Full pipeline: training + inference + validation.
   Both CLI and Streamlit UI are available. Data lives on disk.
2. **HuggingFace Spaces / Streamlit Cloud** — Inference-only mode.
   The Streamlit app auto-detects `SPACE_ID` env var and hides training
   tabs. Pre-trained bundles are served from `models/pretrained/`.

When adding a feature, ask: *Does this work in inference-only mode?*
If it requires local data or training, gate it behind a check like
`if not _is_huggingface_space()`.

---

## Dependencies
Core: pandas, numpy, scikit-learn, xgboost, matplotlib, seaborn, openpyxl
Bio-APIs: requests (Enrichr, STRING-db, DisGeNET)
UI: streamlit, rich
Dev: pytest, ruff, pre-commit
Full list: `dependencies.txt`

---

## Key Conventions Quick-Reference
- **Manuscripts**: Built programmatically via `scripts/build_manuscript_docx.py` from `reports_ARCHIVE/manuscript_data.json`.
- **Biological validation**: Enrichr + STRING-db + DisGeNET. Results in `output/<run>/biological_validation/`.
- **Pre-trained models**: Distributed via `models/pretrained/` (Git LFS).

## When to Update PROJECT_MAP.md
Copilot (or any contributor) should update **`PROJECT_MAP.md`** (not this file) whenever:
- A new source file or folder is added/removed.
- A public function is renamed or its signature changes.
- Pipeline defaults (classifier, seed, FDR α, etc.) are altered.
- New scripts or workflow configs are introduced.

Update **this file** only when coding conventions, design principles, or
documentation standards change.