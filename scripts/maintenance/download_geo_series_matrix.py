"""
Download selected GEO Series (GSE) matrix files and convert them into
GSM-compatible expression CSV files (`class` + numeric feature columns).

Example:
  python scripts/maintenance/download_geo_series_matrix.py \
      --datasets GSE46602 GSE6919 GSE70768 \
      --output-dir data/expression_data

Notes:
- Labels are inferred from sample metadata keywords (configurable).
- Output labels are standardized to `pos` and `neg`.
- Unknown-labeled samples are dropped by default.
"""

from __future__ import annotations

import argparse
import gzip
import io
import re
from pathlib import Path

import pandas as pd
import requests

DEFAULT_DATASETS = ["GSE46602", "GSE6919", "GSE70768"]
DEFAULT_POS_KEYWORDS = [
    "tumor",
    "tumour",
    "cancer",
    "carcinoma",
    "adenocarcinoma",
    "prostate cancer",
]
DEFAULT_NEG_KEYWORDS = [
    "normal",
    "control",
    "benign",
    "healthy",
    "adjacent normal",
]


def _geo_series_prefix(accession: str) -> str:
    digits = accession.replace("GSE", "")
    if len(digits) < 3:
        raise ValueError(f"Invalid accession: {accession}")
    return f"GSE{digits[:-3]}nnn"


def _matrix_url(accession: str) -> str:
    prefix = _geo_series_prefix(accession)
    return (
        "https://ftp.ncbi.nlm.nih.gov/geo/series/"
        f"{prefix}/{accession}/matrix/{accession}_series_matrix.txt.gz"
    )


def _matrix_dir_url(accession: str) -> str:
    prefix = _geo_series_prefix(accession)
    return f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{accession}/matrix/"


def _discover_matrix_filename(accession: str, timeout: int = 120) -> str:
    dir_url = _matrix_dir_url(accession)
    response = requests.get(dir_url, timeout=timeout)
    response.raise_for_status()

    filenames = re.findall(r'href="([^"]+_series_matrix\.txt\.gz)"', response.text)
    filenames = sorted(set(filenames))
    if not filenames:
        raise FileNotFoundError(f"No series matrix files found for {accession} at {dir_url}")

    exact = f"{accession}_series_matrix.txt.gz"
    if exact in filenames:
        return exact

    # Platform-specific series can exist (e.g., GSE6919-GPL8300_series_matrix.txt.gz)
    # Use the first deterministic option and print it to the user.
    return filenames[0]


def _download_matrix_text(accession: str, timeout: int = 120) -> tuple[str, str]:
    matrix_name = _discover_matrix_filename(accession, timeout=timeout)
    url = _matrix_dir_url(accession) + matrix_name
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
        return gz.read().decode("utf-8", errors="replace"), matrix_name


def _dataset_id_from_matrix_name(matrix_name: str) -> str:
    stem = matrix_name.replace("_series_matrix.txt.gz", "")
    return stem.replace("-", "_")


def _strip_quotes(tokens: list[str]) -> list[str]:
    return [t.strip().strip('"') for t in tokens]


def _parse_series_matrix(text: str) -> tuple[pd.DataFrame, list[str], list[str]]:
    lines = text.splitlines()

    sample_ids: list[str] = []
    sample_text: dict[str, list[str]] = {}
    table_lines: list[str] = []
    in_table = False

    for line in lines:
        if line.startswith("!Sample_geo_accession"):
            parts = _strip_quotes(line.split("\t"))
            sample_ids = parts[1:]
            for sid in sample_ids:
                sample_text.setdefault(sid, [])
            continue

        if line.startswith("!Sample_title") or line.startswith("!Sample_source_name_ch1") or line.startswith("!Sample_characteristics_ch"):
            parts = _strip_quotes(line.split("\t"))
            values = parts[1:]
            for sid, value in zip(sample_ids, values):
                if value:
                    sample_text.setdefault(sid, []).append(value)
            continue

        if line.startswith("!series_matrix_table_begin"):
            in_table = True
            continue
        if line.startswith("!series_matrix_table_end"):
            in_table = False
            continue
        if in_table:
            table_lines.append(line)

    if not table_lines:
        raise ValueError("Matrix table not found in series matrix file.")

    matrix = pd.read_csv(io.StringIO("\n".join(table_lines)), sep="\t", dtype=str)
    if "ID_REF" not in matrix.columns:
        raise ValueError("Expected ID_REF column not found in matrix table.")

    matrix = matrix.set_index("ID_REF")
    matrix = matrix.apply(pd.to_numeric, errors="coerce")
    matrix = matrix.fillna(0.0)

    expr = matrix.T
    expr.index.name = "sample_id"

    if expr.columns.duplicated().any():
        expr = expr.T.groupby(level=0).mean().T

    meta = [" | ".join(sample_text.get(sid, [])) for sid in expr.index]
    return expr, list(expr.index), meta


def _infer_label(text: str, pos_keywords: list[str], neg_keywords: list[str]) -> str | None:
    s = text.lower()
    pos = any(k in s for k in pos_keywords)
    neg = any(k in s for k in neg_keywords)
    if pos and not neg:
        return "pos"
    if neg and not pos:
        return "neg"
    return None


def _build_output_df(
    expr: pd.DataFrame,
    sample_ids: list[str],
    metadata_text: list[str],
    *,
    pos_keywords: list[str],
    neg_keywords: list[str],
    drop_unknown: bool,
) -> pd.DataFrame:
    labels = [_infer_label(t, pos_keywords, neg_keywords) for t in metadata_text]

    out = expr.copy()
    out.insert(0, "class", labels)
    out.insert(0, "sample_id", sample_ids)

    if drop_unknown:
        out = out[out["class"].isin(["pos", "neg"])].copy()

    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and convert GEO GSE series matrices.")
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/expression_data"))
    parser.add_argument("--pos-keywords", nargs="+", default=DEFAULT_POS_KEYWORDS)
    parser.add_argument("--neg-keywords", nargs="+", default=DEFAULT_NEG_KEYWORDS)
    parser.add_argument("--keep-unknown", action="store_true", help="Keep samples with unknown labels.")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for accession in args.datasets:
        print(f"\n[download] {accession}")
        text, matrix_name = _download_matrix_text(accession, timeout=args.timeout)
        expr, sample_ids, metadata_text = _parse_series_matrix(text)

        out = _build_output_df(
            expr,
            sample_ids,
            metadata_text,
            pos_keywords=[k.lower() for k in args.pos_keywords],
            neg_keywords=[k.lower() for k in args.neg_keywords],
            drop_unknown=not args.keep_unknown,
        )

        if out.empty:
            print(f"  -> No labeled samples found for {accession}. Check keyword settings.")
            continue

        numeric_cols = [c for c in out.columns if c not in {"sample_id", "class"}]
        out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

        dataset_id = _dataset_id_from_matrix_name(matrix_name)
        csv_path = args.output_dir / f"{dataset_id}.csv"
        out.to_csv(csv_path, index=False)

        class_counts = out["class"].value_counts().to_dict()
        print(
            f"  -> matrix: {matrix_name}\n"
            f"  -> saved {csv_path} | samples={len(out)} features={len(numeric_cols)} "
            f"class_counts={class_counts}"
        )


if __name__ == "__main__":
    main()
