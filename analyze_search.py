#!/usr/bin/env python3
"""反编译search_engine.pyc"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"

with open(pyc, "rb") as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")

# Python 3.13+ header: magic(4) + flags(4) + timestamp(4) + file_size(4) = 16 bytes
# Then the marshalled code object
code = marshal.loads(raw[16:])
print(f"Type: {type(code).__name__}")
print(f"Module: {code.co_name}")
print(f"Filename: {code.co_filename}")
print(f"Names: {code.co_names}")
print(f"Varnames: {code.co_varnames}")
print(f"Consts: {[(i, c) for i, c in enumerate(code.co_consts) if not hasattr(c, 'co_code')][:20]}")
print(f"\nNested code objects: {len([c for c in code.co_consts if hasattr(c, 'co_code')])}")

# Find search function
for i, c in enumerate(code.co_consts):
    if hasattr(c, 'co_code'):
        print(f"\n--- [{i}] {c.co_name} ---")
        print(f"  Args: {c.co_argcount}")
        print(f"  Varnames: {c.co_varnames[:10]}")
        print(f"  Names: {c.co_names[:20]}")
        # Print string constants
        strs = [x for x in c.co_consts if isinstance(x, str)]
        print(f"  String consts: {strs[:15]}")

# Now try to use decompyle3 or uncompyle6 with Python 3.13
