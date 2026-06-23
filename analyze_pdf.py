#!/usr/bin/env python3
"""Analyze pdf_engine - specifically search_text method"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/pdf_engine.pyc"

with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])
print(f"Module: {code.co_name}")
print(f"Names: {code.co_names}")
print(f"String consts: {[x for x in code.co_consts if isinstance(x, str)][:20]}")

# Find classes and methods
for c in code.co_consts:
    if hasattr(c, 'co_code'):
        print(f"\n--- {c.co_name} ---")
        print(f"  Names: {c.co_names[:30]}")
        strs = [x for x in c.co_consts if isinstance(x, str)]
        print(f"  Strings: {strs[:15]}")
        
        # If it's a class, find its methods
        if c.co_name != '<module>':
            for m in c.co_consts:
                if hasattr(m, 'co_code') and m.co_name in ('search_text', '_search_text', 'search'):
                    print(f"\n  >>> METHOD: {m.co_name}")
                    print(f"  Varnames: {m.co_varnames}")
                    print(f"  Names: {m.co_names}")
                    strs2 = [x for x in m.co_consts if isinstance(x, str)]
                    print(f"  Strings: {strs2[:20]}")
                    # Show first 20 instructions
                    for inst in list(dis.get_instructions(m))[:30]:
                        print(f"    {inst.opname} {inst.argrepr}")
