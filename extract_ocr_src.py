#!/usr/bin/env python3
"""直接提取PyInstaller打包的源码"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent/venv/lib/python3.11/site-packages"))
from PyInstaller.archive.readers import CArchiveReader

exe_path = "/tmp/ocr-tool-src/OCRDataExtractor.exe"
out_dir = "/tmp/ocr-tool-src/extracted"
os.makedirs(out_dir, exist_ok=True)

# Open as CArchive
archive = CArchiveReader(exe_path)
print(f"Archive TOC entries: {len(archive.toc)}")

# Show all entries
for i, entry in enumerate(archive.toc):
    name, typ = entry[1], entry[2]
    if typ in ('s', 'm', 'b'):  # script, module, binary
        print(f"  [{typ}] {name}")

# Extract the 'app' script (main source)
print("\n=== Extracting 'app' script ===")
try:
    data = archive.extract("app")
    out_path = os.path.join(out_dir, "app.pyc")
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"Saved: {out_path} ({len(data)} bytes)")
except Exception as e:
    print(f"Error extracting 'app': {e}")
    # Try listing by index
    for i, entry in enumerate(archive.toc):
        print(f"  [{i}] {entry}")

print("\n=== Extracting PYZ ===")
try:
    pyz_data = archive.extract("PYZ.pyz")
    if pyz_data:
        out_pyz = os.path.join(out_dir, "PYZ.pyz")
        with open(out_pyz, "wb") as f:
            f.write(pyz_data)
        print(f"Saved PYZ: {out_pyz} ({len(pyz_data)} bytes)")
        
        # Parse PYZ
        from PyInstaller.archive.readers import ZlibArchiveReader
        pyz = ZlibArchiveReader(out_pyz)
        print(f"PYZ entries: {len(pyz.toc)}")
        
        # Find user code (non-standard-library modules)
        for name in sorted(pyz.toc.keys()):
            if not any(name.startswith(p) for p in ['_','encodings/','importlib','config-3']):
                print(f"  {name}")
        
        # Extract the user code
        app_dir = os.path.join(out_dir, "pyz_modules")
        os.makedirs(app_dir, exist_ok=True)
        
        count = 0
        for name in pyz.toc.keys():
            out_file = os.path.join(app_dir, name.replace('/', os.sep))
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            try:
                code = pyz.extract(name)
                if code:
                    with open(out_file, "wb") as f:
                        f.write(code)
                    count += 1
            except:
                pass
        print(f"Extracted {count} modules")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
