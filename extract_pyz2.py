#!/usr/bin/env python3
"""Extract PYZ using PyInstaller ZlibArchiveReader (isolated)"""
import sys, os, struct, zlib, marshal

pyz_file = "/tmp/pyinstxtractor/OCRDataExtractor.exe_extracted/PYZ.pyz"
out_dir = "/tmp/pyinstxtractor/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted"
os.makedirs(out_dir, exist_ok=True)

with open(pyz_file, "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print(f"First 20 bytes: {data[:20].hex()}")

if data[:3] == b'PYZ':
    version = data[3]
    print(f"PYZ version: {version}")
    toc_data = data[4:]
    toc = marshal.loads(toc_data)
    print(f"TOC type: {type(toc).__name__}, entries: {len(toc)}")
    
    user_modules = []
    for name in sorted(toc.keys()):
        val = toc[name]
        if name in ('ocr_engine', 'pdf_engine', 'search_engine'):
            user_modules.append((name, val))
            print(f"\n*** {name} ***")
            print(f"  Value: {val}")
    
    print(f"\nAll user modules:")
    for name, val in user_modules:
        print(f"  {name}: {val}")
else:
    print("Not a standard PYZ file")
    # Try loading with ZlibArchiveReader from PyInstaller
    # But first we need to handle the struct.pyc issue
