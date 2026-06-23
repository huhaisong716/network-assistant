#!/usr/bin/env python3
"""Debug why search returns 0 for multi-char queries"""
import sys, marshal, types, logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"
with open(pyc_path, "rb") as f:
    raw = f.read()
code = marshal.loads(raw[16:])

mod = types.ModuleType("se")
mod.__file__ = pyc_path
sys.modules["se"] = mod
import re
mod.re = re
mod.logging = logging
exec(code, mod.__dict__)

SearchEngine = mod.SearchEngine

# EXACT data from test_deep
pages = {}
for i in range(3, 24):
    pages[i] = f"第{i+1}页：解 身份证复印件 张三"
pages[25] = "第26页：英 身份证复印件 李四"
pages[26] = "第27页：朋 身份证"
pages[30] = "持证人 解英朋 登记日期 2021年02月20日 J371"
pages[31] = "持证人 孙长娥 登记日期 2021年03月15日 J372"
pages[32] = "持证人 王景行 登记日期 2021年04月10日 J373"

class MockPdfEngine:
    text_pages = pages
    page_count = 35
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

engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine())

print("=== search('解英朋') ===")
r = engine.search("解英朋")
print(f"Results: {len(r)}")
if r:
    for x in r:
        print(f"  page={x.get('page')} src={x.get('source')}")
else:
    print("  EMPTY!")

# Now test _search_impl directly
print("\n=== _search_impl('解英朋', False) ===")
r2 = engine._search_impl("解英朋", False)
print(f"Results: {len(r2) if r2 else 0}")
