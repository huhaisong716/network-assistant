#!/usr/bin/env python3
"""Deep test: compare original vs reconstructed search_engine"""
import sys, marshal, types

# Load original module
pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"
with open(pyc_path, "rb") as f:
    raw = f.read()
code = marshal.loads(raw[16:])

mod = types.ModuleType("search_engine_orig")
mod.__file__ = pyc_path
sys.modules["search_engine_orig"] = mod
import re, logging
mod.re = re
mod.logging = logging
exec(code, mod.__dict__)

SearchEngine = mod.SearchEngine

# Test scenario: text layer HAS 解 but NOT 英朋 on same page
class MockPdfEngine:
    text_pages = {}
    page_count = 10
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

# Scenario: text layer has individual chars on separate pages
pages = {}
for i in range(3, 24):  # pages 4-24 have "解" 
    pages[i] = f"第{i+1}页：解 身份证复印件 张三"
pages[25] = "第26页：英 身份证复印件 李四"  # only has 英
pages[26] = "第27页：朋 身份证"            # only has 朋

# One page has "解英朋" together
pages[30] = "持证人 解英朋 登记日期 2021年02月20日 J371"
pages[31] = "持证人 孙长娥 登记日期 2021年03月15日 J372"
pages[32] = "持证人 王景行 登记日期 2021年04月10日 J373"

engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine())

# Test common name searches
names_to_test = ["解英朋", "孙长娥", "王景行", "解", "英"]
for name in names_to_test:
    result = engine.search(name, case_sensitive=False)
    print(f"search('{name}'): {len(result)} results")
    for r in result[:3]:
        print(f"  Page {r.get('page')}: src={r.get('source')} text={str(r.get('text'))[:40]}")
    print()

# Now test: what if _search_impl is called directly?
print("="*60)
print("Testing _search_impl directly:")
r = engine._search_impl("解英朋", False)
print(f"  _search_impl('解英朋'): {len(r) if r else 0} results")
if r:
    print(f"  Type: {type(r)}")

# Test: what if there's an exception?
print("\n" + "="*60)
print("Testing exception handling:")
try:
    # Try calling with various edge cases
    r = engine.search("", False)
    print(f"  search(''): {len(r)} results (type={type(r).__name__})")
    
    r = engine.search("  ", False)
    print(f"  search('  '): {len(r)} results (type={type(r).__name__})")
except Exception as e:
    print(f"  EXCEPTION: {e}")
