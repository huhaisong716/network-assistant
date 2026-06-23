#!/usr/bin/env python3
"""Full disasm of pdf_engine.search_text"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/pdf_engine.pyc"

with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Find PdfEngine class and search_text method
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'PdfEngine':
        for m in c.co_consts:
            if hasattr(m, 'co_code') and m.co_name == 'search_text':
                print(f"=== search_text (total {len(m.co_code)} bytes) ===")
                dis.dis(m)
                break
