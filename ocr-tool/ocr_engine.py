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
        """Initialize the OCR engine with optional custom model path.
        
        Args:
            models_dir: Path to directory containing ONNX model files.
                        If provided, RapidOCR is configured to use these models.
                        The directory should contain:
                        - ch_PP-OCRv4_det_infer.onnx (or v6 equivalent)
                        - ch_PP-OCRv4_rec_infer.onnx
                        - ch_ppocr_mobile_v2.0_cls_infer.onnx
        """
        try:
            if RapidOCR is None:
                logger.error("rapidocr_onnxruntime not available")
                return

            if models_dir and os.path.isdir(models_dir):
                # Check if the directory has actual ONNX models
                onnx_files = [f for f in os.listdir(models_dir) if f.endswith('.onnx')]
                if onnx_files:
                    logger.info(f"Using custom models from: {models_dir} ({len(onnx_files)} files)")
                    # Create a custom config pointing to this model dir
                    import tempfile
                    import yaml
                    config = {
                        'Global': {
                            'text_score': 0.5, 'use_det': True, 'use_cls': True, 'use_rec': True,
                            'print_verbose': False, 'min_height': 30, 'width_height_ratio': 8,
                            'max_side_len': 2000, 'min_side_len': 30, 'return_word_box': False,
                        },
                        'Det': {
                            'model_path': os.path.join(models_dir, 'ch_PP-OCRv4_det_infer.onnx'),
                            'limit_side_len': 736, 'limit_type': 'min',
                            'std': [0.5, 0.5, 0.5], 'mean': [0.5, 0.5, 0.5],
                            'thresh': 0.3, 'box_thresh': 0.5, 'max_candidates': 1000,
                            'unclip_ratio': 1.6, 'use_dilation': True, 'score_mode': 'fast',
                        },
                        'Cls': {
                            'model_path': os.path.join(models_dir, 'ch_ppocr_mobile_v2.0_cls_infer.onnx'),
                            'cls_image_shape': [3, 48, 192], 'cls_batch_num': 6,
                            'cls_thresh': 0.9, 'label_list': ['0', '180'],
                        },
                        'Rec': {
                            'model_path': os.path.join(models_dir, 'ch_PP-OCRv4_rec_infer.onnx'),
                            'rec_img_shape': [3, 48, 320], 'rec_batch_num': 6,
                        },
                    }
                    # Try to detect actual model names in the directory
                    for fn in onnx_files:
                        fn_lower = fn.lower()
                        if 'det' in fn_lower:
                            config['Det']['model_path'] = os.path.join(models_dir, fn)
                        elif 'rec' in fn_lower:
                            config['Rec']['model_path'] = os.path.join(models_dir, fn)
                        elif 'cls' in fn_lower:
                            config['Cls']['model_path'] = os.path.join(models_dir, fn)
                    
                    config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
                    yaml.dump(config, config_file)
                    config_file.close()
                    
                    self.engine = RapidOCR(config_path=config_file.name)
                    os.unlink(config_file.name)  # Clean up - RapidOCR already loaded models
                    self._ready = True
                    logger.info(f"OCR Engine v6 initialized with custom models from {models_dir}")
                else:
                    logger.warning(f"No ONNX models found in {models_dir}, using defaults")
                    self.engine = RapidOCR()
                    self._ready = True
            else:
                self.engine = RapidOCR()
                self._ready = True
                logger.info("OCR Engine initialized (default models)")
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
