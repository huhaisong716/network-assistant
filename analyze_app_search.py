#!/usr/bin/env python3
"""Find how search is called in app.py"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/app.pyc"
with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Find App class
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'App':
        app_class = c
        break

# Find search-related methods
for i, c in enumerate(app_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name not in ('<listcomp>', '<genexpr>'):
        name = c.co_name
        names = list(c.co_names)
        if any(kw in name.lower() for kw in ['search', 'find', 'bind']) or any(kw in names for kw in ['search', 'SearchEngine']):
            print(f"\n{'='*60}")
            print(f"Method: {name}")
            print(f"Varnames: {c.co_varnames}")
            print(f"Names: {names}")
            strs = [x for x in c.co_consts if isinstance(x, str)]
            print(f"Strings: {strs[:10]}")
            # Show first 20 instructions
            for inst in list(dis.get_instructions(c))[:25]:
                print(f"  {inst.offset:4d}: {inst.opname} {inst.argrepr}")
