#!/usr/bin/env python3
"""Analyze app.py search handling"""
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

# Find all methods and their search-related code
print("=== App class methods ===")
for i, c in enumerate(app_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name not in ('<listcomp>', '<genexpr>', '<lambda>'):
        names = list(c.co_names)
        if any(kw in names for kw in ['search', 'SearchEngine', 'search_engine']):
            print(f"\n{'='*60}")
            print(f"Method [{i}]: {c.co_name}")
            print(f"Varnames: {c.co_varnames}")
            print(f"Names: {names}")
            strs = [x for x in c.co_consts if isinstance(x, str)]
            print(f"Strings: {strs[:15]}")
            print(f"{'='*60}")
            insts = list(dis.get_instructions(c))
            for inst in insts[:40]:
                print(f"  {inst.offset:4d}: {inst.opname} {inst.argrepr}")
            if len(insts) > 40:
                print(f"  ... ({len(insts)} total)")
