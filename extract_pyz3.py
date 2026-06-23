#!/usr/bin/env python3
"""Extract PYZ using correct format"""
import sys, os, struct, zlib, marshal

pyz_file = "/tmp/pyinstxtractor/OCRDataExtractor.exe_extracted/PYZ.pyz"
out_dir = "/tmp/pyinstxtractor/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted"
os.makedirs(out_dir, exist_ok=True)

with open(pyz_file, "rb") as f:
    data = f.read()

# PYZ format: "PYZ" + version_byte + marshalled_dict(toc) + zlib_blocks
# The TOC dict has: name -> (is_pkg, uncomp_len, comp_len)
# After the TOC, each module's data is stored at the end of the file

if data[:3] != b'PYZ':
    print("Not a PYZ file")
    sys.exit(1)

version = data[3]
toc_dict = marshal.loads(data[4:])
print(f"Version: {version}, TOC entries: {len(toc_dict)}")

# Calculate where module data starts
toc_size = len(data) - 4
# Actually the module data offsets might be relative to the end of the TOC
# Or they might be absolute positions

# Try to parse based on toc values
# toc values seem to be: (is_pkg, uncomp_len, comp_len, offset_from_end?)
# or: (typecode, uncomp_len, comp_len, data_offset)

# First, let me see what the values look like
for name in sorted(toc_dict.keys()):
    val = toc_dict[name]
    if name in ('search_engine', 'ocr_engine', 'pdf_engine', 'app'):
        print(f"\n{name}:")
        print(f"  raw: {val}")
        if isinstance(val, tuple):
            print(f"  len: {len(val)}")
            for i, v in enumerate(val):
                print(f"  [{i}]: {v} (type={type(v).__name__})")
