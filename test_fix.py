#!/usr/bin/env python3
"""Test the fixed search_engine with cross-page scenario"""
import sys, logging
sys.path.insert(0, '/home/dytc/network-assistant')
logging.basicConfig(level=logging.INFO)

import importlib
# Force reload the fixed module
if 'search_engine_recon' in sys.modules:
    del sys.modules['search_engine_recon']
from search_engine_recon import SearchEngine

class MockPdfEngine:
    def __init__(self, pages):
        self.text_pages = pages
        self.page_count = max(pages.keys()) + 1 if pages else 0
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
                results.append({'page': pn+1, 'text': snippet, 'source': '文字层'})
        return results

# Test A: Chars on separate pages (real user scenario)
pages = {}
for i in range(3, 24):
    pages[i] = f"第{i+1}页：解 身份证复印件 张三"
pages[25] = "第26页：英 身份证复印件 李四"
pages[26] = "第27页：朋 身份证"

engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine(pages))

print("=== Cross-page test (chars on diff pages) ===")
r = engine.search("解英朋")
print(f"search('解英朋'): {len(r)} results {'PASS' if len(r)>0 else 'FAIL'}")
for x in r:
    print(f"  page={x.get('page')} src={x.get('source')}")

print(f"\nsearch('解'): {len(engine.search('解'))} results")
print(f"search('解朋'): {len(engine.search('解朋'))} results")

# Test B: Normal case - full name together
engine2 = SearchEngine()
engine2.set_pdf_engine(MockPdfEngine({0: "持证人 解英朋 登记日期"}))
print(f"\n=== Normal case ===")
print(f"search('解英朋'): {len(engine2.search('解英朋'))} {'PASS' if len(engine2.search('解英朋'))>0 else 'FAIL'}")

# Test C: Mixed - some have 2/3, some have all 3
pages3 = {
    0: "解 测试文本",
    1: "英 测试文本",
    2: "朋 测试文本",
    3: "解英 测试文本",  # has 2 of 3
    4: "解朋 测试文本",  # has 2 of 3
    5: "持证人 解英朋 登记日期",  # all 3
}
engine3 = SearchEngine()
engine3.set_pdf_engine(MockPdfEngine(pages3))
print(f"\n=== Mixed case ===")
r3 = engine3.search("解英朋")
print(f"search('解英朋'): {len(r3)} results")
for x in r3:
    print(f"  page={x.get('page')} src={x.get('source')}")
