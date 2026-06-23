#!/usr/bin/env python3
"""Reconstruct pdf_engine.py - PDF engine with text extraction and search"""
import os
import fitz  # PyMuPDF
import logging

logger = logging.getLogger('pdf_engine')


class PdfEngine:
    """PDF Engine - PyMuPDF wrapper for PDF loading and text extraction."""

    def __init__(self):
        self.doc = None
        self.text_pages = {}  # page_num (0-idx) -> text
        self.image_pages = set()
        self._page_count = 0

    @property
    def page_count(self):
        return self._page_count

    def load(self, path):
        """Load a PDF file."""
        self.close()
        self.doc = fitz.open(path)
        self._page_count = len(self.doc)

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
        self.text_pages = {}
        self.image_pages = set()
        self._page_count = 0

    def scan_text_pages(self):
        """Extract text from all pages, identify image-only pages."""
        if not self.doc:
            return
        for i in range(len(self.doc)):
            page = self.doc[i]
            text = page.get_text('text')
            if text.strip():
                self.text_pages[i] = text
            else:
                # Check if page has images
                images = page.get_images()
                if images:
                    self.image_pages.add(i)

    def get_page_text(self, page_num):
        """Get raw text for a single page."""
        if not self.doc:
            return ''
        page = self.doc[page_num]
        return page.get_text('text')

    def render_page(self, page_num, dpi=200):
        """Render page as PNG bytes."""
        if not self.doc:
            return b''
        page = self.doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes('png')

    def render_page_pil(self, page_num, dpi=200):
        """Render page as PIL Image."""
        from PIL import Image
        import io
        if not self.doc:
            return None
        img_data = self.render_page(page_num, dpi)
        return Image.open(io.BytesIO(img_data))

    def export_pages(self, page_nums, dpi=200):
        """Export specific pages as PNG bytes list."""
        return [self.render_page(p, dpi) for p in page_nums]

    def search_text(self, query, case_sensitive=False, exact_match=False):
        """Search for text in all pages.
        
        Args:
            query: Search string
            case_sensitive: Case sensitivity
            exact_match: If True and query > 3 chars, require word-boundary match.
                         Prevents short substrings from matching longer words.
        """
        import re
        results = []

        for page_num, text in self.text_pages.items():
            search_text = text if case_sensitive else text.lower()
            search_query = query if case_sensitive else query.lower()
            found = False

            if exact_match and len(search_query) > 3:
                pattern = re.compile(re.escape(search_query))
                if pattern.search(search_text):
                    found = True
                else:
                    # Try with spaces between chars (e.g. "wangjing" -> "wang jing")
                    spaced = re.sub(r'(.{2,}?)', r'\1 ', search_query).strip()
                    if spaced != search_query and spaced in search_text:
                        found = True
            else:
                found = search_query in search_text

            if not found:
                continue

            # Extract snippet around match
            idx = search_text.find(search_query)
            if idx == -1:
                if ' ' in search_query:
                    idx = search_text.find(search_query.split()[0])
                else:
                    idx = 0

            start = max(0, idx - 30)
            end = min(len(search_text), idx + len(search_query) + 30)
            snippet = text[start:end].strip().replace('\n', ' ')

            results.append({
                'page': page_num + 1,
                'text': snippet,
                'source': '文字层',
            })

        return results
