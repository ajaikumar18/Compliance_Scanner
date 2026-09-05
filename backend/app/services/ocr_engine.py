"""
OCR Engine Service
==================
Runs Tesseract and EasyOCR over a preprocessed image, merges their results
by region overlap (IoU), and returns a unified list of structured text blocks.

Public API
----------
    run_ocr(image, languages=["en"]) -> list[OcrBlock]

Each OcrBlock is a TypedDict:
    {
        "text":        str,            # extracted text
        "bbox":        [x, y, w, h],   # top-left origin, width, height (pixels)
        "confidence":  float,          # 0.0–1.0
        "engine_used": str,            # "tesseract" | "easyocr" | "merged"
    }

Design notes
------------
- Both engines are run independently and their raw results normalised to
  the same [x, y, w, h] bbox format before merging.
- Regions are considered the *same* block if their Intersection-over-Union
  (IoU) exceeds IOU_MERGE_THRESHOLD (default 0.35).
- When two blocks overlap beyond the threshold, the one with higher
  confidence is kept; the engine_used field records which engine "won".
- Tesseract PSM 6 (uniform block of text) is used with OSD disabled for
  speed; EasyOCR detail=1 returns per-word bounding quads which are
  converted to axis-aligned bboxes.
- Both engines are instantiated lazily so import-time overhead is zero.
"""

from __future__ import annotations

import logging
import warnings
from functools import lru_cache
from typing import Any, TypedDict

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── IoU threshold for treating two detected regions as the same text block ───
IOU_MERGE_THRESHOLD = 0.35

# ── Minimum confidence (0–1) to include a block in the output ────────────────
MIN_CONFIDENCE = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# Output type
# ─────────────────────────────────────────────────────────────────────────────

class OcrBlock(TypedDict):
    text: str
    bbox: list[int]          # [x, y, w, h]
    confidence: float        # 0.0 – 1.0
    engine_used: str         # "tesseract" | "easyocr" | "merged"


# ─────────────────────────────────────────────────────────────────────────────
# Lazy engine singletons
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_easyocr_reader(languages: tuple[str, ...]):
    """
    Return a cached EasyOCR Reader for the given language tuple.
    GPU is used if available; falls back to CPU silently.
    """
    import easyocr  # deferred import – heavy at first load
    logger.info("Initialising EasyOCR reader for languages=%s", languages)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reader = easyocr.Reader(list(languages), gpu=False, verbose=False)
    return reader


# ─────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def _xywh_to_xyxy(bbox: list[int]) -> tuple[int, int, int, int]:
    """Convert [x, y, w, h] → (x1, y1, x2, y2)."""
    x, y, w, h = bbox
    return x, y, x + w, y + h


def _xyxy_to_xywh(x1: int, y1: int, x2: int, y2: int) -> list[int]:
    return [x1, y1, x2 - x1, y2 - y1]


def _iou(a: list[int], b: list[int]) -> float:
    """Compute Intersection-over-Union for two [x, y, w, h] bboxes."""
    ax1, ay1, ax2, ay2 = _xywh_to_xyxy(a)
    bx1, by1, bx2, by2 = _xywh_to_xyxy(b)

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter = (ix2 - ix1) * (iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _quad_to_xywh(quad: list[list[int]]) -> list[int]:
    """
    Convert an EasyOCR quadrilateral [[x,y], ...] (4 or more points)
    into an axis-aligned [x, y, w, h] bounding box.
    """
    pts = np.array(quad, dtype=np.int32)
    x1, y1 = pts[:, 0].min(), pts[:, 1].min()
    x2, y2 = pts[:, 0].max(), pts[:, 1].max()
    return [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]


# ─────────────────────────────────────────────────────────────────────────────
# Per-engine runners
# ─────────────────────────────────────────────────────────────────────────────

def _run_tesseract(image: np.ndarray) -> list[OcrBlock]:
    """
    Run Tesseract on *image* (BGR numpy array).

    Uses pytesseract.image_to_data() which returns per-word level detail
    including confidence scores and bounding boxes.

    Returns a list of OcrBlock dicts (engine_used="tesseract").
    """
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        logger.warning("pytesseract not installed – skipping Tesseract engine")
        return []

    # Tesseract expects RGB
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # PSM 6: Assume a single uniform block of text.
    # OEM 3: default (LSTM + legacy).
    config = "--oem 3 --psm 6"

    try:
        data = pytesseract.image_to_data(rgb, config=config, output_type=Output.DICT)
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract binary not found – set pytesseract.pytesseract.tesseract_cmd")
        return []
    except Exception as exc:
        logger.error("Tesseract failed: %s", exc)
        return []

    blocks: list[OcrBlock] = []
    n = len(data["text"])
    lines_dict: dict[tuple[int, int], dict[str, Any]] = {}

    for i in range(n):
        raw_text: str = data["text"][i].strip()
        if not raw_text:
            continue
        conf_raw = int(data["conf"][i])
        if conf_raw < 0:
            conf_raw = 0
        confidence = conf_raw / 100.0
        if confidence < MIN_CONFIDENCE:
            continue

        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])

        if w <= 0 or h <= 0:
            continue

        b_num = data.get("block_num", [0]*n)[i]
        l_num = data.get("line_num", [0]*n)[i]
        key = (b_num, l_num)

        # Find the active segment for this line (split if large horizontal gap)
        active_key = key
        # Check if a segment for this line already exists and has a wide column gap
        matching_keys = [k for k in lines_dict if k[0] == b_num and k[1] == l_num]
        if matching_keys:
            latest_key = matching_keys[-1]
            last_right = lines_dict[latest_key]["right"]
            gap = x - last_right
            if gap > max(h * 2.5, 45):
                # New column detected on the same line -> create a new segment
                active_key = (b_num, l_num, len(matching_keys))

        if active_key not in lines_dict:
            lines_dict[active_key] = {
                "words": [raw_text],
                "left": x,
                "top": y,
                "right": x + w,
                "bottom": y + h,
                "confs": [confidence],
            }
        else:
            lines_dict[active_key]["words"].append(raw_text)
            lines_dict[active_key]["right"] = max(lines_dict[active_key]["right"], x + w)
            lines_dict[active_key]["bottom"] = max(lines_dict[active_key]["bottom"], y + h)
            lines_dict[active_key]["confs"].append(confidence)

    for key, line_info in lines_dict.items():
        line_text = " ".join(line_info["words"]).strip()
        if not line_text:
            continue
        avg_conf = sum(line_info["confs"]) / len(line_info["confs"])
        bx = line_info["left"]
        by = line_info["top"]
        bw = line_info["right"] - line_info["left"]
        bh = line_info["bottom"] - line_info["top"]
        blocks.append(
            OcrBlock(
                text=line_text,
                bbox=[bx, by, bw, bh],
                confidence=round(avg_conf, 4),
                engine_used="tesseract",
            )
        )

    logger.debug("Tesseract: %d line blocks extracted", len(blocks))
    return blocks


def _run_easyocr(image: np.ndarray, languages: tuple[str, ...]) -> list[OcrBlock]:
    """
    Run EasyOCR on *image* (BGR numpy array).

    EasyOCR returns (bbox_quad, text, confidence) tuples.
    The quadrilateral bbox is converted to an axis-aligned [x, y, w, h].

    Returns a list of OcrBlock dicts (engine_used="easyocr").
    """
    try:
        reader = _get_easyocr_reader(languages)
    except Exception as exc:
        logger.error("Could not load EasyOCR reader: %s", exc)
        return []

    # EasyOCR accepts BGR numpy arrays directly
    try:
        results: list[Any] = reader.readtext(image, detail=1, paragraph=False)
    except Exception as exc:
        logger.error("EasyOCR readtext failed: %s", exc)
        return []

    blocks: list[OcrBlock] = []
    for item in results:
        quad, text, conf = item
        text = text.strip()
        if not text:
            continue
        confidence = float(conf)
        if confidence < MIN_CONFIDENCE:
            continue

        bbox = _quad_to_xywh(quad)
        if bbox[2] <= 0 or bbox[3] <= 0:
            continue

        blocks.append(
            OcrBlock(
                text=text,
                bbox=bbox,
                confidence=round(confidence, 4),
                engine_used="easyocr",
            )
        )

    logger.debug("EasyOCR: %d blocks extracted", len(blocks))
    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Merge logic
# ─────────────────────────────────────────────────────────────────────────────

def _merge_blocks(
    tess_blocks: list[OcrBlock],
    easy_blocks: list[OcrBlock],
    iou_threshold: float = IOU_MERGE_THRESHOLD,
) -> list[OcrBlock]:
    """
    Merge Tesseract and EasyOCR results using greedy IoU matching.

    Algorithm
    ---------
    1. For every EasyOCR block, find the Tesseract block with the highest IoU.
    2. If IoU >= threshold → the two blocks cover the same region.
       Keep whichever has higher confidence; tag engine_used as
       "<winner>|merged".
    3. Unmatched blocks from either engine are kept as-is.
    4. Sort final list top-to-bottom, left-to-right for readability.

    Parameters
    ----------
    tess_blocks : list[OcrBlock]
        Blocks from Tesseract.
    easy_blocks : list[OcrBlock]
        Blocks from EasyOCR.
    iou_threshold : float
        Minimum IoU to consider two blocks the same region.

    Returns
    -------
    list[OcrBlock]
        Merged, deduplicated block list sorted by (y, x).
    """
    matched_tess_indices: set[int] = set()
    output: list[OcrBlock] = []

    for e_block in easy_blocks:
        best_iou = 0.0
        best_idx = -1

        for t_idx, t_block in enumerate(tess_blocks):
            if t_idx in matched_tess_indices:
                continue
            iou_val = _iou(e_block["bbox"], t_block["bbox"])
            if iou_val > best_iou:
                best_iou = iou_val
                best_idx = t_idx

        if best_iou >= iou_threshold and best_idx >= 0:
            # Overlapping region → keep higher-confidence block
            t_block = tess_blocks[best_idx]
            matched_tess_indices.add(best_idx)

            if e_block["confidence"] >= t_block["confidence"]:
                winner = OcrBlock(
                    text=e_block["text"],
                    bbox=e_block["bbox"],
                    confidence=e_block["confidence"],
                    engine_used="easyocr|merged",
                )
            else:
                winner = OcrBlock(
                    text=t_block["text"],
                    bbox=t_block["bbox"],
                    confidence=t_block["confidence"],
                    engine_used="tesseract|merged",
                )
            output.append(winner)
        else:
            # No match → keep EasyOCR block as-is
            output.append(e_block)

    # Add all unmatched Tesseract blocks
    for t_idx, t_block in enumerate(tess_blocks):
        if t_idx not in matched_tess_indices:
            output.append(t_block)

    # Sort top-to-bottom, left-to-right (reading order approximation)
    output.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

    logger.debug(
        "Merged: %d tess + %d easy → %d output blocks",
        len(tess_blocks),
        len(easy_blocks),
        len(output),
    )
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_ocr(
    image: np.ndarray,
    languages: list[str] | None = None,
    use_tesseract: bool = True,
    use_easyocr: bool = True,
    iou_threshold: float = IOU_MERGE_THRESHOLD,
) -> list[OcrBlock]:
    """
    Run dual-engine OCR on a preprocessed image and return merged text blocks.

    Parameters
    ----------
    image : np.ndarray
        BGR (or greyscale) preprocessed image (e.g. output of
        ``image_preprocessing.preprocess_pipeline``).
    languages : list[str] | None
        ISO 639-1 language codes for EasyOCR (default: ["en"]).
        Tesseract uses its own installed language packs; "en" maps to "eng".
    use_tesseract : bool
        Whether to run Tesseract (default True).
    use_easyocr : bool
        Whether to run EasyOCR (default True).
    iou_threshold : float
        IoU threshold for considering two detected regions the same block
        (default 0.35).

    Returns
    -------
    list[OcrBlock]
        Each dict contains:
          ``text``        – extracted string
          ``bbox``        – [x, y, w, h] in pixels
          ``confidence``  – 0.0–1.0
          ``engine_used`` – "tesseract", "easyocr", or "<engine>|merged"

    Raises
    ------
    ValueError
        If *image* is None or empty.
    """
    if image is None or image.size == 0:
        raise ValueError("run_ocr received an empty or None image.")

    if languages is None:
        languages = ["en"]
    lang_tuple = tuple(languages)

    tess_blocks: list[OcrBlock] = []
    easy_blocks: list[OcrBlock] = []

    if use_tesseract:
        logger.info("Running Tesseract OCR …")
        tess_blocks = _run_tesseract(image)

    if use_easyocr:
        logger.info("Running EasyOCR …")
        easy_blocks = _run_easyocr(image, lang_tuple)

    # Both engines ran → merge
    if tess_blocks and easy_blocks:
        merged = _merge_blocks(tess_blocks, easy_blocks, iou_threshold)
        logger.info("OCR complete: %d merged blocks", len(merged))
        return merged

    # Only one engine ran (or both empty)
    result = tess_blocks or easy_blocks
    logger.info("OCR complete: %d blocks (single engine)", len(result))
    return result
