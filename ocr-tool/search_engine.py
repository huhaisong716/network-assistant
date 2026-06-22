#!/usr/bin/env python3
"""Search Engine - Unified text search across PDF text layers and OCR results.
Fixed: added Strategy D (cross-page fallback) for multi-char names split across pages.
"""
import re
import logging

logger = logging.getLogger('search_engine')


def _has_chinese(text):
    return any('\u4e00' <= c <= '\u9fff' for c in text)


def _count_chinese_chars(text):
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


class SearchEngine:
    """Search across PDF text layer content and OCR recognition results."""

    def __init__(self, pdf_engine=None):
        self.pdf_engine = pdf_engine
        self.ocr_results = {}

    def set_pdf_engine(self, pdf_engine):
        self.pdf_engine = pdf_engine

    def add_ocr_results(self, page_num, results):
        self.ocr_results[page_num] = results

    def clear_ocr_results(self):
        self.ocr_results.clear()

    def search(self, query, case_sensitive=False):
        try:
            return self._search_impl(query, case_sensitive)
        except Exception as e:
            logger.error(f"search() FAILED for '{query}': {e}", exc_info=True)
            return []

    # ── Core search logic ──────────────────────────────────────

    def _search_impl(self, query, case_sensitive):
        page_results = {}

        # Step 1: Direct query search in text and OCR
        self._search_query(query, case_sensitive, page_results)

        chinese_char_count = 0
        chinese_chars = []

        if _has_chinese(query):
            chinese_char_count = _count_chinese_chars(query)

            if chinese_char_count >= 2:
                chinese_chars = [c for c in query if '\u4e00' <= c <= '\u9fff']

                logger.debug(f"[Multi-char] query='{query}' chinese_chars={chinese_chars}")

                # Strategy X: Flattened OCR - join all text per page, check each char
                self._search_flattened_ocr(chinese_chars, page_results)

                # Strategy C: Char-by-char intersection (ALL must be on same page)
                self._search_char_intersection(chinese_chars, page_results)

                # Pinyin strategies (gracefully skip if pypinyin not installed)
                pinyin_variants = self._safe_pinyin_variants(query)
                if pinyin_variants:
                    for pinyin_list in pinyin_variants:
                        full_pinyin = ''.join(pinyin_list)
                        if len(full_pinyin) >= 2:
                            self._search_query(full_pinyin, False, page_results,
                                               skip_pages=set(page_results.keys()))
                        if len(pinyin_list) >= 2:
                            self._search_syllable_intersection(pinyin_list, page_results)

                single_pinyin = self._safe_single_pinyin(query)
                if single_pinyin and len(single_pinyin) >= 2:
                    self._search_query(single_pinyin, False, page_results,
                                       skip_pages=set(page_results.keys()))

        # Strategy D: Cross-page fallback - chars on different pages
        if not page_results and chinese_char_count >= 2 and chinese_chars:
            self._search_cross_page(chinese_chars, page_results)

        # Strategy E: Global fallback - if chars exist in document but no
        # single page meets the threshold, return ALL pages with any char
        if not page_results and chinese_char_count >= 2 and chinese_chars:
            self._search_global_fallback(chinese_chars, page_results)

        unique_results = sorted(page_results.values(), key=lambda x: x.get('page', 0))
        return unique_results

    # ── Search strategies ──────────────────────────────────────

    def _search_query(self, query, case_sensitive, page_results, skip_pages=None):
        """Search for a single query term in text layers and OCR results."""
        if skip_pages is None:
            skip_pages = set()

        query_variants = [query]

        # For long alpha queries with spaces, generate name variants
        if query.isalpha() and len(query) >= 6 and ' ' in query:
            seen = {query}
            for split_pos in range(3, min(len(query), len(query) - 2)):
                v1 = query[:split_pos] + ' ' + query[split_pos:]
                if v1 not in seen:
                    query_variants.append(v1)
                    seen.add(v1)
                if len(query) > split_pos + 4:
                    for split2 in range(split_pos + 3, min(len(query), len(query))):
                        v2 = v1[:split2 + 1] + ' ' + v1[split2 + 1:]
                        if v2 not in seen:
                            query_variants.append(v2)
                            seen.add(v2)

        for search_query in query_variants:
            search_q = search_query if case_sensitive else search_query.lower()
            exact_match = len(search_q) > 4

            # Search text layers
            if self.pdf_engine:
                text_results = self.pdf_engine.search_text(
                    search_query, case_sensitive, exact_match=exact_match,
                )
                for r in text_results:
                    page = r['page']
                    if page in skip_pages or page in page_results:
                        continue
                    page_results[page] = r
                    skip_pages.add(page)

            # Search OCR results
            for page_num, results in self.ocr_results.items():
                display_page = page_num + 1
                if display_page in skip_pages or display_page in page_results:
                    continue
                for result in results:
                    text = result['text']
                    search_text = text if case_sensitive else text.lower()
                    if search_q in search_text:
                        page_results[display_page] = {
                            'page': display_page,
                            'text': text,
                            'source': 'OCR',
                        }
                        skip_pages.add(display_page)
                        break

    def _search_flattened_ocr(self, chinese_chars, page_results):
        """Strategy X: Join all OCR text per page, check each char individually."""
        query_str = ''.join(chinese_chars)

        # OCR pages
        for page_num in sorted(self.ocr_results.keys()):
            display_page = page_num + 1
            if display_page in page_results:
                continue
            results = self.ocr_results[page_num]
            all_text = ' '.join(r['text'] for r in results)
            if all(c in all_text for c in chinese_chars):
                page_results[display_page] = {
                    'page': display_page,
                    'text': all_text[:120],
                    'source': 'OCR(合并)',
                }
                logger.debug(f'[Strategy X] found page {display_page} for {query_str} in OCR')

        # Text pages
        if self.pdf_engine:
            for page_num, text in self.pdf_engine.text_pages.items():
                display_page = page_num + 1
                if display_page in page_results:
                    continue
                if all(c in text for c in chinese_chars):
                    snippet = text[:120].strip().replace('\n', ' ')
                    page_results[display_page] = {
                        'page': display_page,
                        'text': snippet,
                        'source': '文字层(合并)',
                    }
                    logger.debug(f'[Strategy X] found page {display_page} for {query_str} in text layer')

    def _search_char_intersection(self, chinese_chars, page_results):
        """Strategy C: Search each Chinese char individually, require ALL on same page."""
        if len(chinese_chars) < 2:
            return

        char_pages = {}
        all_indices = set(range(len(chinese_chars)))

        for idx, char in enumerate(chinese_chars):
            # Search text layer
            if self.pdf_engine:
                for r in self.pdf_engine.search_text(char, False, exact_match=False):
                    page = r['page']
                    if page in page_results:
                        continue
                    char_pages.setdefault(page, set()).add(idx)

            # Search OCR
            for page_num, results in self.ocr_results.items():
                display_page = page_num + 1
                if display_page in page_results:
                    continue
                for result in results:
                    if char in result['text']:
                        char_pages.setdefault(display_page, set()).add(idx)
                        break

            logger.debug(f"[Strategy C] char '{char}': {len(char_pages)} pages so far")

        for page, matched_indices in char_pages.items():
            if page in page_results:
                continue
            if all_indices.issubset(matched_indices):
                snippet = ''
                source = '文字交叉'
                if self.pdf_engine and (page - 1) in self.pdf_engine.text_pages:
                    text = self.pdf_engine.text_pages[page - 1]
                    snippet = text[:120].strip().replace('\n', ' ')
                    source = '文字层(交叉)'
                elif (page - 1) in self.ocr_results:
                    texts = [r['text'] for r in self.ocr_results[page - 1]]
                    snippet = ' '.join(texts)[:120]
                    source = 'OCR(交叉)'
                page_results[page] = {'page': page, 'text': snippet, 'source': source}

    def _search_syllable_intersection(self, pinyin_list, page_results):
        """Search each pinyin syllable, only keep pages with ALL syllables."""
        syllable_pages = {}
        min_syllables = 2

        for idx, pinyin in enumerate(pinyin_list):
            if len(pinyin) < 2:
                continue
            pinyin_lower = pinyin.lower()

            # Text layer
            if self.pdf_engine:
                for r in self.pdf_engine.search_text(pinyin, False, exact_match=False):
                    page = r['page']
                    if page in page_results:
                        continue
                    syllable_pages.setdefault(page, set()).add(idx)

            # OCR
            for page_num, results in self.ocr_results.items():
                display_page = page_num + 1
                if display_page in page_results:
                    continue
                for result in results:
                    if pinyin_lower in result['text'].lower():
                        syllable_pages.setdefault(display_page, set()).add(idx)
                        break

        all_indices = set(range(len(pinyin_list)))
        for page, matched in syllable_pages.items():
            if page in page_results:
                continue
            if all_indices.issubset(matched):
                snippet = ''
                source = '拼音交叉'
                if self.pdf_engine and (page - 1) in self.pdf_engine.text_pages:
                    snippet = self.pdf_engine.text_pages[page - 1][:120].strip().replace('\n', ' ')
                    source = '文字层(拼音)'
                elif (page - 1) in self.ocr_results:
                    texts = [r['text'] for r in self.ocr_results[page - 1]]
                    snippet = ' '.join(texts)[:120]
                    source = 'OCR(拼音)'
                page_results[page] = {'page': page, 'text': snippet, 'source': source}

    # ── Strategy D: Cross-page fallback ────────────────────────

    def _search_cross_page(self, chinese_chars, page_results):
        """Strategy D: Cross-page fallback for multi-char names.
        
        When characters are split across different pages (e.g. "解" on page 5, 
        "英朋" on page 6), per-page strategies won't find them.
        
        This checks each page for how many of the query's Chinese characters
        appear, and returns pages with at least (N-1) of N characters matched.
        For a 3-char name, requires at least 2 different chars on the same page.
        """
        n = len(chinese_chars)
        threshold = max(2, n - 1)  # for 3 chars: 2; for 2 chars: 2

        logger.debug(f'[Strategy D] cross-page search for {chinese_chars} (threshold={threshold}/{n})')

        # Check text pages
        if self.pdf_engine:
            for page_num, text in self.pdf_engine.text_pages.items():
                display_page = page_num + 1
                if display_page in page_results:
                    continue
                matched = sum(1 for c in chinese_chars if c in text)
                if matched >= threshold:
                    snippet = text[:120].strip().replace('\n', ' ')
                    page_results[display_page] = {
                        'page': display_page,
                        'text': snippet,
                        'source': f'文字层(跨页)',
                    }
                    logger.debug(f'[Strategy D] page {display_page}: {matched}/{n} chars')

        # Check OCR results
        for page_num, results in self.ocr_results.items():
            display_page = page_num + 1
            if display_page in page_results:
                continue
            all_text = ' '.join(r['text'] for r in results)
            matched = sum(1 for c in chinese_chars if c in all_text)
            if matched >= threshold:
                snippet = all_text[:120]
                page_results[display_page] = {
                    'page': display_page,
                    'text': snippet,
                    'source': 'OCR(跨页)',
                }
                logger.debug(f'[Strategy D] page {display_page}: {matched}/{n} chars')

    # ── Pinyin helpers (graceful fallback if pypinyin not installed) ──

    def _get_pypinyin(self):
        try:
            from pypinyin import lazy_pinyin
            return lazy_pinyin
        except ImportError:
            logger.warning('pypinyin not installed, pinyin search disabled')
            return None

    def _to_pinyin_list(self, text):
        func = self._get_pypinyin()
        if not func:
            return []
        try:
            return [p.lower() for p in func(text)]
        except Exception:
            return []

    def _to_pinyin_variants(self, text):
        """Generate all pinyin combinations for Chinese text (handles 多音字)."""
        func = self._get_pypinyin()
        if not func:
            return []
        try:
            from pypinyin import Style, pinyin as py_pinyin
            import itertools
            char_readings = py_pinyin(text, style=Style.NORMAL, heteronym=True)
            variants = []
            for combo in itertools.product(*char_readings):
                variants.append([c.lower() for c in combo])
            return variants
        except Exception:
            return [self._to_pinyin_list(text)]

    def _safe_pinyin_variants(self, query):
        try:
            return self._to_pinyin_variants(query)
        except Exception:
            return []

    def _safe_single_pinyin(self, query):
        try:
            pl = self._to_pinyin_list(query)
            return ''.join(pl) if pl else ''
        except Exception:
            return ''
