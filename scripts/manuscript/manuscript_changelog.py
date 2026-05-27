"""
Manuscript Changelog Generator 📝

Purpose:
    Compare two manuscript .docx files paragraph-by-paragraph and
    produce a human-readable Markdown changelog.  Designed so you can
    rebuild the manuscript, then see *exactly* what changed — and apply
    only those edits in Google Docs (preserving comments, Zotero, etc.).

Usage:
    # Compare the two most recent versions automatically:
    python scripts/manuscript/manuscript_changelog.py

    # Compare specific versions:
    python scripts/manuscript/manuscript_changelog.py --old v33 --new v34

    # Save to file instead of stdout:
    python scripts/manuscript/manuscript_changelog.py --output changelog.md

Output format:
    Markdown with collapsible sections per heading, tables for
    added/removed, and strikethrough/bold for word-level diffs.
"""

import argparse
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document


##### DATA STRUCTURES #####

@dataclass
class Paragraph:
    """A single paragraph with its context."""
    index: int
    text: str
    style: str
    section: str  # nearest heading above this paragraph


@dataclass
class Change:
    """One detected change between old and new manuscripts."""
    kind: str           # "MODIFIED", "ADDED", "REMOVED"
    section: str        # heading context
    old_text: str       # "" for ADDED
    new_text: str       # "" for REMOVED
    para_index: int     # position in the new doc (or old for REMOVED)


@dataclass
class Changelog:
    """Complete diff between two manuscript versions."""
    old_path: Path
    new_path: Path
    changes: list[Change] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


##### CONSTANTS #####

project_root = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = project_root / "reports_ARCHIVE"

# Styles that indicate section headings in the generated .docx
HEADING_STYLES = {"Heading 1", "Heading 2", "Heading 3", "Heading 4"}

# Short preview length for modified paragraphs
PREVIEW_LEN = 120


##### EXTRACTION #####

def extract_paragraphs(doc_path: Path) -> list[Paragraph]:
    """Extract all non-empty paragraphs with section context.

    Args:
        doc_path: Path to a .docx file.

    Returns:
        List of Paragraph objects with heading context attached.
    """
    doc = Document(str(doc_path))
    paragraphs: list[Paragraph] = []
    current_section = "(Preamble)"

    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue

        style_obj = p.style
        style_name = str(style_obj.name) if style_obj is not None else "Normal"

        # Update section tracker on headings
        if style_name in HEADING_STYLES:
            current_section = text

        paragraphs.append(Paragraph(
            index=i,
            text=text,
            style=style_name,
            section=current_section,
        ))

    return paragraphs


##### DIFF ENGINE #####

def compute_changelog(old_paras: list[Paragraph],
                      new_paras: list[Paragraph],
                      old_path: Path,
                      new_path: Path) -> Changelog:
    """Compute structured changelog between two paragraph lists.

    Uses SequenceMatcher on paragraph texts to align old/new
    and detect additions, removals, and modifications.

    Args:
        old_paras: Paragraphs from the old manuscript.
        new_paras: Paragraphs from the new manuscript.
        old_path:  Path to old .docx (for metadata).
        new_path:  Path to new .docx (for metadata).

    Returns:
        Changelog with all detected changes.
    """
    old_texts = [p.text for p in old_paras]
    new_texts = [p.text for p in new_paras]

    matcher = difflib.SequenceMatcher(None, old_texts, new_texts)
    changes: list[Change] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        elif tag == "replace":
            # Pair up old/new paragraphs that were replaced
            old_slice = old_paras[i1:i2]
            new_slice = new_paras[j1:j2]
            max_len = max(len(old_slice), len(new_slice))

            for k in range(max_len):
                old_p = old_slice[k] if k < len(old_slice) else None
                new_p = new_slice[k] if k < len(new_slice) else None

                if old_p and new_p:
                    changes.append(Change(
                        kind="MODIFIED",
                        section=new_p.section,
                        old_text=old_p.text,
                        new_text=new_p.text,
                        para_index=new_p.index,
                    ))
                elif new_p:
                    changes.append(Change(
                        kind="ADDED",
                        section=new_p.section,
                        old_text="",
                        new_text=new_p.text,
                        para_index=new_p.index,
                    ))
                elif old_p:
                    changes.append(Change(
                        kind="REMOVED",
                        section=old_p.section,
                        old_text=old_p.text,
                        new_text="",
                        para_index=old_p.index,
                    ))

        elif tag == "insert":
            for p in new_paras[j1:j2]:
                changes.append(Change(
                    kind="ADDED",
                    section=p.section,
                    old_text="",
                    new_text=p.text,
                    para_index=p.index,
                ))

        elif tag == "delete":
            for p in old_paras[i1:i2]:
                changes.append(Change(
                    kind="REMOVED",
                    section=p.section,
                    old_text=p.text,
                    new_text="",
                    para_index=p.index,
                ))

    # Compute stats
    n_modified = sum(1 for c in changes if c.kind == "MODIFIED")
    n_added = sum(1 for c in changes if c.kind == "ADDED")
    n_removed = sum(1 for c in changes if c.kind == "REMOVED")

    return Changelog(
        old_path=old_path,
        new_path=new_path,
        changes=changes,
        stats={
            "modified": n_modified,
            "added": n_added,
            "removed": n_removed,
            "total": len(changes),
            "old_paragraphs": len(old_paras),
            "new_paragraphs": len(new_paras),
        },
    )


##### INLINE WORD DIFF (Markdown) #####

def _word_diff_md(old: str, new: str) -> str:
    """Produce an inline word-level diff using Markdown formatting.

    Deletions use ~~strikethrough~~ and additions use **bold**.

    Example:
        >>> _word_diff_md("the quick brown fox", "the slow brown cat")
        'the ~~quick~~ **slow** brown ~~fox~~ **cat**'
    """
    old_words = old.split()
    new_words = new.split()
    sm = difflib.SequenceMatcher(None, old_words, new_words)
    parts: list[str] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(" ".join(old_words[i1:i2]))
        elif tag == "replace":
            parts.append("~~" + " ".join(old_words[i1:i2]) + "~~")
            parts.append("**" + " ".join(new_words[j1:j2]) + "**")
        elif tag == "insert":
            parts.append("**" + " ".join(new_words[j1:j2]) + "**")
        elif tag == "delete":
            parts.append("~~" + " ".join(old_words[i1:i2]) + "~~")

    return " ".join(parts)


##### FORMATTING (Markdown) #####

def _truncate(text: str, length: int = PREVIEW_LEN) -> str:
    """Truncate text with ellipsis if needed."""
    if len(text) <= length:
        return text
    return text[:length] + "…"


def _escape_md(text: str) -> str:
    """Escape pipe characters so text doesn't break Markdown tables."""
    return text.replace("|", "\\|")


def format_changelog(changelog: Changelog) -> str:
    """Format a Changelog as a Markdown document.

    Uses collapsible <details> sections grouped by heading,
    with ~~strikethrough~~ for deletions and **bold** for additions.

    Args:
        changelog: The computed changelog.

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    s = changelog.stats

    # Title
    lines.append(f"# Manuscript Changelog")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **Old** | `{changelog.old_path.name}` |")
    lines.append(f"| **New** | `{changelog.new_path.name}` |")
    lines.append(f"| **Paragraphs** | {s['old_paragraphs']} → "
                 f"{s['new_paragraphs']} |")
    lines.append(f"| **Modified** | {s['modified']} |")
    lines.append(f"| **Added** | {s['added']} |")
    lines.append(f"| **Removed** | {s['removed']} |")
    lines.append(f"| **Total changes** | {s['total']} |")
    lines.append("")

    if not changelog.changes:
        lines.append("> ✅ No changes detected. "
                     "The manuscripts are identical.")
        return "\n".join(lines)

    lines.append("---")
    lines.append("")

    # Group changes by section
    current_section = None
    change_num = 0

    for change in changelog.changes:
        # New section heading
        if change.section != current_section:
            # Close previous details block
            if current_section is not None:
                lines.append("")
                lines.append("</details>")
                lines.append("")

            current_section = change.section
            lines.append(f"<details open>")
            lines.append(f"<summary><strong>📌 {current_section}"
                         f"</strong></summary>")
            lines.append("")

        change_num += 1

        if change.kind == "ADDED":
            lines.append(f"#### ✅ Change {change_num} — Added")
            lines.append("")
            lines.append(f"> {_escape_md(change.new_text)}")
            lines.append("")

        elif change.kind == "REMOVED":
            lines.append(f"#### ❌ Change {change_num} — Removed")
            lines.append("")
            lines.append(f"> ~~{_escape_md(change.old_text)}~~")
            lines.append("")

        elif change.kind == "MODIFIED":
            lines.append(f"#### ✏️ Change {change_num} — Modified")
            lines.append("")

            combined_len = len(change.old_text) + len(change.new_text)
            if combined_len < 1500:
                # Inline word-level diff
                diff_str = _word_diff_md(change.old_text, change.new_text)
                lines.append(f"> {_escape_md(diff_str)}")
            else:
                # Too long for inline — show before/after blocks
                lines.append("**Before:**")
                lines.append(f"> {_escape_md(_truncate(change.old_text, 300))}")
                lines.append("")
                lines.append("**After:**")
                lines.append(f"> {_escape_md(_truncate(change.new_text, 300))}")
            lines.append("")

    # Close last details block
    if current_section is not None:
        lines.append("</details>")
        lines.append("")

    lines.append("---")
    lines.append(f"*{s['total']} change(s) total*")

    return "\n".join(lines)


##### VERSION DISCOVERY #####

def find_manuscript(version_str: str) -> Path:
    """Resolve a version string like 'v33' or '33' to a .docx path.

    Args:
        version_str: Version number with or without 'v' prefix.

    Returns:
        Path to the manuscript .docx.

    Raises:
        FileNotFoundError: If the version doesn't exist.
    """
    v = version_str.lstrip("v")
    path = ARCHIVE_DIR / f"GSM_Manuscript_v{v}.docx"
    if not path.exists():
        raise FileNotFoundError(f"Manuscript not found: {path}")
    return path


def find_latest_two() -> tuple[Path, Path]:
    """Find the two most recent manuscript versions.

    Returns:
        (old_path, new_path) — second-latest and latest.

    Raises:
        FileNotFoundError: If fewer than 2 versions exist.
    """
    existing = sorted(
        ARCHIVE_DIR.glob("GSM_Manuscript_v*.docx"),
        key=lambda p: _extract_version(p),
    )
    if len(existing) < 2:
        raise FileNotFoundError(
            "Need at least 2 manuscript versions to compare. "
            f"Found {len(existing)} in {ARCHIVE_DIR}")
    return existing[-2], existing[-1]


def _extract_version(path: Path) -> int:
    """Extract version number from manuscript filename."""
    match = re.search(r"_v(\d+)\.docx$", path.name)
    return int(match.group(1)) if match else 0


##### ENTRY POINT #####

def main():
    """CLI entry point for manuscript changelog."""
    parser = argparse.ArgumentParser(
        description="Compare two GSM manuscript .docx versions "
                    "and output a human-readable changelog.")
    parser.add_argument(
        "--old", type=str, default=None,
        help="Old version (e.g. 'v33' or '33'). "
             "Default: second-latest version.")
    parser.add_argument(
        "--new", type=str, default=None,
        help="New version (e.g. 'v34' or '34'). "
             "Default: latest version.")
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save changelog to this file (e.g. changelog.md) "
             "instead of printing.")

    args = parser.parse_args()

    # Resolve paths
    if args.old and args.new:
        old_path = find_manuscript(args.old)
        new_path = find_manuscript(args.new)
    elif args.old or args.new:
        parser.error("Specify both --old and --new, or neither.")
    else:
        old_path, new_path = find_latest_two()

    print(f"  Comparing: {old_path.name}  →  {new_path.name}")

    # Extract and diff
    old_paras = extract_paragraphs(old_path)
    new_paras = extract_paragraphs(new_path)
    changelog = compute_changelog(old_paras, new_paras, old_path, new_path)

    # Format
    report = format_changelog(changelog)

    # Output
    if args.output:
        out = Path(args.output)
        out.write_text(report, encoding="utf-8")
        print(f"  Saved changelog to: {out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
