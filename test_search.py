#!/usr/bin/env python3
"""Test the search engine with simulated data to find the bug"""
import sys
sys.path.insert(0, '/home/dytc/network-assistant')
from search_engine_recon import SearchEngine, _has_chinese, _count_chinese_chars

# Mock pdf_engine that simulates text layer
class MockPdfEngine:
    def __init__(self, text_pages=None):
        self.text_pages = text_pages or {}
    
    def search_text(self, query, case_sensitive=False, exact_match=False):
        """Simulate text layer search"""
        results = []
        search_q = query if case_sensitive else query.lower()
        for page_num, text in self.text_pages.items():
            search_text = text if case_sensitive else text.lower()
            found = search_q in search_text
            if found:
                idx = search_text.find(search_q)
                start = max(0, idx - 20)
                end = min(len(text), idx + len(search_q) + 20)
                snippet = text[start:end].strip().replace('\n', ' ')
                results.append({
                    'page': page_num + 1,
                    'text': snippet,
                    'source': '文字层',
                })
        return results

# Test with actual data pattern from the user's screenshots
# Text pages: 293 pages with text, 4 image pages without
# When searching 解, 21 results from text layer
text_pages = {}
for i in range(293):
    if i in [18, 20, 24, 30, 35, 40, 45, 50, 55, 60,  # pages 19,21,25,31,36,41,46,51,56,61
             65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 200]:
        text_pages[i] = f"持证人 解英朋 登记日期 2021年02月20日 结婚证字号 J371123 这是测试文本第{i+1}页"
    else:
        text_pages[i] = f"这是普通的测试文本第{i+1}页 不包含搜索内容"

# Test OCR results - 4 pages were OCR'd
ocr_results = {}
for i in range(293, 297):
    ocr_results[i] = [
        {'text': f'居民身份证 姓名 解英朋 性别 男 民族 汉 出生 1990年'},
        {'text': f'住址 北京市朝阳区 公民身份号码 11010819900101XXXX'},
    ]

engine = SearchEngine()
engine.set_pdf_engine(MockPdfEngine(text_pages))

# Test 1: Single character search
print("=" * 60)
print("TEST 1: Single character search '解'")
results1 = engine.search("解", case_sensitive=False)
print(f"  Found {len(results1)} results")
for r in results1[:5]:
    print(f"  Page {r['page']}: {r['source']}")

# Test 2: Full name search
print("\n" + "=" * 60)
print("TEST 2: Full name search '解英朋'")
results2 = engine.search("解英朋", case_sensitive=False)
print(f"  Found {len(results2)} results")
for r in results2[:5]:
    print(f"  Page {r['page']}: {r['source']}")

# Test 3: Check _has_chinese and _count_chinese_chars
print("\n" + "=" * 60)
print("TEST 3: Chinese character detection")
print(f"  _has_chinese('解英朋'): {_has_chinese('解英朋')}")
print(f"  _count_chinese_chars('解英朋'): {_count_chinese_chars('解英朋')}")

# Test 4: Direct Strategy X test
print("\n" + "=" * 60)
print("TEST 4: Direct _search_flattened_ocr")
page_results = {}
engine._search_flattened_ocr(['解', '英', '朋'], page_results)
print(f"  Strategy X found {len(page_results)} pages")
for p, r in page_results.items():
    print(f"  Page {p}: {r['source']}")

# Test 5: Direct _search_char_intersection test
print("\n" + "=" * 60)
print("TEST 5: Direct _search_char_intersection")
page_results2 = {}
engine._search_char_intersection(['解', '英', '朋'], page_results2)
print(f"  Strategy C found {len(page_results2)} pages")
for p, r in page_results2.items():
    print(f"  Page {p}: {r['source']}")
