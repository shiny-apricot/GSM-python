"""
🧬 GSM Pipeline — Rich Interactive Command-Line Interface

Purpose:
    Beautiful, intuitive CLI for the GSM Bioinformatics Pipeline.
    Supports both direct commands and a guided interactive menu.

Usage:
    python -m gsm                  # Interactive menu (recommended)
    python -m gsm train            # Direct training command
    python -m gsm infer            # Clinical inference
    python -m gsm bundle-info      # Inspect a model bundle
    python -m gsm ui               # Launch Streamlit dashboard

Key Functions:
    - main(): Entry point — routes to interactive or direct mode
    - interactive_menu(): Guided menu for all operations
    - handle_train(): Train the GSM pipeline
    - handle_infer(): Run clinical inference
    - handle_bundle_info(): Display bundle metadata

Example Usage:
    python -m gsm
    python -m gsm train --test --iterations 5
    python -m gsm infer -b bundle.gsm.zip -p patients.csv

File Map:
    Discovery helpers:
        - _discover_datasets(), _discover_grouping_files(), _discover_bundles(),
          _discover_patient_files(), _discover_output_runs()

    Job management + monitoring:
        - _load_jobs(), _save_jobs(), _is_pid_alive(), _refresh_job_statuses()
        - _read_progress_file(), _show_bg_jobs_banner(), _interactive_monitor_jobs()

    Interaction + prompts:
        - _prompt_choice(), _prompt_text(), _prompt_yes_no()
        - _collect_advanced_params(), _show_runtime_estimate()

    Interactive actions:
        - _interactive_train(), _interactive_infer(), _interactive_multi_infer()
        - _interactive_bundle_info(), _interactive_browse_outputs(), _inspect_run()
        - _execute_bio_validate(), _launch_background_train_with_config()
        - _stop_job(), _clear_completed_jobs(), _launch_streamlit(), _quick_test()

    Entry points:
        - interactive_menu(), main()
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional

# Project root for resolving data paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


##### Rich Console Setup #####

def _get_console():
    """Lazy-import rich and return a configured Console."""
    from rich.console import Console
    return Console()


##### ASCII Banner #####

BANNER = r"""
[bold cyan]
   ╔══════════════════════════════════════════════════════════════╗
   ║                                                              ║
   ║    ██████╗ ███████╗███╗   ███╗                               ║
   ║   ██╔════╝ ██╔════╝████╗ ████║                               ║
   ║   ██║  ███╗███████╗██╔████╔██║                               ║
   ║   ██║   ██║╚════██║██║╚██╔╝██║                               ║
   ║   ╚██████╔╝███████║██║ ╚═╝ ██║                               ║
   ║    ╚═════╝ ╚══════╝╚═╝     ╚═╝                               ║
   ║                                                              ║
   ║   [bold white]Group  ·  Score  ·  Model[/bold white]                               ║
   ║   [dim]Bioinformatics Gene Expression Pipeline[/dim]                   ║
   ║                                                              ║
   ╚══════════════════════════════════════════════════════════════╝
[/bold cyan]"""

VERSION = "2.0.0"


##### Discovery Helpers #####

def _discover_datasets() -> list[Path]:
    """Find all CSV datasets in data/expression_data/."""
    data_dir = PROJECT_ROOT / "data" / "expression_data"
    if not data_dir.exists():
        return []
    return sorted(data_dir.glob("*.csv"))


def _discover_grouping_files() -> list[Path]:
    """Find all grouping files in data/grouping_data/."""
    group_dir = PROJECT_ROOT / "data" / "grouping_data"
    if not group_dir.exists():
        return []
    return sorted(group_dir.glob("*"))


def _discover_bundles() -> list[Path]:
    """Find all .gsm.zip bundles in output/ and models/pretrained/."""
    bundles: list[Path] = []
    output_dir = PROJECT_ROOT / "output"
    if output_dir.exists():
        bundles.extend(output_dir.rglob("*.gsm.zip"))
    pretrained_dir = PROJECT_ROOT / "models" / "pretrained"
    if pretrained_dir.exists():
        bundles.extend(pretrained_dir.glob("*.gsm.zip"))
    return sorted(bundles)


def _bundle_label(b: Path) -> str:
    """Human-readable label for a bundle, with [pretrained] tag."""
    pretrained_dir = PROJECT_ROOT / "models" / "pretrained"
    if b.parent == pretrained_dir:
        return f"{b.stem}  [magenta][pretrained][/magenta]"
    return f"{b.stem}  [dim]{b.parent.parent.name}[/dim]"


def _discover_patient_files() -> list[Path]:
    """Find all CSV files in data/patient_data/."""
    patient_dir = PROJECT_ROOT / "data" / "patient_data"
    if not patient_dir.exists():
        return []
    return sorted(patient_dir.glob("*.csv"))


def _discover_output_runs() -> list[Path]:
    """Find all output run directories."""
    output_dir = PROJECT_ROOT / "output"
    if not output_dir.exists():
        return []
    runs = []
    for d in sorted(output_dir.iterdir(), reverse=True):
        if d.is_dir() and d.name.startswith(("gsm_", "gl_")):
            runs.append(d)
    return runs


##### Background Job Tracker #####

JOBS_FILE = PROJECT_ROOT / "output" / ".gsm_jobs.json"


def _load_jobs() -> list[dict]:
    """Load background job records from .gsm_jobs.json."""
    import json
    if not JOBS_FILE.exists():
        return []
    try:
        return json.loads(JOBS_FILE.read_text())
    except Exception:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    """Persist background job records."""
    import json
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    import signal
    try:
        os.kill(pid, signal.SIG_DFL)
        return True
    except (OSError, ProcessLookupError):
        return False


def _refresh_job_statuses(jobs: list[dict]) -> list[dict]:
    """Update status of each job based on PID liveness."""
    for job in jobs:
        if job.get("status") == "running":
            if not _is_pid_alive(job["pid"]):
                job["status"] = "completed"
    return jobs


def _read_progress_file(job: dict) -> Optional[dict]:
    """Read the progress JSON file for a background job, if it exists."""
    import json
    progress_path = job.get("progress_file")
    if not progress_path:
        return None
    p = Path(progress_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _show_bg_jobs_banner(console) -> None:
    """Show a one-line banner if there are running background jobs."""
    jobs = _load_jobs()
    jobs = _refresh_job_statuses(jobs)
    _save_jobs(jobs)

    running = [j for j in jobs if j.get("status") == "running"]
    if running:
        parts = []
        for j in running:
            name = j.get("dataset", "?")
            prog = _read_progress_file(j)
            if prog and prog.get("total"):
                cur = prog.get("iteration", 0)
                tot = prog["total"]
                parts.append(f"{name} ({cur}/{tot})")
            else:
                parts.append(name)
        console.print(
            f"  [bold yellow]⟳ {len(running)} background job(s) running: "
            f"{', '.join(parts)}[/bold yellow]"
        )
        console.print(
            "  [dim]Select 'Monitor Background Jobs' to see details.[/dim]\n"
        )


##### Prompt Helpers #####

def _prompt_choice(console, prompt: str, choices: list[str],
                   descriptions: Optional[list[str]] = None,
                   allow_back: bool = True) -> Optional[int]:
    """Display a numbered menu and return the selected index (0-based), or None for back."""
    from rich.panel import Panel

    lines = []
    for i, choice in enumerate(choices, 1):
        desc = f"  [dim]{descriptions[i-1]}[/dim]" if descriptions else ""
        lines.append(f"  [bold cyan]{i}[/bold cyan])  {choice}{desc}")
    if allow_back:
        lines.append(f"  [bold red]0[/bold red])  ← Back")
    lines.append("")

    menu_text = "\n".join(lines)
    console.print(Panel(menu_text, title=f"[bold]{prompt}[/bold]",
                        border_style="cyan", padding=(1, 2)))

    while True:
        try:
            raw = console.input("[bold cyan]  ▶ Your choice: [/bold cyan]").strip()
            if not raw:
                continue
            num = int(raw)
            if allow_back and num == 0:
                return None
            if 1 <= num <= len(choices):
                return num - 1
            console.print(f"  [red]Please enter a number between "
                          f"{0 if allow_back else 1} and {len(choices)}[/red]")
        except ValueError:
            console.print("  [red]Please enter a number.[/red]")
        except (KeyboardInterrupt, EOFError):
            return None


def _prompt_text(console, prompt: str, default: str = "") -> str:
    """Prompt for free text input with an optional default."""
    suffix = f" [dim](default: {default} — press Enter to keep)[/dim]" if default else ""
    try:
        raw = console.input(
            f"  [bold cyan]▶ {prompt}{suffix}: [/bold cyan]"
        ).strip()
        return raw or default
    except (KeyboardInterrupt, EOFError):
        return default


def _prompt_yes_no(console, prompt: str, default: bool = True) -> bool:
    """Prompt for a yes/no answer."""
    hint = "[Y/n]" if default else "[y/N]"
    try:
        raw = console.input(
            f"  [bold cyan]▶ {prompt} {hint}: [/bold cyan]"
        ).strip().lower()
        if not raw:
            return default
        return raw in ("y", "yes", "1", "true")
    except (KeyboardInterrupt, EOFError):
        return default


##### Interactive Menu #####

def interactive_menu() -> None:
    """Launch the interactive guided menu."""
    console = _get_console()
    console.print(BANNER)
    console.print(
        f"  [dim]Version {VERSION} · Python {sys.version.split()[0]}[/dim]\n"
    )

    while True:
        # Show background job status banner if any are running
        _show_bg_jobs_banner(console)

        choice = _prompt_choice(
            console,
            "What would you like to do?",
            [
                "🧬  Train Pipeline",
                "🏥  Clinical Inference",
                "🏥  Multi-Bundle Inference",
                "📦  Inspect Model Bundle",
                "📂  Browse Output Runs",
                "📋  Monitor Background Jobs",
                "📊  Launch Dashboard (Streamlit)",
                "⚡  Quick Test Run",
                "❓  Help & Documentation",
            ],
            [
                "Train classifiers (foreground or background)",
                "Diagnose patients using a single trained model",
                "Combine multiple dataset models for robust diagnosis",
                "View metadata of a saved .gsm.zip bundle",
                "Inspect past pipeline runs and their results",
                "Check status of background training jobs",
                "Open the web-based UI for results exploration",
                "Run a fast test with sample data (3 iterations)",
                "Show usage guide and available commands",
            ],
            allow_back=False,
        )

        if choice is None:
            _goodbye(console)
            return

        if choice == 0:
            _interactive_train(console)
        elif choice == 1:
            _interactive_infer(console)
        elif choice == 2:
            _interactive_multi_infer(console)
        elif choice == 3:
            _interactive_bundle_info(console)
        elif choice == 4:
            _interactive_browse_outputs(console)
        elif choice == 5:
            _interactive_monitor_jobs(console)
        elif choice == 6:
            _launch_streamlit(console)
        elif choice == 7:
            _quick_test(console)
        elif choice == 8:
            _show_help(console)


def _goodbye(console) -> None:
    """Print goodbye message."""
    console.print(
        "\n  [bold cyan]👋 Goodbye! Happy researching.[/bold cyan]\n"
    )


##### Advanced Parameters Collector #####

def _collect_advanced_params(
    console,
    *,
    split_ratio_default: float,
    normalization_default: str,
    ttest_default: float,
    cv_folds_default: int,
    best_groups_default: int,
    feature_filter_default: int,
    scoring_model_default: str,
    class_balancing_default: bool,
    balance_ratio_default: float,
    sampling_default: str,
    save_intermediate_default: bool,
    bio_top_genes_default: int,
) -> dict:
    """Present an advanced parameter tuning page and return overrides.

    Shows current defaults and lets users change any value they like.
    Only keys whose values differ from the default are returned.
    """
    from rich.panel import Panel

    console.print(
        "\n[bold cyan]═══ ⚙️  ADVANCED PARAMETERS ═══[/bold cyan]\n"
    )
    console.print(
        "  [dim]Press Enter to keep the default value (shown in parentheses).[/dim]\n"
    )

    overrides: dict = {}

    # ── Data Processing ──
    console.print(Panel(
        "  [bold]Data Processing[/bold]",
        border_style="dim", expand=False,
    ))

    val = _prompt_text(
        console, "Train/test split ratio",
        str(split_ratio_default),
    )
    try:
        split_ratio = float(val)
        if not (0.3 <= split_ratio <= 0.95):
            console.print("  [yellow]⚠ Clamped to [0.3, 0.95][/yellow]")
            split_ratio = max(0.3, min(0.95, split_ratio))
        if split_ratio != split_ratio_default:
            overrides["split_ratio"] = split_ratio
    except ValueError:
        pass

    norm_choices = ["zscore", "minmax", "robust"]
    nidx = _prompt_choice(
        console, "Normalization Method", norm_choices,
        [
            f"{'(current)' if normalization_default == 'zscore' else ''}",
            f"{'(current)' if normalization_default == 'minmax' else ''}",
            f"{'(current)' if normalization_default == 'robust' else ''}",
        ],
        allow_back=False,
    )
    if nidx is not None:
        chosen_norm = norm_choices[nidx]
        if chosen_norm != normalization_default:
            overrides["normalization"] = chosen_norm

    # ── Feature Selection ──
    console.print(Panel(
        "  [bold]Feature Selection[/bold]",
        border_style="dim", expand=False,
    ))

    val = _prompt_text(
        console, "T-test FDR threshold (α)",
        str(ttest_default),
    )
    try:
        tv = float(val)
        if tv != ttest_default:
            overrides["ttest_threshold"] = tv
    except ValueError:
        pass

    val = _prompt_text(
        console, "Initial feature filter size (0 = off)",
        str(feature_filter_default),
    )
    if val.isdigit():
        ff = int(val)
        if ff != feature_filter_default:
            overrides["feature_filter_size"] = ff

    val = _prompt_text(
        console, "Best groups to keep for final model",
        str(best_groups_default),
    )
    if val.isdigit():
        bg = int(val)
        if bg != best_groups_default:
            overrides["best_groups"] = bg

    # ── Cross-Validation & Scoring ──
    console.print(Panel(
        "  [bold]Cross-Validation & Scoring[/bold]",
        border_style="dim", expand=False,
    ))

    val = _prompt_text(
        console, "CV folds (scoring phase)",
        str(cv_folds_default),
    )
    if val.isdigit():
        cf = int(val)
        if cf != cv_folds_default:
            overrides["cv_folds"] = cf

    scoring_choices = ["RandomForest", "XGBoost", "DecisionTree"]
    scoring_desc = [
        f"Best bio coherence {'(current)' if scoring_model_default == 'RandomForest' else ''}",
        f"Faster {'(current)' if scoring_model_default == 'XGBoost' else ''}",
        f"Fastest {'(current)' if scoring_model_default == 'DecisionTree' else ''}",
    ]
    sidx = _prompt_choice(
        console, "Scoring Model (group ranking)", scoring_choices,
        scoring_desc, allow_back=False,
    )
    if sidx is not None:
        chosen_scoring = scoring_choices[sidx]
        if chosen_scoring != scoring_model_default:
            overrides["scoring_model"] = chosen_scoring

    # ── Class Balancing ──
    console.print(Panel(
        "  [bold]Class Balancing[/bold]",
        border_style="dim", expand=False,
    ))

    bal = _prompt_yes_no(
        console, "Apply class balancing?",
        default=class_balancing_default,
    )
    if bal != class_balancing_default:
        overrides["class_balancing"] = bal

    if bal:
        samp_choices = ["undersampling", "oversampling"]
        samp_desc = [
            f"Reduce majority class {'(current)' if sampling_default == 'undersampling' else ''}",
            f"Duplicate minority class {'(current)' if sampling_default == 'oversampling' else ''}",
        ]
        sampidx = _prompt_choice(
            console, "Sampling Method", samp_choices,
            samp_desc, allow_back=False,
        )
        if sampidx is not None:
            chosen_samp = samp_choices[sampidx]
            if chosen_samp != sampling_default:
                overrides["sampling_method"] = chosen_samp

        val = _prompt_text(
            console, "Min class balance ratio",
            str(balance_ratio_default),
        )
        try:
            br = float(val)
            if br != balance_ratio_default:
                overrides["balance_ratio"] = br
        except ValueError:
            pass

    # ── Output Options ──
    console.print(Panel(
        "  [bold]Output Options[/bold]",
        border_style="dim", expand=False,
    ))

    si = _prompt_yes_no(
        console, "Save intermediate results?",
        default=save_intermediate_default,
    )
    if si != save_intermediate_default:
        overrides["save_intermediate"] = si

    val = _prompt_text(
        console, "Bio validation top genes count",
        str(bio_top_genes_default),
    )
    if val.isdigit():
        btg = int(val)
        if btg != bio_top_genes_default:
            overrides["bio_top_genes"] = btg

    if overrides:
        console.print(
            f"\n  [green]✓[/green] {len(overrides)} advanced parameter(s) "
            f"customized.\n"
        )
    else:
        console.print(
            "\n  [dim]No changes — using all defaults.[/dim]\n"
        )

    return overrides


def _show_runtime_estimate(console, n_iterations: int, data_path: Path) -> None:
    """Show a rough runtime estimate based on dataset size and iterations."""
    try:
        file_mb = data_path.stat().st_size / (1024 * 1024)
        # Rough heuristic: ~0.3s per iteration for small test data,
        # ~3-5s per iteration for medium (30-50 MB) GEO datasets,
        # scales roughly with file size.
        per_iter_sec = max(0.3, min(15.0, file_mb * 0.08))
        total_sec = per_iter_sec * n_iterations
        if total_sec < 60:
            est = f"~{total_sec:.0f}s"
        elif total_sec < 3600:
            est = f"~{total_sec / 60:.0f} min"
        else:
            est = f"~{total_sec / 3600:.1f} hr"
        console.print(
            f"\n  [dim]⏱  Estimated runtime: {est} "
            f"(rough estimate based on dataset size)[/dim]"
        )
    except Exception:
        pass


##### Interactive Train #####

def _interactive_train(console) -> None:
    """Guided training flow with optional advanced parameter tuning."""
    from rich.table import Table

    console.print("\n[bold cyan]═══ 🧬 TRAIN PIPELINE ═══[/bold cyan]\n")

    # Import config defaults (used as fallbacks throughout)
    from src.workflows.GSM_workflow_config import (
        TRAIN_TEST_SPLIT_RATIO, NORMALIZATION_METHOD,
        TTEST_THRESHOLD, CROSS_VALIDATION_FOLDS,
        BEST_GROUPS_TO_KEEP, INITIAL_FEATURE_FILTER_SIZE,
        SCORING_MODEL, APPLY_CLASS_BALANCING,
        MIN_CLASS_BALANCE_RATIO, SAMPLING_METHOD,
        SAVE_INTERMEDIATE_RESULTS,
        BIOLOGICAL_VALIDATION_TOP_GENES,
    )

    # Step 1: Select dataset
    datasets = _discover_datasets()
    if not datasets:
        console.print("  [red]No datasets found in data/expression_data/[/red]")
        console.print(
            "  [dim]Place your expression CSV files there and try again.[/dim]\n"
        )
        return

    console.print("  [bold]Step 1/5 · Select Dataset[/bold]\n")
    names = [p.stem for p in datasets]
    sizes = []
    for d in datasets:
        try:
            # Fast: read header in binary for column count,
            # count newlines in 1 MB blocks (avoids full text decode).
            with open(d, "rb") as fh:
                header = fh.readline()
                n_cols = header.count(b",")  # genes (excl. label col)
                n_rows = 0
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    n_rows += chunk.count(b"\n")
            sizes.append(f"{n_rows} samples × {n_cols} genes")
        except Exception:
            mb = d.stat().st_size / (1024 * 1024)
            sizes.append(f"{mb:.0f} MB")
    idx = _prompt_choice(console, "Available Datasets", names, sizes)
    if idx is None:
        return
    data_path = datasets[idx]

    # Step 2: Select grouping file
    groups = _discover_grouping_files()
    console.print("\n  [bold]Step 2/5 · Select Grouping File[/bold]\n")
    if len(groups) == 1:
        group_path = groups[0]
        console.print(
            f"  [green]✓[/green] Using: [bold]{group_path.name}[/bold]\n"
        )
    elif groups:
        gnames = [p.name for p in groups]
        gidx = _prompt_choice(console, "Available Grouping Files", gnames)
        if gidx is None:
            return
        group_path = groups[gidx]
    else:
        console.print(
            "  [red]No grouping files found in data/grouping_data/[/red]\n"
        )
        return

    # Step 3: Select model
    console.print("  [bold]Step 3/5 · Select Classifier[/bold]\n")
    models = [
        "RandomForest", "XGBoost", "DecisionTree", "SVM", "KNN", "MLP",
    ]
    model_desc = [
        "Best biological coherence (recommended)",
        "Fast alternative, 2.7× faster",
        "Simple, interpretable",
        "Support Vector Machine",
        "K-Nearest Neighbors",
        "Neural Network",
    ]
    midx = _prompt_choice(console, "Classifiers", models, model_desc)
    if midx is None:
        return
    model_name = models[midx]

    # Step 4: Iterations & seed
    console.print("\n  [bold]Step 4/5 · Configure Run[/bold]\n")
    n_iter_str = _prompt_text(console, "Number of iterations", "100")
    n_iterations = int(n_iter_str) if n_iter_str.isdigit() else 100
    seed_str = _prompt_text(console, "Random seed", "44")
    seed = int(seed_str) if seed_str.isdigit() else 44

    # Optional experiment name
    run_name_input = _prompt_text(
        console, "Experiment name (optional, press Enter to skip)", ""
    )
    run_name: Optional[str] = run_name_input.strip() or None

    # Step 5: Options
    console.print("\n  [bold]Step 5/5 · Options[/bold]\n")
    run_bio = _prompt_yes_no(
        console, "Run biological validation?", default=True
    )

    # ── Advanced Parameters (optional) ──
    # Collect all tuneable parameters with their current defaults.
    # Only values the user changes are stored as overrides.
    advanced: dict = {}
    console.print()
    configure_advanced = _prompt_yes_no(
        console,
        "Configure advanced parameters?",
        default=False,
    )

    if configure_advanced:
        advanced = _collect_advanced_params(
            console,
            split_ratio_default=TRAIN_TEST_SPLIT_RATIO,
            normalization_default=NORMALIZATION_METHOD,
            ttest_default=TTEST_THRESHOLD,
            cv_folds_default=CROSS_VALIDATION_FOLDS,
            best_groups_default=BEST_GROUPS_TO_KEEP,
            feature_filter_default=INITIAL_FEATURE_FILTER_SIZE,
            scoring_model_default=SCORING_MODEL,
            class_balancing_default=APPLY_CLASS_BALANCING,
            balance_ratio_default=MIN_CLASS_BALANCE_RATIO,
            sampling_default=SAMPLING_METHOD,
            save_intermediate_default=SAVE_INTERMEDIATE_RESULTS,
            bio_top_genes_default=BIOLOGICAL_VALIDATION_TOP_GENES,
        )

    # Summary table
    summary = Table(
        title="Training Configuration", border_style="cyan",
        show_header=False, padding=(0, 2),
    )
    summary.add_column("Setting", style="bold")
    summary.add_column("Value", style="green")
    summary.add_row("Dataset", data_path.stem)
    summary.add_row("Grouping", group_path.name)
    summary.add_row("Classifier", model_name)
    summary.add_row("Iterations", str(n_iterations))
    summary.add_row("Seed", str(seed))
    if run_name:
        summary.add_row("Name", run_name)
    summary.add_row("Bio Validation", "Yes" if run_bio else "No")

    # Show advanced overrides in table (only those that differ from default)
    if advanced:
        summary.add_row("", "")  # blank separator
        for key, val in advanced.items():
            label = key.replace("_", " ").title()
            summary.add_row(f"  {label}", str(val))
    console.print()
    console.print(summary)

    # Estimated runtime hint
    _show_runtime_estimate(console, n_iterations, data_path)

    console.print()

    run_mode = _prompt_choice(
        console,
        "How to run?",
        [
            "▶️  Run in foreground",
            "🔄  Run in background",
        ],
        [
            "Run here — see live progress (blocks the terminal)",
            "Launch as a background job — continue using the CLI",
        ],
    )

    if run_mode is None:
        console.print("  [dim]Training cancelled.[/dim]\n")
        return

    if run_mode == 1:
        # Background mode
        _launch_background_train_with_config(
            console,
            data_path=data_path,
            group_path=group_path,
            model_name=model_name,
            n_iterations=n_iterations,
            seed=seed,
            advanced=advanced,
            run_name=run_name,
        )
        return

    # Foreground mode
    _execute_train(
        console,
        data_path=data_path,
        group_path=group_path,
        model_name=model_name,
        n_iterations=n_iterations,
        seed=seed,
        run_bio=run_bio,
        advanced=advanced,
        run_name=run_name,
    )


##### Interactive Infer #####

def _interactive_infer(console) -> None:
    """Guided inference flow."""
    console.print("\n[bold cyan]═══ 🏥 CLINICAL INFERENCE ═══[/bold cyan]\n")

    # Step 1: Select bundle
    bundles = _discover_bundles()
    if not bundles:
        console.print("  [red]No model bundles found.[/red]")
        console.print(
            "  [dim]Train a pipeline first, then you'll find "
            ".gsm.zip files in output/[/dim]\n"
        )
        return

    console.print("  [bold]Step 1/2 · Select Model Bundle[/bold]\n")
    bundle_names = [_bundle_label(b) for b in bundles]
    bidx = _prompt_choice(console, "Available Bundles", bundle_names)
    if bidx is None:
        return
    bundle_path = bundles[bidx]

    # Step 2: Patient data
    console.print("\n  [bold]Step 2/2 · Patient Data[/bold]\n")
    console.print(
        "  [dim]Provide a CSV file where rows = samples, "
        "columns = gene IDs[/dim]"
    )
    console.print(
        "  [dim]Gene columns must match those used during training.[/dim]\n"
    )

    # Auto-discover patient files from data/patient_data/
    patient_files = _discover_patient_files()
    patients_path: Optional[Path] = None

    if patient_files:
        file_names = [f.name for f in patient_files]
        file_names.append("[dim]Enter a different path manually[/dim]")
        pidx = _prompt_choice(console, "Patient CSV Files", file_names)
        if pidx is None:
            return
        if pidx < len(patient_files):
            patients_path = patient_files[pidx]
        # else: fall through to manual entry below

    if patients_path is None:
        patients_path_str = _prompt_text(
            console, "Path to patient CSV file"
        )
        if not patients_path_str:
            console.print("  [red]No file provided.[/red]\n")
            return
        patients_path = Path(patients_path_str)

    if not patients_path.exists():
        console.print(f"  [red]File not found: {patients_path}[/red]\n")
        return

    # Optional: sample ID column
    sample_id_col = _prompt_text(
        console, "Sample ID column (leave blank to auto-number)"
    )

    console.print()
    if not _prompt_yes_no(console, "Run inference?", default=True):
        console.print("  [dim]Inference cancelled.[/dim]\n")
        return

    _execute_infer(
        console, bundle_path, patients_path,
        sample_id_col if sample_id_col else None,
    )


##### Interactive Multi-Bundle Infer #####

def _interactive_multi_infer(console) -> None:
    """Guided multi-bundle inference flow.

    Lets the user select multiple .gsm.zip bundles trained on
    different datasets and combine their predictions for more
    robust clinical inference.
    """
    console.print(
        "\n[bold cyan]═══ 🏥 MULTI-BUNDLE INFERENCE ═══[/bold cyan]\n"
    )

    # Step 1: Select multiple bundles
    bundles = _discover_bundles()
    if not bundles:
        console.print("  [red]No model bundles found.[/red]")
        console.print(
            "  [dim]Train pipelines on multiple datasets first.[/dim]\n"
        )
        return

    if len(bundles) < 2:
        console.print("  [yellow]Only 1 bundle found — need at least 2 for multi-bundle.[/yellow]")
        console.print(
            "  [dim]Use single-bundle inference instead, or train more datasets.[/dim]\n"
        )
        return

    console.print("  [bold]Step 1/2 · Select Model Bundles[/bold]\n")
    console.print(
        "  [dim]Select bundles one at a time. Enter 0 when done.[/dim]\n"
    )

    bundle_names = [_bundle_label(b) for b in bundles]
    selected_bundle_paths: list = []
    available_indices = list(range(len(bundles)))

    while True:
        remaining_names = [bundle_names[i] for i in available_indices]
        remaining_names.append("[bold green]✓ Done selecting[/bold green]")

        console.print(
            f"  [dim]Selected so far: {len(selected_bundle_paths)} bundles[/dim]"
        )
        bidx = _prompt_choice(
            console, "Available Bundles", remaining_names,
            allow_back=True,
        )
        if bidx is None:
            return

        # "Done selecting" option
        if bidx == len(remaining_names) - 1:
            break

        # Map back to original index
        original_idx = available_indices[bidx]
        selected_bundle_paths.append(bundles[original_idx])
        available_indices.remove(original_idx)
        console.print(
            f"  [green]Added: {bundles[original_idx].stem}[/green]"
        )

        if len(available_indices) == 0:
            break

    if len(selected_bundle_paths) < 2:
        console.print("  [red]Need at least 2 bundles for multi-bundle inference.[/red]\n")
        return

    console.print(
        f"\n  [bold]Selected {len(selected_bundle_paths)} bundles:[/bold]"
    )
    for bp in selected_bundle_paths:
        console.print(f"    • {bp.stem}")

    # Step 2: Patient data (same as single-bundle)
    console.print("\n  [bold]Step 2/2 · Patient Data[/bold]\n")
    console.print(
        "  [dim]Provide a CSV file where rows = samples, "
        "columns = gene IDs[/dim]\n"
    )

    patient_files = _discover_patient_files()
    patients_path: Optional[Path] = None

    if patient_files:
        file_names = [f.name for f in patient_files]
        file_names.append("[dim]Enter a different path manually[/dim]")
        pidx = _prompt_choice(console, "Patient CSV Files", file_names)
        if pidx is None:
            return
        if pidx < len(patient_files):
            patients_path = patient_files[pidx]

    if patients_path is None:
        patients_path_str = _prompt_text(
            console, "Path to patient CSV file"
        )
        if not patients_path_str:
            console.print("  [red]No file provided.[/red]\n")
            return
        patients_path = Path(patients_path_str)

    if not patients_path.exists():
        console.print(f"  [red]File not found: {patients_path}[/red]\n")
        return

    sample_id_col = _prompt_text(
        console, "Sample ID column (leave blank to auto-number)"
    )

    console.print()
    if not _prompt_yes_no(console, "Run multi-bundle inference?", default=True):
        console.print("  [dim]Inference cancelled.[/dim]\n")
        return

    _execute_multi_infer(
        console, selected_bundle_paths, patients_path,
        sample_id_col if sample_id_col else None,
    )


##### Interactive Bundle Info #####

def _interactive_bundle_info(console) -> None:
    """Guided bundle inspection flow."""
    console.print(
        "\n[bold cyan]═══ 📦 INSPECT MODEL BUNDLE ═══[/bold cyan]\n"
    )

    bundles = _discover_bundles()
    if not bundles:
        console.print("  [red]No model bundles found.[/red]")
        console.print(
            "  [dim]Train a pipeline first to create bundles.[/dim]\n"
        )
        return

    bundle_names = [_bundle_label(b) for b in bundles]
    bidx = _prompt_choice(console, "Available Bundles", bundle_names)
    if bidx is None:
        return

    _execute_bundle_info(console, bundles[bidx])


##### Browse Output Runs #####

def _interactive_browse_outputs(console) -> None:
    """Browse past pipeline runs and inspect their results."""
    import json
    from rich.table import Table
    from rich.panel import Panel

    console.print(
        "\n[bold cyan]═══ 📂 BROWSE OUTPUT RUNS ═══[/bold cyan]\n"
    )

    runs = _discover_output_runs()
    if not runs:
        console.print("  [dim]No pipeline runs found in output/.[/dim]\n")
        return

    # Build a summary table
    run_summaries = []
    for run_dir in runs:
        summary = {"path": run_dir, "name": run_dir.name}

        # Read optional run_name from runtime_config.json
        rc_path = run_dir / "runtime_config.json"
        if rc_path.exists():
            try:
                rc = json.loads(rc_path.read_text())
                rn = rc.get("run_name", "")
                if rn:
                    summary["run_name"] = rn
            except Exception:
                pass

        # Try to get basic metrics from results JSON
        results_json = run_dir / "modeling_results_all_iterations.json"
        if results_json.exists():
            try:
                data = json.loads(results_json.read_text())
                last_iter = data[-1] if data else {}
                best = (
                    last_iter.get("results", [{}])[0]
                    if "results" in last_iter else last_iter
                )
                summary["f1"] = best.get("f1_score", 0)
                summary["auc"] = best.get("auc_roc", 0)
                summary["groups"] = best.get("num_groups_used", "?")
                summary["features"] = best.get("num_features_used", "?")
                summary["finished"] = True
            except Exception:
                summary["finished"] = False
        else:
            summary["finished"] = False

        # Check for bundle
        bundles_dir = run_dir / "bundles"
        summary["has_bundle"] = (
            bundles_dir.exists()
            and bool(list(bundles_dir.glob("*.gsm.zip")))
        )

        # Check for biological validation
        bio_dir = run_dir / "biological_validation"
        summary["has_bio"] = (
            bio_dir.exists() and bool(list(bio_dir.glob("*")))
        )

        run_summaries.append(summary)

    # Display overview table
    overview = Table(
        title=f"Pipeline Runs ({len(run_summaries)} found)",
        border_style="cyan",
        padding=(0, 1),
    )
    overview.add_column("#", style="bold cyan", width=3)
    overview.add_column("Run", style="bold", max_width=50)
    overview.add_column("Name", style="magenta", max_width=20)
    overview.add_column("F1", justify="center", width=6)
    overview.add_column("AUC", justify="center", width=6)
    overview.add_column("Status", justify="left", width=18)

    for i, s in enumerate(run_summaries):
        f1 = f"{s['f1']:.3f}" if "f1" in s else "—"
        auc = f"{s['auc']:.3f}" if "auc" in s else "—"
        rn = s.get("run_name", "")

        # Compact status: ✓done/⚠partial + 📦bundle + 🧬bio
        status_parts = []
        if s["finished"]:
            status_parts.append("[green]✓done[/green]")
        else:
            status_parts.append("[yellow]⚠partial[/yellow]")
        if s["has_bundle"]:
            status_parts.append("[green]📦[/green]")
        if s["has_bio"]:
            status_parts.append("[green]🧬[/green]")
        status = " ".join(status_parts)

        overview.add_row(str(i + 1), s["name"], rn, f1, auc, status)

    console.print(overview)
    console.print(
        "  [dim]Enter a row number to inspect, or 0 to go back.[/dim]\n"
    )

    # Direct numeric selection using the table row numbers
    while True:
        try:
            raw = console.input(
                "[bold cyan]  ▶ Your choice: [/bold cyan]"
            ).strip()
            if not raw:
                continue
            num = int(raw)
            if num == 0:
                return
            if 1 <= num <= len(run_summaries):
                _inspect_run(console, run_summaries[num - 1])
                return
            console.print(
                f"  [red]Enter a number between 0 and "
                f"{len(run_summaries)}[/red]"
            )
        except ValueError:
            console.print("  [red]Please enter a number.[/red]")
        except (KeyboardInterrupt, EOFError):
            return


def _inspect_run(console, run_summary: dict) -> None:
    """Drill into a single run's details."""
    from rich.panel import Panel
    from rich.table import Table

    run_dir: Path = run_summary["path"]
    console.print(
        f"\n[bold cyan]═══ 📂 {run_dir.name} ═══[/bold cyan]\n"
    )

    while True:
        actions = [
            "📄  View summary report",
            "📊  Show result metrics",
            "📁  List output files",
            "📋  View pipeline log",
            "🧬  Re-run biological validation",
        ]
        descs = [
            "Display the text summary report",
            "Show detailed F1, AUC, groups, features",
            "List all files with sizes",
            "Show the last 50 lines of the log file",
            "Run Enrichr + STRING-db + DisGeNET on this run's genes",
        ]

        # Add bundle-specific option if available
        if run_summary.get("has_bundle"):
            actions.append("📦  Inspect model bundle")
            descs.append("Show metadata of the .gsm.zip bundle")

        action_idx = _prompt_choice(
            console, "What do you want to view?", actions, descs,
        )
        if action_idx is None:
            return

        if action_idx == 0:
            _view_summary_report(console, run_dir)
        elif action_idx == 1:
            _view_result_metrics(console, run_dir)
        elif action_idx == 2:
            _view_output_files(console, run_dir)
        elif action_idx == 3:
            _view_pipeline_log(console, run_dir)
        elif action_idx == 4:
            _execute_bio_validate(console, run_dir)
        elif action_idx == 5:
            _view_run_bundle(console, run_dir)

        console.print()


def _view_summary_report(console, run_dir: Path) -> None:
    """Display the summary report text."""
    from rich.panel import Panel

    report_path = run_dir / "summary_report.txt"
    if not report_path.exists():
        console.print("  [dim]No summary report found.[/dim]")
        return

    text = report_path.read_text()
    # Truncate very long reports
    lines = text.splitlines()
    if len(lines) > 80:
        display_text = "\n".join(lines[:80])
        display_text += f"\n\n... ({len(lines) - 80} more lines)"
    else:
        display_text = text

    console.print(Panel(
        display_text,
        title="[bold]Summary Report[/bold]",
        border_style="cyan",
    ))


def _view_result_metrics(console, run_dir: Path) -> None:
    """Show detailed metrics from results JSON."""
    import json
    from rich.table import Table

    results_path = run_dir / "modeling_results_all_iterations.json"
    if not results_path.exists():
        console.print("  [dim]No results JSON found.[/dim]")
        return

    try:
        data = json.loads(results_path.read_text())
    except Exception:
        console.print("  [dim]Could not parse results JSON.[/dim]")
        return

    # Show per-iteration best results
    table = Table(
        title="Per-Iteration Results",
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Iter", style="bold", width=5)
    table.add_column("F1", justify="center", width=8)
    table.add_column("AUC", justify="center", width=8)
    table.add_column("Accuracy", justify="center", width=8)
    table.add_column("Groups", justify="center", width=7)
    table.add_column("Features", justify="center", width=9)

    for i, iteration in enumerate(data):
        results = iteration.get("results", [])
        if results:
            best = results[0]
            table.add_row(
                str(i + 1),
                f"{best.get('f1_score', 0):.4f}",
                f"{best.get('auc_roc', 0):.4f}",
                f"{best.get('accuracy', 0):.4f}",
                str(best.get("num_groups_used", "?")),
                str(best.get("num_features_used", "?")),
            )

    console.print(table)

    # Summary stats
    all_f1 = []
    for iteration in data:
        for r in iteration.get("results", []):
            if "f1_score" in r:
                all_f1.append(r["f1_score"])

    if all_f1:
        import numpy as np
        console.print(
            f"\n  Mean F1: [bold]{np.mean(all_f1):.4f}[/bold] ± "
            f"{np.std(all_f1):.4f}  "
            f"(min={min(all_f1):.4f}, max={max(all_f1):.4f})"
        )


def _view_output_files(console, run_dir: Path) -> None:
    """List all output files with sizes."""
    from rich.table import Table

    exts = {".txt", ".json", ".xlsx", ".csv", ".png", ".log", ".zip"}
    files = []
    for f in sorted(run_dir.rglob("*")):
        if f.is_file() and f.suffix in exts:
            rel = f.relative_to(run_dir)
            size_kb = f.stat().st_size / 1024
            files.append((str(rel), size_kb))

    if not files:
        console.print("  [dim]No recognized output files found.[/dim]")
        return

    table = Table(
        title=f"Output Files ({len(files)} files)",
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("File", style="bold", max_width=60)
    table.add_column("Size", justify="right", width=10)

    for name, size_kb in files:
        if size_kb >= 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"
        table.add_row(name, size_str)

    console.print(table)


def _view_pipeline_log(console, run_dir: Path) -> None:
    """Show tail of the pipeline log file."""
    from rich.panel import Panel

    # Search for log files
    log_files = list(run_dir.glob("*.log"))
    if not log_files:
        log_files = list(run_dir.rglob("*.log"))

    if not log_files:
        console.print("  [dim]No log files found.[/dim]")
        return

    log_path = log_files[0]
    text = log_path.read_text()
    lines = text.splitlines()

    # Show last 50 lines
    if len(lines) > 50:
        display_lines = lines[-50:]
        header = f"... (showing last 50 of {len(lines)} lines)"
    else:
        display_lines = lines
        header = f"{len(lines)} lines"

    console.print(Panel(
        "\n".join(display_lines),
        title=f"[bold]Pipeline Log ({header})[/bold]",
        border_style="dim",
    ))


def _view_run_bundle(console, run_dir: Path) -> None:
    """Inspect the bundle in this run."""
    bundles_dir = run_dir / "bundles"
    if not bundles_dir.exists():
        console.print("  [dim]No bundles directory found.[/dim]")
        return

    bundle_files = list(bundles_dir.glob("*.gsm.zip"))
    if not bundle_files:
        console.print("  [dim]No .gsm.zip bundles found.[/dim]")
        return

    _execute_bundle_info(console, bundle_files[0])


##### Re-run Biological Validation #####

def _execute_bio_validate(console, run_dir: Path) -> None:
    """Re-run biological validation on an existing pipeline run.

    Useful when the original training completed successfully but
    biological validation was skipped (no internet, API timeout, etc.).
    """
    from rich.panel import Panel

    results_json = run_dir / "modeling_results_all_iterations.json"
    if not results_json.exists():
        console.print(
            "  [red]No modeling_results_all_iterations.json found.[/red]"
        )
        console.print(
            "  [dim]This run may not have completed successfully.[/dim]\n"
        )
        return

    # Check if bio validation already exists
    bio_dir = run_dir / "biological_validation"
    if bio_dir.exists() and list(bio_dir.glob("*")):
        console.print(
            "  [yellow]⚠ biological_validation/ already exists "
            "for this run.[/yellow]"
        )
        if not _prompt_yes_no(
            console,
            "Overwrite existing validation results?",
            default=False,
        ):
            console.print("  [dim]Cancelled.[/dim]\n")
            return

    # Warn about internet requirement
    console.print(Panel(
        "  This will query external APIs:\n\n"
        "  • [bold]Enrichr[/bold] — pathway enrichment\n"
        "  • [bold]STRING-db[/bold] — protein-protein interactions\n"
        "  • [bold]DisGeNET[/bold] — disease-gene associations "
        "(requires API key)\n\n"
        "  [yellow]⚠ Internet connection is required.[/yellow]\n"
        "  [dim]Typical runtime: 30–60 seconds.[/dim]",
        title="[bold]Biological Validation[/bold]",
        border_style="cyan",
    ))

    if not _prompt_yes_no(console, "Proceed?", default=True):
        console.print("  [dim]Cancelled.[/dim]\n")
        return

    # Optional: DisGeNET API key
    from src.workflows.GSM_workflow_config import (
        DISGENET_API_KEY, BIOLOGICAL_VALIDATION_TOP_GENES,
        GENE_COLUMN_NAME, GROUP_COLUMN_NAME,
    )
    api_key = DISGENET_API_KEY or ""
    custom_key = _prompt_text(
        console,
        "DisGeNET API key (Enter to skip/use default)",
        api_key if api_key else "",
    )

    # Top N genes
    top_n_str = _prompt_text(
        console, "Top N genes to validate",
        str(BIOLOGICAL_VALIDATION_TOP_GENES),
    )
    top_n = (
        int(top_n_str) if top_n_str.isdigit()
        else BIOLOGICAL_VALIDATION_TOP_GENES
    )

    # Attempt to find grouping data for group validation
    grouping_data_path: Optional[Path] = None
    group_files = _discover_grouping_files()
    if group_files:
        if len(group_files) == 1:
            grouping_data_path = group_files[0]
        else:
            console.print()
            gnames = [p.name for p in group_files]
            gidx = _prompt_choice(
                console,
                "Select grouping file for group validation (optional)",
                gnames,
            )
            if gidx is not None:
                grouping_data_path = group_files[gidx]

    # Run bio validation
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            "Running biological validation (querying APIs)...",
            total=None,
        )

        try:
            from src.utils.biological_validation import (
                run_biological_validation,
            )
            from src.utils.logger import setup_logger
            import tempfile

            log_path = Path(tempfile.mktemp(suffix=".log"))
            logger = setup_logger(
                str(log_path), logger_name="bio_validate_cli",
            )

            report = run_biological_validation(
                output_dir=run_dir,
                results_json_path=results_json,
                logger=logger,
                disgenet_api_key=custom_key or None,
                top_n_genes=top_n,
                grouping_data_path=grouping_data_path,
                gene_column=GENE_COLUMN_NAME,
                group_column=GROUP_COLUMN_NAME,
            )

            progress.update(task, description="Done!")
        except Exception as e:
            progress.update(task, description="Failed!")
            console.print(
                f"\n  [bold red]✗ Biological validation failed: "
                f"{e}[/bold red]"
            )
            console.print(
                "  [yellow]⚠ Check your internet connection and "
                "try again.[/yellow]\n"
            )
            return

    # Display results summary
    console.print(Panel(
        f"  Genes validated:     [bold]{len(report.input_genes)}[/bold]\n"
        f"  Enrichr results:     [bold]{len(report.enrichr_results)}"
        f"[/bold]\n"
        f"  STRING interactions: [bold]"
        f"{len(report.string_interactions)}[/bold]\n"
        f"  Disease assocs:      [bold]"
        f"{len(report.disease_associations)}[/bold]\n\n"
        f"  Output saved to: [bold]{run_dir.name}/biological_validation/"
        f"[/bold]",
        title="[bold green]✅ Biological Validation Complete[/bold green]",
        border_style="green",
    ))

    if report.string_network_url:
        console.print(
            f"  [dim]STRING network: {report.string_network_url}[/dim]"
        )
    console.print()


##### Background Training #####

def _launch_background_train_with_config(
    console,
    data_path: Path,
    group_path: Path,
    model_name: str,
    n_iterations: int,
    seed: int,
    advanced: Optional[dict] = None,
    run_name: Optional[str] = None,
) -> None:
    """Launch a background training subprocess with pre-configured params."""
    import subprocess
    import time

    log_dir = PROJECT_ROOT / "output" / ".bg_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"bg_{data_path.stem}_{timestamp}.log"
    progress_path = log_dir / f"bg_{data_path.stem}_{timestamp}.progress.json"

    cmd = [
        sys.executable, "-m", "gsm", "train",
        "--data", str(data_path),
        "--groups", str(group_path),
        "--iterations", str(n_iterations),
        "--seed", str(seed),
        "--model", model_name,
        "--progress-file", str(progress_path),
    ]

    if run_name:
        cmd.extend(["--name", run_name])

    # Append advanced parameter overrides as CLI flags
    adv = advanced or {}
    _ADV_CLI_MAP = {
        "split_ratio": "--split-ratio",
        "normalization": "--normalization",
        "ttest_threshold": "--ttest-threshold",
        "cv_folds": "--cv-folds",
        "best_groups": "--best-groups",
        "feature_filter_size": "--feature-filter-size",
        "scoring_model": "--scoring-model",
        "class_balancing": "--class-balancing",
        "sampling_method": "--sampling-method",
        "balance_ratio": "--balance-ratio",
        "save_intermediate": "--save-intermediate",
        "bio_top_genes": "--bio-top-genes",
    }
    for key, flag in _ADV_CLI_MAP.items():
        if key in adv:
            val = adv[key]
            # Convert booleans to lowercase strings for argparse
            if isinstance(val, bool):
                cmd.extend([flag, "yes" if val else "no"])
            else:
                cmd.extend([flag, str(val)])

    console.print(
        f"\n  [dim]Launching: {' '.join(cmd[-10:])}[/dim]"
    )

    with open(log_path, "w") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            start_new_session=True,
        )

    jobs = _load_jobs()
    jobs.append({
        "pid": proc.pid,
        "dataset": data_path.stem,
        "model": model_name,
        "iterations": n_iterations,
        "seed": seed,
        "status": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "log_file": str(log_path),
        "progress_file": str(progress_path),
        "command": " ".join(cmd),
    })
    _save_jobs(jobs)

    console.print(
        f"\n  [bold green]✓ Training launched in background![/bold green]"
    )
    console.print(
        f"  [dim]PID: {proc.pid} | Log: {log_path.name}[/dim]"
    )
    console.print(
        f"  [dim]Use 'Monitor Background Jobs' to check progress.[/dim]\n"
    )


def _interactive_monitor_jobs(console) -> None:
    """Monitor background jobs — view status, logs, stop, clear."""
    from rich.table import Table
    from rich.panel import Panel

    console.print(
        "\n[bold cyan]═══ 📋 BACKGROUND JOBS ═══[/bold cyan]\n"
    )

    jobs = _load_jobs()
    jobs = _refresh_job_statuses(jobs)
    _save_jobs(jobs)

    if not jobs:
        console.print("  [dim]No background jobs recorded.[/dim]\n")
        return

    # Show status table
    table = Table(
        title=f"Background Jobs ({len(jobs)})",
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("#", style="bold cyan", width=3)
    table.add_column("Dataset", style="bold", width=15)
    table.add_column("Iterations", justify="center", width=10)
    table.add_column("PID", justify="center", width=8)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Progress", justify="center", width=14)
    table.add_column("Started At", width=20)

    for i, job in enumerate(jobs):
        status = job.get("status", "unknown")
        if status == "running":
            status_styled = "[bold yellow]⟳ running[/bold yellow]"
        elif status == "completed":
            status_styled = "[bold green]✓ done[/bold green]"
        elif status == "stopped":
            status_styled = "[bold red]✗ stopped[/bold red]"
        else:
            status_styled = f"[dim]{status}[/dim]"

        # Read progress info
        prog = _read_progress_file(job)
        if prog and prog.get("total"):
            cur = prog.get("iteration", 0)
            tot = prog["total"]
            pct = int(100 * cur / tot) if tot else 0
            progress_str = f"{cur}/{tot} ({pct}%)"
        else:
            progress_str = "[dim]—[/dim]"

        table.add_row(
            str(i + 1),
            job.get("dataset", "?"),
            str(job.get("iterations", "?")),
            str(job.get("pid", "?")),
            status_styled,
            progress_str,
            job.get("started_at", "?"),
        )

    console.print(table)
    console.print()

    # Check if there are running jobs (needed for stop option)
    has_running = any(
        j.get("status") == "running" for j in jobs
    )

    # Actions
    actions = [
        "📋  View a job's log",
        "🧹  Clear finished jobs",
    ]
    action_desc = [
        "See output from a background training",
        "Remove completed/stopped jobs from the tracker",
    ]
    if has_running:
        actions.append("🛑  Stop a running job")
        action_desc.append(
            "Send termination signal to a running job"
        )

    action = _prompt_choice(
        console, "Action", actions, action_desc,
    )

    if action is None:
        return
    elif action == 0:
        _view_job_log(console, jobs)
    elif action == 1:
        _clear_completed_jobs(console)
    elif action == 2 and has_running:
        _stop_job(console, jobs)


def _view_job_log(console, jobs: list[dict]) -> None:
    """Let the user pick a job and view its log."""
    from rich.panel import Panel

    job_names = [
        f"{j['dataset']} ({j['status']})" for j in jobs
    ]
    jidx = _prompt_choice(console, "View log for", job_names)
    if jidx is None:
        return

    log_path = Path(jobs[jidx].get("log_file", ""))
    if log_path.exists():
        text = log_path.read_text()
        lines = text.splitlines()
        if len(lines) > 40:
            display = "\n".join(lines[-40:])
            header = f"last 40 of {len(lines)} lines"
        else:
            display = text
            header = f"{len(lines)} lines"

        console.print(Panel(
            display or "[dim]Log is empty — job may still be starting.[/dim]",
            title=f"[bold]Job Log ({header})[/bold]",
            border_style="dim",
        ))
    else:
        console.print(f"  [dim]Log file not found: {log_path}[/dim]")


def _clear_completed_jobs(console) -> None:
    """Remove completed and stopped jobs from the tracker."""
    jobs = _load_jobs()
    jobs = _refresh_job_statuses(jobs)

    before = len(jobs)
    jobs = [j for j in jobs if j.get("status") == "running"]
    after = len(jobs)
    _save_jobs(jobs)

    removed = before - after
    console.print(
        f"  [green]Cleared {removed} finished job(s). "
        f"{after} still running.[/green]\n"
    )


def _stop_job(console, jobs: list[dict]) -> None:
    """Let the user pick a running job and send SIGTERM to stop it."""
    import signal

    running = [
        (i, j) for i, j in enumerate(jobs)
        if j.get("status") == "running"
    ]
    if not running:
        console.print("  [dim]No running jobs to stop.[/dim]\n")
        return

    job_labels = [
        f"{j['dataset']} (PID {j['pid']})" for _, j in running
    ]
    pick = _prompt_choice(console, "Stop which job?", job_labels)
    if pick is None:
        return

    orig_idx, job = running[pick]
    pid = job["pid"]

    try:
        # Process was started with start_new_session=True,
        # so kill the entire process group to include children.
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
        job["status"] = "stopped"
        console.print(
            f"  [bold green]✓ Sent SIGTERM to job "
            f"{job['dataset']} (PID {pid}).[/bold green]\n"
        )
    except ProcessLookupError:
        job["status"] = "completed"
        console.print(
            f"  [dim]Process {pid} already exited.[/dim]\n"
        )
    except PermissionError:
        console.print(
            f"  [bold red]✗ Permission denied stopping "
            f"PID {pid}.[/bold red]\n"
        )
        return

    # Persist updated status
    _save_jobs(jobs)


##### Launch Streamlit #####

def _launch_streamlit(console) -> None:
    """Launch the Streamlit dashboard."""
    console.print(
        "\n[bold cyan]═══ 📊 LAUNCHING DASHBOARD ═══[/bold cyan]\n"
    )
    app_path = PROJECT_ROOT / "src" / "ui" / "app.py"
    if not app_path.exists():
        console.print(
            "  [red]Streamlit app not found at src/ui/app.py[/red]\n"
        )
        return
    console.print(
        "  [dim]Starting Streamlit server... Press Ctrl+C to stop.[/dim]\n"
    )
    os.system(f"streamlit run {app_path}")


##### Quick Test #####

def _quick_test(console) -> None:
    """Run a quick test with sample data."""
    console.print("\n[bold cyan]═══ ⚡ QUICK TEST RUN ═══[/bold cyan]\n")

    data_path = PROJECT_ROOT / "data" / "test" / "test_expression_data.csv"
    group_path = PROJECT_ROOT / "data" / "test" / "test_grouping_data.csv"

    if not data_path.exists():
        console.print("  [red]Test data not found at data/test/[/red]\n")
        return

    console.print("  [dim]Running 3 iterations with test data...[/dim]\n")

    _execute_train(
        console,
        data_path=data_path,
        group_path=group_path,
        model_name="RandomForest",
        n_iterations=3,
        seed=44,
        run_bio=False,
        is_test=True,
    )


##### Help #####

def _show_help(console) -> None:
    """Display help and usage information."""
    from rich.panel import Panel
    from rich.table import Table

    console.print(
        "\n[bold cyan]═══ ❓ HELP & DOCUMENTATION ═══[/bold cyan]\n"
    )

    # Command reference
    t = Table(
        title="Command Reference", border_style="cyan", padding=(0, 2),
    )
    t.add_column("Command", style="bold cyan")
    t.add_column("Description")
    t.add_column("Example", style="dim")
    t.add_row("python -m gsm", "Interactive menu", "")
    t.add_row(
        "python -m gsm train", "Train pipeline",
        "--data GDS2545.csv --iterations 100",
    )
    t.add_row(
        "python -m gsm infer", "Clinical inference",
        "-b bundle.gsm.zip -p patients.csv",
    )
    t.add_row(
        "python -m gsm bundle-info", "Inspect bundle",
        "-b bundle.gsm.zip",
    )
    t.add_row(
        "python -m gsm runs", "Browse output runs",
        "",
    )
    t.add_row(
        "python -m gsm jobs", "Monitor background jobs",
        "",
    )
    t.add_row(
        "python -m gsm bio-validate", "Re-run bio validation",
        "--run output/gsm_2026_...",
    )
    t.add_row("python -m gsm ui", "Streamlit dashboard", "")
    t.add_row(
        "python scripts/maintenance/run_test.py", "Quick test (legacy)",
        "--iterations 5",
    )
    t.add_row(
        "python scripts/experiments/run_all_datasets.py", "Batch all datasets",
        "--iterations 50",
    )
    console.print(t)

    # Pipeline stages
    console.print()
    console.print(Panel(
        "[bold]Pipeline Stages:[/bold]\n\n"
        "  1. [cyan]Filter[/cyan]    →  Welch t-test (α=0.05) "
        "+ Benjamini-Hochberg FDR\n"
        "  2. [cyan]Group[/cyan]     →  Map genes to biological "
        "pathways (DisGeNET)\n"
        "  3. [cyan]Score[/cyan]     →  Rank groups by "
        "classification performance\n"
        "  4. [cyan]Model[/cyan]     →  Train final classifier "
        "on top gene groups\n"
        "  5. [cyan]Rank[/cyan]      →  Robust Rank Aggregation "
        "across iterations\n"
        "  6. [cyan]Validate[/cyan]  →  Enrichr + STRING-db "
        "+ DisGeNET queries\n"
        "  7. [cyan]Bundle[/cyan]    →  Package top models "
        "into .gsm.zip\n"
        "  8. [cyan]Infer[/cyan]     →  Diagnose new patients "
        "using model ensemble",
        title="[bold]GSM Pipeline Overview[/bold]",
        border_style="cyan",
    ))

    # Documentation links
    console.print()
    docs_t = Table(
        title="Documentation", border_style="cyan",
        show_header=False, padding=(0, 2),
    )
    docs_t.add_column("File", style="bold")
    docs_t.add_column("Description")
    docs_t.add_row("DOCS/RUNNING.md", "Detailed usage guide")
    docs_t.add_row("DOCS/DEVELOPMENT.md", "Developer guide")
    docs_t.add_row("DOCS/TROUBLESHOOTING.md", "Common issues & fixes")
    docs_t.add_row("README.md", "Project overview")
    console.print(docs_t)
    console.print()


##### Execution Engines #####

def _execute_train(
    console,
    data_path: Path,
    group_path: Path,
    model_name: str,
    n_iterations: int,
    seed: int,
    run_bio: bool,
    is_test: bool = False,
    progress_file: Optional[Path] = None,
    advanced: Optional[dict] = None,
    run_name: Optional[str] = None,
) -> None:
    """Execute the GSM training pipeline with rich progress display.

    Args:
        advanced: Optional dict of advanced parameter overrides.
            Valid keys: split_ratio, normalization, ttest_threshold,
            cv_folds, best_groups, feature_filter_size, scoring_model,
            class_balancing, sampling_method, balance_ratio,
            save_intermediate, bio_top_genes.
    """
    from rich.panel import Panel
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn,
        MofNCompleteColumn, TimeElapsedColumn, TimeRemainingColumn,
    )
    import time

    from src.data_processing.data_loader import (
        load_input_file, load_group_file,
    )
    from src.workflows.GSM_workflow import gsm_run
    from src.workflows.GSM_workflow_config import (
        MAIN_DATA_FILE_SEPARATOR, GROUPING_FILE_SEPARATOR,
        TRAIN_TEST_SPLIT_RATIO, SCORING_MODEL,
        LABEL_COLUMN_NAME, CLASS_LABELS_POSITIVE, CLASS_LABELS_NEGATIVE,
        GENE_COLUMN_NAME, GROUP_COLUMN_NAME, NORMALIZATION_METHOD,
        BIOLOGICAL_VALIDATION_TOP_GENES, DISGENET_API_KEY,
        TTEST_THRESHOLD, CROSS_VALIDATION_FOLDS,
        BEST_GROUPS_TO_KEEP, INITIAL_FEATURE_FILTER_SIZE,
        APPLY_CLASS_BALANCING, MIN_CLASS_BALANCE_RATIO,
        SAMPLING_METHOD, SAVE_INTERMEDIATE_RESULTS,
    )

    adv = advanced or {}

    console.print()
    console.print(Panel(
        f"  Dataset:     [bold]{data_path.stem}[/bold]\n"
        f"  Grouping:    [bold]{group_path.name}[/bold]\n"
        f"  Classifier:  [bold]{model_name}[/bold]\n"
        f"  Iterations:  [bold]{n_iterations}[/bold]\n"
        f"  Seed:        [bold]{seed}[/bold]"
        + (f"\n  Name:        [bold]{run_name}[/bold]" if run_name else ""),
        title="[bold cyan]🧬 Starting Training[/bold cyan]",
        border_style="green",
    ))

    # Load data with spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            "Loading expression data...", total=None,
        )
        input_data = load_input_file(
            data_path, separator=MAIN_DATA_FILE_SEPARATOR,
        )
        progress.update(task, description="Loading grouping data...")
        group_data = load_group_file(
            group_path, separator=GROUPING_FILE_SEPARATOR,
        )
        progress.update(task, description="Data loaded!")

    console.print(
        f"  [green]✓[/green] Expression data: "
        f"[bold]{input_data.shape[0]}[/bold] samples × "
        f"[bold]{input_data.shape[1]}[/bold] features"
    )
    console.print(
        f"  [green]✓[/green] Grouping data:   "
        f"[bold]{group_data.shape[0]}[/bold] gene-group mappings\n"
    )

    # Run pipeline with a live iteration progress bar
    t0 = time.time()

    # Build a shared progress bar that the callback will update
    train_progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
    )
    train_task = train_progress.add_task(
        "Preprocessing…", total=n_iterations, completed=0,
    )

    def _on_progress(iteration, total, elapsed, eta_seconds):
        """Callback invoked by gsm_run after each iteration."""
        train_progress.update(
            train_task,
            completed=iteration,
            description=f"Iteration {iteration}/{total}",
        )

    console.print("  [bold]Running GSM pipeline…[/bold]\n")

    try:
        with train_progress:
            output_path = gsm_run(
                input_data,
                group_data,
                n_iterations=n_iterations,
                model_name=model_name,
                scoring_model=adv.get(
                    "scoring_model", SCORING_MODEL,
                ),
                initial_seed=seed,
                sample_ratio=adv.get(
                    "split_ratio", TRAIN_TEST_SPLIT_RATIO,
                ),
                label_column=LABEL_COLUMN_NAME,
                positive_class_label=CLASS_LABELS_POSITIVE,
                negative_class_label=CLASS_LABELS_NEGATIVE,
                gene_column=GENE_COLUMN_NAME,
                group_column=GROUP_COLUMN_NAME,
                normalization_method=adv.get(
                    "normalization", NORMALIZATION_METHOD,
                ),
                ttest_threshold=adv.get(
                    "ttest_threshold", TTEST_THRESHOLD,
                ),
                cross_validation_folds=adv.get(
                    "cv_folds", CROSS_VALIDATION_FOLDS,
                ),
                best_groups_to_keep=adv.get(
                    "best_groups", BEST_GROUPS_TO_KEEP,
                ),
                initial_feature_filter_size=adv.get(
                    "feature_filter_size", INITIAL_FEATURE_FILTER_SIZE,
                ),
                apply_class_balancing=adv.get(
                    "class_balancing", APPLY_CLASS_BALANCING,
                ),
                min_class_balance_ratio=adv.get(
                    "balance_ratio", MIN_CLASS_BALANCE_RATIO,
                ),
                sampling_method=adv.get(
                    "sampling_method", SAMPLING_METHOD,
                ),
                save_intermediate_results=adv.get(
                    "save_intermediate", SAVE_INTERMEDIATE_RESULTS,
                ),
                run_biological_validation_flag=run_bio,
                biological_validation_top_genes=adv.get(
                    "bio_top_genes", BIOLOGICAL_VALIDATION_TOP_GENES,
                ),
                disgenet_api_key=DISGENET_API_KEY,
                input_data_name=data_path.stem,
                group_data_name=group_path.stem,
                progress_callback=_on_progress,
                progress_file=progress_file,
                run_name=run_name,
            )
    except Exception as e:
        console.print(
            f"\n  [bold red]✗ Pipeline failed: {e}[/bold red]\n"
        )
        return

    elapsed = time.time() - t0

    # Success display
    console.print()
    result_lines = [
        f"  Status:      [bold green]SUCCESS[/bold green]",
        f"  Time:        [bold]{elapsed:.1f}s[/bold]",
        f"  Output:      [bold]{output_path}[/bold]",
    ]

    # Check for bundle
    bundles_dir = output_path / "bundles" if output_path else None
    if bundles_dir and bundles_dir.exists():
        bundle_files = list(bundles_dir.glob("*.gsm.zip"))
        if bundle_files:
            result_lines.append(
                f"  Bundle:      [bold]{bundle_files[0].name}[/bold]"
            )

    console.print(Panel(
        "\n".join(result_lines),
        title="[bold green]🎉 Training Complete[/bold green]",
        border_style="green",
    ))

    # Next steps
    if bundles_dir and bundles_dir.exists():
        bundle_files = list(bundles_dir.glob("*.gsm.zip"))
        if bundle_files:
            console.print()
            console.print(Panel(
                f"  To diagnose patients:\n"
                f"  [bold cyan]python -m gsm infer "
                f"-b {bundle_files[0]} -p patients.csv[/bold cyan]\n\n"
                f"  To inspect the bundle:\n"
                f"  [bold cyan]python -m gsm bundle-info "
                f"-b {bundle_files[0]}[/bold cyan]",
                title="[bold]Next Steps[/bold]",
                border_style="dim",
            ))
    console.print()


def _execute_infer(
    console,
    bundle_path: Path,
    patients_path: Path,
    sample_id_column: Optional[str] = None,
) -> None:
    """Execute clinical inference with rich result display."""
    import pandas as pd
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from src.inference.model_bundle import load_bundle
    from src.inference.inference_engine import infer
    from src.inference.clinical_report import (
        generate_clinical_report,
        save_clinical_report,
    )
    from src.utils.logger import setup_logger

    output_dir = bundle_path.parent.parent / "inference_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(
        str(output_dir / "inference.log"),
        logger_name="GSM_inference",
    )

    console.print()

    # Load with spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            "Loading model bundle...", total=None,
        )
        bundle = load_bundle(bundle_path, logger=logger)

        progress.update(
            task, description="Loading patient data...",
        )
        patient_data = pd.read_csv(
            patients_path, sep=None, engine="python",
        )
        progress.update(
            task, description="Running ensemble inference...",
        )
        summary = infer(
            bundle, patient_data, logger=logger,
            sample_id_column=sample_id_column,
        )

    # Bundle info compact
    console.print(Panel(
        f"  Models:   [bold]{bundle.metadata.n_models_saved}[/bold] "
        f"in ensemble\n"
        f"  Train DS: [bold]{bundle.metadata.dataset_name}[/bold]\n"
        f"  Train N:  [bold]{bundle.metadata.n_training_samples}[/bold]\n"
        f"  Features: [bold]{bundle.metadata.n_features}[/bold] genes\n"
        f"  F1:       [bold]{bundle.metadata.ensemble_f1_mean:.4f}[/bold]"
        f" ± {bundle.metadata.ensemble_f1_std:.4f}\n"
        f"  Patients: [bold]{len(patient_data)}[/bold] samples",
        title="[bold cyan]🏥 Inference Summary[/bold cyan]",
        border_style="cyan",
    ))

    # Results table
    results_table = Table(
        title="Patient Predictions",
        border_style="cyan",
        show_lines=True,
        padding=(0, 1),
    )
    results_table.add_column("Sample", style="bold")
    results_table.add_column("Prediction", justify="center")
    results_table.add_column("Probability", justify="center")
    results_table.add_column("Risk", justify="center")
    results_table.add_column("Confidence", justify="center")
    results_table.add_column("Agreement", justify="center")
    results_table.add_column("Top Contributing Genes", max_width=40)

    for result in summary.results:
        # Color-code risk
        risk = result.risk_level
        if risk == "HIGH":
            risk_styled = "[bold red]HIGH[/bold red]"
        elif risk == "MEDIUM":
            risk_styled = "[bold yellow]MEDIUM[/bold yellow]"
        else:
            risk_styled = "[bold green]LOW[/bold green]"

        # Color-code prediction
        pred_label = result.predicted_label
        if pred_label.lower() in (
            "pos", "positive", "1", "true", "disease",
        ):
            pred_styled = f"[bold red]{pred_label}[/bold red]"
        else:
            pred_styled = f"[bold green]{pred_label}[/bold green]"

        # Format confidence
        conf = result.confidence
        if conf >= 0.9:
            conf_styled = f"[bold green]{conf:.1%}[/bold green]"
        elif conf >= 0.7:
            conf_styled = f"[yellow]{conf:.1%}[/yellow]"
        else:
            conf_styled = f"[red]{conf:.1%}[/red]"

        # Top genes
        top_genes = ", ".join(
            list(result.top_contributing_genes.keys())[:5]
        )

        # Mean probability from individual model probs
        mean_prob = (
            sum(result.individual_probabilities)
            / len(result.individual_probabilities)
            if result.individual_probabilities else 0.0
        )

        results_table.add_row(
            str(result.sample_id),
            pred_styled,
            f"{mean_prob:.3f}",
            risk_styled,
            conf_styled,
            f"{result.agreement_ratio:.1%}",
            top_genes,
        )

    console.print()
    console.print(results_table)

    # Save reports
    save_clinical_report(summary, output_dir, logger)

    console.print()
    console.print(Panel(
        f"  Reports saved to: [bold]{output_dir}[/bold]\n"
        f"  Files: clinical_report.txt, clinical_report.csv",
        title="[bold green]📁 Reports Saved[/bold green]",
        border_style="green",
    ))
    console.print()


def _execute_multi_infer(
    console,
    bundle_paths: list[Path],
    patients_path: Path,
    sample_id_column: Optional[str] = None,
) -> None:
    """Execute multi-bundle inference with rich result display."""
    import pandas as pd
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from src.inference.model_bundle import load_bundle
    from src.inference.inference_engine import multi_infer
    from src.inference.clinical_report import save_multi_bundle_report
    from src.utils.logger import setup_logger

    # Use first bundle's parent for output
    output_dir = bundle_paths[0].parent.parent / "inference_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(
        str(output_dir / "multi_inference.log"),
        logger_name="GSM_multi_inference",
    )

    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            "Loading model bundles...", total=None,
        )
        loaded_bundles = []
        for i, bp in enumerate(bundle_paths):
            progress.update(
                task,
                description=f"Loading bundle {i+1}/{len(bundle_paths)}...",
            )
            loaded_bundles.append(load_bundle(bp, logger=logger))

        progress.update(
            task, description="Loading patient data...",
        )
        patient_data = pd.read_csv(
            patients_path, sep=None, engine="python",
        )

        progress.update(
            task, description="Running multi-bundle inference...",
        )
        summary = multi_infer(
            loaded_bundles, patient_data,
            logger=logger,
            sample_id_column=sample_id_column,
        )

    # Summary panel
    bundle_info_lines = []
    for b in loaded_bundles:
        m = b.metadata
        bundle_info_lines.append(
            f"  • {m.dataset_name}: {m.n_models_saved} models, "
            f"{m.n_features} features, F1={m.ensemble_f1_mean:.3f}"
        )

    console.print(Panel(
        f"  Bundles:  [bold]{summary.n_bundles}[/bold]\n"
        + "\n".join(bundle_info_lines) + "\n"
        f"  Patients: [bold]{summary.n_samples}[/bold] samples",
        title="[bold cyan]🏥 Multi-Bundle Inference[/bold cyan]",
        border_style="cyan",
    ))

    # Results table
    results_table = Table(
        title="Consensus Predictions",
        border_style="cyan",
        show_lines=True,
        padding=(0, 1),
    )
    results_table.add_column("Sample", style="bold")
    results_table.add_column("Consensus", justify="center")
    results_table.add_column("Confidence", justify="center")
    results_table.add_column("Risk", justify="center")
    results_table.add_column("Bundles +", justify="center")
    results_table.add_column("Agreement", justify="center")
    results_table.add_column("Top Genes (merged)", max_width=40)

    for r in summary.results:
        risk = r.risk_level
        if risk == "HIGH":
            risk_styled = "[bold red]HIGH[/bold red]"
        elif risk == "MEDIUM":
            risk_styled = "[bold yellow]MEDIUM[/bold yellow]"
        else:
            risk_styled = "[bold green]LOW[/bold green]"

        pred = r.predicted_class
        if pred == "positive":
            pred_styled = "[bold red]positive[/bold red]"
        else:
            pred_styled = "[bold green]negative[/bold green]"

        conf = r.consensus_confidence
        if conf >= 0.9:
            conf_styled = f"[bold green]{conf:.1%}[/bold green]"
        elif conf >= 0.7:
            conf_styled = f"[yellow]{conf:.1%}[/yellow]"
        else:
            conf_styled = f"[red]{conf:.1%}[/red]"

        top_genes = ", ".join(
            list(r.top_contributing_genes.keys())[:5]
        )

        results_table.add_row(
            str(r.sample_id),
            pred_styled,
            conf_styled,
            risk_styled,
            f"{r.n_bundles_positive}/{r.n_bundles_total}",
            f"{r.agreement_ratio:.0%}",
            top_genes,
        )

    console.print()
    console.print(results_table)

    # Save reports
    save_multi_bundle_report(summary, output_dir, logger)

    console.print()
    console.print(Panel(
        f"  Reports saved to: [bold]{output_dir}[/bold]\n"
        f"  Files: multi_bundle_report.txt, multi_bundle_report.xlsx",
        title="[bold green]📁 Reports Saved[/bold green]",
        border_style="green",
    ))
    console.print()


def _execute_bundle_info(console, bundle_path: Path) -> None:
    """Display bundle info with rich formatting."""
    from rich.panel import Panel
    from src.inference.model_bundle import bundle_info

    info_text = bundle_info(bundle_path)

    console.print()
    console.print(Panel(
        info_text,
        title=f"[bold cyan]📦 {bundle_path.name}[/bold cyan]",
        border_style="cyan",
    ))
    console.print()


##### Argparse CLI (Direct Commands) #####

def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for non-interactive use."""
    parser = argparse.ArgumentParser(
        prog="gsm",
        description=(
            "🧬 GSM Bioinformatics Pipeline — "
            "Train classifiers & diagnose patients"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Interactive mode (no arguments):\n"
            "  python -m gsm\n\n"
            "Direct commands:\n"
            "  python -m gsm train --data data/expression_data/GDS2545.csv "
            "--iterations 100\n"
            "  python -m gsm bio-validate --run output/gsm_2026_...\n"
            "  python -m gsm infer -b bundle.gsm.zip -p patients.csv\n"
            "  python -m gsm multi-infer -b b1.gsm.zip b2.gsm.zip "
            "-p patients.csv\n"
            "  python -m gsm bundle-info -b bundle.gsm.zip\n"
            "  python -m gsm ui\n"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands",
    )

    # ── train ──
    train_p = subparsers.add_parser(
        "train", help="Train the GSM pipeline",
    )
    train_p.add_argument(
        "--data", type=str, default=None,
        help="Path to expression data CSV",
    )
    train_p.add_argument(
        "--groups", type=str, default=None,
        help="Path to grouping data file",
    )
    train_p.add_argument(
        "--iterations", "-n", type=int, default=None,
        help="Number of iterations (default: config)",
    )
    train_p.add_argument(
        "--model", type=str, default=None,
        choices=[
            "RandomForest", "XGBoost", "DecisionTree",
            "SVM", "KNN", "MLP",
        ],
        help="Classifier to use",
    )
    train_p.add_argument(
        "--seed", type=int, default=None,
        help="Random seed (default: 44)",
    )
    train_p.add_argument(
        "--test", action="store_true",
        help="Use test data for a quick run",
    )
    train_p.add_argument(
        "--no-bio-validation", action="store_true",
        help="Skip biological validation",
    )
    train_p.add_argument(
        "--name", type=str, default=None,
        help="Optional experiment name (appended to output folder and bundle)",
    )
    train_p.add_argument(
        "--progress-file", type=str, default=None,
        help="Path to write iteration progress JSON (used by background jobs)",
    )

    # ── train: advanced parameters ──
    adv_group = train_p.add_argument_group("advanced parameters")
    adv_group.add_argument(
        "--split-ratio", type=float, default=None,
        help="Train/test split ratio (default: 0.7)",
    )
    adv_group.add_argument(
        "--normalization", type=str, default=None,
        choices=["zscore", "minmax", "robust"],
        help="Normalization method (default: zscore)",
    )
    adv_group.add_argument(
        "--ttest-threshold", type=float, default=None,
        help="T-test FDR threshold (default: 0.05)",
    )
    adv_group.add_argument(
        "--cv-folds", type=int, default=None,
        help="Cross-validation folds for scoring (default: 3)",
    )
    adv_group.add_argument(
        "--best-groups", type=int, default=None,
        help="Number of top gene groups to keep (default: 10)",
    )
    adv_group.add_argument(
        "--feature-filter-size", type=int, default=None,
        help="Initial feature filter size, 0=off (default: 0)",
    )
    adv_group.add_argument(
        "--scoring-model", type=str, default=None,
        choices=["RandomForest", "XGBoost", "DecisionTree"],
        help="Model used for group scoring (default: RandomForest)",
    )
    adv_group.add_argument(
        "--class-balancing", type=str, default=None,
        choices=["yes", "no"],
        help="Apply class balancing (default: yes)",
    )
    adv_group.add_argument(
        "--sampling-method", type=str, default=None,
        choices=["undersampling", "oversampling"],
        help="Sampling method for class balancing (default: undersampling)",
    )
    adv_group.add_argument(
        "--balance-ratio", type=float, default=None,
        help="Min class balance ratio (default: 0.5)",
    )
    adv_group.add_argument(
        "--save-intermediate", type=str, default=None,
        choices=["yes", "no"],
        help="Save intermediate iteration results (default: yes)",
    )
    adv_group.add_argument(
        "--bio-top-genes", type=int, default=None,
        help="Number of top genes for bio validation (default: 20)",
    )

    # ── infer ──
    infer_p = subparsers.add_parser(
        "infer", help="Clinical inference on patient data",
    )
    infer_p.add_argument(
        "--bundle", "-b", type=str, required=True,
        help="Path to .gsm.zip bundle",
    )
    infer_p.add_argument(
        "--patients", "-p", type=str, required=True,
        help="Path to patient expression CSV",
    )
    infer_p.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output directory for reports",
    )
    infer_p.add_argument(
        "--sample-id-column", type=str, default=None,
        help="Column with sample IDs",
    )

    # ── bundle-info ──
    info_p = subparsers.add_parser(
        "bundle-info", help="Inspect a model bundle",
    )
    info_p.add_argument(
        "--bundle", "-b", type=str, required=True,
        help="Path to .gsm.zip bundle",
    )

    # ── multi-infer ──
    multi_p = subparsers.add_parser(
        "multi-infer",
        help="Multi-bundle inference (combine multiple datasets)",
    )
    multi_p.add_argument(
        "--bundles", "-b", type=str, nargs="+", required=True,
        help="Paths to .gsm.zip bundles (2 or more)",
    )
    multi_p.add_argument(
        "--patients", "-p", type=str, required=True,
        help="Path to patient expression CSV",
    )
    multi_p.add_argument(
        "--sample-id-column", type=str, default=None,
        help="Column with sample IDs",
    )

    # ── ui ──
    subparsers.add_parser("ui", help="Launch Streamlit dashboard")

    # ── runs ──
    subparsers.add_parser(
        "runs", help="Browse and inspect past pipeline output runs",
    )

    # ── jobs ──
    subparsers.add_parser(
        "jobs", help="Monitor background training jobs",
    )

    # ── bio-validate ──
    bio_p = subparsers.add_parser(
        "bio-validate",
        help="Re-run biological validation on a completed run",
    )
    bio_p.add_argument(
        "--run", "-r", type=str, required=True,
        help="Path to the output run directory",
    )
    bio_p.add_argument(
        "--top-genes", type=int, default=None,
        help="Number of top genes to validate (default: config)",
    )
    bio_p.add_argument(
        "--grouping", "-g", type=str, default=None,
        help="Path to grouping file for group validation",
    )
    bio_p.add_argument(
        "--disgenet-key", type=str, default=None,
        help="DisGeNET API key",
    )

    return parser


def _build_advanced_from_args(args: argparse.Namespace) -> dict:
    """Extract advanced parameter overrides from parsed CLI arguments.

    Maps argparse attribute names (with underscores/hyphens) to the
    canonical keys used by _execute_train's `advanced` dict.
    Only non-None values are included.
    """
    mapping = {
        "split_ratio": "split_ratio",
        "normalization": "normalization",
        "ttest_threshold": "ttest_threshold",
        "cv_folds": "cv_folds",
        "best_groups": "best_groups",
        "feature_filter_size": "feature_filter_size",
        "scoring_model": "scoring_model",
        "sampling_method": "sampling_method",
        "balance_ratio": "balance_ratio",
        "bio_top_genes": "bio_top_genes",
    }
    result: dict = {}
    for attr, key in mapping.items():
        val = getattr(args, attr, None)
        if val is not None:
            result[key] = val

    # Boolean-from-string fields: yes/no → True/False
    cb = getattr(args, "class_balancing", None)
    if cb is not None:
        result["class_balancing"] = cb.lower() in ("yes", "true", "1")

    si = getattr(args, "save_intermediate", None)
    if si is not None:
        result["save_intermediate"] = si.lower() in ("yes", "true", "1")

    return result


def _handle_train_args(args: argparse.Namespace) -> None:
    """Handle direct train command."""
    from src.workflows.GSM_workflow_config import (
        INPUT_EXPRESSION_DATA, INPUT_GROUP_DATA,
        NUMBER_OF_ITERATIONS, RANDOM_SEED, MODEL_NAME,
        RUN_BIOLOGICAL_VALIDATION,
    )

    console = _get_console()
    console.print(BANNER)

    if args.test:
        data_path = (
            PROJECT_ROOT / "data" / "test" / "test_expression_data.csv"
        )
        group_path = (
            PROJECT_ROOT / "data" / "test" / "test_grouping_data.csv"
        )
        n_iterations = args.iterations or 3
    else:
        data_path = (
            Path(args.data) if args.data
            else PROJECT_ROOT / INPUT_EXPRESSION_DATA
        )
        group_path = (
            Path(args.groups) if args.groups
            else PROJECT_ROOT / INPUT_GROUP_DATA
        )
        n_iterations = args.iterations or NUMBER_OF_ITERATIONS

    # Build advanced overrides dict from CLI arguments
    advanced = _build_advanced_from_args(args)

    _execute_train(
        console,
        data_path=data_path,
        group_path=group_path,
        model_name=args.model or MODEL_NAME,
        n_iterations=n_iterations,
        seed=args.seed or RANDOM_SEED,
        run_bio=(
            not args.no_bio_validation and RUN_BIOLOGICAL_VALIDATION
        ),
        is_test=args.test,
        progress_file=(
            Path(args.progress_file) if args.progress_file else None
        ),
        advanced=advanced if advanced else None,
        run_name=getattr(args, "name", None),
    )


def _handle_infer_args(args: argparse.Namespace) -> None:
    """Handle direct infer command."""
    console = _get_console()
    console.print(BANNER)

    bundle_path = Path(args.bundle)
    patients_path = Path(args.patients)

    if not bundle_path.exists():
        console.print(
            f"  [bold red]✗ Bundle not found: {bundle_path}[/bold red]\n"
        )
        sys.exit(1)
    if not patients_path.exists():
        console.print(
            f"  [bold red]✗ Patient file not found: "
            f"{patients_path}[/bold red]\n"
        )
        sys.exit(1)

    _execute_infer(
        console, bundle_path, patients_path, args.sample_id_column,
    )


def _handle_bundle_info_args(args: argparse.Namespace) -> None:
    """Handle direct bundle-info command."""
    console = _get_console()
    console.print(BANNER)

    bundle_path = Path(args.bundle)
    if not bundle_path.exists():
        console.print(
            f"  [bold red]✗ Bundle not found: "
            f"{bundle_path}[/bold red]\n"
        )
        sys.exit(1)

    _execute_bundle_info(console, bundle_path)


def _handle_bio_validate_args(args: argparse.Namespace) -> None:
    """Handle direct bio-validate command."""
    from rich.panel import Panel

    console = _get_console()
    console.print(BANNER)

    run_dir = Path(args.run)
    if not run_dir.exists():
        console.print(
            f"  [bold red]✗ Run directory not found: "
            f"{run_dir}[/bold red]\n"
        )
        sys.exit(1)

    results_json = run_dir / "modeling_results_all_iterations.json"
    if not results_json.exists():
        console.print(
            f"  [bold red]✗ No modeling results JSON in "
            f"{run_dir.name}[/bold red]\n"
        )
        sys.exit(1)

    from src.workflows.GSM_workflow_config import (
        DISGENET_API_KEY, BIOLOGICAL_VALIDATION_TOP_GENES,
        GENE_COLUMN_NAME, GROUP_COLUMN_NAME,
    )
    from src.utils.biological_validation import run_biological_validation
    from src.utils.logger import setup_logger
    import tempfile

    api_key = args.disgenet_key or DISGENET_API_KEY or None
    top_n = args.top_genes or BIOLOGICAL_VALIDATION_TOP_GENES
    grouping_path = Path(args.grouping) if args.grouping else None

    console.print(Panel(
        f"  Run:        [bold]{run_dir.name}[/bold]\n"
        f"  Top genes:  [bold]{top_n}[/bold]\n"
        f"  Grouping:   [bold]"
        f"{grouping_path.name if grouping_path else 'None'}[/bold]\n"
        f"  DisGeNET:   [bold]"
        f"{'yes' if api_key else 'no key'}[/bold]",
        title="[bold cyan]🧬 Biological Validation[/bold cyan]",
        border_style="cyan",
    ))

    console.print(
        "  [yellow]⚠ Internet connection is required for API queries."
        "[/yellow]\n"
    )

    log_path = Path(tempfile.mktemp(suffix=".log"))
    logger = setup_logger(str(log_path), logger_name="bio_validate_cli")

    try:
        report = run_biological_validation(
            output_dir=run_dir,
            results_json_path=results_json,
            logger=logger,
            disgenet_api_key=api_key,
            top_n_genes=top_n,
            grouping_data_path=grouping_path,
            gene_column=GENE_COLUMN_NAME,
            group_column=GROUP_COLUMN_NAME,
        )
        console.print(Panel(
            f"  Genes validated:     [bold]{len(report.input_genes)}"
            f"[/bold]\n"
            f"  Enrichr results:     [bold]"
            f"{len(report.enrichr_results)}[/bold]\n"
            f"  STRING interactions: [bold]"
            f"{len(report.string_interactions)}[/bold]\n"
            f"  Disease assocs:      [bold]"
            f"{len(report.disease_associations)}[/bold]\n\n"
            f"  Output: [bold]{run_dir.name}/biological_validation/"
            f"[/bold]",
            title="[bold green]✅ Validation Complete[/bold green]",
            border_style="green",
        ))
    except Exception as e:
        console.print(
            f"\n  [bold red]✗ Biological validation failed: "
            f"{e}[/bold red]"
        )
        console.print(
            "  [yellow]⚠ Check your internet connection and "
            "try again.[/yellow]\n"
        )
        sys.exit(1)


def _handle_ui_args(args: argparse.Namespace) -> None:
    """Handle direct ui command."""
    console = _get_console()
    console.print(BANNER)
    _launch_streamlit(console)


def _handle_runs_args(args: argparse.Namespace) -> None:
    """Handle direct runs command."""
    console = _get_console()
    console.print(BANNER)
    _interactive_browse_outputs(console)


def _handle_jobs_args(args: argparse.Namespace) -> None:
    """Handle direct jobs command."""
    console = _get_console()
    console.print(BANNER)
    _interactive_monitor_jobs(console)


def _handle_multi_infer_args(args: argparse.Namespace) -> None:
    """Handle direct multi-infer command."""
    console = _get_console()
    console.print(BANNER)

    bundle_paths = [Path(b) for b in args.bundles]
    patients_path = Path(args.patients)

    for bp in bundle_paths:
        if not bp.exists():
            console.print(
                f"  [bold red]✗ Bundle not found: {bp}[/bold red]\n"
            )
            sys.exit(1)

    if not patients_path.exists():
        console.print(
            f"  [bold red]✗ Patient file not found: "
            f"{patients_path}[/bold red]\n"
        )
        sys.exit(1)

    if len(bundle_paths) < 2:
        console.print(
            "  [bold red]✗ Need at least 2 bundles for "
            "multi-bundle inference.[/bold red]\n"
        )
        sys.exit(1)

    _execute_multi_infer(
        console, bundle_paths, patients_path,
        args.sample_id_column,
    )


##### Main Entry Point #####

def main() -> None:
    """Main CLI entry point.

    No arguments → interactive menu.
    With subcommand → direct dispatch.
    """
    # If no arguments, launch interactive mode
    if len(sys.argv) <= 1 or (
        len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help")
    ):
        if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
            # Show help via argparse for --help flag
            parser = _build_parser()
            console = _get_console()
            console.print(BANNER)
            parser.print_help()
            return
        # No args → interactive
        interactive_menu()
        return

    # Parse and dispatch
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        interactive_menu()
    elif args.command == "train":
        _handle_train_args(args)
    elif args.command == "infer":
        _handle_infer_args(args)
    elif args.command == "multi-infer":
        _handle_multi_infer_args(args)
    elif args.command == "bundle-info":
        _handle_bundle_info_args(args)
    elif args.command == "ui":
        _handle_ui_args(args)
    elif args.command == "runs":
        _handle_runs_args(args)
    elif args.command == "jobs":
        _handle_jobs_args(args)
    elif args.command == "bio-validate":
        _handle_bio_validate_args(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
