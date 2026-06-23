#!/usr/bin/env python3
"""Find search-related methods in app.py"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/app.pyc"
with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Find App class
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'App':
        app_class = c
        break

# Find the search method (triggered by UI button)
for i, c in enumerate(app_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name not in ('<listcomp>', '<genexpr>', '<lambda>'):
        name = c.co_name
        names = c.co_names
        if 'search' in name.lower() or 'search' in str(names):
            print(f"\n{'='*60}")
            print(f"[{i}] Method: {name}")
            print(f"Varnames: {c.co_varnames}")
            print(f"Names: {list(names)}")
            strs = [x for x in c.co_consts if isinstance(x, str)]
            print(f"Strings: {strs[:10]}")
            insts = list(dis.get_instructions(c))
            for inst in insts[:50]:
                print(f"  {inst.offset:4d}: {inst.opname} {inst.argrepr}")
            if len(insts) > 50:
                print(f"  ... ({len(insts)} total)")
