#!/usr/bin/env python3
"""Patch search_engine.pyc to add cross-page search strategies.
This modifies the compiled bytecode directly."""
import sys, marshal, types, logging, re

# Load original search_engine module
pyc_path = "/tmp/OCRDataExtractor.exe_extracted/PYZ.pyz_extracted/search_engine.pyc"
with open(pyc_path, "rb") as f:
    pyc_data = f.read()

code = marshal.loads(pyc_data[16:])
mod = types.ModuleType("se_src")
mod.re = re
mod.logging = logging
sys.modules["se_src"] = mod
exec(code, mod.__dict__)

OriginalSearchEngine = mod.SearchEngine

print(f"Original class: {OriginalSearchEngine}")
print(f"Original _search_impl: {OriginalSearchEngine._search_impl}")
print(f"Original methods: {[m for m in dir(OriginalSearchEngine) if not m.startswith('_') and not m.startswith('__')]}")

# Now define our monkey-patched methods
def _search_cross_page(self, chinese_chars, page_results):
    """Strategy D: Cross-page fallback."""
    n = len(chinese_chars)
    threshold = max(2, n - 1)
    
    if self.pdf_engine:
        for page_num, text in self.pdf_engine.text_pages.items():
            dp = page_num + 1
            if dp in page_results:
                continue
            matched = sum(1 for c in chinese_chars if c in text)
            if matched >= threshold:
                page_results[dp] = {
                    'page': dp,
                    'text': text[:120].strip().replace('\n', ' '),
                    'source': '文字层(跨页)',
                }

    for page_num, results in self.ocr_results.items():
        dp = page_num + 1
        if dp in page_results:
            continue
        all_txt = ' '.join(r['text'] for r in results)
        matched = sum(1 for c in chinese_chars if c in all_txt)
        if matched >= threshold:
            page_results[dp] = {
                'page': dp,
                'text': all_txt[:120],
                'source': 'OCR(跨页)',
            }

def _search_global_fallback(self, chinese_chars, page_results):
    """Strategy E: Global fallback."""
    n = len(chinese_chars)
    all_text = ''
    if self.pdf_engine:
        all_text += ' '.join(self.pdf_engine.text_pages.values())
    all_text += ' '.join(
        ' '.join(r['text'] for r in results)
        for results in self.ocr_results.values()
    )
    if not all(c in all_text for c in chinese_chars):
        return
    
    if self.pdf_engine:
        for page_num, text in self.pdf_engine.text_pages.items():
            dp = page_num + 1
            if dp in page_results:
                continue
            matched = [c for c in chinese_chars if c in text]
            if matched:
                page_results[dp] = {
                    'page': dp,
                    'text': text[:120].strip().replace('\n', ' '),
                    'source': '文字层(全局)',
                }
    for page_num, results in self.ocr_results.items():
        dp = page_num + 1
        if dp in page_results:
            continue
        all_txt = ' '.join(r['text'] for r in results)
        matched = [c for c in chinese_chars if c in all_txt]
        if matched:
            page_results[dp] = {
                'page': dp,
                'text': all_txt[:120],
                'source': 'OCR(全局)',
            }

# Patch _search_impl to add calls to our new strategies
def patched_search_impl(self, query, case_sensitive):
    """Patched _search_impl with cross-page fallback."""
    # Get the original implementation
    try:
        # Call original logic first via the unbound method
        page_results = {}
        self._original_search_impl_setup(query, case_sensitive, page_results)
        return self._original_search_impl_finish(page_results)
    except AttributeError:
        # Fallback to original
        pass

# Monkey-patch the class
OriginalSearchEngine._search_cross_page = _search_cross_page
OriginalSearchEngine._search_global_fallback = _search_global_fallback

# Patch search method to add cross-page fallback
original_search = OriginalSearchEngine.search

def patched_search(self, query, case_sensitive=False):
    results = original_search(self, query, case_sensitive)
    if results:
        return results
    
    # No results - try cross-page strategies
    if any('\u4e00' <= c <= '\u9fff' for c in query):
        chinese_chars = [c for c in query if '\u4e00' <= c <= '\u9fff']
        if len(chinese_chars) >= 2:
            page_results = {}
            self._search_cross_page(chinese_chars, page_results)
            if not page_results:
                self._search_global_fallback(chinese_chars, page_results)
            if page_results:
                return sorted(page_results.values(), key=lambda x: x.get('page', 0))
    return results

OriginalSearchEngine.search = patched_search

print(f"\nTesting patched SearchEngine...")

# Test
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
                results.append({'page': pn+1, 'text': txt, 'source': '文字层'})
        return results

# Test 1: Normal case
engine = OriginalSearchEngine()
engine.set_pdf_engine(MockPdfEngine({0: "持证人 解英朋 登记日期"}))
r = engine.search("解英朋")
print(f"Test 1 (normal): {len(r)} {'PASS' if len(r) > 0 else 'FAIL'}")

# Test 2: Cross-page case
engine2 = OriginalSearchEngine()
engine2.set_pdf_engine(MockPdfEngine({0: "解 身份证", 1: "英 身份证", 2: "朋 身份证"}))
r2 = engine2.search("解英朋")
print(f"Test 2 (cross-page): {len(r2)} results {'PASS' if len(r2) > 0 else 'FAIL'}")
for x in r2:
    print(f"  page={x.get('page')} src={x.get('source')}")
