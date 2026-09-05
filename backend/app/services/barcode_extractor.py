"""
Barcode, QR Code, GTIN, and Batch Code Extractor Service
=========================================================
Detects and decodes EAN-13, UPC-A, GS1-128, and QR codes from product label imagery.
Extracts Global Trade Item Numbers (GTIN) and detects nearby Batch/Lot codes via OCR.

Supported Standards:
--------------------
- EAN-13 (13-digit standard for retail items in India / International)
- UPC-A (12-digit standard, normalized to GTIN-12 / GTIN-14)
- QR Codes (Standard URLs, plain GTINs, GS1 Digital Link URIs with AI (01) and AI (10))
- Batch / Lot Codes via OCR proximity clustering and regex pattern matching.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, TypedDict

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Try importing zxing-cpp (primary high-performance C++20 engine)
try:
    import zxingcpp
    HAS_ZXING = True
except Exception as exc:
    logger.warning("zxing-cpp not available: %s", exc)
    HAS_ZXING = False

# Try importing pyzbar as secondary fallback
try:
    import pyzbar.pyzbar as pyzbar_mod
    HAS_PYZBAR = True
except Exception:
    HAS_PYZBAR = False


class DecodedBarcode(TypedDict):
    text: str
    format: str
    gtin: str | None
    bbox: list[int] | None  # [x, y, w, h]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Barcode & QR Code Detection
# ─────────────────────────────────────────────────────────────────────────────

def decode_barcodes(image: np.ndarray) -> list[DecodedBarcode]:
    """
    Detect and decode all barcodes and QR codes present in the image.
    Uses zxing-cpp as primary engine, with pyzbar and OpenCV as fallbacks.
    """
    if image is None or image.size == 0:
        return []

    results: list[DecodedBarcode] = []
    seen_texts: set[str] = set()

    # Engine 1: zxing-cpp
    if HAS_ZXING:
        try:
            barcodes = zxingcpp.read_barcodes(image)
            for b in barcodes:
                raw_text = (b.text or "").strip()
                if not raw_text or raw_text in seen_texts:
                    continue

                fmt_name = str(b.format).replace("BarcodeFormat.", "").upper()
                bbox = None
                try:
                    pos = b.position
                    xs = [pos.top_left.x, pos.top_right.x, pos.bottom_right.x, pos.bottom_left.x]
                    ys = [pos.top_left.y, pos.top_right.y, pos.bottom_right.y, pos.bottom_left.y]
                    min_x, max_x = max(0, min(xs)), max(xs)
                    min_y, max_y = max(0, min(ys)), max(ys)
                    bbox = [int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y)]
                except Exception as pos_exc:
                    logger.debug("Could not compute barcode bbox: %s", pos_exc)

                gtin = extract_gtin_from_text(raw_text, fmt_name)
                seen_texts.add(raw_text)
                results.append({
                    "text": raw_text,
                    "format": fmt_name,
                    "gtin": gtin,
                    "bbox": bbox,
                })
        except Exception as exc:
            logger.debug("zxing-cpp detection encountered error: %s", exc)

    # Engine 2: pyzbar fallback (if zxing missed or wasn't loaded)
    if not results and HAS_PYZBAR:
        try:
            pz_results = pyzbar_mod.decode(image)
            for pb in pz_results:
                raw_text = pb.data.decode("utf-8", errors="ignore").strip()
                if not raw_text or raw_text in seen_texts:
                    continue
                fmt_name = str(pb.type).upper()
                rect = pb.rect
                bbox = [int(rect.left), int(rect.top), int(rect.width), int(rect.height)]
                gtin = extract_gtin_from_text(raw_text, fmt_name)
                seen_texts.add(raw_text)
                results.append({
                    "text": raw_text,
                    "format": fmt_name,
                    "gtin": gtin,
                    "bbox": bbox,
                })
        except Exception as pz_exc:
            logger.debug("pyzbar fallback encountered error: %s", pz_exc)

    # Engine 3: OpenCV QRCodeDetector fallback
    if not any(r["format"] in ("QRCODE", "QR_CODE") for r in results):
        try:
            qr_detector = cv2.QRCodeDetector()
            val, points, _ = qr_detector.detectAndDecode(image)
            if val and val.strip() and val.strip() not in seen_texts:
                bbox = None
                if points is not None and len(points) > 0:
                    pts = points[0]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    bbox = [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))]
                gtin = extract_gtin_from_text(val.strip(), "QRCODE")
                seen_texts.add(val.strip())
                results.append({
                    "text": val.strip(),
                    "format": "QRCODE",
                    "gtin": gtin,
                    "bbox": bbox,
                })
        except Exception as cv_exc:
            logger.debug("OpenCV QRCodeDetector fallback error: %s", cv_exc)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 2. GTIN Standardization
# ─────────────────────────────────────────────────────────────────────────────

def extract_gtin_from_text(text: str, format_name: str) -> str | None:
    """
    Extract standard 8, 12, 13, or 14-digit GTIN from decoded barcode or QR text.
    Handles standard barcodes, GS1 element strings, and GS1 Digital Link URLs.
    """
    clean_text = text.strip()
    fmt_clean = re.sub(r"[^A-Z0-9]", "", format_name.upper())

    # 1. Direct Linear Barcodes (EAN-13, UPC-A, EAN-8, ITF-14)
    if fmt_clean == "EAN13" and re.fullmatch(r"\d{13}", clean_text):
        return clean_text

    if fmt_clean in ("UPCA", "UPC") and re.fullmatch(r"\d{12}", clean_text):
        return clean_text

    if fmt_clean == "EAN8" and re.fullmatch(r"\d{8}", clean_text):
        return clean_text

    if fmt_clean == "ITF14" and re.fullmatch(r"\d{14}", clean_text):
        return clean_text

    # 2. GS1 Digital Link URI / Element String (AI 01 = GTIN)
    # Examples:
    #   https://id.gs1.org/01/08901030999999
    #   (01)08901030999999(10)BATCH123
    gs1_match = re.search(r"(?:/01/|\(01\))(\d{8,14})", clean_text)
    if gs1_match:
        return gs1_match.group(1)

    # 3. Plain numeric payload in QR code or DataMatrix
    if re.fullmatch(r"\d{8}|\d{12}|\d{13}|\d{14}", clean_text):
        return clean_text

    return None



# ─────────────────────────────────────────────────────────────────────────────
# 3. Batch / Lot Code Extraction via OCR Proximity
# ─────────────────────────────────────────────────────────────────────────────

BATCH_PATTERNS = [
    # Explicit prefix: "B.No: B4208", "Batch No. 89A", "Lot: 09/25-A"
    re.compile(r"(?:B\.?\s*No\.?|Batch\s*(?:No\.?|Number|#)?|Lot\s*(?:No\.?|Number|#)?|B/N|BN)\s*[:\-\.]*\s*([A-Za-z0-9/\-_]{3,25})", re.IGNORECASE),
    # Header format: "BATCH: L24-001"
    re.compile(r"\b(?:BATCH|LOT)\s*[:\-\.]*\s*([A-Za-z0-9/\-_]{3,25})\b", re.IGNORECASE),
]


def extract_batch_code(
    ocr_blocks: list[dict[str, Any] | Any] | None = None,
    barcode_bbox: list[int] | None = None,
    raw_text_pool: str | None = None,
) -> str | None:
    """
    Search OCR blocks or raw text pool for Batch / Lot number declarations.
    If multiple candidates exist and barcode_bbox is provided, prioritizes the
    block closest in physical proximity to the barcode.
    """
    candidates: list[tuple[str, list[int] | None, float]] = []

    if ocr_blocks:
        for block in ocr_blocks:
            if isinstance(block, dict):
                text = str(block.get("text", "")).strip()
                bbox = block.get("bbox")
            else:
                text = str(getattr(block, "text", "")).strip()
                bbox = getattr(block, "bbox", None)

            if not text:
                continue

            for pattern in BATCH_PATTERNS:
                m = pattern.search(text)
                if m:
                    val = m.group(1).strip().strip(".,:-/")
                    # Filter out obvious false positives
                    if len(val) >= 2 and val.lower() not in ("date", "mfg", "exp", "pkd", "rs", "mrp", "net"):
                        dist = 0.0
                        if barcode_bbox and bbox and len(bbox) >= 4:
                            bc_cx = barcode_bbox[0] + barcode_bbox[2] / 2.0
                            bc_cy = barcode_bbox[1] + barcode_bbox[3] / 2.0
                            txt_cx = bbox[0] + bbox[2] / 2.0
                            txt_cy = bbox[1] + bbox[3] / 2.0
                            dist = math.hypot(txt_cx - bc_cx, txt_cy - bc_cy)

                        candidates.append((val, bbox, dist))
                        break

    if candidates:
        if barcode_bbox:
            candidates.sort(key=lambda c: c[2])
        best_val = candidates[0][0]
        logger.info("Batch/Lot code extracted: '%s' (from %d candidate blocks)", best_val, len(candidates))
        return best_val

    # Fallback to searching raw_text_pool
    if raw_text_pool:
        for pattern in BATCH_PATTERNS:
            m = pattern.search(raw_text_pool)
            if m:
                val = m.group(1).strip().strip(".,:-/")
                if len(val) >= 2 and val.lower() not in ("date", "mfg", "exp", "pkd", "rs", "mrp", "net"):
                    logger.info("Batch/Lot code extracted from raw_text_pool: '%s'", val)
                    return val

    return None

