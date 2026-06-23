#!/usr/bin/env python3
"""Test original search_engine.pyc with Python 3.13"""
import sys
import marshal
import types
import importlib.util

# Load the search_engine module directly from pyc
pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"

with open(pyc_path, "rb") as f:
    raw = f.read()

code = marshal.loads(raw[16:])

# Create a module from the code object
mod = types.ModuleType("search_engine")
mod.__file__ = pyc_path
mod.__package__ = ""
sys.modules["search_engine"] = mod

# Patch re and logging before executing
import re
import logging
mod.re = re
mod.logging = logging

# Execute the code to populate the module
exec(code, mod.__dict__)

# Now we can use the module's classes and functions
SearchEngine = mod.SearchEngine
_has_chinese = mod._has_chinese
_count_chinese_chars = mod._count_chinese_chars

print(f"Functions loaded:")
print(f"  SearchEngine: {SearchEngine}")
print(f"  _has_chinese('解英朋'): {_has_chinese('解英朋')}")
print(f"  _count_chinese_chars('解英朋'): {_count_chinese_chars('解英朋')}")

# Create mock pdf_engine
class MockPdfEngine:
    text_pages = {}
    page_count = 297
    image_pages = set()
    
    def search_text(self, query, case_sensitive=False, exact_match=False):
        results = []
        search_q = query if case_sensitive else query.lower()
        for pn, txt in self.text_pages.items():
            st = txt if case_sensitive else txt.lower()
            if search_q in st:
                idx = st.find(search_q)
                start = max(0, idx - 20)
                end = min(len(txt), idx + len(search_q) + 20)
                snippet = txt[start:end].strip().replace('\n', ' ')
                results.append({'page': pn + 1, 'text': snippet, 'source': '文字层'})
        return results

# Create engine and test
engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine())

# Add OCR results with real-looking data
# Page where all 3 chars appear together
engine.add_ocr_results(0, [
    {'text': '持证人 解英朋 登记日期 2021年02月20日'},
    {'text': '结婚证字号 J371123'},
])
# Page where only 解 appears
engine.add_ocr_results(1, [
    {'text': '解 身份证复印件'},
])

# Test single character
print("\n--- Test: search('解') ---")
r1 = engine.search("解", case_sensitive=False)
print(f"  Results: {len(r1)}")

# Test full name
print("\n--- Test: search('解英朋') ---")
r2 = engine.search("解英朋", case_sensitive=False)
print(f"  Results: {len(r2)}")
if r2:
    for r in r2:
        print(f"  Page {r.get('page')}: source={r.get('source')}, text={r.get('text')[:50]}")
else:
    print("  EMPTY - BUG CONFIRMED!")

# Test with page_results populated  
print("\n--- Debug: calling strategies directly ---")
pr = {}
engine._search_flattened_ocr(['解','英','朋'], pr)
print(f"  Strategy X found: {len(pr)} pages")

pr2 = {}
engine._search_char_intersection(['解','英','朋'], pr2)
print(f"  Strategy C found: {len(pr2)} pages")
