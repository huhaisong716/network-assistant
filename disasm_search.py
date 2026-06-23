#!/usr/bin/env python3
"""反编译search_engine.pyc - Python 3.13"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"

with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Get SearchEngine class
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'SearchEngine':
        engine_class = c
        break

print("=== SearchEngine Methods ===")
for i, c in enumerate(engine_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name not in ('<listcomp>', '<genexpr>'):
        print(f"\n{'='*60}")
        print(f"Method: {c.co_name}")
        print(f"Args: {c.co_argcount} (+self)")
        print(f"Varnames: {c.co_varnames}")
        print(f"Names: {c.co_names}")
        strs = [x for x in c.co_consts if isinstance(x, str)]
        print(f"Strings: {strs[:20]}")
        print(f"{'='*60}")
        dis.dis(c)
        print()
