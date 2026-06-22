#!/usr/bin/env python3
"""OCR Engine - Wraps rapidocr_onnxruntime for text recognition."""
import os
import sys
import time
import logging
import numpy as np

logger = logging.getLogger('ocr_engine')

# Import rapidocr components
try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None
    logger.warning("rapidocr_onnxruntime not installed")


class OCREngine:
    """OCR Engine using rapidocr_onnxruntime with optimized inference."""

    def __init__(self, model_dir=None):
        self.engine = None
        self._ready = False
        if model_dir:
            self._init_engine(model_dir)

    def _init_engine(self, model_dir=None):
        """Initialize the OCR engine."""
        try:
            if RapidOCR is not None:
                self.engine = RapidOCR()
                self._ready = True
                logger.info("OCR Engine initialized")
            else:
                logger.error("rapidocr_onnxruntime not available")
        except Exception as e:
            logger.error(f"Failed to init OCR engine: {e}")
            self._ready = False

    def is_ready(self):
        return self._ready

    def recognize(self, img):
        """Recognize text from an image (numpy array or PIL Image).
        
        Returns list of dicts with 'text' key.
        """
        if not self._ready or self.engine is None:
            return []

        try:
            result = self.engine(img)
            if result is None:
                return []
            
            # rapidocr returns: (boxes, texts, scores) or list of (bbox, text, score)
            results = []
            if isinstance(result, tuple) and len(result) >= 2:
                boxes, texts = result[0], result[1]
                if texts:
                    for text_item in texts:
                        if isinstance(text_item, (list, tuple)):
                            text = text_item[0] if len(text_item) > 0 else str(text_item)
                        else:
                            text = str(text_item)
                        results.append({'text': text})
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        text = item[1] if isinstance(item[1], str) else str(item[1])
                        results.append({'text': text})
            
            return results
        except Exception as e:
            logger.error(f"OCR recognition error: {e}")
            return []


# Quick test if run directly
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    import numpy as np
    from PIL import Image
    
    engine = OCREngine()
    print(f"Engine ready: {engine.is_ready()}")
    
    if engine.is_ready():
        # Test with blank image
        test_img = Image.new('RGB', (100, 30), color='white')
        import PIL.ImageDraw as ImageDraw
        import PIL.ImageFont as ImageFont
        draw = ImageDraw.Draw(test_img)
        
        # Try to load a font
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, 14)
        else:
            font = None
        
        draw.text((5, 5), "Hello OCR", fill='black', font=font)
        
        img_array = np.array(test_img)
        results = engine.recognize(img_array)
        print(f"OCR Results: {results}")
