"""
Font Size Analyzer & Scale Calibration Service
===============================================
Measures font height on product labels in real-world millimeters and checks
compliance against Legal Metrology (Packaged Commodities) Rules.

Public API
----------
    calibrate_scale(image, reference_object_diameter_mm=None, package_width_mm=None) -> ScaleCalibrationResult
    measure_text_height(bbox, pixels_per_mm) -> float
    check_font_compliance(field_name, measured_height_mm, net_quantity_g=None, package_width_mm=None, calibration_method="uncalibrated") -> FontComplianceResult
    load_font_size_rules() -> dict

Output Structures
-----------------
    ScaleCalibrationResult:
        pixels_per_mm:       float
        calibration_method:  "hough_circle_reference" | "manual_package_width" | "uncalibrated_default_dpi"
        detected_circle:     dict[str, float] | None
        tolerance_note:      str

    FontComplianceResult:
        field_name:          str
        compliant:           bool
        measured_mm:         float
        required_mm:         float
        tolerance_note:      str
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TypedDict

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Path to rules JSON config file
_RULES_JSON_PATH = Path(__file__).resolve().parent.parent / "core" / "font_size_rules.json"

# Default fallback rules (if JSON file is missing)
DEFAULT_FONT_SIZE_RULES = {
    "net_quantity_rules": [
        {"min_net_quantity_g": 0, "max_net_quantity_g": 50, "min_font_height_mm": 1.5},
        {"min_net_quantity_g": 50, "max_net_quantity_g": 200, "min_font_height_mm": 2.0},
        {"min_net_quantity_g": 200, "max_net_quantity_g": 1000, "min_font_height_mm": 4.0},
        {"min_net_quantity_g": 1000, "max_net_quantity_g": None, "min_font_height_mm": 6.0},
    ],
    "general_declaration_rules": [
        {"min_panel_area_cm2": 0, "max_panel_area_cm2": 100, "min_font_height_mm": 1.0},
        {"min_panel_area_cm2": 100, "max_panel_area_cm2": 500, "min_font_height_mm": 2.0},
        {"min_panel_area_cm2": 500, "max_panel_area_cm2": 2500, "min_font_height_mm": 4.0},
        {"min_panel_area_cm2": 2500, "max_panel_area_cm2": None, "min_font_height_mm": 6.0},
    ],
    "default_min_font_height_mm": 2.0,
}

# Standard 300 DPI scale factor (300 dots per 25.4 mm = ~11.81 pixels/mm)
DEFAULT_300_DPI_PIXELS_PER_MM = 300.0 / 25.4


# ─────────────────────────────────────────────────────────────────────────────
# TypedDict Definitions
# ─────────────────────────────────────────────────────────────────────────────

class ScaleCalibrationResult(TypedDict):
    pixels_per_mm: float
    calibration_method: str  # "hough_circle_reference" | "manual_package_width" | "uncalibrated_default_dpi"
    detected_circle: dict[str, float] | None  # {"center_x": ..., "center_y": ..., "radius_px": ..., "diameter_px": ...}
    tolerance_note: str


class FontComplianceResult(TypedDict):
    field_name: str
    compliant: bool
    measured_mm: float
    required_mm: float
    tolerance_note: str


# ─────────────────────────────────────────────────────────────────────────────
# Config Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_font_size_rules() -> dict[str, Any]:
    """Load font size rules from font_size_rules.json or fallback to defaults."""
    if _RULES_JSON_PATH.exists():
        try:
            with open(_RULES_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not read %s: %s; using default rules", _RULES_JSON_PATH, exc)
    return DEFAULT_FONT_SIZE_RULES


# ─────────────────────────────────────────────────────────────────────────────
# 1. Scale Calibration
# ─────────────────────────────────────────────────────────────────────────────

def calibrate_scale(
    image: np.ndarray,
    reference_object_diameter_mm: float | None = None,
    package_width_mm: float | None = None,
) -> ScaleCalibrationResult:
    """
    Calibrate pixel-to-millimeter scale factor for a product image.

    Strategy
    --------
    1. Primary method: Detect circular reference object (e.g. coin) using Hough Circle
       Detection. If found and reference_object_diameter_mm > 0, compute scale:
           pixels_per_mm = diameter_pixels / reference_object_diameter_mm
    2. Alternative method: If no circle detected (or reference size not given), use
       manual package_width_mm:
           pixels_per_mm = image_width_pixels / package_width_mm
    3. Fallback method: Default to standard 300 DPI scale assumption (~11.81 px/mm).

    Parameters
    ----------
    image : np.ndarray
        Input BGR or greyscale image array.
    reference_object_diameter_mm : float | None
        Known diameter of circular reference object in mm (e.g. 24.26mm for Rs 5 coin).
    package_width_mm : float | None
        Known real-world width of the product package in mm.

    Returns
    -------
    ScaleCalibrationResult
        {
            "pixels_per_mm": float,
            "calibration_method": "hough_circle_reference" | "manual_package_width" | "uncalibrated_default_dpi",
            "detected_circle": dict | None,
            "tolerance_note": str
        }
    """
    if image is None or image.size == 0:
        raise ValueError("calibrate_scale received an empty or None image.")

    h_img, w_img = image.shape[:2]

    # Convert to greyscale if 3-channel
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    blurred = cv2.medianBlur(gray, 5)

    # Attempt Hough Circle Detection
    circles = None
    try:
        min_dim = min(h_img, w_img)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min_dim // 8 if min_dim >= 8 else 10,
            param1=50,
            param2=30,
            minRadius=max(10, min_dim // 40),
            maxRadius=min_dim // 2,
        )
    except Exception as exc:
        logger.debug("Hough Circle Detection failed: %s", exc)

    # Primary Method: Hough Circle Reference
    if circles is not None and len(circles) > 0 and reference_object_diameter_mm and reference_object_diameter_mm > 0:
        # Pick circle with largest radius / highest confidence
        best_circle = max(circles[0], key=lambda c: c[2])
        cx, cy, radius = float(best_circle[0]), float(best_circle[1]), float(best_circle[2])
        diameter_px = radius * 2.0

        if diameter_px > 0:
            pixels_per_mm = diameter_px / reference_object_diameter_mm
            circle_info = {
                "center_x": round(cx, 1),
                "center_y": round(cy, 1),
                "radius_px": round(radius, 1),
                "diameter_px": round(diameter_px, 1),
            }
            tolerance_note = (
                f"+/-0.2mm estimated tolerance based on circular reference object calibration "
                f"(detected diameter={diameter_px:.1f}px for {reference_object_diameter_mm:.1f}mm object)"
            )
            logger.info("Scale calibrated via Hough Circle: %.2f px/mm", pixels_per_mm)
            return ScaleCalibrationResult(
                pixels_per_mm=round(pixels_per_mm, 4),
                calibration_method="hough_circle_reference",
                detected_circle=circle_info,
                tolerance_note=tolerance_note,
            )

    # Alternative Method: Manual Package Width
    if package_width_mm and package_width_mm > 0:
        pixels_per_mm = w_img / package_width_mm
        tolerance_note = (
            f"+/-0.3mm estimated tolerance based on manual package width calibration "
            f"({w_img}px width for {package_width_mm:.1f}mm package)"
        )
        logger.info("Scale calibrated via package width: %.2f px/mm", pixels_per_mm)
        return ScaleCalibrationResult(
            pixels_per_mm=round(pixels_per_mm, 4),
            calibration_method="manual_package_width",
            detected_circle=None,
            tolerance_note=tolerance_note,
        )

    # Fallback Method: Default 300 DPI
    pixels_per_mm = DEFAULT_300_DPI_PIXELS_PER_MM
    tolerance_note = (
        "+/-0.5mm estimated tolerance due to uncalibrated default 300 DPI scale assumption"
    )
    logger.info("Scale uncalibrated – using default 300 DPI (%.2f px/mm)", pixels_per_mm)
    return ScaleCalibrationResult(
        pixels_per_mm=round(pixels_per_mm, 4),
        calibration_method="uncalibrated_default_dpi",
        detected_circle=None,
        tolerance_note=tolerance_note,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Measure Text Height
# ─────────────────────────────────────────────────────────────────────────────

def measure_text_height(
    bbox: list[int] | tuple[int, int, int, int],
    pixels_per_mm: float,
) -> float:
    """
    Convert a text bounding box's pixel height to real-world millimeters.

    Parameters
    ----------
    bbox : list[int] | tuple[int, int, int, int]
        [x, y, w, h] bounding box.
    pixels_per_mm : float
        Scale factor in pixels per millimeter (> 0).

    Returns
    -------
    float
        Measured font height in millimeters rounded to 2 decimal places.

    Raises
    ------
    ValueError
        If bbox format is invalid or pixels_per_mm <= 0.
    """
    if not bbox or len(bbox) != 4:
        raise ValueError("measure_text_height requires a 4-element bbox [x, y, w, h].")

    if pixels_per_mm <= 0:
        raise ValueError("pixels_per_mm must be positive.")

    h_pixels = bbox[3]
    if h_pixels <= 0:
        return 0.0

    height_mm = h_pixels / pixels_per_mm
    return round(height_mm, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Check Font Compliance
# ─────────────────────────────────────────────────────────────────────────────

def check_font_compliance(
    field_name: str,
    measured_height_mm: float,
    net_quantity_g: float | None = None,
    package_width_mm: float | None = None,
    calibration_method: str = "uncalibrated",
) -> FontComplianceResult:
    """
    Check measured font height against minimum requirements defined in Legal
    Metrology (Packaged Commodities) Rules based on package size / net quantity.

    Parameters
    ----------
    field_name : str
        Name of the field (e.g. 'net_quantity', 'mrp', 'manufacture_date').
    measured_height_mm : float
        Measured font height in mm.
    net_quantity_g : float | None
        Package net quantity in grams/milliliters (if known).
    package_width_mm : float | None
        Package width in mm (if known).
    calibration_method : str
        Calibration method used ("hough_circle_reference", "manual_package_width", etc.)
        used to format appropriate measurement uncertainty tolerance note.

    Returns
    -------
    FontComplianceResult
        {
            "field_name": field_name,
            "compliant": bool,
            "measured_mm": float,
            "required_mm": float,
            "tolerance_note": str
        }
    """
    rules = load_font_size_rules()
    required_mm = rules.get("default_min_font_height_mm", 2.0)

    field_clean = field_name.lower()

    # Rule lookup based on Net Quantity
    if field_clean == "net_quantity" and net_quantity_g is not None and net_quantity_g >= 0:
        net_rules = rules.get("net_quantity_rules", [])
        for rule in net_rules:
            max_g = rule.get("max_net_quantity_g")
            min_g = rule.get("min_net_quantity_g", 0)
            if max_g is None or (min_g <= net_quantity_g <= max_g):
                required_mm = rule.get("min_font_height_mm", 2.0)
                break
    elif package_width_mm and package_width_mm > 0:
        # Estimate display area from package_width_mm (assuming 1:1.5 height aspect ratio)
        estimated_area_cm2 = (package_width_mm * (package_width_mm * 1.5)) / 100.0
        gen_rules = rules.get("general_declaration_rules", [])
        for rule in gen_rules:
            max_area = rule.get("max_panel_area_cm2")
            min_area = rule.get("min_panel_area_cm2", 0)
            if max_area is None or (min_area <= estimated_area_cm2 <= max_area):
                required_mm = rule.get("min_font_height_mm", 2.0)
                break

    # Compliance determination
    compliant = measured_height_mm >= required_mm

    # Measurement uncertainty tolerance note as requested
    if "hough_circle" in calibration_method:
        tol_str = "+/-0.2mm estimated tolerance due to circular reference calibration"
    elif "manual" in calibration_method:
        tol_str = "+/-0.3mm estimated tolerance due to manual package width calibration"
    else:
        tol_str = "+/-0.5mm estimated tolerance due to uncalibrated default DPI scale assumption"

    tolerance_note = (
        f"{tol_str} (measured {measured_height_mm:.2f}mm vs required {required_mm:.1f}mm)"
    )

    return FontComplianceResult(
        field_name=field_name,
        compliant=compliant,
        measured_mm=round(measured_height_mm, 2),
        required_mm=round(required_mm, 2),
        tolerance_note=tolerance_note,
    )
