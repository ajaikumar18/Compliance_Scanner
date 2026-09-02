"""
Tests for backend/app/services/font_size_analyzer.py

Tests cover:
- calibrate_scale via Hough circle detection on synthetic images
- calibrate_scale via manual package width input
- calibrate_scale fallback to default 300 DPI
- measure_text_height pixel-to-mm conversions
- check_font_compliance with Legal Metrology Net Quantity rules (50g, 200g, 1000g, >1kg)
- tolerance_note format and measurement uncertainty acknowledgment

Run with:
    cd backend
    python -m pytest tests/test_font_size_analyzer.py -v
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.font_size_analyzer import (
    calibrate_scale,
    measure_text_height,
    check_font_compliance,
    load_font_size_rules,
)


def _make_circle_image(width: int = 400, height: int = 400, radius: int = 50) -> np.ndarray:
    """Create a synthetic image with a clear circular object in the center."""
    img = np.full((height, width, 3), 240, dtype=np.uint8)
    cv2.circle(img, (width // 2, height // 2), radius, (30, 30, 30), -1)
    return img


def _make_blank_image(width: int = 400, height: int = 400) -> np.ndarray:
    """Create a blank synthetic image with no circles."""
    return np.full((height, width, 3), 240, dtype=np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Scale Calibration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibrateScale:
    def test_hough_circle_detection_calibration(self):
        # Draw circle of radius 50px (diameter = 100px)
        img = _make_circle_image(width=500, height=500, radius=50)
        # reference diameter = 25.0 mm -> expected scale = 100 / 25 = 4.0 px/mm
        res = calibrate_scale(img, reference_object_diameter_mm=25.0)

        assert res["calibration_method"] == "hough_circle_reference"
        assert res["detected_circle"] is not None
        assert abs(res["pixels_per_mm"] - 4.0) < 0.35
        assert "tolerance" in res["tolerance_note"].lower()

    def test_manual_package_width_calibration(self):
        # Image width 600px, package_width_mm = 150mm -> expected 4.0 px/mm
        img = _make_blank_image(width=600, height=400)
        res = calibrate_scale(img, package_width_mm=150.0)

        assert res["calibration_method"] == "manual_package_width"
        assert res["pixels_per_mm"] == 4.0
        assert res["detected_circle"] is None
        assert "tolerance" in res["tolerance_note"].lower()

    def test_fallback_uncalibrated_default_dpi(self):
        img = _make_blank_image(width=400, height=400)
        res = calibrate_scale(img)

        assert res["calibration_method"] == "uncalibrated_default_dpi"
        assert res["pixels_per_mm"] > 0
        assert "uncalibrated" in res["tolerance_note"].lower()

    def test_raises_on_empty_image(self):
        with pytest.raises(ValueError, match="empty or None"):
            calibrate_scale(np.array([]))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Text Height Measurement Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMeasureTextHeight:
    def test_valid_height_conversion(self):
        # Bbox height = 20px, pixels_per_mm = 4.0 -> expected 5.0 mm
        bbox = [10, 20, 100, 20]
        h_mm = measure_text_height(bbox, pixels_per_mm=4.0)
        assert h_mm == 5.0

    def test_rounds_to_two_decimal_places(self):
        bbox = [0, 0, 50, 15]
        # 15 / 4.0 = 3.75
        h_mm = measure_text_height(bbox, pixels_per_mm=4.0)
        assert h_mm == 3.75

    def test_raises_on_invalid_pixels_per_mm(self):
        with pytest.raises(ValueError, match="positive"):
            measure_text_height([0, 0, 10, 10], pixels_per_mm=0.0)

    def test_raises_on_invalid_bbox(self):
        with pytest.raises(ValueError, match="4-element bbox"):
            measure_text_height([0, 0, 10], pixels_per_mm=4.0)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Compliance Checking Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckFontCompliance:
    def test_net_qty_under_50g_rule(self):
        # Rule: <= 50g requires min 1.5mm
        res = check_font_compliance("net_quantity", measured_height_mm=2.0, net_quantity_g=40.0)
        assert res["required_mm"] == 1.5
        assert res["compliant"] is True

    def test_net_qty_50g_to_200g_rule(self):
        # Rule: 50g-200g requires min 2.0mm
        res_pass = check_font_compliance("net_quantity", measured_height_mm=2.5, net_quantity_g=150.0)
        assert res_pass["required_mm"] == 2.0
        assert res_pass["compliant"] is True

        res_fail = check_font_compliance("net_quantity", measured_height_mm=1.2, net_quantity_g=150.0)
        assert res_fail["required_mm"] == 2.0
        assert res_fail["compliant"] is False

    def test_net_qty_200g_to_1000g_rule(self):
        # Rule: 200g-1000g requires min 4.0mm
        res = check_font_compliance("net_quantity", measured_height_mm=3.5, net_quantity_g=500.0)
        assert res["required_mm"] == 4.0
        assert res["compliant"] is False

    def test_net_qty_over_1kg_rule(self):
        # Rule: > 1kg requires min 6.0mm
        res = check_font_compliance("net_quantity", measured_height_mm=6.5, net_quantity_g=1500.0)
        assert res["required_mm"] == 6.0
        assert res["compliant"] is True

    def test_general_field_default_rule(self):
        res = check_font_compliance("mrp", measured_height_mm=2.5)
        assert res["required_mm"] == 2.0
        assert res["compliant"] is True

    def test_tolerance_note_includes_uncertainty(self):
        res = check_font_compliance(
            "mrp",
            measured_height_mm=2.5,
            calibration_method="hough_circle_reference",
        )
        assert "tolerance" in res["tolerance_note"].lower()
        assert "2.50mm" in res["tolerance_note"]
        assert "2.0mm" in res["tolerance_note"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Rules Config Loader Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadRules:
    def test_load_font_size_rules(self):
        rules = load_font_size_rules()
        assert "net_quantity_rules" in rules
        assert "general_declaration_rules" in rules
        assert isinstance(rules["net_quantity_rules"], list)
