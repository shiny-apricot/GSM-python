"""Loads expression and grouping datasets."""
import csv
import pandas as pd


def _detect_separator(filepath: str) -> str:
    """Auto-detect the column separator (comma, tab, etc.) of a data file.

    Reads a small sample from the file and uses Python's csv.Sniffer to
    determine the delimiter.  Falls back to comma if detection fails.

    Args:
        filepath: Path to a delimited text file.

    Returns:
        The detected single-character delimiter string.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        sample = f.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def load_input_file(input_file_name, *, separator: str = "auto"):
    """
    Load the input file from the data folder.

    Tries UTF-8 first, then falls back to latin-1 if a UnicodeDecodeError
    is raised (some GEO datasets contain non-ASCII probe annotations).

    Args:
        input_file_name (str): The name of the input file.
        separator (str): Column separator used in the input file.
            Use "auto" (default) to detect automatically.

    Returns:
        pd.DataFrame: The input file data.
    """
    if separator == "auto":
        separator = _detect_separator(input_file_name)
    try:
        data = pd.read_csv(input_file_name, sep=separator)
    except UnicodeDecodeError:
        data = pd.read_csv(input_file_name, sep=separator, encoding="latin-1")
    return data


def load_group_file(group_file_name, *, separator: str = "auto"):
    """
    Load the group file from the data folder.

    Args:
        group_file_name (str): The name of the group file.
        separator (str): Column separator used in the grouping file.
            Use "auto" (default) to detect automatically.

    Returns:
        pd.DataFrame: The group file data.
    """
    if separator == "auto":
        separator = _detect_separator(group_file_name)
    group = pd.read_csv(group_file_name, sep=separator)
    return group