#!/usr/bin/env python3
"""Debug original search_engine - add logging to track flow"""
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

class MockPdfEngine:
    text_pages = {0: "持证人 解英朋 登记日期 2021年02月20日 J371"}
    page_count = 10
    image_pages = set()
    
    def search_text(self, query, case_sensitive=False, exact_match=False):
        results = []
        search_q = query if case_sensitive else query.lower()
        for pn, txt in self.text_pages.items():
            st = txt if case_sensitive else txt.lower()
            found = search_q in st
            print(f"  [search_text] page={pn+1} query='{search_q}' found={found}")
            if found:
                idx = st.find(search_q)
                start = max(0, idx - 20)
                end = min(len(txt), idx + len(search_q) + 20)
                snippet = txt[start:end].strip().replace('\n', ' ')
                results.append({'page': pn + 1, 'text': snippet, 'source': '文字层'})
        print(f"  [search_text] returning {len(results)} results")
        return results

engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine())

print("=== search('解') ===")
r = engine.search("解")
print(f"Result: {r}")

print("\n=== search('解英朋') ===")
r = engine.search("解英朋")
print(f"Result: {r}")
