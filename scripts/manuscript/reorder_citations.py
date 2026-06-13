import re

def process():
    file_path = "scripts/manuscript/build_manuscript_docx.py"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into body and refs block
    refs_func_idx = content.find("def write_references(doc):")
    body = content[:refs_func_idx]
    refs_block = content[refs_func_idx:]

    # Parse old refs from refs_block
    # Pattern to capture "[X] Text"
    ref_matches = re.findall(r'(["\'])(\[([0-9]+)\].*?)\1', refs_block)
    old_refs = {}
    for quote_char, full_str, num_str in ref_matches:
        num = int(num_str)
        # Strip off the "[X] " prefix to just get the text
        text_only = re.sub(r'^\[\d+\]\s*', '', full_str)
        old_refs[num] = text_only

    old_to_new = {}
    next_id = 1

    # We need to replace citations in the body carefully to not break arrays like ci_widths[0]
    # We will only process things that look like string citations inside paragraph literals.
    # To be safe, we'll use a regex replacement function that only replaces if it looks like a citation.
    
    def repl_citation(m):
        nonlocal next_id
        inner = m.group(1)
        
        # Check if it's likely an array index rather than citation
        # Most of our bad hits were things like `[0]`. Citations never use 0.
        parts = [p.strip() for p in inner.split(',')]
        if '0' in parts:
            return m.group(0) # don't touch it
        
        # Valid citation array
        is_valid = True
        nums = []
        for p in parts:
            if not p.isdigit():
                is_valid = False
                break
            else:
                nums.append(int(p))
                
        if not is_valid:
            return m.group(0)
            
        new_nums = []
        for n in nums:
            if n not in old_to_new:
                old_to_new[n] = next_id
                next_id += 1
            new_nums.append(old_to_new[n])
            
        new_nums.sort()
        new_inner = ",".join(map(str, new_nums))
        return f"[{new_inner}]"

    # We only apply this to strings enclosed in quotes.
    # Let's write a helper to replace within a string.
    def repl_str(m):
        quote = m.group(1)
        text = m.group(2)
        # replace citations within text
        new_text = re.sub(r'\[([0-9\s,]+)\]', repl_citation, text)
        return f"{quote}{new_text}{quote}"

    new_body = re.sub(r'(["\'])(.*?)\1', repl_str, body, flags=re.DOTALL)
    
    # Now build the new refs array
    # Notice the old refs array format:
    # refs = [
    #     "[1] Bellman R. Dynamic programming. Science. 1966;153(3731):34-37.",
    #     ...
    # ]
    
    new_refs_lines = []
    
    # Sort old_to_new by new ID
    sorted_mappings = sorted(old_to_new.items(), key=lambda x: x[1])
    
    for old_id, new_id in sorted_mappings:
        text = old_refs.get(old_id, f"MISSING OLD REF {old_id}")
        new_refs_lines.append(f'        "[{new_id}] {text}"')
        
    new_refs_array_str = "refs = [\n" + ",\n".join(new_refs_lines) + "\n    ]"
    
    # We replace the refs array in the refs_block.
    # From "refs = [" to the closing bracket.
    start_refs = refs_block.find("refs = [")
    import ast
    # Instead of ast, let's just find the closing bracket
    # It might have trailing spacing
    # Better: just use regex
    new_refs_block = re.sub(r'refs\s*=\s*\[.*?\]', new_refs_array_str, refs_block, flags=re.DOTALL)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_body + new_refs_block)
        
    print(f"Renumbered {len(old_to_new)} unique citations.")

if __name__ == "__main__":
    process()
