"""
Tests for backend/app/services/genai_extraction.py

Tests cover:
- crop_image_region boundary, padding, and edge cases
- extract_field_via_genai with mock extractor, NOT_FOUND handling, and response cleaning
- merge_ocr_and_genai_results merging high-conf OCR, low-conf OCR, and GenAI fallback
- Summary stats calculation (fields_found, fields_missing, method_breakdown)

Run with:
    cd backend
    python -m pytest tests/test_genai_extraction.py -v
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.genai_extraction import (
    crop_image_region,
    extract_field_via_genai,
    merge_ocr_and_genai_results,
    DEFAULT_MANDATORY_FIELDS,
)


def _sample_image(height=400, width=600) -> np.ndarray:
    return np.full((height, width, 3), 200, dtype=np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Image Cropping Helper Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCropImageRegion:
    def test_valid_crop_with_padding(self):
        img = _sample_image(height=400, width=600)
        bbox = [100, 100, 200, 100]  # x, y, w, h
        crop = crop_image_region(img, bbox, padding=10)
        # expected x1=90, y1=90, x2=310, y2=210 -> height=120, width=220
        assert crop.shape == (120, 220, 3)

    def test_crop_at_image_boundaries(self):
        img = _sample_image(height=400, width=600)
        bbox = [0, 0, 50, 50]
        crop = crop_image_region(img, bbox, padding=20)
        # x1=0, y1=0, x2=70, y2=70 -> height=70, width=70
        assert crop.shape == (70, 70, 3)

    def test_none_bbox_returns_full_image(self):
        img = _sample_image(height=200, width=300)
        crop = crop_image_region(img, None)
        assert crop.shape == img.shape

    def test_invalid_bbox_returns_full_image(self):
        img = _sample_image(height=200, width=300)
        crop = crop_image_region(img, [10, 10, -5, 0])
        assert crop.shape == img.shape

    def test_raises_on_empty_image(self):
        with pytest.raises(ValueError, match="empty or None"):
            crop_image_region(None, [10, 10, 50, 50])


# ─────────────────────────────────────────────────────────────────────────────
# 2. GenAI Field Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractFieldViaGenai:
    def test_mock_successful_extraction(self):
        img = _sample_image()

        def mock_extractor(field_name: str, crop: np.ndarray) -> str:
            if field_name == "mrp":
                return "Rs. 199.00"
            return "NOT_FOUND"

        res = extract_field_via_genai(
            image=img,
            field_name="mrp",
            bbox=[50, 50, 100, 30],
            mock_fn=mock_extractor,
        )

        assert res["field_name"] == "mrp"
        assert res["extracted_value"] == "Rs. 199.00"
        assert res["extraction_method"] == "genai_fallback"
        assert res["confidence"] > 0.0

    def test_mock_not_found_extraction(self):
        img = _sample_image()

        def mock_extractor(field_name: str, crop: np.ndarray) -> str:
            return "NOT_FOUND"

        res = extract_field_via_genai(
            image=img,
            field_name="country_of_origin",
            mock_fn=mock_extractor,
        )

        assert res["field_name"] == "country_of_origin"
        assert res["extracted_value"] is None
        assert res["extraction_method"] == "genai_fallback"
        assert res["confidence"] == 0.0

    def test_markdown_and_quote_cleaning(self):
        img = _sample_image()

        def mock_extractor(field_name: str, crop: np.ndarray) -> str:
            return "```text\n\"Net Wt. 250g\"\n```"

        res = extract_field_via_genai(
            image=img,
            field_name="net_quantity",
            mock_fn=mock_extractor,
        )

        assert res["extracted_value"] == "Net Wt. 250g"

    def test_raises_on_empty_image(self):
        with pytest.raises(ValueError, match="empty or None"):
            extract_field_via_genai(
                image=np.array([]),
                field_name="mrp",
                mock_fn=lambda f, c: "NOT_FOUND",
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Unified Merger Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeOcrAndGenaiResults:
    def test_high_confidence_ocr_mapped(self):
        img = _sample_image()
        classified = [
            {
                "text": "MRP Rs. 120.00",
                "bbox": [10, 40, 80, 20],
                "confidence": 0.95,
                "engine_used": "tesseract",
                "field": "mrp",
                "match_confidence": 0.95,
                "pattern_matched": "mrp_explicit_label",
            },
            {
                "text": "Net Wt 500g",
                "bbox": [10, 10, 100, 20],
                "confidence": 0.88,
                "engine_used": "easyocr",
                "field": "net_quantity",
                "match_confidence": 0.92,
                "pattern_matched": "net_qty_wt_volume",
            },
        ]
        unmatched = []

        def mock_genai(field_name: str, crop: np.ndarray) -> str:
            return "NOT_FOUND"

        res = merge_ocr_and_genai_results(
            image=img,
            classified_blocks=classified,
            unmatched_blocks=unmatched,
            mock_fn=mock_genai,
        )

        fields = res["fields"]
        assert fields["mrp"]["extraction_method"] == "ocr_tesseract"
        assert fields["mrp"]["extracted_value"] == "MRP Rs. 120.00"

        assert fields["net_quantity"]["extraction_method"] == "ocr_easyocr"
        assert fields["net_quantity"]["extracted_value"] in ["Net Wt 500g", "Net Wt. 500g"]

    def test_genai_fallback_triggered_for_missing_field(self):
        img = _sample_image()
        classified = []
        unmatched = []

        def mock_genai(field_name: str, crop: np.ndarray) -> str:
            if field_name == "manufacture_date":
                return "Mfg Date: 01/2026"
            return "NOT_FOUND"

        res = merge_ocr_and_genai_results(
            image=img,
            classified_blocks=classified,
            unmatched_blocks=unmatched,
            mock_fn=mock_genai,
        )

        fields = res["fields"]
        assert fields["manufacture_date"]["extraction_method"] == "genai_fallback"
        assert fields["manufacture_date"]["extracted_value"] == "Mfg Date: 01/2026"

        assert fields["mrp"]["extraction_method"] == "not_found"
        assert fields["mrp"]["extracted_value"] is None

    def test_genai_fallback_triggered_for_low_confidence_ocr(self):
        img = _sample_image()
        classified = [
            {
                "text": "India",
                "bbox": [5, 5, 40, 15],
                "confidence": 0.50,
                "engine_used": "tesseract",
                "field": "country_of_origin",
                "match_confidence": 0.55,  # low confidence (< 0.60)
                "pattern_matched": "india_keyword",
            }
        ]
        unmatched = []

        def mock_genai(field_name: str, crop: np.ndarray) -> str:
            if field_name == "country_of_origin":
                return "Country of Origin: India"
            return "NOT_FOUND"

        res = merge_ocr_and_genai_results(
            image=img,
            classified_blocks=classified,
            unmatched_blocks=unmatched,
            mock_fn=mock_genai,
        )

        fields = res["fields"]
        assert fields["country_of_origin"]["extraction_method"] == "genai_fallback"
        assert fields["country_of_origin"]["extracted_value"] == "Country of Origin: India"

    def test_summary_calculation(self):
        img = _sample_image()
        classified = [
            {
                "text": "MRP Rs. 120.00",
                "bbox": [10, 40, 80, 20],
                "confidence": 0.95,
                "engine_used": "tesseract",
                "field": "mrp",
                "match_confidence": 0.95,
                "pattern_matched": "mrp_explicit_label",
            }
        ]

        def mock_genai(field_name: str, crop: np.ndarray) -> str:
            if field_name == "net_quantity":
                return "500g"
            return "NOT_FOUND"

        res = merge_ocr_and_genai_results(
            image=img,
            classified_blocks=classified,
            unmatched_blocks=[],
            mock_fn=mock_genai,
        )

        summary = res["summary"]
        assert summary["total_fields"] == len(DEFAULT_MANDATORY_FIELDS)
        assert summary["fields_found"] == 2
        assert summary["fields_missing"] == len(DEFAULT_MANDATORY_FIELDS) - 2
        assert summary["method_breakdown"]["ocr_tesseract"] == 1
        assert summary["method_breakdown"]["genai_fallback"] == 1
        assert summary["method_breakdown"]["not_found"] == len(DEFAULT_MANDATORY_FIELDS) - 2
