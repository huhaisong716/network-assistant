#!/usr/bin/env python3
"""修复 .pyc 头部并反编译 v2"""
import os
import struct
import time
import marshal
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent/venv/lib/python3.11/site-packages"))

src_pyc = "/tmp/ocr-tool-src/extracted/app.pyc"
out_py = "/tmp/ocr-tool-src/extracted/app.py"

# Read raw marshal code
with open(src_pyc, "rb") as f:
    raw = f.read()

# Python 3.11 magic: 0xa70d (227 + 0x0a0d)
magic = struct.pack("<H", 227) + b'\x0d\x0a'
header = magic
header += struct.pack("<I", 0)  # flags
header += struct.pack("<I", int(time.time()))  # timestamp
header += struct.pack("<I", 0)  # source size

proper_pyc = src_pyc.replace(".pyc", "_fixed.pyc")
with open(proper_pyc, "wb") as f:
    f.write(header)
    f.write(raw)

print(f"Written: {proper_pyc}")

# Fix Python 3.11 magic in xdis
import xdis.magics as magics
# Add the magic
if 227 not in magics.magicint2version:
    magics.magicint2version[227] = '3.11'

# For 3.11, the tuple is (3, 11)
import xdis.version
if not hasattr(magics, 'magic2version'):
    # Create a mapping
    magics.magic2version = {}

# Now decompile
import decompyle3
try:
    with open(out_py, "w", encoding="utf-8") as f:
        decompyle3.decompile_file(proper_pyc, f)
    lines = open(out_py, encoding="utf-8").readlines()
    print(f"Decompiled: {out_py} ({len(lines)} lines)")
    for i, line in enumerate(lines[:40]):
        print(f"{i+1:4d}: {line.rstrip()}")
except Exception as e:
    print(f"decompyle3 failed: {e}")
    # Fall back to disassembly
    print("\n=== Fallback: disassembly ===")
    import dis
    code_obj = marshal.loads(raw)
    dis.dis(code_obj)
