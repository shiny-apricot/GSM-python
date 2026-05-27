#!/usr/bin/env python3
"""
Publication Finalization Script 📄

Purpose:
    After all experiments (main pipeline, baselines, sensitivity, seed
    stability, classifier comparison) have finished, this script:
      1. Moves main pipeline outputs into output/main_runs/
      2. Runs analyze_manuscript_results.py → manuscript_data.json + figures
      3. Runs generate_baseline_comparison.py → baseline comparison figure
      4. Updates the LaTeX presentation with fresh numbers from results
      5. Builds the manuscript docx

Usage:
    python scripts/manuscript/finalize_publication.py
    python scripts/manuscript/finalize_publication.py --skip-move      # don't reorganise outputs
    python scripts/manuscript/finalize_publication.py --skip-manuscript # don't rebuild docx
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


##### CONSTANTS #####

DATASETS = [
    "GDS1962", "GDS2545", "GDS2547", "GDS2771",
    "GDS3257", "GDS3837", "GDS5499",
]

DATASET_SHORT = {
    "GDS1962": "Glioblastoma",
    "GDS2545": "Prostate",
    "GDS2547": "Prostate (L.)",
    "GDS2771": "Lung",
    "GDS3257": "AML",
    "GDS3837": "Colorectal",
    "GDS5499": "Pancreatic",
}


##### STEP 1: MOVE OUTPUTS TO main_runs/ #####

def move_outputs_to_main_runs():
    """Move publication pipeline output folders into output/main_runs/."""
    output_dir = project_root / "output"
    main_runs = output_dir / "main_runs"
    main_runs.mkdir(exist_ok=True)

    moved = 0
    for folder in sorted(output_dir.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name in (
            "main_runs", "sensitivity_runs", "test_runs",
            "classifier_comparison", "archives", "baselines",
            "seed_stability", "comparison_gl_vs_gsm",
            "main_runs_xgboost_archive", "stability_test",
        ):
            continue
        # Only move publication-main runs
        if "publication-main" in folder.name:
            dest = main_runs / folder.name
            if dest.exists():
                print(f"   ⚠️  Already exists: {dest.name}")
                continue
            shutil.move(str(folder), str(dest))
            moved += 1
            print(f"   ✓ Moved {folder.name}")

    print(f"   Moved {moved} folders to output/main_runs/")
    return moved


##### STEP 2: RUN ANALYSIS PIPELINE #####

def run_analysis():
    """Run analyze_manuscript_results.py to generate manuscript_data.json."""
    script = project_root / "scripts" / "manuscript" / "analyze_manuscript_results.py"
    print(f"\n📊 Running {script.name}...")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(project_root),
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"⚠️  Analysis failed:\n{result.stderr}")
        return False
    return True


##### STEP 3: GENERATE BASELINE FIGURE #####

def run_baseline_figure():
    """Run generate_baseline_comparison.py."""
    script = project_root / "scripts" / "manuscript" / "generate_baseline_comparison.py"
    bl_data = project_root / "output" / "baselines" / "baseline_results.json"
    if not bl_data.exists():
        print("⚠️  Baseline results not found — skipping figure generation")
        return False

    print(f"\n📊 Running {script.name}...")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(project_root),
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"⚠️  Baseline figure failed:\n{result.stderr}")
        return False
    return True


##### STEP 4: UPDATE PRESENTATION #####

def update_presentation():
    """Update gsm_presentation.tex with numbers from manuscript_data.json."""
    json_path = (
        project_root / "reports_ARCHIVE" / "manuscript" / "data"
        / "manuscript_data.json"
    )
    tex_path = (
        project_root / "reports_ARCHIVE" / "presentations" / "gsm"
        / "gsm_presentation.tex"
    )

    if not json_path.exists():
        print("⚠️  manuscript_data.json not found — skipping presentation update")
        return False

    data = json.loads(json_path.read_text())
    perf = data["performance"]
    val = data.get("validation", [])

    if not perf:
        print("⚠️  No performance data — skipping presentation update")
        return False

    tex = tex_path.read_text()
    original = tex

    # Compute aggregate metrics
    n = len(perf)
    avg_f1 = sum(d["f1_score"] for d in perf) / n
    avg_auc = sum(d["auc_roc"] for d in perf) / n
    perfect = sum(1 for d in perf if d["f1_score"] >= 0.999)
    hardest = min(perf, key=lambda d: d["f1_score"])
    total_ppi = sum(v.get("string_interaction_count", 0) for v in val)

    # --- Update "Overall Performance" table ---
    old_table = _extract_tex_block(tex, r"\\midrule", r"\\midrule",
                                    block_name="performance table")
    if old_table:
        new_rows = []
        for d in perf:
            ds = d["dataset_id"]
            short = DATASET_SHORT.get(ds, "")
            f1 = d["f1_score"]
            f1_lo = d["f1_ci_lower"]
            f1_hi = d["f1_ci_upper"]
            auc = d["auc_roc"]
            auc_lo = d["auc_ci_lower"]
            auc_hi = d["auc_ci_upper"]
            grp = d["groups_used"]
            feat = d["features_used"]
            bold = r"\textbf{" + f"{f1:.3f}" + "}" if f1 >= 0.999 else f"{f1:.3f}"
            new_rows.append(
                f"{ds} & {short} & {bold} & "
                f"[{f1_lo:.2f}--{f1_hi:.2f}] & "
                f"{auc:.3f} & [{auc_lo:.2f}--{auc_hi:.2f}] & "
                f"{grp}  & {feat}  \\\\"
            )
        mean_row = (
            f"\\multicolumn{{2}}{{l}}{{\\textit{{Mean}}}} &\n"
            f"  \\textbf{{{avg_f1:.3f}}} & & "
            f"\\textbf{{{avg_auc:.3f}}} & & & \\\\"
        )
        # Build full replacement
        new_block = "\n".join(new_rows) + "\n\\midrule\n" + mean_row
        # Replace the performance table body between the two \midrule lines
        tex = _replace_perf_table(tex, perf, avg_f1, avg_auc)

    # --- Update "Key Numbers at a Glance" ---
    tex = re.sub(
        r"Mean F1\s+&\s+\\textbf\{[\d.]+\}",
        f"Mean F1                     & \\\\textbf{{{avg_f1:.3f}}}",
        tex,
    )
    tex = re.sub(
        r"Mean AUC-ROC\s+&\s+\\textbf\{[\d.]+\}",
        f"Mean AUC-ROC                & \\\\textbf{{{avg_auc:.3f}}}",
        tex,
    )
    tex = re.sub(
        r"Perfect F1 datasets\s+&\s+\d+\s*/\s*\d+",
        f"Perfect F1 datasets         & {perfect} / {n}",
        tex,
    )
    if total_ppi > 0:
        tex = re.sub(
            r"Total STRING interactions\s+&\s+\d+",
            f"Total STRING interactions   & {total_ppi}",
            tex,
        )

    # --- Update narrative text ---
    # "4/7 datasets reach perfect F1" line
    tex = re.sub(
        r"\d+/\d+ datasets reach \\textbf\{perfect\}.*?lowest is.*?\)",
        f"{perfect}/{n} datasets reach \\\\textbf{{perfect}} F1\\,=\\,1.00;\n"
        f"lowest is {hardest['dataset_id']} "
        f"({DATASET_SHORT.get(hardest['dataset_id'], '')}, "
        f"{hardest.get('features_used', '?')} samples, "
        f"F1\\,=\\,{hardest['f1_score']:.2f})",
        tex,
    )

    # --- Update STRING PPI table ---
    if val:
        tex = _replace_string_table(tex, val)
        tex = re.sub(
            r"93 protein--protein interactions among 140 genes",
            f"{total_ppi} protein--protein interactions among "
            f"{sum(len(v.get('input_genes', [])) for v in val)} genes",
            tex,
        )

    if tex != original:
        tex_path.write_text(tex)
        print("   ✓ Presentation updated with new numbers")
    else:
        print("   ℹ️  No changes needed in presentation")
    return True


def _replace_perf_table(tex: str, perf: list[dict],
                        avg_f1: float, avg_auc: float) -> str:
    """Replace the performance table rows in the presentation."""
    # Find the performance table block
    pattern = (
        r"(\\begin\{tabular\}\{ll\s*\n\s*>\{\\columncolor.*?\\midrule\n)"
        r"(.*?)"
        r"(\\midrule\s*\n\\multicolumn\{2\}.*?\\\\)"
    )
    match = re.search(pattern, tex, re.DOTALL)
    if not match:
        return tex

    new_rows = []
    for d in perf:
        ds = d["dataset_id"]
        short = DATASET_SHORT.get(ds, "")
        f1 = d["f1_score"]
        f1_lo = d["f1_ci_lower"]
        f1_hi = d["f1_ci_upper"]
        auc = d["auc_roc"]
        auc_lo = d["auc_ci_lower"]
        auc_hi = d["auc_ci_upper"]
        grp = d["groups_used"]
        feat = d["features_used"]
        bold = r"\textbf{" + f"{f1:.3f}" + "}" if f1 >= 0.999 else f"{f1:.3f}"
        new_rows.append(
            f"{ds} & {short} & {bold} & "
            f"[{f1_lo:.2f}--{f1_hi:.2f}] & "
            f"{auc:.3f} & [{auc_lo:.2f}--{auc_hi:.2f}] & "
            f"{grp}  & {feat}  \\\\"
        )
    mean_row = (
        f"\\multicolumn{{2}}{{l}}{{\\textit{{Mean}}}} &\n"
        f"  \\textbf{{{avg_f1:.3f}}} & & "
        f"\\textbf{{{avg_auc:.3f}}} & & & \\\\"
    )
    new_body = "\n".join(new_rows) + "\n"
    new_mean = "\\midrule\n" + mean_row

    return tex[:match.start(2)] + new_body + new_mean + tex[match.end(3):]


def _replace_string_table(tex: str, val: list[dict]) -> str:
    """Replace the STRING PPI table rows in the presentation."""
    # Anchor to the STRING PPI table specifically using its unique header
    pattern = (
        r"(\\textbf\{Top Interaction \(score\)\}\s*\\\\\s*\n\\midrule\n)"
        r"(GDS\d+.*?)"
        r"(\\midrule\s*\n\\multicolumn\{2\}.*?\\\\)"
    )
    match = re.search(pattern, tex, re.DOTALL)
    if not match:
        return tex

    new_rows = []
    for v in val:
        ds = v["dataset_id"]
        short = DATASET_SHORT.get(ds, "")
        n_genes = len(v.get("input_genes", []))
        ppi = v.get("string_interaction_count", 0)
        top_int = v.get("top_interactions", [])
        if top_int:
            ti = top_int[0]
            top_str = (
                f"{ti['protein1']}--{ti['protein2']} "
                f"({ti['score']:.2f})"
            )
        else:
            top_str = "N/A"
        bold_ppi = f"\\textbf{{{ppi}}}" if ppi > 30 else str(ppi)
        new_rows.append(
            f"{ds} & {short} & {n_genes} & {bold_ppi} & {top_str} \\\\"
        )
    total_ppi = sum(v.get("string_interaction_count", 0) for v in val)
    total_genes = sum(len(v.get("input_genes", [])) for v in val)

    new_body = "\n".join(new_rows) + "\n"
    total_row = (
        f"\\midrule\n"
        f"\\multicolumn{{2}}{{l}}{{\\textit{{Total}}}} & "
        f"{total_genes} & \\textbf{{{total_ppi}}} & \\\\"
    )
    return tex[:match.start(2)] + new_body + total_row + tex[match.end(3):]


def _extract_tex_block(tex, start_marker, end_marker, block_name=""):
    """Extract text between two markers."""
    start = tex.find(start_marker)
    if start < 0:
        return None
    end = tex.find(end_marker, start + len(start_marker))
    if end < 0:
        return None
    return tex[start + len(start_marker):end]


##### STEP 5: BUILD MANUSCRIPT #####

def build_manuscript():
    """Run build_manuscript_docx.py to generate the Word document."""
    script = project_root / "scripts" / "build_manuscript_docx.py"
    print(f"\n📄 Running {script.name}...")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(project_root),
        capture_output=True, text=True,
    )
    print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    if result.returncode != 0:
        print(f"⚠️  Manuscript build failed:\n{result.stderr[-500:]}")
        return False
    return True


##### MAIN #####

def main():
    parser = argparse.ArgumentParser(description="Finalize publication outputs")
    parser.add_argument("--skip-move", action="store_true",
                        help="Skip moving output folders to main_runs/")
    parser.add_argument("--skip-manuscript", action="store_true",
                        help="Skip building the manuscript docx")
    parser.add_argument("--skip-presentation", action="store_true",
                        help="Skip updating the presentation")
    args = parser.parse_args()

    print("=" * 70)
    print("📄 GSM Publication Finalization")
    print("=" * 70)

    # Step 1: Move outputs
    if not args.skip_move:
        print("\n📁 Step 1: Organizing output folders...")
        move_outputs_to_main_runs()
    else:
        print("\n📁 Step 1: Skipped (--skip-move)")

    # Step 2: Run analysis
    print("\n📊 Step 2: Running manuscript analysis...")
    analysis_ok = run_analysis()

    # Step 3: Baseline figure
    print("\n📊 Step 3: Generating baseline comparison figure...")
    run_baseline_figure()

    # Step 4: Update presentation
    if not args.skip_presentation:
        print("\n📊 Step 4: Updating presentation...")
        update_presentation()
    else:
        print("\n📊 Step 4: Skipped (--skip-presentation)")

    # Step 5: Build manuscript
    if not args.skip_manuscript and analysis_ok:
        print("\n📄 Step 5: Building manuscript docx...")
        build_manuscript()
    else:
        print("\n📄 Step 5: Skipped")

    print("\n" + "=" * 70)
    print("✅ Publication finalization complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
