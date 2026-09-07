"""
Image preprocessing service for compliance scanning.

Provides four public functions:
  - detect_and_correct_skew(image)   → deskewed image
  - correct_perspective(image)       → perspective-corrected image
  - enhance_contrast(image)          → CLAHE + glare-suppressed image
  - preprocess_pipeline(image)       → all three in sequence

All functions accept a BGR numpy array (as returned by cv2.imread / cv2.VideoCapture)
and return a BGR numpy array.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _to_gray(image: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale; return as-is if already single-channel."""
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _rotate_image(image: np.ndarray, angle_deg: float) -> np.ndarray:
    """
    Rotate *image* counter-clockwise by *angle_deg* degrees around its centre.
    The canvas is expanded so no pixels are clipped.
    Background is filled with the median border colour to avoid harsh black edges.
    """
    h, w = image.shape[:2]
    cx, cy = w / 2.0, h / 2.0

    rad = math.radians(abs(angle_deg))
    new_w = int(h * math.sin(rad) + w * math.cos(rad))
    new_h = int(h * math.cos(rad) + w * math.sin(rad))

    M = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
    M[0, 2] += (new_w - w) / 2.0
    M[1, 2] += (new_h - h) / 2.0

    border_pixels = np.concatenate([
        image[0, :].reshape(-1, image.shape[2] if image.ndim == 3 else 1),
        image[-1, :].reshape(-1, image.shape[2] if image.ndim == 3 else 1),
        image[:, 0].reshape(-1, image.shape[2] if image.ndim == 3 else 1),
        image[:, -1].reshape(-1, image.shape[2] if image.ndim == 3 else 1),
    ])
    fill_color = tuple(int(v) for v in np.median(border_pixels, axis=0).tolist())

    rotated = cv2.warpAffine(
        image, M, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=fill_color,
    )
    return rotated


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order four corner points as [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def detect_and_correct_skew(image: np.ndarray) -> np.ndarray:
    """
    Detect text/line skew using the Probabilistic Hough Transform and rotate
    the image so that the dominant line orientation is horizontal.

    Algorithm
    ---------
    1. Greyscale -> Gaussian blur -> Canny edge detection.
    2. Probabilistic Hough Line Transform to find line segments.
    3. Compute each segment's angle; weight by segment length.
    4. Weighted-median of near-horizontal angles (-45..+45 deg) gives skew.
    5. Rotate by the negative of the detected skew.

    Parameters
    ----------
    image : np.ndarray
        Input BGR (or grayscale) image.

    Returns
    -------
    np.ndarray
        Deskewed BGR image.  Returns the original image unchanged if fewer
        than 5 line segments are detected.
    """
    gray = _to_gray(image)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, threshold1=50, threshold2=150, apertureSize=3)

    min_line_length = max(30, min(image.shape[:2]) // 10)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=min_line_length,
        maxLineGap=10,
    )

    if lines is None or len(lines) < 5:
        logger.debug(
            "detect_and_correct_skew: too few lines (%s), skipping",
            0 if lines is None else len(lines),
        )
        return image

    angles: list[float] = []
    weights: list[float] = []

    # OpenCV 5 returns (N, 4); earlier versions returned (N, 1, 4)
    for line in lines:
        seg = line[0] if line.ndim == 2 else line
        x1, y1, x2, y2 = seg
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            continue
        angle = math.degrees(math.atan2(dy, dx))

        # Normalise to -90..+90
        if angle < -90:
            angle += 180
        elif angle > 90:
            angle -= 180

        if abs(angle) <= 45:
            angles.append(angle)
            weights.append(length)

    if not angles:
        logger.debug("detect_and_correct_skew: no near-horizontal lines found")
        return image

    # Weighted median (robust against outliers)
    sorted_pairs = sorted(zip(angles, weights), key=lambda p: p[0])
    sorted_angles = [p[0] for p in sorted_pairs]
    sorted_weights = [p[1] for p in sorted_pairs]
    cumulative = np.cumsum(sorted_weights)
    half_total = cumulative[-1] / 2.0
    median_idx = int(np.searchsorted(cumulative, half_total))
    skew_angle = sorted_angles[min(median_idx, len(sorted_angles) - 1)]

    logger.debug("detect_and_correct_skew: detected skew = %.2f deg", skew_angle)

    if abs(skew_angle) < 2.0:
        return image

    # Sign convention: cv2.getRotationMatrix2D positive angle = CCW.
    # If detected skew_angle is +θ (lines slanting up-right), the image was
    # rotated CW by θ.  Passing +skew_angle to _rotate_image applies a CCW
    # rotation of θ, which undoes the original CW skew.
    return _rotate_image(image, skew_angle)


def correct_perspective(image: np.ndarray) -> np.ndarray:
    """
    Detect the largest rectangular contour (product label boundary) and apply
    a perspective (four-point) transform to produce a flat, front-facing view.

    Algorithm
    ---------
    1. Greyscale -> bilateral filter -> adaptive threshold.
    2. Find external contours; approximate each to a polygon.
    3. Select the largest quadrilateral by area.
    4. Four-point perspective warp to an axis-aligned rectangle whose
       dimensions are derived from the max side lengths of the quad.

    Returns the original image unchanged if no suitable quadrilateral is found.

    Parameters
    ----------
    image : np.ndarray
        Input BGR (or grayscale) image.

    Returns
    -------
    np.ndarray
        Perspective-corrected BGR image.
    """
    gray = _to_gray(image)
    filtered = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    thresh = cv2.adaptiveThreshold(
        filtered, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=11, C=2,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.debug("correct_perspective: no contours found, returning original")
        return image

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    image_area = image.shape[0] * image.shape[1]
    best_quad: Optional[np.ndarray] = None

    for cnt in contours[:10]:
        if cv2.contourArea(cnt) < image_area * 0.05:
            break
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            best_quad = approx
            break

    if best_quad is None:
        logger.debug("correct_perspective: no quadrilateral found, returning original")
        return image

    pts = best_quad.reshape(4, 2).astype(np.float32)
    rect = _order_points(pts)
    tl, tr, br, bl = rect

    dst_w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    dst_h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))

    if dst_w < 10 or dst_h < 10:
        return image

    dst = np.array(
        [[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (dst_w, dst_h))

    logger.debug("correct_perspective: warped to %dx%d", dst_w, dst_h)
    return warped


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """
    Improve image contrast for OCR and visual inspection via:

    1. **CLAHE** on the LAB L-channel – adaptive local contrast boost with
       a clip limit that prevents noise amplification.
    2. **Highlight suppression** – pixels whose L value exceeds 230 have
       their excess brightness rolled off (halved), suppressing glare and
       specular reflections.

    Parameters
    ----------
    image : np.ndarray
        Input BGR (or grayscale) image.

    Returns
    -------
    np.ndarray
        Contrast-enhanced BGR image.
    """
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # CLAHE on L channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_clahe = clahe.apply(l_channel)

    # Highlight suppression
    glare_threshold = 230
    l_float = l_clahe.astype(np.float32)
    glare_mask = l_float > glare_threshold
    excess = l_float[glare_mask] - glare_threshold
    l_float[glare_mask] = glare_threshold + excess * 0.4
    l_final = np.clip(l_float, 0, 255).astype(np.uint8)

    lab_enhanced = cv2.merge([l_final, a_channel, b_channel])
    enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    logger.debug("enhance_contrast: CLAHE + highlight suppression applied")
    return enhanced


def preprocess_pipeline(image: np.ndarray) -> np.ndarray:
    """
    Full preprocessing pipeline – runs all three steps in sequence:

      1. detect_and_correct_skew   – straighten rotated text
      2. correct_perspective       – flatten label perspective distortion
      3. enhance_contrast          – CLAHE + glare suppression

    Parameters
    ----------
    image : np.ndarray
        Input BGR (or grayscale) image.

    Returns
    -------
    np.ndarray
        Fully preprocessed BGR image ready for OCR.

    Raises
    ------
    ValueError
        If *image* is None or empty.
    """
    if image is None or image.size == 0:
        raise ValueError("preprocess_pipeline received an empty or None image.")

    logger.info("preprocess_pipeline: starting on shape=%s", image.shape)

    # Resolution normalization for OCR speed/accuracy balance:
    # 1. Downscale oversized images (> 2500px) to prevent memory bottlenecks.
    # 2. Upscale truly low-res images (< 800px) so tiny packaging fonts are readable.
    #    Images 800px–2500px are already at a good resolution; no resizing needed.
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim > 2500:
        scale = 2500.0 / max_dim
        new_w, new_h = int(w * scale), int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.info("preprocess_pipeline: downscaled shape (%d, %d) -> (%d, %d)", h, w, new_h, new_w)
    elif max_dim < 800 and max_dim >= 100:
        scale = min(1600.0 / max_dim, 2.5)
        new_w, new_h = int(w * scale), int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        logger.info("preprocess_pipeline: upscaled shape (%d, %d) -> (%d, %d) for OCR legibility", h, w, new_h, new_w)
    else:
        logger.info("preprocess_pipeline: no resize needed for shape (%d, %d)", h, w)

    step1 = detect_and_correct_skew(image)
    # NOTE: correct_perspective() is intentionally skipped in the default pipeline.
    # It frequently misdetects quadrilaterals and crops text off the image.
    # Gemini Vision AI handles perspective distortion natively.
    # Call correct_perspective() explicitly only when needed.
    step2 = enhance_contrast(step1)

    logger.info("preprocess_pipeline: complete -> shape=%s", step2.shape)
    return step2


def generate_preprocessing_variants(image: np.ndarray) -> dict[str, np.ndarray]:
    if image is None or image.size == 0:
        raise ValueError("generate_preprocessing_variants received empty or None image.")

    h, w = image.shape[:2]
    max_dim = max(h, w)

    # Resolution normalization for optimal OCR glyph height (target approx 25-35px font height)
    if max_dim < 1100:
        scale_factor = min(3.0, 1400.0 / max_dim)
        working_img = cv2.resize(image, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    elif max_dim > 1600:
        scale_factor = 1400.0 / max_dim
        working_img = cv2.resize(image, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA)
    else:
        working_img = image

    variants: dict[str, np.ndarray] = {}

    # 1. CLAHE Grayscale directly from raw working image (preserves delicate font glyphs)
    gray = _to_gray(working_img)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    clahe_gray = clahe.apply(gray)
    variants["clahe_gray"] = clahe_gray

    # 2. Enhanced BGR (contrast + glare roll-off)
    enhanced_bgr = enhance_contrast(working_img)
    variants["enhanced_bgr"] = enhanced_bgr

    # 3. Deskewed orientation variant
    deskewed = detect_and_correct_skew(working_img)
    variants["deskewed"] = deskewed

    # 4. Vertical Text Variant (for statutory dates / batch numbers printed on packaging side flaps)
    rot_270 = cv2.rotate(clahe_gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    variants["vertical_rot270"] = rot_270

    # 4. Adaptive Thresholding (robust against shadows and gradient backgrounds)
    blurred = cv2.GaussianBlur(clahe_gray, (3, 3), 0)
    adaptive_thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=4,
    )
    variants["adaptive_thresh"] = adaptive_thresh

    # 4. Otsu's Bimodal Thresholding
    _, otsu_thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["otsu_thresh"] = otsu_thresh

    # 5. Sharpened (Unsharp Masking for small character edges)
    gaussian = cv2.GaussianBlur(enhanced_bgr, (0, 0), 2.0)
    sharpened = cv2.addWeighted(enhanced_bgr, 1.5, gaussian, -0.5, 0)
    variants["sharpened"] = sharpened

    logger.debug("generate_preprocessing_variants: generated %d variants", len(variants))
    return variants


def detect_text_regions(
    image: np.ndarray,
    min_area: int = 150,
    max_area_ratio: float = 0.95,
) -> list[list[int]]:
    """
    Dynamically discover text-dense candidate regions on arbitrary packaging using
    morphological gradient and horizontal connected-component clustering.

    Zero fixed crops or hardcoded coordinates.

    Parameters:
    -----------
    image : np.ndarray
        Input BGR or grayscale image.
    min_area : int
        Minimum contour area to consider (filters out specks / noise).
    max_area_ratio : float
        Maximum fraction of total image area (filters out whole-image border box).

    Returns:
    --------
    list[list[int]]
        List of [x, y, w, h] bounding rectangles for detected text regions.
    """
    if image is None or image.size == 0:
        return []

    h_img, w_img = image.shape[:2]
    total_area = h_img * w_img
    gray = _to_gray(image)

    # 1. Morphological Gradient to highlight character strokes
    kernel_grad = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel_grad)

    # 2. Binarize gradient using Otsu
    _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3. Connect horizontally adjacent characters into words / lines (25x3 kernel)
    kernel_horiz = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_horiz)

    # 4. Find external contours
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[list[int]] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        # Filter noise and huge bounding boxes
        if area < min_area:
            continue
        if area > total_area * max_area_ratio:
            continue
        if w < 12 or h < 6:
            continue

        # Add small padding to avoid clipping character strokes
        pad_x = int(w * 0.05)
        pad_y = int(h * 0.05)
        x_pad = max(0, x - pad_x)
        y_pad = max(0, y - pad_y)
        w_pad = min(w_img - x_pad, w + 2 * pad_x)
        h_pad = min(h_img - y_pad, h + 2 * pad_y)

        boxes.append([x_pad, y_pad, w_pad, h_pad])

    # 5. Sort regions top-to-bottom, left-to-right
    boxes.sort(key=lambda b: (b[1], b[0]))
    logger.debug("detect_text_regions: discovered %d text regions", len(boxes))
    return boxes


def preprocess_pipeline(image: np.ndarray) -> np.ndarray:
    """
    Full preprocessing pipeline – runs all three steps in sequence:

      1. detect_and_correct_skew   – straighten rotated text
      2. correct_perspective       – flatten label perspective distortion
      3. enhance_contrast          – CLAHE + glare suppression

    Parameters
    ----------
    image : np.ndarray
        Input BGR (or grayscale) image.

    Returns
    -------
    np.ndarray
        Fully preprocessed BGR image ready for OCR.

    Raises
    ------
    ValueError
        If *image* is None or empty.
    """
    if image is None or image.size == 0:
        raise ValueError("preprocess_pipeline received an empty or None image.")

    logger.info("preprocess_pipeline: starting on shape=%s", image.shape)

    # Downscale oversized images (max dimension > 1600px) for high-performance OCR
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim > 1600:
        scale = 1600.0 / max_dim
        new_w, new_h = int(w * scale), int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.info("preprocess_pipeline: resized shape (%d, %d) -> (%d, %d)", h, w, new_h, new_w)

    step1 = detect_and_correct_skew(image)
    step2 = correct_perspective(step1)
    step3 = enhance_contrast(step2)

    logger.info("preprocess_pipeline: complete -> shape=%s", step3.shape)
    return step3
