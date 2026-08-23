#!/usr/bin/env python3
"""Parses tracked changes and review comments from Word documents."""
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def parse_final_node(node):
    tag = node.tag.split('}')[-1]
    if tag == "t":
        return node.text or ""
    elif tag == "delText" or tag == "del":
        # Ignore deleted text completely
        return ""
    elif tag == "ins":
        # Keep inserted text
        return "".join([parse_final_node(c) for c in node])
    elif tag == "commentReference":
        return ""
    else:
        return "".join([parse_final_node(c) for c in node])

def extract_final_text(filepath, out_path):
    print(f"Extracting final text from {filepath}...")
    with zipfile.ZipFile(filepath) as z:
        try:
            doc_xml = z.read('word/document.xml')
        except KeyError:
            print("Error: Could not find word/document.xml inside the DOCX.")
            sys.exit(1)

    doc_tree = ET.fromstring(doc_xml)
    
    out_lines = []
    
    for p in doc_tree.iter(f"{{{NS['w']}}}p"):
        text = parse_final_node(p).strip()
        # Clean up double spaces caused by insertions/deletions spacing
        import re
        text = re.sub(r'\s+', ' ', text)
        if text:
            out_lines.append(text)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    
    print(f"Saved final clean text to {out_path}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python scripts/manuscript/parse_docx_reviews.py <input.docx> <output.txt> --final")
        sys.exit(1)
    extract_final_text(sys.argv[1], sys.argv[2])
