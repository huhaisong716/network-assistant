#!/usr/bin/env python3
"""List ALL App methods"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/app.pyc"
with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'App':
        app_class = c
        break

# List ALL methods with their names and key names/strings
print("=== ALL App Methods ===")
for i, c in enumerate(app_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name not in ('<listcomp>', '<genexpr>', '<lambda>'):
        names = list(c.co_names)
        strs = [x for x in c.co_consts if isinstance(x, str)]
        # Look for search-related keywords
        has_search = any('search' in s.lower() for s in strs[:5]) or 'search' in c.co_name.lower()
        markers = []
        if has_search: markers.append('*** SEARCH ***')
        if 'do_search' in names: markers.append('do_search!')
        if 'search_engine' in names: markers.append('has_search_engine!')
        
        print(f"[{i:3d}] {c.co_name:25s} {', '.join(markers)}")
