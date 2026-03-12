import os
import re

base_dir = r"c:\Users\John Romel Lucot\OneDrive\Desktop\Capstone project\capstone-projectv2\apps\admin_panel\templates\admin_panel"
out_file = r"C:\Users\John Romel Lucot\.gemini\antigravity\brain\f90d5a1b-abf5-4e8b-89ec-139705c17f90\clean_admin_panel_code.md"

def html_replacer(match):
    full_comment = match.group(0)
    inner_text = match.group(1).strip()
    words = inner_text.split()
    
    lower_inner = inner_text.lower()
    if "fixed" in lower_inner or "note:" in lower_inner or "here we" in lower_inner or "ensure that" in lower_inner:
        return ""
    
    if len(words) > 4:
        return ""
        
    return full_comment

html_files = []
for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.endswith(".html"):
            html_files.append(os.path.join(root, f))

with open(out_file, "w", encoding="utf-8") as out:
    out.write("# Cleaned Admin Panel Templates\n\n")
    out.write("Here are the fully cleaned templates ready for copyright submission.\n\n")
    
    for filepath in html_files:
        rel_path = os.path.relpath(filepath, base_dir)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 1. Django comments
        content = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '', content, flags=re.DOTALL)
        
        # 2. CSS comments line
        content = re.sub(r'^\s*/\*.*?\*/\s*\n', '', content, flags=re.DOTALL | re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # 3. HTML comments line
        content = re.sub(r'^\s*<!--(.*?)-->\s*\n', lambda m: m.group(0) if html_replacer(m) != "" else "", content, flags=re.DOTALL | re.MULTILINE)
        content = re.sub(r'<!--(.*?)-->', lambda m: html_replacer(m), content, flags=re.DOTALL)
        
        # cleanup double empty lines caused by deletions
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        out.write(f"## {rel_path}\n\n```html\n{content.strip()}\n```\n\n")

print(f"Done processing {len(html_files)} files. Output: {out_file}")
