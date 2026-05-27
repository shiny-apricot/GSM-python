import re
import difflib
from pathlib import Path

# 1. Parse the accepted text from the markdown reviews.
# We will read parsed_reviews.md, strip out the markup for insertions and deletions,
# to recover the "Final" intended text for each update block.
def get_final_text(block):
    # Remove deleted text: ~~ ... ~~
    text = re.sub(r'~~.*?~~', '', block, flags=re.DOTALL)
    # Extract inserted text: **++ ... (by Author) ++** -> ...
    text = re.sub(r'\*\*\+\+\s*(.*?)\s*\(by.*?\)\s*\+\+\*\*', r'\1', text, flags=re.DOTALL)
    # Extract inserted text without author (if any)
    text = re.sub(r'\*\*\+\+\s*(.*?)\s*\+\+\*\*', r'\1', text, flags=re.DOTALL)
    # Remove comment blocks: 💬 [COMMENT ...]
    text = re.sub(r'> 💬 \[COMMENT.*?\].*?\n', '', text)
    # Clean up excess spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def load_updates():
    with open("reports_ARCHIVE/manuscript/review/docx_imports/parsed_reviews.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    updates = []
    blocks = content.split("### Update #")[1:]
    for block in blocks:
        lines = block.split('\n', 1)
        if len(lines) > 1:
            body = lines[1].split('---')[0]
            final_text = get_final_text(body)
            if final_text:
                updates.append(final_text)
    return updates

# 2. Patch the python file
def patch_python_script(updates):
    script_path = Path("scripts/manuscript/build_manuscript_docx.py")
    code = script_path.read_text(encoding="utf-8")
    
    # Logic to find exact python string blocks and replace them.
    # This is a bit complex, let's just print the updates for now.
    print(f"Loaded {len(updates)} distinct updated paragraphs.")
    for i, u in enumerate(updates[:5]):
        print(f"[{i}]: {u}")

if __name__ == "__main__":
    updates = load_updates()
    patch_python_script(updates)
