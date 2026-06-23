#!/usr/bin/env python3
"""Final verification - is the original code actually working?"""
import sys, marshal, types

pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"
with open(pyc_path, "rb") as f:
    raw = f.read()
code = marshal.loads(raw[16:])

mod = types.ModuleType("se")
mod.__file__ = pyc_path
sys.modules["se"] = mod
import re, logging
mod.re = re
mod.logging = logging
exec(code, mod.__dict__)

SearchEngine = mod.SearchEngine

# Build proper mock - text_pages is an INSTANCE attribute
class MockPdfEngine:
    def __init__(self, pages=None):
        self.text_pages = pages or {}
        self.page_count = len(self.text_pages)
        self.image_pages = set()
    
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

# Test 1: Single page with full name
pages = {0: "持证人 解英朋 登记日期 2021年02月20日 J371"}
engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine(pages))

print("=== Test 1: Full name in text ===")
r = engine.search("解英朋")
print(f"  Result: {len(r)} {'PASS' if len(r)>0 else 'FAIL'}")
for x in r:
    print(f"  page={x.get('page')} src={x.get('source')}")

# Test 2: Character splits across pages (realistic scenario)
pages2 = {}
pages2[4] = "结婚登记审查处理表 解 英朋 身份证 110108"
pages2[5] = "持证人 解英朋 登记日期 2021年02月20日 婚姻登记"
engine2 = SearchEngine()
engine2.set_pdf_engine(MockPdfEngine(pages2))

print("\n=== Test 2: Full name on one page, split on another ===")
r = engine2.search("解英朋")
print(f"  Result: {len(r)} {'PASS' if len(r)>0 else 'FAIL'}")
for x in r:
    print(f"  page={x.get('page')} src={x.get('source')}")

r2 = engine2.search("解")
print(f"  search('解'): {len(r2)} results {'PASS' if len(r2)>0 else 'FAIL'}")

# Test 3: Only individual characters, no full string
pages3 = {}
pages3[0] = "解 身份证"
pages3[1] = "英 身份证"  
pages3[2] = "朋 身份证"

engine3 = SearchEngine()
engine3.set_pdf_engine(MockPdfEngine(pages3))

print("\n=== Test 3: Chars on separate pages, no page has all 3 ===")
r = engine3.search("解英朋")
print(f"  search('解英朋'): {len(r)} results")
for x in r:
    print(f"  page={x.get('page')} src={x.get('source')}")
print("  (Expected: 0 if no page has all 3 characters)")

# Test 4: With OCR results - char by char output
engine4 = SearchEngine()
engine4.set_pdf_engine(MockPdfEngine(pages3))
engine4.add_ocr_results(0, [
    {'text': '解 英 朋'},  # OCR output has all 3 with spaces
    {'text': '身份证号码 110108'}
])

print("\n=== Test 4: OCR has all 3 chars (Strategy X) ===")
r = engine4.search("解英朋")
print(f"  search('解英朋'): {len(r)} results {'PASS' if len(r)>0 else 'FAIL'}")
for x in r:
    print(f"  page={x.get('page')} src={x.get('source')} text={str(x.get('text'))[:40]}")

# Test 5: Mixed - text has individual chars, OCR has them together  
engine5 = SearchEngine()
pages5 = {0: "xxx 解 xxx", 1: "yyy 英 yyy", 2: "zzz 朋 zzz"}
engine5.set_pdf_engine(MockPdfEngine(pages5))
engine5.add_ocr_results(0, [{'text': '持证人 解英朋 2021'}])

print("\n=== Test 5: Text has individual chars, OCR has full name ===")
r = engine5.search("解英朋")
print(f"  search('解英朋'): {len(r)} results {'PASS' if len(r)>0 else 'FAIL'}")
for x in r:
    print(f"  page={x.get('page')} src={x.get('source')}")
