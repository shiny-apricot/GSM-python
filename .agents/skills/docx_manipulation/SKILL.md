---
name: DOCX Manipulation
description: Triggers whenever the user asks to edit, read, format, or manipulate a .docx (Microsoft Word) file.
---
# DOCX Manipulation Methodology for AI Agents

## Overview
AI Agents working in this repository often need to read, analyze, and directly modify Microsoft Word documents (`.docx`), such as manuscript drafts or reviewer response letters.

## Challenge
`.docx` files are complex ZIP archives containing multiple XML files representing formatting, styles, images, and text. Writing to them by extracting plain text, modifying it, and trying to reconstruct the document will **destroy** the original formatting (fonts, bolding, italics, tables, and images).

## Solution
We use the `python-docx` library to safely manipulate the document in-place.

1. **Hierarchy**: `Document` -> `Paragraph` -> `Run`. 
2. A `Run` is a contiguous sequence of characters sharing the exact same font/style. 
3. **Safe Modification**: By performing targeted string replacements exclusively on the `Run.text` property, we avoid disrupting the underlying XML structure. 

## Best Practices for Reading
When AI agents need to understand the structural content, headings, and tables of a `.docx` file, reading the raw XML or using `python-docx` for simple text extraction can be slow and error-prone. 
*   **Recommendation**: To make it easy to read a docx file, first convert it to a Markdown (`.md`) file (e.g., using `pandoc` or `mammoth`) and read the resulting markdown file. This preserves tables and headings in a highly readable format for AI context.

## Critical Gotchas & Best Practices

### 0. STRICT BACKUP PROTOCOL (CRITICAL)
**Never perform in-place read-modify-write operations on the exact same `.docx` file without a pristine backup.** Because docx scripts are often destructive, running them multiple times on the same file compounds changes (e.g., duplicating tables or paragraphs).
*   **Rule**: Before modifying any document, always create or read from a `.orig` backup (e.g., `copy manuscript.docx manuscript.orig.docx`). Your scripts must *read* from `.orig` and *write* to the target file. This guarantees idempotency.

### 0.5. Prefer Advanced Tooling (Spire.Doc / Aspose)
While `python-docx` is useful for simple tasks, it is inherently fragile for complex structural edits (e.g., manual MDPI table borders, dynamic figure references, native comments). 
*   **Rule**: If a task requires complex table manipulation, exact formatting preservation, or native Word comments, **DO NOT hack around `python-docx` limitations**. Use a robust library like `Spire.Doc for Python` or `Aspose.Words`. These libraries natively handle document DOMs, split runs, and advanced table styling without breaking the document.

### 1. The "Split Run" Problem (CRITICAL)
Word frequently splits a single word or phrase across multiple `Run`s due to spellchecking, tracking changes, or minor formatting differences. 
*   **Symptom**: `'TARGET_STRING' in p.text` is `True`, but `'TARGET_STRING' in r.text` is `False` for all runs.
*   **Resolution**: Do not loop endlessly. If the target string is split across runs, you must either:
    1. Implement a run-merging script (clear text of subsequent runs and combine into the first).
    2. As a last resort, modify `p.text` directly (`p.text = p.text.replace(...)`), which will reset the formatting of that specific paragraph to the default style. Warn the user if you do this.

### 2. Searching Beyond Paragraphs (Tables, Headers, & Nested Elements)
`doc.paragraphs` only searches the main body text. You must explicitly iterate through tables and headers to find all text.
*   **Tables**: Iterate via `doc.tables` -> `table.rows` -> `row.cells` -> `cell.paragraphs`.
    *   **Nested Tables**: Cells can contain nested tables! Always check `cell.tables` and iterate through them as well.
*   **Headers/Footers**: Iterate via `doc.sections` -> `section.header.paragraphs` and `section.header.tables`.

### 3. Manipulating Figures and Cross-References (CRITICAL)
When updating Figure or Table numbers (e.g., changing "Figure 4" to "Figure 3"), be extremely careful:
*   **Word Fields**: Figure numbers, Table numbers, and cross-references are often implemented as dynamic Word fields (e.g., `SEQ Figure` or `REF`). 
*   **The Split-Run Field Problem**: These fields often separate the label (e.g., "Figure ") and the dynamic number (e.g., "4") into different runs, interspersed with hidden XML field codes. A naive `r.text.replace('Figure 4', 'Figure 3')` will frequently fail because the string "Figure 4" does not exist in any single `Run`.
*   **Resolution**: 
    1. First, check the combined text of the paragraph: `full_text = "".join([r.text for r in p.runs])`.
    2. If the target string exists in `full_text` but not in any single `r.text`, you must implement a robust run-merging logic or carefully clear the `.text` of the specific constituent runs containing the field, and place the new combined string into the first run.
*   **Finding Captions**: Figure and Table captions are typically paragraphs where `p.style.name.startswith('Caption')` (or exactly `'Caption'`). Use this to safely target caption updates without accidentally altering identical strings in the body text.

## Example Patterns

### Pattern 1: Safe String Replacement (Body Text)
```python
import docx
doc = docx.Document('manuscript.docx')

for p in doc.paragraphs:
    if 'TARGET_STRING' in p.text:
        # Check if it exists cleanly in a single run
        for r in p.runs:
            if 'TARGET_STRING' in r.text:
                r.text = r.text.replace('TARGET_STRING', 'NEW_STRING')
                
doc.save('manuscript.docx')
```

### Pattern 2: Modifying Tables (including Nested Tables) safely
```python
def replace_text_in_table(table, target, new_text):
    for row in table.rows:
        for cell in row.cells:
            # 1. Replace in paragraphs
            for p in cell.paragraphs:
                for r in p.runs:
                    if target in r.text:
                        r.text = r.text.replace(target, new_text)
            # 2. Recursively handle nested tables
            for nested_table in cell.tables:
                replace_text_in_table(nested_table, target, new_text)

for table in doc.tables:
    replace_text_in_table(table, 'TARGET', 'NEW')
```

### Pattern 3: Updating Figure/Table References with Split Runs
```python
for p in doc.paragraphs:
    full_text = "".join([r.text for r in p.runs])
    if 'Figure 4' in full_text:
        # If 'Figure 4' is split across runs due to being a Word field,
        # find the sequence of runs containing it and merge/replace.
        # A simple brute-force approach (destroys run formatting):
        p.text = p.text.replace('Figure 4', 'Figure 3') 
        # WARNING: Modifying p.text resets the paragraph formatting.
        # For a safer approach, clear `r.text` for the specific runs 
        # containing "Figure" and "4", then inject "Figure 3".
```

### Pattern 4: Handling Images/Figures
Images are stored as `InlineShape` objects inside `Run`s. `python-docx` has limited support for modifying them in-place.
```python
# To replace or remove an image, you typically find the paragraph containing it,
# clear its contents, and insert a new image.
for p in doc.paragraphs:
    if '[Placeholder for Figure 1]' in p.text:
        p.text = "" # Clear the placeholder
        r = p.add_run()
        import docx
        r.add_picture('figure1.png', width=docx.shared.Inches(4.0))
```

### Pattern 5: Highlighting Changes
```python
from docx.enum.text import WD_COLOR_INDEX

for p in doc.paragraphs:
    for r in p.runs:
        if 'MODIFIED_STRING' in r.text:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
```

### Adding Comments (Office Word Feature)

**CRITICAL RULE FOR AGENTS**: If you change a part of a `.docx` document and the user needs a specific explanation to understand what is happening (e.g., why a value was updated, a formatting issue was bypassed, or an assumption was made), **you must directly and proactively decide to add a native Word comment** in the document near the change. 

Because `python-docx` does not natively support inserting new Word comments easily, you must bypass `python-docx` and use an appropriate library (such as `Spire.Doc for Python` or `Aspose.Words`) or write a robust script that properly injects comment objects and links them to specific text ranges in the document XML. Do not use inline highlighted text or any other mock-comment workaround. The comment must appear as a native Office Word review comment.

By strictly adhering to this methodology, agents can fix typos, update table numbers, and revise paragraphs while keeping the manuscript's styling perfectly intact.
