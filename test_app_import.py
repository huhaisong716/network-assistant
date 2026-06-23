#!/usr/bin/env python3
"""Test running original app.pyc with fixed search_engine.py"""
import sys, marshal, os

# Add our fixed modules to path
sys.path.insert(0, '/home/dytc/network-assistant')

# First, let's verify our search_engine is importable
print("Testing imports...")
from search_engine_recon import SearchEngine as FixedSearchEngine
print(f"  Fixed search_engine: OK ({FixedSearchEngine})")

from pdf_engine_recon import PdfEngine as FixedPdfEngine
print(f"  Fixed pdf_engine: OK ({FixedPdfEngine})")

# Now try to load and exec the original app.pyc
app_pyc = "/tmp/OCRDataExtractor.exe_extracted/app.pyc"
with open(app_pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])
print(f"\nLoaded app.pyc: {code.co_name}")
print(f"  Filename: {code.co_filename}")
print(f"  Names: {code.co_names[:20]}")
print(f"  Consts: {[x for x in code.co_consts if isinstance(x, str)][:10]}")

# Check what modules app.pyc imports
imports = [n for n in code.co_names if n in ('import', 'Import')]
for c in code.co_consts:
    if isinstance(c, tuple) and len(c) >= 2:
        if isinstance(c[0], int) and c[0] == 0:  # import statement
            print(f"  Import: {c[1]}")

# Find nested import statements  
for i, c in enumerate(code.co_consts[:50]):
    if isinstance(c, str) and ('import' in c.lower() or 'pdf_engine' in c or 'search' in c):
        print(f"  Const[{i}]: {c[:60]}")
