# Troubleshooting 🔧

This page covers common problems when installing and running the GSM pipeline.
For WSL-specific issues (installation, networking, VPN), see [INSTALLATION.md](INSTALLATION.md).

---

## Quick Diagnosis

| Symptom | Likely Cause | Jump To |
|---------|-------------|---------|
| Data files are tiny (~130 bytes) | Git LFS not installed | [Section 1](#1-git-lfs--data-files-are-empty) |
| "Missing column" error | Wrong delimiter or headers | [Section 2](#2-missing-column-error-when-loading-data) |
| "command not found: python" | Python not installed or aliased | [Section 3](#3-python-or-python3-not-found) |
| Virtual env won't activate | Wrong path or shell | [Section 4](#4-virtual-environment-not-activating) |
| `pip install` fails | Missing build tools | [Section 5](#5-pip-install--r-dependenciestxt-fails) |
| Import errors | Wrong working directory | [Section 8](#8-import-errors-when-running-the-workflow) |
| Streamlit won't start | Env not activated or port conflict | [Section 6](#6-streamlit-does-not-start) |
| Pipeline runs but poor results | Check config and data | [Section 11](#11-pipeline-runs-but-results-look-wrong) |
| Memory errors / process killed | Dataset too large for RAM | [Section 12](#12-memory-errors--process-killed) |

---

## 1) Git LFS — Data Files Are Empty

If data files are tiny (~130 bytes) and start with `version https://git-lfs.github.com/spec/v1`, LFS didn't download the actual content.

```bash
# Install Git LFS (once per machine)
sudo apt install -y git-lfs
git lfs install

# Pull all tracked data files
git lfs pull
```

**Verify it worked:**
```bash
ls -lh data/expression_data/
# Files should be several MB, not ~130 bytes
```

If you cloned *before* installing `git-lfs`, run `git lfs pull` from the repo root.

---

## 2) "Missing column" Error When Loading Data

The pipeline auto-detects the separator (comma, tab, etc.) in both expression and grouping files. If you still get a "missing column" error:

- **Check the header row** — expected columns:
  - Expression data: must have a `class` column
  - Grouping files: must have `feature_id` and `group_name` columns
- **Check the delimiter** — open the file in a text editor and verify it uses commas, tabs, or another consistent separator.
- **Check encoding** — Windows-created files with `\r\n` line endings work fine. But if the file was exported from Excel with unusual encoding, try re-saving as UTF-8 CSV.
- **Check for BOM** — Some editors add a byte-order mark. Remove it:

```bash
sed -i '1s/^\xEF\xBB\xBF//' your_file.csv
```

---

## 3) "python" or "python3" Not Found

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

**If `python` doesn't work but `python3` does:**
```bash
# Option 1: Use python3 directly
python3 run_test.py

# Option 2: Create a permanent alias
echo 'alias python=python3' >> ~/.bashrc
source ~/.bashrc
```

---

## 4) Virtual Environment Not Activating

```bash
# Create it (if it doesn't exist)
python3 -m venv venv

# Activate it
source venv/bin/activate
```

**Common issues:**
- `source: command not found` — You might be using a non-bash shell. Try: `bash` first, then `source venv/bin/activate`.
- `venv/bin/activate: No such file or directory` — The venv wasn't created. Run `python3 -m venv venv` first.
- Using `venv` vs `.venv` — Check which one you created. Some steps say `.venv`, others say `venv`. Use whichever folder exists.

**Verify activation:**
```bash
which python
# Should show: /home/<you>/GSM-to-python/venv/bin/python
```

---

## 5) `pip install -r dependencies.txt` Fails

### Step 1: Upgrade pip first

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r dependencies.txt
```

### Step 2: If errors mention build tools (gcc, g++)

```bash
sudo apt update
sudo apt install -y build-essential python3-dev gfortran libopenblas-dev
pip install -r dependencies.txt
```

### Step 3: If a specific package fails

Try installing it separately to see the full error:

```bash
pip install xgboost       # or whichever package failed
pip install scikit-learn
```

### Step 4: If pip can't download packages (network)

```bash
# Check connectivity
curl -I https://pypi.org/

# If behind a proxy
pip install --proxy http://proxy.company.com:8080 -r dependencies.txt

# If SSL errors
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r dependencies.txt
```

### Step 5: Python version mismatch

This project requires **Python 3.10+**. Check your version:

```bash
python3 --version
```

If below 3.10, you'll need to install a newer Python:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 -m venv venv
source venv/bin/activate
pip install -r dependencies.txt
```

---

## 6) Streamlit Does Not Start

```bash
# Make sure the environment is activated
source venv/bin/activate

# Run Streamlit
streamlit run src/ui/app.py
```

**If port is in use:**
```bash
# Use a different port
streamlit run src/ui/app.py --server.port 8502

# Or kill the old Streamlit process
pkill -f streamlit
```

**If Streamlit is not installed:**
```bash
pip install streamlit
```

---

## 7) Browser Cannot Open `localhost:8501`

1. **Confirm Streamlit is running** — check the terminal for errors.
2. **Try the full URL** that Streamlit prints (e.g., `http://localhost:8501`).
3. **Try `127.0.0.1`** instead: `http://127.0.0.1:8501`.
4. **WSL users:** See [INSTALLATION.md](INSTALLATION.md#cannot-connect-to-localhost--streamlit-url-doesnt-open) for network fixes.
5. **VPN/firewall:** Some VPNs block local ports. Try disconnecting the VPN temporarily.

---

## 8) Import Errors When Running the Workflow

**Fix 1: Use the module form**
```bash
python -m src.workflows.GSM_workflow
```

**Fix 2: Confirm you're in the project root**
```bash
pwd
# Should show: /home/<you>/GSM-to-python

# If not:
cd ~/GSM-to-python
```

**Fix 3: Confirm the environment is activated**
```bash
which python
# Should show path inside venv, not /usr/bin/python3
```

**Fix 4: Reinstall dependencies**
```bash
pip install -r dependencies.txt
```

---

## 9) "Permission denied"

This is uncommon for Python scripts, but if you see it:

```bash
# Run with python explicitly (recommended)
python run_test.py

# Or fix permissions
chmod +x run_test.py
```

---

## 10) Tests Fail (`pytest`)

### A specific test fails after your changes

1. Read the error message carefully — it tells you which assertion failed.
2. Run just that test with verbose output:

```bash
pytest tests/test_core_functions.py::test_name -v
```

3. Check if your changes accidentally broke the function being tested.

### All tests fail

```bash
# Confirm environment
source venv/bin/activate
pip install -r dependencies.txt

# Run tests
pytest -v
```

If tests fail with `ModuleNotFoundError`, make sure you're running from the project root.

---

## 11) Pipeline Runs But Results Look Wrong

### Zero significant genes in every iteration

The t-test filter found no differentially expressed genes. This can happen when:
- The dataset has weak class separation
- There's severe class imbalance
- The wrong class column was used

**Check:** Look at `gsm_workflow.log` in the output folder for `ZeroSignificantGenesWarning`.

### Very low F1 / AUC scores

- **Small sample size:** Datasets with < 30 samples may not have enough signal.
- **Wrong grouping file:** Make sure the grouping file matches the gene IDs in the expression data.
- **Class imbalance:** Check the class distribution in your data.

### Results differ between runs

This is expected! Each run uses random seeds for train/test splits. Run with 100+ iterations for stable results. The pipeline uses seed 44 by default for reproducibility.

---

## 12) Memory Errors / Process Killed

### "Killed" or "MemoryError"

Your dataset may be too large for available RAM.

**Fixes:**
1. Close other applications to free memory.
2. Increase WSL memory (see [INSTALLATION.md](INSTALLATION.md#wsl-out-of-memory-or-process-killed)).
3. Reduce iterations: `python run_all_datasets.py --iterations 10`.
4. Run one dataset at a time instead of batch.

### Check available memory

```bash
free -h
# Look at the "available" column
```

---

## 13) Git Issues

### "fatal: not a git repository"

```bash
cd ~/GSM-to-python
```

### Merge conflicts

Don't panic — conflicts are Git asking you to choose between two edits. See [GITHUB_WORKFLOW.md](developer/GITHUB_WORKFLOW.md) for guidance.

### "Your branch is behind origin/main"

```bash
git pull origin main
```

### Accidentally committed to main

```bash
# Undo the last commit (keeps your changes)
git reset --soft HEAD~1

# Create a proper branch
git checkout -b my-feature
git add -A
git commit -m "My changes"
```

---

## 14) Biological Validation API Errors

### Enrichr / STRING-db / DisGeNET returns errors

These are external web APIs and can have downtime.

**Fixes:**
1. Check your internet connection.
2. Try again later — APIs may be temporarily down.
3. If behind a corporate proxy, configure it:

```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
```

4. Re-run just the bio validation without re-running the entire pipeline:

```bash
python scripts/maintenance/rerun_bio_validation.py
```

---

## 15) Performance Is Very Slow

| Symptom | Cause | Fix |
|---------|-------|-----|
| Everything slow in WSL | Files on `/mnt/c/` | Move to `/home/<you>/` |
| `pip install` slow | Slow network | Check proxy/VPN settings |
| Pipeline takes hours | Large dataset + many iterations | Reduce iterations for testing |
| Plotting is slow | matplotlib rendering | Set `MPLBACKEND=Agg` for headless |

---

## Still Stuck?

When asking for help, provide:
1. The **exact command** you ran
2. The **full error message** (copy-paste, don't screenshot)
3. Whether you're in **WSL** (Ubuntu) or **Windows**
4. Your **Python version** (`python3 --version`)
5. Whether the virtual environment is **activated** (`which python`)

Open an issue on GitHub with this information, or ask a colleague.

See also:
- [WSL Troubleshooting](INSTALLATION.md#wsl-troubleshooting-guide-) — WSL installation and networking
- [Microsoft WSL Docs](https://learn.microsoft.com/en-us/windows/wsl/troubleshooting) — Official reference
