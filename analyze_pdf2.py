#!/usr/bin/env python3
"""Reconstruct pdf_engine.py from bytecode analysis"""
import sys, marshal, types, logging, re

pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/pdf_engine.pyc"
with open(pyc_path, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

mod = types.ModuleType("pe")
mod.__file__ = pyc_path
sys.modules["pe"] = mod
mod.logging = logging
mod.re = re
exec(code, mod.__dict__)

# Get the PdfEngine class
PdfEngine = mod.PdfEngine

# Inspect the class
print("PdfEngine methods:")
import dis
for i, c in enumerate(PdfEngine.__init__.__code__.co_consts):
    if hasattr(c, 'co_code') and c.co_name not in ('<listcomp>', '<genexpr>', '<lambda>'):
        print(f"  {c.co_name}")

# Test creating an instance with search_text
engine = PdfEngine()
print(f"\nCreated engine: {engine}")
print(f"Attributes: {[a for a in dir(engine) if not a.startswith('__')]}")

# Try to understand the structure by testing
print(f"\ntext_pages: {engine.text_pages}")
print(f"image_pages: {engine.image_pages}")
print(f"page_count: {engine.page_count}")
