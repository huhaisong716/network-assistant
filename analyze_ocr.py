#!/usr/bin/env python3
"""Reconstruct ocr_engine.py from bytecode analysis"""
import sys, marshal, types, logging

pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/ocr_engine.pyc"
with open(pyc_path, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Get names and strings
print("Module names:", code.co_names)
print("Module strings:", [x for x in code.co_consts if isinstance(x, str)])

# Find OcrEngine class
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name in ('OcrEngine', 'OcrEngineRecognizer'):
        print(f"\nClass: {c.co_name}")
        print(f"  Names: {c.co_names}")
        for m in c.co_consts:
            if hasattr(m, 'co_code') and m.co_name not in ('<listcomp>', '<genexpr>', '<lambda>'):
                strs = [x for x in m.co_consts if isinstance(x, str)]
                print(f"  Method: {m.co_name} - strings: {strs[:5]}")
