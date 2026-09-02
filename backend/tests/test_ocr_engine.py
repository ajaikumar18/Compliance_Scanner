"""
Tests for backend/app/services/ocr_engine.py

Strategy
--------
- All Tesseract and EasyOCR calls are mocked so the tests run without any
  binary/GPU dependency.
- Geometry helpers (_iou, _quad_to_xywh, _order_points) are tested directly.
- Merge logic is tested with synthetic OcrBlock lists.
- run_ocr() is tested via mocks to verify routing and fallback behaviour.

Run with:
    cd backend
    python -m pytest tests/test_ocr_engine.py -v
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.ocr_engine import (
    OcrBlock,
    _iou,
    _quad_to_xywh,
    _merge_blocks,
    _run_tesseract,
    _run_easyocr,
    run_ocr,
    MIN_CONFIDENCE,
    IOU_MERGE_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _blk(text="hello", bbox=None, conf=0.90, engine="tesseract") -> OcrBlock:
    return OcrBlock(
        text=text,
        bbox=bbox or [10, 10, 100, 20],
        confidence=conf,
        engine_used=engine,
    )


def _dummy_image(h=100, w=200) -> np.ndarray:
    return np.full((h, w, 3), 200, dtype=np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestIou:
    def test_identical_boxes_iou_is_1(self):
        b = [10, 10, 100, 50]
        assert abs(_iou(b, b) - 1.0) < 1e-6

    def test_non_overlapping_iou_is_0(self):
        a = [0, 0, 50, 50]
        b = [60, 60, 50, 50]
        assert _iou(a, b) == 0.0

    def test_half_overlap(self):
        a = [0, 0, 100, 100]
        b = [50, 0, 100, 100]   # shifted right by 50px
        iou = _iou(a, b)
        # Intersection = 50*100 = 5000; Union = 10000+10000-5000 = 15000
        assert abs(iou - 5000 / 15000) < 1e-4

    def test_contained_box(self):
        outer = [0, 0, 200, 200]
        inner = [50, 50, 50, 50]
        iou = _iou(outer, inner)
        # inner fully inside outer; iou = 2500 / 40000
        assert 0.0 < iou < 1.0

    def test_zero_width_box_returns_0(self):
        a = [10, 10, 0, 50]   # zero width
        b = [10, 10, 50, 50]
        assert _iou(a, b) == 0.0

    def test_symmetry(self):
        a = [0, 0, 80, 40]
        b = [20, 10, 80, 40]
        assert abs(_iou(a, b) - _iou(b, a)) < 1e-9


class TestQuadToXywh:
    def test_axis_aligned_quad(self):
        quad = [[10, 20], [110, 20], [110, 60], [10, 60]]
        result = _quad_to_xywh(quad)
        assert result == [10, 20, 100, 40]

    def test_slightly_skewed_quad(self):
        quad = [[8, 18], [112, 20], [110, 62], [12, 60]]
        result = _quad_to_xywh(quad)
        assert result[0] == 8   # min x
        assert result[1] == 18  # min y
        assert result[2] == 112 - 8    # width
        assert result[3] == 62  - 18   # height

    def test_output_is_ints(self):
        quad = [[0.5, 1.2], [100.7, 1.2], [100.7, 51.3], [0.5, 51.3]]
        result = _quad_to_xywh(quad)
        assert all(isinstance(v, int) for v in result)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Merge logic
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeBlocks:
    def test_high_iou_keeps_higher_confidence(self):
        """Two overlapping boxes → winner is the one with higher confidence."""
        tess = [_blk("hello", [10, 10, 100, 20], conf=0.70, engine="tesseract")]
        easy = [_blk("Hello", [10, 10, 100, 20], conf=0.90, engine="easyocr")]
        merged = _merge_blocks(tess, easy, iou_threshold=0.35)
        assert len(merged) == 1
        assert merged[0]["engine_used"] == "easyocr|merged"
        assert merged[0]["text"] == "Hello"

    def test_high_iou_tess_wins_when_higher_conf(self):
        tess = [_blk("MRP 99", [0, 0, 150, 30], conf=0.95, engine="tesseract")]
        easy = [_blk("MRP 99", [0, 0, 150, 30], conf=0.80, engine="easyocr")]
        merged = _merge_blocks(tess, easy, iou_threshold=0.35)
        assert merged[0]["engine_used"] == "tesseract|merged"

    def test_non_overlapping_blocks_kept_separately(self):
        tess = [_blk("Net Wt", [0, 0, 80, 20], engine="tesseract")]
        easy = [_blk("500g",   [200, 0, 80, 20], engine="easyocr")]
        merged = _merge_blocks(tess, easy, iou_threshold=0.35)
        assert len(merged) == 2
        engines = {b["engine_used"] for b in merged}
        assert "tesseract" in engines
        assert "easyocr" in engines

    def test_empty_tess_returns_easy_blocks(self):
        easy = [_blk("hello", engine="easyocr"), _blk("world", engine="easyocr")]
        merged = _merge_blocks([], easy, iou_threshold=0.35)
        assert len(merged) == 2

    def test_empty_easy_returns_tess_blocks(self):
        tess = [_blk("hello", engine="tesseract")]
        merged = _merge_blocks(tess, [], iou_threshold=0.35)
        assert len(merged) == 1
        assert merged[0]["engine_used"] == "tesseract"

    def test_both_empty_returns_empty(self):
        assert _merge_blocks([], []) == []

    def test_sorted_top_to_bottom(self):
        tess = [_blk("bottom", [0, 200, 80, 20], engine="tesseract")]
        easy = [_blk("top",    [0, 10,  80, 20], engine="easyocr")]
        merged = _merge_blocks(tess, easy)
        assert merged[0]["text"] == "top"
        assert merged[1]["text"] == "bottom"

    def test_each_tess_block_matched_at_most_once(self):
        """Two EasyOCR blocks both overlapping a single Tesseract block."""
        tess = [_blk("abc", [0, 0, 200, 40], engine="tesseract")]
        easy = [
            _blk("abc", [0, 0, 200, 40], conf=0.80, engine="easyocr"),
            _blk("abc", [0, 0, 200, 40], conf=0.70, engine="easyocr"),
        ]
        merged = _merge_blocks(tess, easy)
        # First easyocr block matches (higher conf), second becomes unmatched
        assert len(merged) == 2

    def test_output_dtypes(self):
        tess = [_blk()]
        easy = [_blk(engine="easyocr")]
        merged = _merge_blocks(tess, easy)
        for block in merged:
            assert isinstance(block["text"], str)
            assert isinstance(block["bbox"], list)
            assert isinstance(block["confidence"], float)
            assert isinstance(block["engine_used"], str)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tesseract runner (mocked)
# ─────────────────────────────────────────────────────────────────────────────

_TESS_DATA_FIXTURE = {
    "text":  ["", "Net Wt", "500g",  "MRP", "Rs.99", ""],
    "conf":  [-1,  85,       78,      92,    90,      -1],
    "left":  [ 0,  10,       80,      10,    50,       0],
    "top":   [ 0,  10,       10,      40,    40,       0],
    "width": [ 0,  60,       40,      30,    50,       0],
    "height":[ 0,  20,       20,      20,    20,       0],
}


class TestRunTesseract:
    @patch("app.services.ocr_engine.cv2.cvtColor", return_value=np.zeros((100, 200, 3), dtype=np.uint8))
    def test_returns_ocr_blocks_on_success(self, mock_cvt):
        import pytesseract
        with patch.object(pytesseract, "image_to_data", return_value=_TESS_DATA_FIXTURE):
            result = _run_tesseract(_dummy_image())

        assert isinstance(result, list)
        assert all("text" in b and "bbox" in b for b in result)

    @patch("app.services.ocr_engine.cv2.cvtColor", return_value=np.zeros((100, 200, 3), dtype=np.uint8))
    def test_filters_empty_text(self, mock_cvt):
        import pytesseract
        with patch.object(pytesseract, "image_to_data", return_value=_TESS_DATA_FIXTURE):
            result = _run_tesseract(_dummy_image())
        texts = [b["text"] for b in result]
        assert "" not in texts

    @patch("app.services.ocr_engine.cv2.cvtColor", return_value=np.zeros((100, 200, 3), dtype=np.uint8))
    def test_filters_low_confidence(self, mock_cvt):
        import pytesseract
        low_conf_data = dict(_TESS_DATA_FIXTURE)
        low_conf_data["conf"] = [-1, 5, 8, 3, 2, -1]  # all below MIN_CONFIDENCE*100
        with patch.object(pytesseract, "image_to_data", return_value=low_conf_data):
            result = _run_tesseract(_dummy_image())
        assert result == []

    @patch("app.services.ocr_engine.cv2.cvtColor", return_value=np.zeros((100, 200, 3), dtype=np.uint8))
    def test_confidence_normalised_0_to_1(self, mock_cvt):
        import pytesseract
        with patch.object(pytesseract, "image_to_data", return_value=_TESS_DATA_FIXTURE):
            result = _run_tesseract(_dummy_image())
        for block in result:
            assert 0.0 <= block["confidence"] <= 1.0

    @patch("app.services.ocr_engine.cv2.cvtColor", return_value=np.zeros((100, 200, 3), dtype=np.uint8))
    def test_engine_label_is_tesseract(self, mock_cvt):
        import pytesseract
        with patch.object(pytesseract, "image_to_data", return_value=_TESS_DATA_FIXTURE):
            result = _run_tesseract(_dummy_image())
        assert all(b["engine_used"] == "tesseract" for b in result)

    def test_returns_empty_on_not_found(self):
        import pytesseract
        with patch.object(
            pytesseract, "image_to_data",
            side_effect=pytesseract.TesseractNotFoundError,
        ):
            result = _run_tesseract(_dummy_image())
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. EasyOCR runner (mocked)
# ─────────────────────────────────────────────────────────────────────────────

_EASY_RESULTS_FIXTURE = [
    ([[10, 10], [110, 10], [110, 30], [10, 30]], "Net Wt", 0.88),
    ([[80, 10], [120, 10], [120, 30], [80, 30]], "500g",   0.82),
    ([[10, 40], [60, 40], [60, 60],  [10, 60]], "MRP",    0.91),
    ([[50, 40], [100, 40], [100, 60], [50, 60]], "Rs.99", 0.89),
]


class TestRunEasyOcr:
    def _mock_reader(self, results):
        reader = MagicMock()
        reader.readtext.return_value = results
        return reader

    def test_returns_ocr_blocks(self):
        with patch("app.services.ocr_engine._get_easyocr_reader",
                   return_value=self._mock_reader(_EASY_RESULTS_FIXTURE)):
            result = _run_easyocr(_dummy_image(), ("en",))

        assert isinstance(result, list)
        assert len(result) == len(_EASY_RESULTS_FIXTURE)

    def test_bbox_is_xywh(self):
        with patch("app.services.ocr_engine._get_easyocr_reader",
                   return_value=self._mock_reader(_EASY_RESULTS_FIXTURE)):
            result = _run_easyocr(_dummy_image(), ("en",))

        for block in result:
            assert len(block["bbox"]) == 4
            x, y, w, h = block["bbox"]
            assert w > 0 and h > 0

    def test_confidence_is_float(self):
        with patch("app.services.ocr_engine._get_easyocr_reader",
                   return_value=self._mock_reader(_EASY_RESULTS_FIXTURE)):
            result = _run_easyocr(_dummy_image(), ("en",))
        assert all(isinstance(b["confidence"], float) for b in result)

    def test_engine_label_is_easyocr(self):
        with patch("app.services.ocr_engine._get_easyocr_reader",
                   return_value=self._mock_reader(_EASY_RESULTS_FIXTURE)):
            result = _run_easyocr(_dummy_image(), ("en",))
        assert all(b["engine_used"] == "easyocr" for b in result)

    def test_filters_low_confidence(self):
        low_conf = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "junk", 0.05),
        ]
        with patch("app.services.ocr_engine._get_easyocr_reader",
                   return_value=self._mock_reader(low_conf)):
            result = _run_easyocr(_dummy_image(), ("en",))
        assert result == []

    def test_returns_empty_on_reader_failure(self):
        with patch("app.services.ocr_engine._get_easyocr_reader",
                   side_effect=RuntimeError("no model")):
            result = _run_easyocr(_dummy_image(), ("en",))
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# 5. Public run_ocr() integration (mocked engines)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunOcr:
    def _tess_blocks(self):
        return [_blk("MRP Rs.99", [10, 40, 80, 20], conf=0.88)]

    def _easy_blocks(self):
        return [_blk("Net Wt 500g", [10, 10, 100, 20], conf=0.91, engine="easyocr")]

    def test_raises_on_none_image(self):
        with pytest.raises(ValueError, match="empty or None"):
            run_ocr(None)  # type: ignore[arg-type]

    def test_raises_on_empty_image(self):
        with pytest.raises(ValueError, match="empty or None"):
            run_ocr(np.array([]))

    def test_returns_list(self):
        with (
            patch("app.services.ocr_engine._run_tesseract", return_value=self._tess_blocks()),
            patch("app.services.ocr_engine._run_easyocr", return_value=self._easy_blocks()),
        ):
            result = run_ocr(_dummy_image())
        assert isinstance(result, list)

    def test_merged_when_both_engines_run(self):
        with (
            patch("app.services.ocr_engine._run_tesseract", return_value=self._tess_blocks()),
            patch("app.services.ocr_engine._run_easyocr", return_value=self._easy_blocks()),
        ):
            result = run_ocr(_dummy_image())
        # Non-overlapping → 2 blocks
        assert len(result) == 2

    def test_only_tess_when_easyocr_disabled(self):
        with patch("app.services.ocr_engine._run_tesseract", return_value=self._tess_blocks()):
            result = run_ocr(_dummy_image(), use_easyocr=False)
        assert all(b["engine_used"] == "tesseract" for b in result)

    def test_only_easy_when_tesseract_disabled(self):
        with patch("app.services.ocr_engine._run_easyocr", return_value=self._easy_blocks()):
            result = run_ocr(_dummy_image(), use_tesseract=False)
        assert all(b["engine_used"] == "easyocr" for b in result)

    def test_output_schema(self):
        with (
            patch("app.services.ocr_engine._run_tesseract", return_value=self._tess_blocks()),
            patch("app.services.ocr_engine._run_easyocr", return_value=[]),
        ):
            result = run_ocr(_dummy_image())
        for block in result:
            assert "text" in block
            assert "bbox" in block
            assert "confidence" in block
            assert "engine_used" in block
            assert len(block["bbox"]) == 4
            assert 0.0 <= block["confidence"] <= 1.0

    def test_both_engines_disabled_returns_empty(self):
        result = run_ocr(_dummy_image(), use_tesseract=False, use_easyocr=False)
        assert result == []

    def test_default_language_is_english(self):
        captured = {}

        def fake_easy(image, lang_tuple):
            captured["lang"] = lang_tuple
            return []

        with (
            patch("app.services.ocr_engine._run_tesseract", return_value=[]),
            patch("app.services.ocr_engine._run_easyocr", side_effect=fake_easy),
        ):
            run_ocr(_dummy_image())

        assert captured["lang"] == ("en",)
