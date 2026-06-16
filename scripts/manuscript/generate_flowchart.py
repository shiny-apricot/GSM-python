
# """
# GSM Pipeline Flowchart Generator

# Purpose:
#     Creates a detailed, publication-quality flowchart of the G-S-M pipeline
#     using matplotlib for embedding as Figure 1 in the manuscript.
"""
GSM Pipeline Flowchart Generator

Purpose:
    Creates a detailed, publication-quality flowchart of the G-S-M pipeline
    using matplotlib for embedding as Figure 1 in the manuscript.

Usage:
    python scripts/manuscript/generate_flowchart.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

project_root = Path(__file__).resolve().parents[2]

##### CONSTANTS #####

OUTPUT_PATH = (
    project_root / "reports_ARCHIVE" / "manuscript" / "figures"
    / "fig_pipeline_flowchart.png"
)

# Colour palette
C_INPUT = "#4A90D9"       # blue — input
C_PHASE1 = "#2E8B57"      # green — grouping
C_PHASE2 = "#D4A017"      # gold — scoring
C_PHASE3 = "#C0392B"      # red — modeling
C_OUTPUT = "#7D3C98"       # purple — output
C_ITER = "#555555"         # grey — iteration loop
C_TEXT = "#FFFFFF"         # white text on dark boxes
C_DARK_TEXT = "#1A1A1A"   # dark text for light boxes
C_BG = "#FAFAFA"          # background
C_STAT = "#1ABC9C"        # teal — statistical safeguards


##### HELPER FUNCTIONS #####

def _add_box(ax, x, y, w, h, text, color, text_color=C_TEXT,
             fontsize=10, style="round,pad=0.1", alpha=1.0, bold=False):
    """Draw a rounded rectangle with centred text."""
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=style,
        facecolor=color,
        edgecolor="none",
        alpha=alpha,
        zorder=2,
    )
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color=text_color,
            fontweight=weight, zorder=3,
            linespacing=1.3)


def _arrow(ax, x1, y1, x2, y2, color="#333333", lw=1.5,
           style="->", connectionstyle="arc3,rad=0"):
    """Draw an arrow from (x1,y1) to (x2,y2)."""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        connectionstyle=connectionstyle,
        color=color,
        lw=lw,
        mutation_scale=15,
        zorder=1,
    )
    ax.add_patch(arrow)


def _side_label(ax, x, y, text, fontsize=9, color="#666666"):
    """Add a small annotation label."""
    ax.text(x, y, text, ha="left", va="center",
            fontsize=fontsize, color=color, style="italic", zorder=3)


##### MAIN FLOWCHART #####

def generate_flowchart():
    """Build the complete GSM pipeline flowchart."""
    fig, ax = plt.subplots(figsize=(11, 17))
    ax.set_xlim(-0.2, 11.5)
    ax.set_ylim(2.5, 19.8)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)

    # ---- LAYOUT GRID ----
    cx = 5.8         # centre column — shifted right for safeguards room
    bw = 3.6         # content-box width
    bh = 0.65        # content-box height
    hdr_h = 0.48     # phase-header height
    hdr_w = bw + 0.6 # phase-header width

    # Edge-to-edge gaps between box *painted* edges (pad adds ~0.1 visually)
    e2e_hdr = 0.30   # header-bottom ↔ first content-top
    e2e_box = 0.30   # content-bottom ↔ content-top (same phase)
    e2e_phase = 0.42 # last content ↔ next phase header

    # Right-side annotation column
    ann_x = cx + bw / 2 + 0.65

    # Helper: next y-centre given previous centre, half-heights, and gap.
    def _next_y(y_prev, half_prev, gap, half_next):
        return y_prev - half_prev - gap - half_next

    # ---- TITLE ----
    ax.text(cx, 19.0,
            "G-S-M Pipeline: Grouping–Scoring–Modeling Framework",
            ha="center", va="center", fontsize=16,
            fontweight="bold", color="#1A237E")

    # ---- ROW 0: INPUTS ----
    y_inp = 18.0
    inp_h = 0.60
    _add_box(ax, cx - 2.2, y_inp, 2.8, inp_h,
             "Gene-expression\nmatrix  X  (n \u00d7 p)", C_INPUT, fontsize=10)
    _add_box(ax, cx + 2.2, y_inp, 2.8, inp_h,
             "Knowledge mapping\nK  (DisGeNET)", C_INPUT, fontsize=10)

    lbl_h = 0.48
    y_lbl = _next_y(y_inp, inp_h / 2, 0.25, lbl_h / 2)
    _add_box(ax, cx, y_lbl, 2.0, lbl_h,
             "Class labels  y", C_INPUT, fontsize=10)

    _arrow(ax, cx - 2.2, y_inp - inp_h / 2, cx - 0.35, y_lbl + lbl_h / 2)
    _arrow(ax, cx + 2.2, y_inp - inp_h / 2, cx + 0.35, y_lbl + lbl_h / 2)

    # ---- ROW 1: PREPROCESSING ----
    y_pre = _next_y(y_lbl, lbl_h / 2, 0.32, bh / 2)
    _add_box(ax, cx, y_pre, bw, bh,
             "Data Preprocessing\n(normalisation, label encoding)", "#607D8B",
             fontsize=10.5)
    _arrow(ax, cx, y_lbl - lbl_h / 2, cx, y_pre + bh / 2)
    _side_label(ax, ann_x, y_pre, "z-score / quantile\nnormalisation")

    # ---- ITERATION LOOP — label sits ABOVE the dashed box ----
    loop_top = y_pre - bh / 2 - 0.60   # generous gap below preprocessing

    # "Repeat N iterations" label placed clearly above the dashed line
    ax.text(cx, loop_top + 0.28,
            "Repeat N iterations  (different random seeds)",
            ha="center", va="center",
            fontsize=10, color=C_ITER, fontweight="bold", style="italic",
            bbox=dict(boxstyle="round,pad=0.15", facecolor=C_BG,
                      edgecolor="none", alpha=0.9))

    # ---- ROW 2: TRAIN/TEST SPLIT (first element inside Loop) ----
    y_tt = loop_top - 0.50
    _add_box(ax, cx, y_tt, bw, bh,
             "Stratified Train / Test Split", C_ITER, fontsize=10.5)
    _arrow(ax, cx, y_pre - bh / 2, cx, y_tt + bh / 2)
    _side_label(ax, ann_x, y_tt, "preserves class\ndistribution")

    # ============================================================
    #  PHASE I — GROUPING  (green)
    # ============================================================
    y_p1h = _next_y(y_tt, bh / 2, e2e_phase, hdr_h / 2)
    _add_box(ax, cx, y_p1h, hdr_w, hdr_h,
             "PHASE I — GROUPING", C_PHASE1, bold=True, fontsize=12)
    _arrow(ax, cx, y_tt - bh / 2, cx, y_p1h + hdr_h / 2)

    y_ttest = _next_y(y_p1h, hdr_h / 2, e2e_hdr, bh / 2)
    _add_box(ax, cx, y_ttest, bw, bh,
             "Welch t-test + BH FDR\ncorrection  (α = 0.05)", C_PHASE1,
             fontsize=10.5, alpha=0.85)
    _arrow(ax, cx, y_p1h - hdr_h / 2, cx, y_ttest + bh / 2)
    _side_label(ax, ann_x, y_ttest, "gene-level filter;\nretain p_adj < 0.05")

    y_grp = _next_y(y_ttest, bh / 2, e2e_box, bh / 2)
    _add_box(ax, cx, y_grp, bw, bh,
             "Project genes onto\ndisease-association groups", C_PHASE1,
             fontsize=10.5, alpha=0.85)
    _arrow(ax, cx, y_ttest - bh / 2, cx, y_grp + bh / 2)
    _side_label(ax, ann_x, y_grp,
                "X_g = X[:, K(g)]\n(one sub-matrix per group)")

    # ============================================================
    #  PHASE II — SCORING  (gold)
    # ============================================================
    y_p2h = _next_y(y_grp, bh / 2, e2e_phase, hdr_h / 2)
    _add_box(ax, cx, y_p2h, hdr_w, hdr_h,
             "PHASE II — SCORING", C_PHASE2, C_DARK_TEXT, bold=True,
             fontsize=12)
    _arrow(ax, cx, y_grp - bh / 2, cx, y_p2h + hdr_h / 2)

    y_cv = _next_y(y_p2h, hdr_h / 2, e2e_hdr, bh / 2)
    _add_box(ax, cx, y_cv, bw, bh,
             "Stratified k-fold CV\n(RandomForest per group)", C_PHASE2,
             text_color=C_DARK_TEXT, fontsize=10.5, alpha=0.85)
    _arrow(ax, cx, y_p2h - hdr_h / 2, cx, y_cv + bh / 2)
    _side_label(ax, ann_x, y_cv,
                "S_g = mean F1\nacross k folds")

    y_rank = _next_y(y_cv, bh / 2, e2e_box, bh / 2)
    _add_box(ax, cx, y_rank, bw, bh,
             "Rank groups by score S_g\n(descending)", C_PHASE2,
             text_color=C_DARK_TEXT, fontsize=10.5, alpha=0.85)
    _arrow(ax, cx, y_cv - bh / 2, cx, y_rank + bh / 2)

    # ============================================================
    #  PHASE III — MODELING  (red)
    # ============================================================
    y_p3h = _next_y(y_rank, bh / 2, e2e_phase, hdr_h / 2)
    _add_box(ax, cx, y_p3h, hdr_w, hdr_h,
             "PHASE III — MODELING", C_PHASE3, bold=True, fontsize=12)
    _arrow(ax, cx, y_rank - bh / 2, cx, y_p3h + hdr_h / 2)

    y_top = _next_y(y_p3h, hdr_h / 2, e2e_hdr, bh / 2)
    _add_box(ax, cx, y_top, bw, bh,
             "Select top-m groups;\npool member genes", C_PHASE3,
             fontsize=10.5, alpha=0.85)
    _arrow(ax, cx, y_p3h - hdr_h / 2, cx, y_top + bh / 2)
    _side_label(ax, ann_x, y_top,
                "expand until features\nincrease (dedup)")

    y_clf = _next_y(y_top, bh / 2, e2e_box, bh / 2)
    _add_box(ax, cx, y_clf, bw, bh,
             "Train final classifier\n(RandomForest, default)", C_PHASE3,
             fontsize=10.5, alpha=0.85)
    _arrow(ax, cx, y_top - bh / 2, cx, y_clf + bh / 2)
    _side_label(ax, ann_x, y_clf,
                "outputs P(y=1|x)\nprobabilities")

    # ---- ITERATION LOOP BOX (encloses Train/Test through Train-clf) ----
    loop_bot = y_clf - bh / 2 - 0.25
    loop_left = cx - bw / 2 - 0.65     # comfortably left of content boxes
    loop_right = ann_x + 1.8           # enough to not clip annotations
    loop_box = FancyBboxPatch(
        (loop_left, loop_bot),
        loop_right - loop_left,
        loop_top - loop_bot,
        boxstyle="round,pad=0.15",
        facecolor="none",
        edgecolor=C_ITER,
        linestyle="--",
        linewidth=1.5,
        zorder=0,
    )
    ax.add_patch(loop_box)

    # ---- ROW: AGGREGATION (outside the iteration loop) ----
    y_agg = _next_y(y_clf, bh / 2, 0.65, bh / 2)
    _add_box(ax, cx, y_agg, bw, bh,
             "Aggregate iterations\n(rank aggregation, best-averaged)", "#607D8B",
             fontsize=10.5)
    _arrow(ax, cx, y_clf - bh / 2, cx, y_agg + bh / 2)

    # ---- ROW: OUTPUTS ----
    out_bw = 2.4
    out_bh = 0.60
    y_out = _next_y(y_agg, bh / 2, 0.55, out_bh / 2)
    _add_box(ax, cx - 3.0, y_out, out_bw, out_bh,
             "Performance\nmetrics + 95 % CI", C_OUTPUT, fontsize=10)
    _add_box(ax, cx, y_out, out_bw, out_bh,
             "Ranked groups\n& gene lists", C_OUTPUT, fontsize=10)
    _add_box(ax, cx + 3.0, y_out, out_bw, out_bh,
             "Biological\nvalidation", C_OUTPUT, fontsize=10)

    _arrow(ax, cx - 1.2, y_agg - bh / 2, cx - 3.0, y_out + out_bh / 2)
    _arrow(ax, cx, y_agg - bh / 2, cx, y_out + out_bh / 2)
    _arrow(ax, cx + 1.2, y_agg - bh / 2, cx + 3.0, y_out + out_bh / 2)

    # ---- STATISTICAL SAFEGUARDS (positioned left, OUTSIDE the loop) ----
    sg_w, sg_h = 2.1, 2.0
    sg_cx = loop_left - 0.25 - sg_w / 2   
    sg_cy = y_ttest       
    
    _add_box(ax, sg_cx, sg_cy, sg_w, sg_h,
             "Statistical\nSafeguards\n\n• BH FDR\n• Bootstrap CI\n"
             "• Stratified CV\n• AUC-ROC",
             C_STAT, fontsize=9, alpha=0.18, text_color=C_STAT,
             style="round,pad=0.12")

    # Small connecting arrow from safeguards pointing into the pipeline gap
    _arrow(ax, sg_cx + sg_w / 2, sg_cy,
           cx - bw / 2, sg_cy,
           color=C_STAT, lw=1.0, style="->")

    # ---- FRAME around the entire figure ----
    frame_pad = 0.15
    frame = FancyBboxPatch(
        (ax.get_xlim()[0] + frame_pad, ax.get_ylim()[0] + frame_pad),
        ax.get_xlim()[1] - ax.get_xlim()[0] - 2 * frame_pad,
        ax.get_ylim()[1] - ax.get_ylim()[0] - 2 * frame_pad,
        boxstyle="round,pad=0.08",
        facecolor="none",
        edgecolor="#333333",
        linewidth=1.8,
        zorder=4,
    )
    ax.add_patch(frame)

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUTPUT_PATH), dpi=300, bbox_inches="tight",
                pad_inches=0.25,
                facecolor=C_BG, edgecolor="#333333")
    plt.close(fig)
    print(f"Flowchart saved to: {OUTPUT_PATH}")
    return str(OUTPUT_PATH)


if __name__ == "__main__":
    generate_flowchart()
# Usage:
#     python scripts/manuscript/generate_flowchart.py
# """

# from pathlib import Path

# import matplotlib
# matplotlib.use("Agg")
# import matplotlib.pyplot as plt
# import matplotlib.patches as mpatches
# from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# project_root = Path(__file__).resolve().parents[2]

# ##### CONSTANTS #####

# OUTPUT_PATH = (
#     project_root / "reports_ARCHIVE" / "manuscript" / "figures"
#     / "fig_pipeline_flowchart.png"
# )

# # Colour palette
# C_INPUT = "#4A90D9"       # blue — input
# C_PHASE1 = "#2E8B57"      # green — grouping
# C_PHASE2 = "#D4A017"      # gold — scoring
# C_PHASE3 = "#C0392B"      # red — modeling
# C_OUTPUT = "#7D3C98"       # purple — output
# C_ITER = "#555555"         # grey — iteration loop
# C_TEXT = "#FFFFFF"         # white text on dark boxes
# C_DARK_TEXT = "#1A1A1A"   # dark text for light boxes
# C_BG = "#FAFAFA"          # background
# C_STAT = "#1ABC9C"        # teal — statistical safeguards


# ##### HELPER FUNCTIONS #####

# def _add_box(ax, x, y, w, h, text, color, text_color=C_TEXT,
#              fontsize=10, style="round,pad=0.1", alpha=1.0, bold=False):
#     """Draw a rounded rectangle with centred text."""
#     box = FancyBboxPatch(
#         (x - w / 2, y - h / 2), w, h,
#         boxstyle=style,
#         facecolor=color,
#         edgecolor="none",
#         alpha=alpha,
#         zorder=2,
#     )
#     ax.add_patch(box)
#     weight = "bold" if bold else "normal"
#     ax.text(x, y, text, ha="center", va="center",
#             fontsize=fontsize, color=text_color,
#             fontweight=weight, zorder=3,
#             linespacing=1.3)


# def _arrow(ax, x1, y1, x2, y2, color="#333333", lw=1.5,
#            style="->", connectionstyle="arc3,rad=0"):
#     """Draw an arrow from (x1,y1) to (x2,y2)."""
#     arrow = FancyArrowPatch(
#         (x1, y1), (x2, y2),
#         arrowstyle=style,
#         connectionstyle=connectionstyle,
#         color=color,
#         lw=lw,
#         mutation_scale=15,
#         zorder=1,
#     )
#     ax.add_patch(arrow)


# def _side_label(ax, x, y, text, fontsize=9, color="#666666"):
#     """Add a small annotation label."""
#     ax.text(x, y, text, ha="left", va="center",
#             fontsize=fontsize, color=color, style="italic", zorder=3)


# ##### MAIN FLOWCHART #####

# def generate_flowchart():
#     """Build the complete GSM pipeline flowchart."""
#     fig, ax = plt.subplots(figsize=(11, 17))
#     ax.set_xlim(-0.2, 11.5)
#     ax.set_ylim(2.5, 19.8)
#     ax.set_aspect("equal")
#     ax.axis("off")
#     fig.patch.set_facecolor(C_BG)
#     ax.set_facecolor(C_BG)

#     # ---- LAYOUT GRID ----
#     cx = 5.8         # centre column — shifted right for safeguards room
#     bw = 3.6         # content-box width
#     bh = 0.65        # content-box height
#     hdr_h = 0.48     # phase-header height
#     hdr_w = bw + 0.6 # phase-header width

#     # Edge-to-edge gaps between box *painted* edges (pad adds ~0.1 visually)
#     e2e_hdr = 0.30   # header-bottom ↔ first content-top
#     e2e_box = 0.30   # content-bottom ↔ content-top (same phase)
#     e2e_phase = 0.42 # last content ↔ next phase header

#     # Right-side annotation column
#     ann_x = cx + bw / 2 + 0.65

#     # Helper: next y-centre given previous centre, half-heights, and gap.
#     def _next_y(y_prev, half_prev, gap, half_next):
#         return y_prev - half_prev - gap - half_next

#     # ---- TITLE ----
#     ax.text(cx, 19.0,
#             "G-S-M Pipeline: Grouping–Scoring–Modeling Framework",
#             ha="center", va="center", fontsize=16,
#             fontweight="bold", color="#1A237E")

#     # ---- ROW 0: INPUTS ----
#     y_inp = 18.0
#     inp_h = 0.60
#     _add_box(ax, cx - 2.2, y_inp, 2.8, inp_h,
#              "Gene-expression\nmatrix  X  (n \u00d7 p)", C_INPUT, fontsize=10)
#     _add_box(ax, cx + 2.2, y_inp, 2.8, inp_h,
#              "Knowledge mapping\nK  (DisGeNET)", C_INPUT, fontsize=10)

#     lbl_h = 0.48
#     y_lbl = _next_y(y_inp, inp_h / 2, 0.25, lbl_h / 2)
#     _add_box(ax, cx, y_lbl, 2.0, lbl_h,
#              "Class labels  y", C_INPUT, fontsize=10)

#     _arrow(ax, cx - 2.2, y_inp - inp_h / 2, cx - 0.35, y_lbl + lbl_h / 2)
#     _arrow(ax, cx + 2.2, y_inp - inp_h / 2, cx + 0.35, y_lbl + lbl_h / 2)

#     # ---- ROW 1: PREPROCESSING ----
#     y_pre = _next_y(y_lbl, lbl_h / 2, 0.32, bh / 2)
#     _add_box(ax, cx, y_pre, bw, bh,
#              "Data Preprocessing\n(normalisation, label encoding)", "#607D8B",
#              fontsize=10.5)
#     _arrow(ax, cx, y_lbl - lbl_h / 2, cx, y_pre + bh / 2)
#     _side_label(ax, ann_x, y_pre, "z-score / quantile\nnormalisation")

#     # ---- ITERATION LOOP — label sits ABOVE the dashed box ----
#     loop_top = y_pre - bh / 2 - 0.60   # generous gap below preprocessing

#     # "Repeat N iterations" label placed clearly above the dashed line
#     ax.text(cx, loop_top + 0.28,
#             "Repeat N iterations  (different random seeds)",
#             ha="center", va="center",
#             fontsize=10, color=C_ITER, fontweight="bold", style="italic",
#             bbox=dict(boxstyle="round,pad=0.15", facecolor=C_BG,
#                       edgecolor="none", alpha=0.9))

#     # ---- ROW 2: TRAIN/TEST SPLIT (first element inside Loop) ----
#     y_tt = loop_top - 0.50
#     _add_box(ax, cx, y_tt, bw, bh,
#              "Stratified Train / Test Split", C_ITER, fontsize=10.5)
#     _arrow(ax, cx, y_pre - bh / 2, cx, y_tt + bh / 2)
#     _side_label(ax, ann_x, y_tt, "preserves class\ndistribution")

#     # ============================================================
#     #  PHASE I — GROUPING  (green)
#     # ============================================================
#     y_p1h = _next_y(y_tt, bh / 2, e2e_phase, hdr_h / 2)
#     _add_box(ax, cx, y_p1h, hdr_w, hdr_h,
#              "PHASE I — GROUPING", C_PHASE1, bold=True, fontsize=12)
#     _arrow(ax, cx, y_tt - bh / 2, cx, y_p1h + hdr_h / 2)

#     y_grp = _next_y(y_p1h, hdr_h / 2, e2e_hdr, bh / 2)
#     _add_box(ax, cx, y_grp, bw, bh,
#              "Project genes onto\ndisease-association groups", C_PHASE1,
#              fontsize=10.5, alpha=0.85)
#     _arrow(ax, cx, y_p1h - hdr_h / 2, cx, y_grp + bh / 2)
#     _side_label(ax, ann_x, y_grp,
#                 "X_g = X[:, K(g)]\n(one sub-matrix per group)")

#     # ============================================================
#     #  PHASE II — SCORING  (gold)
#     # ============================================================
#     y_p2h = _next_y(y_grp, bh / 2, e2e_phase, hdr_h / 2)
#     _add_box(ax, cx, y_p2h, hdr_w, hdr_h,
#              "PHASE II — SCORING", C_PHASE2, C_DARK_TEXT, bold=True,
#              fontsize=12)
#     _arrow(ax, cx, y_grp - bh / 2, cx, y_p2h + hdr_h / 2)

#     y_ttest = _next_y(y_p2h, hdr_h / 2, e2e_hdr, bh / 2)
#     _add_box(ax, cx, y_ttest, bw, bh,
#              "Welch t-test + BH FDR\ncorrection  (α = 0.05)", C_PHASE2,
#              C_DARK_TEXT, fontsize=10.5, alpha=0.85)
#     _arrow(ax, cx, y_p2h - hdr_h / 2, cx, y_ttest + bh / 2)
#     _side_label(ax, ann_x, y_ttest, "gene-level filter;\nretain p_adj < 0.05")

#     y_cv = _next_y(y_ttest, bh / 2, e2e_box, bh / 2)
#     _add_box(ax, cx, y_cv, bw, bh,
#              "Stratified k-fold CV\n(RandomForest per group)", C_PHASE2,
#              C_DARK_TEXT, fontsize=10.5, alpha=0.85)
#     _arrow(ax, cx, y_ttest - bh / 2, cx, y_cv + bh / 2)
#     _side_label(ax, ann_x, y_cv,
#                 "S_g = mean F1\nacross k folds")

#     y_rank = _next_y(y_cv, bh / 2, e2e_box, bh / 2)
#     _add_box(ax, cx, y_rank, bw, bh,
#              "Rank groups by score S_g\n(descending)", C_PHASE2,
#              C_DARK_TEXT, fontsize=10.5, alpha=0.85)
#     _arrow(ax, cx, y_cv - bh / 2, cx, y_rank + bh / 2)

#     # ============================================================
#     #  PHASE III — MODELING  (red)
#     # ============================================================
#     y_p3h = _next_y(y_rank, bh / 2, e2e_phase, hdr_h / 2)
#     _add_box(ax, cx, y_p3h, hdr_w, hdr_h,
#              "PHASE III — MODELING", C_PHASE3, bold=True, fontsize=12)
#     _arrow(ax, cx, y_rank - bh / 2, cx, y_p3h + hdr_h / 2)

#     y_top = _next_y(y_p3h, hdr_h / 2, e2e_hdr, bh / 2)
#     _add_box(ax, cx, y_top, bw, bh,
#              "Select top-m groups;\npool member genes", C_PHASE3,
#              fontsize=10.5, alpha=0.85)
#     _arrow(ax, cx, y_p3h - hdr_h / 2, cx, y_top + bh / 2)
#     _side_label(ax, ann_x, y_top,
#                 "expand until features\nincrease (dedup)")

#     y_clf = _next_y(y_top, bh / 2, e2e_box, bh / 2)
#     _add_box(ax, cx, y_clf, bw, bh,
#              "Train final classifier\n(RandomForest, default)", C_PHASE3,
#              fontsize=10.5, alpha=0.85)
#     _arrow(ax, cx, y_top - bh / 2, cx, y_clf + bh / 2)
#     _side_label(ax, ann_x, y_clf,
#                 "outputs P(y=1|x)\nprobabilities")

#     # ---- ITERATION LOOP BOX (encloses Train/Test through Train-clf) ----
#     loop_bot = y_clf - bh / 2 - 0.25
#     loop_left = cx - bw / 2 - 0.65     # comfortably left of content boxes
#     loop_right = ann_x + 1.8           # enough to not clip annotations
#     loop_box = FancyBboxPatch(
#         (loop_left, loop_bot),
#         loop_right - loop_left,
#         loop_top - loop_bot,
#         boxstyle="round,pad=0.15",
#         facecolor="none",
#         edgecolor=C_ITER,
#         linestyle="--",
#         linewidth=1.5,
#         zorder=0,
#     )
#     ax.add_patch(loop_box)

#     # ---- ROW: AGGREGATION (outside the iteration loop) ----
#     y_agg = _next_y(y_clf, bh / 2, 0.65, bh / 2)
#     _add_box(ax, cx, y_agg, bw, bh,
#              "Aggregate iterations\n(rank aggregation, best-averaged)", "#607D8B",
#              fontsize=10.5)
#     _arrow(ax, cx, y_clf - bh / 2, cx, y_agg + bh / 2)

#     # ---- ROW: OUTPUTS ----
#     out_bw = 2.4
#     out_bh = 0.60
#     y_out = _next_y(y_agg, bh / 2, 0.55, out_bh / 2)
#     _add_box(ax, cx - 3.0, y_out, out_bw, out_bh,
#              "Performance\nmetrics + 95 % CI", C_OUTPUT, fontsize=10)
#     _add_box(ax, cx, y_out, out_bw, out_bh,
#              "Ranked groups\n& gene lists", C_OUTPUT, fontsize=10)
#     _add_box(ax, cx + 3.0, y_out, out_bw, out_bh,
#              "Biological\nvalidation", C_OUTPUT, fontsize=10)

#     _arrow(ax, cx - 1.2, y_agg - bh / 2, cx - 3.0, y_out + out_bh / 2)
#     _arrow(ax, cx, y_agg - bh / 2, cx, y_out + out_bh / 2)
#     _arrow(ax, cx + 1.2, y_agg - bh / 2, cx + 3.0, y_out + out_bh / 2)

#     # ---- STATISTICAL SAFEGUARDS (positioned left, OUTSIDE the loop) ----
#     sg_w, sg_h = 2.1, 2.0
#     sg_cx = loop_left - 0.25 - sg_w / 2   # sits to the left of the loop box
#     sg_cy = (y_ttest + y_rank) / 2         # vertically centred on scoring
#     _add_box(ax, sg_cx, sg_cy, sg_w, sg_h,
#              "Statistical\nSafeguards\n\n• BH FDR\n• Bootstrap CI\n"
#              "• Stratified CV\n• AUC-ROC",
#              C_STAT, fontsize=9, alpha=0.18, text_color=C_STAT,
#              style="round,pad=0.12")

#     # Small connecting arrow from safeguards to the scoring phase
#     _arrow(ax, sg_cx + sg_w / 2, sg_cy,
#            cx - bw / 2, sg_cy,
#            color=C_STAT, lw=1.0, style="->")

#     # ---- FRAME around the entire figure ----
#     frame_pad = 0.15
#     frame = FancyBboxPatch(
#         (ax.get_xlim()[0] + frame_pad, ax.get_ylim()[0] + frame_pad),
#         ax.get_xlim()[1] - ax.get_xlim()[0] - 2 * frame_pad,
#         ax.get_ylim()[1] - ax.get_ylim()[0] - 2 * frame_pad,
#         boxstyle="round,pad=0.08",
#         facecolor="none",
#         edgecolor="#333333",
#         linewidth=1.8,
#         zorder=4,
#     )
#     ax.add_patch(frame)

#     # Save
#     OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
#     fig.savefig(str(OUTPUT_PATH), dpi=300, bbox_inches="tight",
#                 pad_inches=0.25,
#                 facecolor=C_BG, edgecolor="#333333")
#     plt.close(fig)
#     print(f"Flowchart saved to: {OUTPUT_PATH}")
#     return str(OUTPUT_PATH)


# if __name__ == "__main__":
#     generate_flowchart()
