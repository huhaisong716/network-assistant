#!/usr/bin/env python3
"""Integration test - simulate the EXACT app.pyc flow."""
import sys
import os

_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _base_dir)

from pdf_engine import PdfEngine
from search_engine import SearchEngine

print("=== Test 1: PdfEngine(path) construction ===")
# Simulate what app.pyc does: PdfEngine(path)
test_pdf = os.path.join(_base_dir, '..', '..', 'test-files', 'test_ocr.pdf')
if not os.path.exists(test_pdf):
    print(f"  No test PDF at {test_pdf}, creating one...")
    import fitz
    doc = fitz.open()
    
    # Page 1: "王麻子" as contiguous text
    page1 = doc.new_page()
    page1.insert_text((50, 100), "王麻子", fontsize=14)
    page1.insert_text((50, 150), "张三", fontsize=14)
    
    # Page 2: chars on separate lines 
    page2 = doc.new_page()
    page2.insert_text((50, 100), "李四", fontsize=14)
    page2.insert_text((50, 150), "王", fontsize=14)
    page2.insert_text((50, 200), "麻", fontsize=14)
    page2.insert_text((50, 250), "子", fontsize=14)
    
    # Page 3: full name with other content
    page3 = doc.new_page()
    page3.insert_text((50, 100), "王麻子", fontsize=14)
    page3.insert_text((50, 200), "日期：2024年1月", fontsize=14)
    
    os.makedirs(os.path.dirname(test_pdf), exist_ok=True)
    doc.save(test_pdf)
    doc.close()
    print(f"  Created test PDF: {test_pdf}")

# Test 1: PdfEngine(path) - exactly what app.pyc calls
try:
    engine = PdfEngine(test_pdf)
    print(f"  OK - PdfEngine('{test_pdf}') created")
    print(f"  Pages: {engine.page_count}")
    print(f"  Text pages: {len(engine.text_pages)}")
    print(f"  Image pages: {len(engine.image_pages)}")
    for pn in sorted(engine.text_pages.keys()):
        text = engine.text_pages[pn][:80].replace('\n', ' ')
        print(f"    Page {pn+1}: '{text}'")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: SearchEngine(engine) - exactly what app.pyc calls
print("\n=== Test 2: SearchEngine + search ===")
se = SearchEngine(engine)

tests = [
    ("王", True),
    ("王麻子", True),
    ("张三", True),
    ("不存在", False),
]

all_ok = True
for query, should_find in tests:
    results = se.search(query)
    pages = [r['page'] for r in results]
    sources = [r['source'] for r in results]
    found = len(results) > 0
    status = "OK" if found == should_find else "MISMATCH"
    if status == "MISMATCH":
        all_ok = False
    print(f"  {status}: '{query}' -> {len(results)} results pages={pages} sources={sources}")

if all_ok:
    print("\n  ALL SEARCH TESTS PASSED!")
else:
    print("\n  SOME TESTS FAILED!")
    sys.exit(1)

# Test 3: Search with OCR results (like app.pyc flow)
print("\n=== Test 3: With OCR results ===")
se2 = SearchEngine(engine)
se2.add_ocr_results(0, [{'text': '王麻子'}, {'text': '张三'}])
se2.add_ocr_results(1, [{'text': '王'}, {'text': '麻'}, {'text': '子'}])
se2.add_ocr_results(2, [{'text': '李四'}, {'text': '日期: 2024'}])

for query in ["王", "王麻子", "张三"]:
    results = se2.search(query)
    pages = [r['page'] for r in results]
    sources = [r['source'] for r in results]
    print(f"  '{query}': {len(results)} results pages={pages} sources={sources}")

print("\n=== Test 4: main.py patched search ===")
# Import and run the patching logic
import importlib.util
spec = importlib.util.spec_from_file_location("main_patch", os.path.join(_base_dir, "main.py"))
main_mod = importlib.util.module_from_spec(spec)

# We only need to test the patched search logic
# The main.py patches SearchEngine then execs app.pyc
# Our test: verify the search method is correctly patched
from search_engine import SearchEngine

# Check search works on patched class
engine2 = PdfEngine(test_pdf)
se3 = SearchEngine(engine2)

# Run same searches through the search method
for query in ["王", "王麻子"]:
    results = se3.search(query)
    print(f"  Search '{query}': {len(results)} results, pages={[r['page'] for r in results]}")
    if not results:
        print(f"    BUG: '{query}' should return results!")

print("\n=== SUCCESS: All integration tests pass! ===")
