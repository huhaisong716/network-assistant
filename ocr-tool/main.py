#!/usr/bin/env python3
"""OCR资料提取 v3.0 - Entry point with patched search engine"""
import os
import sys
import marshal
import types

# Ensure we can find our modules
_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _base_dir)

# ── Patch SearchEngine with cross-page strategies ────────────
import search_engine
from search_engine import SearchEngine

def _search_cross_page(self, chinese_chars, page_results):
    n = len(chinese_chars)
    threshold = max(2, n - 1)
    
    if self.pdf_engine:
        for pn, txt in self.pdf_engine.text_pages.items():
            dp = pn + 1
            if dp in page_results:
                continue
            matched = sum(1 for c in chinese_chars if c in txt)
            if matched >= threshold:
                page_results[dp] = {
                    'page': dp,
                    'text': txt[:120].strip().replace('\n', ' '),
                    'source': '文字层(跨页)',
                }

    for pn, results in self.ocr_results.items():
        dp = pn + 1
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
        for pn, txt in self.pdf_engine.text_pages.items():
            dp = pn + 1
            if dp in page_results:
                continue
            matched = [c for c in chinese_chars if c in txt]
            if matched:
                page_results[dp] = {
                    'page': dp,
                    'text': txt[:120].strip().replace('\n', ' '),
                    'source': '文字层(全局)',
                }
    for pn, results in self.ocr_results.items():
        dp = pn + 1
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

original_search = SearchEngine.search

def patched_search(self, query, case_sensitive=False):
    results = original_search(self, query, case_sensitive)
    if results:
        return results
    
    # Cross-page fallback
    if any('\u4e00' <= c <= '\u9fff' for c in query):
        chars = [c for c in query if '\u4e00' <= c <= '\u9fff']
        if len(chars) >= 2:
            pr = {}
            _search_cross_page(self, chars, pr)
            if not pr:
                _search_global_fallback(self, chars, pr)
            if pr:
                return sorted(pr.values(), key=lambda x: x.get('page', 0))
    return results

SearchEngine._search_cross_page = _search_cross_page
SearchEngine._search_global_fallback = _search_global_fallback
SearchEngine.search = patched_search

# ── Now run the original app ────────────────────────────────
# Load and exec the original app.pyc bytecode
app_pyc = os.path.join(_base_dir, 'app.pyc')
if os.path.exists(app_pyc):
    with open(app_pyc, 'rb') as f:
        raw = f.read()
    app_code = marshal.loads(raw[16:])
    
    # Create module context
    app_mod = types.ModuleType('__main__')
    app_mod.__file__ = os.path.join(_base_dir, 'app.py')
    app_mod.__package__ = ''
    sys.modules['__main__'] = app_mod
    
    ns = app_mod.__dict__
    ns['__file__'] = os.path.join(_base_dir, 'app.py')
    ns['__name__'] = '__main__'
    exec(app_code, ns)
else:
    print("Error: app.pyc not found in", _base_dir)
    sys.exit(1)
