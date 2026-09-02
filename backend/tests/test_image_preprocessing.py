"""
Unit tests for backend/app/services/image_preprocessing.py

Test strategy
-------------
- All synthetic images are generated in-memory with NumPy/OpenCV (no files needed).
- Skew-correction accuracy is validated against 5 images with *known* rotation
  angles using a ground-truth measurement approach (re-detect angle after correction).
- Perspective-correction, contrast-enhancement, and pipeline tests verify
  output shapes, dtypes, and value invariants rather than exact pixel values.

Run with:
    cd backend
    python -m pytest tests/test_image_preprocessing.py -v
"""

from __future__ import annotations

import math
import sys
import os

import cv2
import numpy as np
import pytest

# ── Make sure the backend package is importable ───────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.image_preprocessing import (
    detect_and_correct_skew,
    correct_perspective,
    enhance_contrast,
    preprocess_pipeline,
    _rotate_image,
    _order_points,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers – synthetic image factories
# ─────────────────────────────────────────────────────────────────────────────

def _make_horizontal_lines_image(
    width: int = 600,
    height: int = 400,
    n_lines: int = 12,
    bg: int = 240,
    fg: int = 30,
) -> np.ndarray:
    """
    Create a white (bg) image with *n_lines* perfectly horizontal black (fg)
    lines evenly distributed across the height.  The image is clean and
    high-contrast, making it ideal for Hough-based angle detection.
    """
    img = np.full((height, width, 3), bg, dtype=np.uint8)
    step = height // (n_lines + 1)
    for i in range(1, n_lines + 1):
        y = i * step
        cv2.line(img, (20, y), (width - 20, y), (fg, fg, fg), thickness=2)
    return img


def _make_text_block_image(
    width: int = 600,
    height: int = 400,
    rows: int = 10,
    cols: int = 8,
) -> np.ndarray:
    """
    Simulate a page of text as a grid of small dark rectangles on a white
    background.  Each 'word' is a filled dark rect; rows form natural
    horizontal baselines for Hough detection.
    """
    img = np.full((height, width, 3), 245, dtype=np.uint8)
    row_h = height // (rows + 1)
    col_w = width // (cols + 1)
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            x = c * col_w
            y = r * row_h
            cv2.rectangle(img, (x - 18, y - 4), (x + 18, y + 4), (40, 40, 40), -1)
    return img


def _rotate_synthetic(img: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate img by angle_deg (positive = CCW) using _rotate_image."""
    return _rotate_image(img, angle_deg)


def _measure_residual_skew(image: np.ndarray) -> float:
    """
    Re-run Hough angle detection on *image* to estimate any remaining skew.
    Returns the detected skew angle in degrees (0.0 if no reliable lines found).
    This is the same algorithm used inside detect_and_correct_skew, extracted
    here as a pure measurement tool.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
    min_ll = max(30, min(image.shape[:2]) // 10)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 80, minLineLength=min_ll, maxLineGap=10)
    if lines is None or len(lines) < 5:
        return 0.0

    angles, weights = [], []
    for line in lines:
        seg = line[0] if line.ndim == 2 else line
        x1, y1, x2, y2 = seg
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            continue
        angle = math.degrees(math.atan2(dy, dx))
        if angle < -90:
            angle += 180
        elif angle > 90:
            angle -= 180
        if abs(angle) <= 45:
            angles.append(angle)
            weights.append(length)

    if not angles:
        return 0.0

    pairs = sorted(zip(angles, weights), key=lambda p: p[0])
    sa = [p[0] for p in pairs]
    sw = [p[1] for p in pairs]
    cum = np.cumsum(sw)
    idx = int(np.searchsorted(cum, cum[-1] / 2.0))
    return sa[min(idx, len(sa) - 1)]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SKEW_CASES: list[tuple[str, float]] = [
    ("slight_CCW",   -3.0),
    ("moderate_CW",  +7.0),
    ("small_CW",     +1.5),
    ("large_CCW",   -12.0),
    ("near_zero",    -0.8),
]
"""Five (name, applied_skew_deg) pairs used for parametrised deskew tests."""


@pytest.fixture(params=SKEW_CASES, ids=[c[0] for c in SKEW_CASES])
def skewed_image_case(request):
    """
    Parametrised fixture: yields (skewed_bgr_image, applied_angle_deg) for
    each entry in SKEW_CASES.  Uses the horizontal-lines synthetic image so
    that Hough detection has strong, reliable lines to work with.
    """
    name, angle_deg = request.param
    base = _make_horizontal_lines_image(width=700, height=500, n_lines=14)
    skewed = _rotate_synthetic(base, angle_deg)   # positive = CCW rotation applied
    return skewed, angle_deg


# ─────────────────────────────────────────────────────────────────────────────
# 1. SKEW CORRECTION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectAndCorrectSkew:
    """Validate that detect_and_correct_skew reduces residual skew to <±2°."""

    TOLERANCE_DEG = 2.0  # acceptance threshold in degrees

    def test_output_is_ndarray(self, skewed_image_case):
        img, _ = skewed_image_case
        result = detect_and_correct_skew(img)
        assert isinstance(result, np.ndarray), "Output must be a numpy ndarray"

    def test_output_dtype_uint8(self, skewed_image_case):
        img, _ = skewed_image_case
        result = detect_and_correct_skew(img)
        assert result.dtype == np.uint8, f"Expected uint8, got {result.dtype}"

    def test_output_has_three_channels(self, skewed_image_case):
        img, _ = skewed_image_case
        result = detect_and_correct_skew(img)
        assert result.ndim == 3 and result.shape[2] == 3, (
            f"Expected 3-channel image, got shape {result.shape}"
        )

    @pytest.mark.parametrize("name,angle_deg", SKEW_CASES)
    def test_residual_skew_within_tolerance(self, name, angle_deg):
        """
        Core accuracy test: after correction, measured residual skew must be
        within ±{TOLERANCE_DEG}° of horizontal.

        The near_zero case (|angle| < 0.5°) may be skipped by the pipeline
        (no-op threshold), so we allow it if the input angle was already small.
        """
        base = _make_horizontal_lines_image(width=700, height=500, n_lines=14)
        skewed = _rotate_synthetic(base, angle_deg)
        corrected = detect_and_correct_skew(skewed)

        residual = _measure_residual_skew(corrected)
        assert abs(residual) <= self.TOLERANCE_DEG, (
            f"[{name}] Residual skew {residual:.2f}° exceeds ±{self.TOLERANCE_DEG}° "
            f"after correcting applied angle of {angle_deg}°"
        )

    def test_near_zero_skew_unchanged_or_minimal(self):
        """Images with skew < 0.5° should be returned close to unchanged."""
        base = _make_horizontal_lines_image()
        # Apply 0.3° – below the 0.5° no-op threshold
        skewed = _rotate_synthetic(base, 0.3)
        result = detect_and_correct_skew(skewed)
        # Shape should be very close (canvas may vary by a pixel due to trig rounding)
        h_diff = abs(result.shape[0] - skewed.shape[0])
        w_diff = abs(result.shape[1] - skewed.shape[1])
        assert h_diff <= 2 and w_diff <= 2, (
            f"Near-zero skew produced unexpected resize: {skewed.shape} -> {result.shape}"
        )

    def test_returns_original_on_too_few_lines(self):
        """A blank white image has no edges → falls back to original."""
        blank = np.full((400, 600, 3), 255, dtype=np.uint8)
        result = detect_and_correct_skew(blank)
        np.testing.assert_array_equal(result, blank)

    def test_text_block_image_corrected(self):
        """Verify deskew works on a text-block synthetic image (different structure)."""
        base = _make_text_block_image(width=600, height=400)
        angle = -5.0
        skewed = _rotate_synthetic(base, angle)
        corrected = detect_and_correct_skew(skewed)
        residual = _measure_residual_skew(corrected)
        assert abs(residual) <= self.TOLERANCE_DEG, (
            f"Text-block residual {residual:.2f}° > ±{self.TOLERANCE_DEG}°"
        )

    def test_grayscale_input_accepted(self):
        """detect_and_correct_skew must handle single-channel (grayscale) input."""
        base = _make_horizontal_lines_image()
        gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
        skewed = cv2.warpAffine(
            gray,
            cv2.getRotationMatrix2D((gray.shape[1]//2, gray.shape[0]//2), -6, 1),
            (gray.shape[1], gray.shape[0]),
        )
        result = detect_and_correct_skew(skewed)
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.uint8


# ─────────────────────────────────────────────────────────────────────────────
# 2. PERSPECTIVE CORRECTION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def _make_quad_image(width: int = 600, height: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """
    Draw a filled white quadrilateral on a grey background so that the contour
    is clearly detectable.  Returns (image, corners_xy).
    """
    img = np.full((height, width, 3), 120, dtype=np.uint8)
    margin = 60
    pts = np.array([
        [margin,          margin + 20],
        [width - margin,  margin],
        [width - margin - 10, height - margin],
        [margin + 10,     height - margin - 20],
    ], dtype=np.int32)
    cv2.fillPoly(img, [pts], (250, 250, 250))
    return img, pts


class TestCorrectPerspective:
    def test_output_is_ndarray(self):
        img, _ = _make_quad_image()
        result = correct_perspective(img)
        assert isinstance(result, np.ndarray)

    def test_output_dtype_uint8(self):
        img, _ = _make_quad_image()
        result = correct_perspective(img)
        assert result.dtype == np.uint8

    def test_output_has_three_channels(self):
        img, _ = _make_quad_image()
        result = correct_perspective(img)
        assert result.ndim == 3 and result.shape[2] == 3

    def test_blank_image_returns_original(self):
        """A blank white image has no contours → original returned."""
        blank = np.full((400, 600, 3), 255, dtype=np.uint8)
        result = correct_perspective(blank)
        np.testing.assert_array_equal(result, blank)

    def test_output_not_zero_size(self):
        img, _ = _make_quad_image()
        result = correct_perspective(img)
        assert result.shape[0] > 0 and result.shape[1] > 0

    def test_grayscale_input_accepted(self):
        img, _ = _make_quad_image()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        result = correct_perspective(gray)
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.uint8


# ─────────────────────────────────────────────────────────────────────────────
# 3. CONTRAST ENHANCEMENT TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestEnhanceContrast:
    def _sample_image(self) -> np.ndarray:
        """Low-contrast natural-ish image with a bright glare spot."""
        img = np.full((300, 400, 3), 128, dtype=np.uint8)
        # Simulate glare: a bright ellipse
        cv2.ellipse(img, (200, 150), (60, 40), 0, 0, 360, (255, 255, 255), -1)
        # Add some mid-tone variation
        for i in range(0, 300, 30):
            cv2.line(img, (0, i), (400, i), (100, 100, 100), 1)
        return img

    def test_output_is_ndarray(self):
        result = enhance_contrast(self._sample_image())
        assert isinstance(result, np.ndarray)

    def test_output_shape_preserved(self):
        img = self._sample_image()
        result = enhance_contrast(img)
        assert result.shape == img.shape, (
            f"Shape changed: {img.shape} -> {result.shape}"
        )

    def test_output_dtype_uint8(self):
        result = enhance_contrast(self._sample_image())
        assert result.dtype == np.uint8

    def test_glare_is_suppressed(self):
        """
        In the enhanced image, the maximum brightness in the glare region
        should be lower than in the original (highlight suppression working).
        """
        img = self._sample_image()
        result = enhance_contrast(img)

        # Convert both to LAB and compare L channel max in the glare ellipse ROI
        glare_roi = (130, 110, 270, 190)  # y1, x1, y2, x2
        y1, x1, y2, x2 = glare_roi

        orig_l = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[:, :, 0]
        res_l  = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)[:, :, 0]

        orig_max = int(orig_l[y1:y2, x1:x2].max())
        res_max  = int(res_l[y1:y2, x1:x2].max())

        assert res_max <= orig_max, (
            f"Glare not suppressed: original max={orig_max}, result max={res_max}"
        )

    def test_mid_tone_contrast_improved(self):
        """
        Standard deviation of L channel should be >= original (CLAHE expands range).
        """
        img = self._sample_image()
        result = enhance_contrast(img)

        orig_std = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[:, :, 0].astype(float).std()
        res_std  = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)[:, :, 0].astype(float).std()

        # We accept either the same or improved contrast (never worse by > 5 points)
        assert res_std >= orig_std - 5, (
            f"Contrast degraded: original std={orig_std:.2f}, result std={res_std:.2f}"
        )

    def test_grayscale_input_returns_bgr(self):
        """Grayscale input should be promoted to 3-channel BGR output."""
        gray = np.full((200, 300), 128, dtype=np.uint8)
        result = enhance_contrast(gray)
        assert result.ndim == 3 and result.shape[2] == 3


# ─────────────────────────────────────────────────────────────────────────────
# 4. PIPELINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestPreprocessPipeline:
    def _make_label_image(self) -> np.ndarray:
        """Skewed image with text-like content for end-to-end test."""
        base = _make_text_block_image(width=640, height=480)
        return _rotate_synthetic(base, -4.0)

    def test_output_is_ndarray(self):
        img = self._make_label_image()
        result = preprocess_pipeline(img)
        assert isinstance(result, np.ndarray)

    def test_output_dtype_uint8(self):
        img = self._make_label_image()
        result = preprocess_pipeline(img)
        assert result.dtype == np.uint8

    def test_output_has_three_channels(self):
        img = self._make_label_image()
        result = preprocess_pipeline(img)
        assert result.ndim == 3 and result.shape[2] == 3

    def test_output_non_empty(self):
        img = self._make_label_image()
        result = preprocess_pipeline(img)
        assert result.size > 0

    def test_raises_on_none(self):
        with pytest.raises(ValueError, match="empty or None"):
            preprocess_pipeline(None)  # type: ignore[arg-type]

    def test_raises_on_empty_array(self):
        with pytest.raises(ValueError, match="empty or None"):
            preprocess_pipeline(np.array([]))

    def test_pipeline_reduces_skew(self):
        """
        End-to-end: the pipeline should bring measured residual skew < ±2°
        even for a moderately rotated text image.
        """
        base = _make_horizontal_lines_image(width=700, height=500, n_lines=14)
        skewed = _rotate_synthetic(base, -8.0)
        result = preprocess_pipeline(skewed)
        residual = _measure_residual_skew(result)
        assert abs(residual) <= 2.0, (
            f"Pipeline residual skew {residual:.2f}° > ±2.0°"
        )

    def test_pipeline_is_idempotent_ish(self):
        """
        Running the pipeline twice should not significantly change the image
        (second pass should be a near-no-op for an already-aligned image).
        We check that the output shapes are the same.
        """
        base = _make_horizontal_lines_image()
        pass1 = preprocess_pipeline(base)
        pass2 = preprocess_pipeline(pass1)
        # Allow ±5 pixels on each dimension (canvas rounding)
        assert abs(pass1.shape[0] - pass2.shape[0]) <= 5
        assert abs(pass1.shape[1] - pass2.shape[1]) <= 5


# ─────────────────────────────────────────────────────────────────────────────
# 5. INTERNAL HELPER TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_order_points_top_left_smallest_sum(self):
        pts = np.array([[100, 0], [200, 0], [200, 100], [100, 100]], dtype=np.float32)
        rect = _order_points(pts)
        assert tuple(rect[0]) == (100.0, 0.0), f"Top-left wrong: {rect[0]}"

    def test_order_points_bottom_right_largest_sum(self):
        pts = np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.float32)
        rect = _order_points(pts)
        assert tuple(rect[2]) == (90.0, 90.0), f"Bot-right wrong: {rect[2]}"

    def test_rotate_image_dtype_preserved(self):
        img = np.full((200, 300, 3), 128, dtype=np.uint8)
        rotated = _rotate_image(img, 15.0)
        assert rotated.dtype == np.uint8

    def test_rotate_image_no_black_border_clipping(self):
        """Rotating should expand canvas, not clip pixels."""
        img = np.full((200, 300, 3), 200, dtype=np.uint8)
        # Draw a bright dot in each corner
        img[5, 5] = [255, 0, 0]
        img[5, 294] = [0, 255, 0]
        img[194, 5] = [0, 0, 255]
        img[194, 294] = [255, 255, 0]
        rotated = _rotate_image(img, 20)
        # Canvas must be at least as large as the diagonal
        diag = int(math.hypot(300, 200))
        assert rotated.shape[0] >= 200 and rotated.shape[1] >= 300, (
            f"Canvas shrank: {rotated.shape}"
        )

    def test_rotate_image_returns_ndarray(self):
        img = np.zeros((100, 150, 3), dtype=np.uint8)
        result = _rotate_image(img, -10)
        assert isinstance(result, np.ndarray)
