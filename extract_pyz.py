#!/usr/bin/env python3
"""Extract PYZ archive from PyInstaller build"""
import struct, zlib, marshal, os

pyz_file = "/tmp/pyinstxtractor/OCRDataExtractor.exe_extracted/PYZ.pyz"
out_dir = "/tmp/pyinstxtractor/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted"
os.makedirs(out_dir, exist_ok=True)

with open(pyz_file, "rb") as f:
    data = f.read()

magic = struct.unpack("<I", data[:4])[0]
print(f"Magic: {hex(magic)}")

if magic == 0x78563412:
    toc_len = struct.unpack("<I", data[4:8])[0]
    print(f"TOC len: {toc_len}")
    
    # Decompress TOC
    toc_compressed = data[8:8+toc_len]
    toc_data = zlib.decompress(toc_compressed)
    toc = marshal.loads(toc_data)
    print(f"TOC entries: {len(toc)}")
    
    # Find position after TOC
    pos = 8 + toc_len
    
    # Extract modules
    for name, (typ, uncompressed_len, compressed_len, offset) in toc.items():
        print(f"  [{typ}] {name} (uncomp={uncompressed_len})")
        
        if typ == 's':  # source (compressed code object)
            # Read compressed data
            chunk = data[pos:pos+compressed_len]
            code_bytes = zlib.decompress(chunk)
            
            # Save as .pyc
            out_file = os.path.join(out_dir, name.replace("/", os.sep) + ".pyc")
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            with open(out_file, "wb") as f:
                f.write(code_bytes)
            
            pos += compressed_len
        
        if name == "search_engine":
            print(f"\n*** search_engine found! ***")
            print(f"  Type: {typ}, uncompressed: {uncompressed_len}")
            try:
                code_obj = marshal.loads(code_bytes)
                print(f"  Code names: {code_obj.co_names}")
                print(f"  Code varnames: {code_obj.co_varnames}")
                print(f"  Code consts: {code_obj.co_consts}")
            except Exception as e:
                print(f"  Error loading: {e}")

elif magic == 0x78563413:
    # Different PYZ format
    print("Different PYZ format detected")
else:
    print(f"Unknown magic: trying alternative parsing")
    # Try reading as raw zlib
    try:
        decomp = zlib.decompress(data)
        toc2 = marshal.loads(decomp)
        print(f"Raw zlib worked! TOC entries: {len(toc2)}")
    except:
        print("Raw zlib failed too")
