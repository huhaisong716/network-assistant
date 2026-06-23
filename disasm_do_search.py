#!/usr/bin/env python3
"""Full disasm of _do_search"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/app.pyc"
with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'App':
        app_class = c
        break

# Get _do_search (index 16)
c = app_class.co_consts[16]
print(f"=== {c.co_name} ({len(c.co_code)} bytes) ===")
print(f"Varnames: {c.co_varnames}")
print(f"Names: {c.co_names}")
print(f"String consts: {[x for x in c.co_consts if isinstance(x, str)]}")
dis.dis(c)
