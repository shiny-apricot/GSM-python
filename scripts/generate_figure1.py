#!/usr/bin/env python3
"""Script to generate Figure 1 flowchart for the manuscript."""
import os

def generate_tikz_flowchart():
    tikz_code = r"""
\documentclass[tikz,border=10pt]{standalone}
\usetikzlibrary{shapes.geometric, arrows, positioning, fit, backgrounds, calc}

\begin{document}

\begin{tikzpicture}[
    auto,
    block/.style={rectangle, draw=blue!80!black, fill=blue!10, text width=12em, text centered, rounded corners, minimum height=3em, thick},
    process/.style={rectangle, draw=purple!80!black, fill=purple!10, text width=14em, text centered, rounded corners, minimum height=3em, thick},
    eval/.style={rectangle, draw=green!60!black, fill=green!10, text width=12em, text centered, rounded corners, minimum height=3em, thick},
    line/.style={draw, thick, -latex', shorten >=2pt},
    dashedline/.style={draw, thick, dashed, -latex', shorten >=2pt},
    groupbox/.style={rectangle, draw=gray!60, fill=gray!5, inner sep=10pt, rounded corners, thick, dashed}
]

% Top level: Data split
\node [block] (rawdata) {Raw Microarray Data \& Phenotype Labels};
\node [block, below=1.5cm of rawdata] (split) {\textbf{Random Split} (70\% Train / 30\% Test)};
\path [line] (rawdata) -- (split);

% Phase 1: Training Partition
\node [block, below left=2cm and 1cm of split] (traindata) {Training Partition (70\%)};
\node [process, below=1cm of traindata] (norm) {1. Calculate Normalization Parameters (e.g. Z-score)};
\node [process, below=1cm of norm] (filter) {2. Welch's t-test \& FDR Correction ($\alpha=0.05$)};
\node [process, below=1cm of filter, fill=purple!20, ultra thick] (group) {3. \textbf{Grouping:}\\ Feature Grouping via DisGeNET};
\node [process, below=1cm of group, fill=purple!20, ultra thick] (cv) {4. \textbf{Scoring:}\\ Score \& Rank Groups via Internal CV};
\node [process, below=1cm of cv, fill=purple!20, ultra thick] (train) {5. \textbf{Modeling:}\\ Train Final Model on Top $K$ Groups};

\path [line] (split) -| (traindata);
\path [line] (traindata) -- (norm);
\path [line] (norm) -- (filter);
\path [line] (filter) -- (group);
\path [line] (group) -- (cv);
\path [line] (cv) -- (train);

% Group background for Training
\begin{scope}[on background layer]
    \node [groupbox, fit=(traindata) (norm) (filter) (group) (cv) (train), label={[font=\bfseries, text=blue!80!black]above:Phase 1: Training Phase}] (trainbox) {};
\end{scope}

% Phase 2: Testing Partition
\node [block, below right=2cm and 1cm of split] (testdata) {Test Partition (30\%)};
\node [eval, below=1cm of testdata] (applynorm) {Apply Training Normalization Parameters};
\node [eval, below=5.1cm of applynorm] (evaluate) {Evaluate Model on Selected Features};
\node [eval, below=1cm of evaluate, text width=14em, fill=green!20, draw=green!80!black] (metrics) {\textbf{Final Metrics:}\\ AUC, F1, PR-AUC, Accuracy};

\path [line] (split) -| (testdata);
\path [line] (testdata) -- (applynorm);
\path [dashedline, color=red!80!black] (norm) -- node[above, fill=white] {Scaling Parameters} (applynorm);
\path [line] (applynorm) -- (evaluate);
\path [dashedline, color=red!80!black] (train) -- node[above, fill=white] {Trained Model \& Feature List} (evaluate);
\path [line] (evaluate) -- (metrics);

% Group background for Testing
\begin{scope}[on background layer]
    \node [groupbox, fit=(testdata) (applynorm) (evaluate) (metrics), label={[font=\bfseries, text=green!60!black]above:Phase 2: Held-out Evaluation}] (testbox) {};
\end{scope}

% Strict Isolation Note
\node [rectangle, draw=orange!80, fill=orange!10, dashed, right=0.5cm of split, text width=10em, text centered] (note) {Strict isolation prevents data leakage and selection bias};
\draw [dashed, orange!80, thick] (note) -- (split);

\end{tikzpicture}

\end{document}
"""
    
    output_path = os.path.join("output", "figure1.tex")
    os.makedirs("output", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(tikz_code.strip())
        
    print(f"Successfully generated LaTeX TikZ flowchart at {output_path}")
    print("You can compile this in Overleaf or any local TeX distribution to produce a vector PDF.")

if __name__ == "__main__":
    generate_tikz_flowchart()
