#!/usr/bin/env python3
"""Get last instructions of _search_impl to find return value"""
import sys, marshal, dis

pyc = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"

with open(pyc, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Get SearchEngine class
for c in code.co_consts:
    if hasattr(c, 'co_code') and c.co_name == 'SearchEngine':
        engine_class = c
        break

# Find _search_impl
for i, c in enumerate(engine_class.co_consts):
    if hasattr(c, 'co_code') and c.co_name == '_search_impl':
        print(f"Method: {c.co_name}")
        print(f"Total bytecode: {len(c.co_code)} bytes")
        # Get last instructions
        instructions = list(dis.get_instructions(c))
        n = len(instructions)
        for i in range(max(0, n-20), n):
            inst = instructions[i]
            print(f"  [{i}] {inst.opname} {inst.argrepr}")
        
        # Check all return-like instructions
        returns = [inst for inst in instructions if 'RETURN' in inst.opname]
        print(f"\nAll RETURN instructions:")
        for r in returns:
            print(f"  pos={r.offset}: {r.opname} {r.argrepr}")
        break
