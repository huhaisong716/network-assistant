#!/usr/bin/env python3
"""Disassemble specific methods from search_engine"""
import sys, marshal, dis, re

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"

with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Get SearchEngine class
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'SearchEngine':
        engine_class = c
        break

methods_to_show = ['_search_query', '_search_flattened_ocr', '_search_char_intersection', '_search_syllable_intersection']

for i, c in enumerate(engine_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name in methods_to_show:
        print(f"\n{'='*70}")
        print(f"METHOD: {c.co_name}")
        print(f"Args: {c.co_argcount} (+self)")
        print(f"Varnames: {c.co_varnames}")
        print(f"Names: {c.co_names}")
        strs = [x for x in c.co_consts if isinstance(x, str)]
        print(f"Strings: {strs[:30]}")
        print(f"{'='*70}")
        try:
            dis.dis(c)
        except Exception as e:
            print(f"Disassembly error: {e}")
