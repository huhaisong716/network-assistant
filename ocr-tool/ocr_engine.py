#!/usr/bin/env python3
"""OCR Engine - Wraps rapidocr_onnxruntime for text recognition.
Compatible with original app.pyc: supports both v6 and v3/v4 modes.
"""
import os
import sys
import time
import logging
import numpy as np

logger = logging.getLogger('ocr_engine')

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None
    logger.warning("rapidocr_onnxruntime not installed")


class OCREngine:
    """OCR Engine supporting rapidocr_onnxruntime.
    
    Compatible with app.pyc's two calling conventions:
    - v6 mode: recognize(img) -> (results_list, elapsed_seconds)
    - legacy mode: __call__(img) -> raw_rapidocr_result
    
    Each result dict: {'text': str, 'box': list, 'confidence': float}
    """

    def __init__(self, models_dir=None):
        self.engine = None
        self._ready = False
        if models_dir:
            self._init_engine(models_dir)

    def _init_engine(self, models_dir=None):
        """Initialize the OCR engine.
        
        Args:
            models_dir: Optional path (ignored for default init, 
                        included for API compatibility with original app.pyc).
        """
        try:
            if RapidOCR is not None:
                self.engine = RapidOCR()
                self._ready = True
                logger.info("OCR Engine v6 initialized")
            else:
                logger.error("rapidocr_onnxruntime not available")
        except Exception as e:
            logger.error(f"Failed to init OCR engine: {e}")
            self._ready = False

    def is_ready(self):
        return self._ready

    def recognize(self, img):
        """Compatible with app.pyc's v6 mode.
        
        Returns: (results_list, elapsed_seconds)
        Each result: {'text': str, 'box': list, 'confidence': float}
        
        If engine not ready, returns ([], 0.0)
        """
        start = time.time()
        if not self._ready or self.engine is None:
            return ([], 0.0)

        try:
            result = self.engine(img)
            elapsed = time.time() - start

            results = []
            if result is None:
                return (results, elapsed)

            # rapidocr returns: (boxes, texts, scores) tuple
            if isinstance(result, tuple) and len(result) >= 2:
                boxes, texts, scores = result[0] if len(result) >= 1 else [], result[1], result[2] if len(result) >= 3 else []
                if texts:
                    for i, text_item in enumerate(texts):
                        text = str(text_item[0]) if isinstance(text_item, (list, tuple)) else str(text_item)
                        if not text.strip():
                            continue
                        box = boxes[i] if i < len(boxes) else []
                        confidence = float(scores[i]) if i < len(scores) else 1.0
                        results.append({
                            'text': text,
                            'box': box,
                            'confidence': confidence,
                        })
            elif isinstance(result, list):
                # List of (bbox, text, score) items
                for item in result:
                    if isinstance(item, (list, tuple)):
                        box = item[0] if len(item) >= 1 else []
                        text = str(item[1]) if len(item) >= 2 and isinstance(item[1], str) else str(item[1]) if len(item) >= 2 else ''
                        confidence = float(item[2]) if len(item) >= 3 else 1.0
                        if text.strip():
                            results.append({
                                'text': text,
                                'box': box,
                                'confidence': confidence,
                            })
            return (results, elapsed)
        except Exception as e:
            logger.error(f"OCR recognize error: {e}")
            return ([], time.time() - start)

    def __call__(self, img):
        """Compatible with app.pyc's legacy mode (non-v6).
        
        Returns raw rapidocr result format for the app.pyc's own processing.
        """
        if not self._ready or self.engine is None:
            return None
        try:
            return self.engine(img)
        except Exception as e:
            logger.error(f"OCR __call__ error: {e}")
            return None
