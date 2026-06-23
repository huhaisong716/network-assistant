#!/usr/bin/env python3
"""Compare reconstructed code bytecode with actual"""
import sys, marshal, dis

# Load actual code
pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"
with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Find SearchEngine class and _search_impl
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'SearchEngine':
        engine_class = c
        break

for i, c in enumerate(engine_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name == '_search_impl':
        print(f"=== _search_impl ({len(c.co_code)} bytes) ===")
        print(f"Varnames: {c.co_varnames}")
        print(f"Names: {c.co_names}")
        dis.dis(c)
        break
