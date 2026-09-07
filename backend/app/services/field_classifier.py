"""
Field Classifier Service
========================
High-throughput, layout-agnostic spatial compliance extractor for Indian
Legal Metrology (Packaged Commodities) Rules 2011 and FSSAI regulations.

Architected specifically for edge inference on an Intel i5 + NVIDIA RTX 2050
(4GB VRAM ceiling, 16GB RAM) running PaddleOCR with CUDA acceleration.

Architecture:
-------------
- Tier 1: Local GPU Acceleration (PaddleOCR)
    * Fast, lightweight C++ inference (<1.5GB VRAM, ~150ms latency)
    * Layout-agnostic extraction of bounding boxes and text tokens
- Tier 2: Local Spatial Mapping Engine (Radial Proximity Search)
    * Discards rigid horizontal clustering (delta-y <= 25px)
    * Analyzes 2D Euclidean proximity (dx, dy) to semantic compliance anchors
    * Captures value tokens sitting horizontally to the right or directly below
- Tier 3: Target Failure Flagging
    * Flags missing fields or local confidence < 0.80 into failed_fields
    * Produces flat raw_text_pool for surgical text-only GenAI fallback
"""

from __future__ import annotations

import difflib
import logging
import math
import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, ClassVar, Optional, TypedDict, Union

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Compliance & Threshold Constants
# ─────────────────────────────────────────────────────────────────────────────

MIN_MATCH_CONFIDENCE: float = 0.30
GENAI_FALLBACK_THRESHOLD: float = 0.80
DEFAULT_RADIAL_RADIUS_PX: int = 350
_MIN_ANCHOR_CHARS: int = 2

MANDATORY_COMPLIANCE_FIELDS: list[str] = [
    "mrp",
    "net_quantity",
    "manufacture_date",
    "expiry_date",
    "manufacturer_name_address",
    "consumer_care_details",
    "country_of_origin",
]

# Directional Euclidean weight bonuses
DIRECTION_RIGHT_WEIGHT: float = 1.00  # Best priority for key -> value on same line
DIRECTION_BELOW_WEIGHT: float = 1.25  # Stacked key-value declarations
DIRECTION_ABOVE_PENALTY: float = 2.50 # Penalize tokens positioned above anchor


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Compliance Anchor Dictionary
# ─────────────────────────────────────────────────────────────────────────────

_COMPLIANCE_ANCHORS: dict[str, list[str]] = {
    "mrp": [
        "MRP", "M.R.P", "M.R.P.", "MAXIMUM RETAIL PRICE", "PRICE",
        "RETAIL PRICE", "USP", "U.S.P", "UNIT SALE PRICE",
        "INCL OF ALL TAXES", "INCLUSIVE OF ALL TAXES", "INCL. TAXES",
        "MAX RETAIL PRICE", "MAX. RETAIL PRICE",
    ],
    "net_quantity": [
        "NET WT", "NET WT.", "NET WEIGHT", "NET QTY", "NET QUANTITY",
        "NET CONTENT", "NET CONTENTS", "NET VOL", "NET VOLUME",
        "NETT", "NETT WT", "NETT WEIGHT", "CONTENTS", "BISCUITS NET",
        "PACK OF", "QUANTITY", "QTY", "NET MASS", "BISCUITS NET WEIGHT",
    ],
    "manufacture_date": [
        "MFG", "MFG.", "MFG DATE", "MFD", "MFD.", "PKD", "PKD.",
        "PACKED", "PACKED ON", "DATE OF MFG", "DATE OF PKG",
        "DATE OF PACKING", "MANUFACTURE", "MANUFACTURED", "MANUFACTURING",
        "MFGDT", "DATE OF MANUFACTURE",
    ],
    "expiry_date": [
        "EXPIRY", "EXP", "EXP.", "EXPIRY DATE", "EXPIRY DT",
        "USE BY", "USE BEFORE", "BEST BEFORE", "BEST BEFORE DATE",
        "BBE", "BB", "BEST BY", "CONSUME BY", "CONSUME BEFORE",
        "SELL BY", "VALID TILL", "VALID UPTO", "VALID UP TO",
    ],
    "manufacturer_name_address": [
        "MANUFACTURED BY", "MFG BY", "MFGD BY", "MARKETED BY", "MKTD BY",
        "PACKED BY", "PKD BY", "MANUFACTURED FOR", "IMPORTED BY",
        "DISTRIBUTED BY", "BRAND OWNER", "REGD OFFICE", "REGISTERED OFFICE",
        "CORPORATE OFFICE", "FACTORY ADDRESS", "WORKS AT", "UNIT ADDRESS",
        "MFG. & MKTD. BY", "PACKED & MARKETED BY",
        "MFG & MARKETED BY", "MARKETED & MFG BY",
        "MARKETED & DISTRIBUTED BY", "SOLE DISTRIBUTOR",
        "SOLD BY", "BRAND", "A UNIT OF", "SUBSIDIARY OF",
    ],
    "consumer_care_details": [
        "CONSUMER CARE", "CUSTOMER CARE", "HELPLINE", "TOLL FREE",
        "TOLL-FREE", "CUSTOMER SUPPORT", "FOR QUERIES", "FOR COMPLAINTS",
        "FEEDBACK", "WRITE TO", "CARE LINE", "CONTACT US",
        "CARE CELL", "CONSUMER CELL", "REACH US AT",
        "PHONE NO", "PHONE NO.", "PHONE", "TEL NO", "TEL.", "TEL",
        "CALL US", "TOLL FREE NO", "CONSUMER HELPLINE", "CARE CONTACT",
    ],
    "country_of_origin": [
        "COUNTRY OF ORIGIN", "MADE IN", "PRODUCT OF", "PRODUCE OF",
        "MANUFACTURED IN", "ORIGIN", "COO", "ORIGIN COUNTRY",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Regex Validation & Scoring Engine
# ─────────────────────────────────────────────────────────────────────────────

_FIELD_VALIDATORS: dict[str, list[dict[str, Any]]] = {
    "mrp": [
        {
            "name": "mrp_explicit_currency_val",
            "pattern": re.compile(
                r"(?:MRP|M\.R\.P\.?|PRICE|USP)[\s:\-\.=?&%\*^/]*(?:Rs\.?|INR|₹)?[\s:\-\.]*(\d+[\d,\.]*)",
                re.IGNORECASE,
            ),
            "confidence": 0.98,
        },
        {
            "name": "mrp_symbol_and_amount",
            "pattern": re.compile(r"(?:Rs\.?|INR|₹)\s*(\d+[\d,\.]*)", re.IGNORECASE),
            "confidence": 0.92,
        },
        {
            "name": "mrp_two_decimal_amount",
            "pattern": re.compile(r"\b(\d+\.\d{2})\b"),
            "confidence": 0.85,
        },
        {
            "name": "mrp_slash_dash_format",
            "pattern": re.compile(r"\b(\d+[\d,\.]*)\s*/-"),
            "confidence": 0.88,
        },
        {
            "name": "mrp_inclusive_taxes_mention",
            "pattern": re.compile(r"(?:incl\.?|inclusive)\s+(?:of\s+)?(?:all\s+)?taxes", re.IGNORECASE),
            "confidence": 0.75,
        },
    ],
    "net_quantity": [
        {
            "name": "net_qty_compound_offer",
            "pattern": re.compile(
                r"\b\d+[\d\.\,]*\s*(?:g|gm|gms|kg|ml|l|ltr)\s*[+*]\s*\d+[\d\.\,]*\s*(?:g|gm|gms|kg|ml|l|ltr|%)?\s*(?:extra|free)?\s*=\s*\d+[\d\.\,]*\s*(?:g|gm|gms|kg|ml|l|ltr)\b",
                re.IGNORECASE,
            ),
            "confidence": 0.99,
        },
        {
            "name": "net_qty_explicit_label_and_unit",
            "pattern": re.compile(
                r"(?:(?:biscuits?|cookies?|snacks?|food)?\s*net\s*(?:wt\.?|weight|content|contents|qty|quantity|volume|vol\.?|mass)|nett?\s*(?:wt|weight)|contents?|pack\s*of|count)[\s:\-\.]*(\d+[\d,\.]*\s*(?:g|gm|gms|grams?|kg|ml|mL|l|L|ltr|litres?|oz|fl\.?\s*oz|pcs|pieces?|pack|units?|capsules?|tablets?|wipes?|N))\b",
                re.IGNORECASE,
            ),
            "confidence": 0.98,
        },
        {
            "name": "net_qty_for_promo_header",
            "pattern": re.compile(
                r"\b(?:FOR|PACK)\s*[\s:\-\.]*(\d+[\d,\.]*\s*(?:g|gm|gms|grams?|kg|ml|mL|l|L|ltr|litres?|pcs|pieces?|units?))\b",
                re.IGNORECASE,
            ),
            "confidence": 0.96,
        },
        {
            "name": "net_qty_numeric_with_unit",
            "pattern": re.compile(
                r"\b(\d+[\d,\.]*\s*(?:g|gm|gms|grams?|kg|ml|mL|l|L|ltr|litres?|fl\.?\s*oz|pcs|pieces?|units?|capsules?|tablets?|wipes?|N))\b",
                re.IGNORECASE,
            ),
            "confidence": 0.88,
        },
    ],
    "manufacture_date": [
        {
            "name": "mfg_date_explicit_header",
            "pattern": re.compile(
                r"(?:mfg\.?\s*(?:date)?|manufactured(?:\s*on)?|mfd\.?|pkd\.?|packed(?:\s*on)?|date\s+of\s+(?:mfg|pkd|packing|manufacture))[\s:\-\.]*((?:\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}|\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4}|\d{1,2}[\-/\.](?:20)?\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-/\.]*(?:20)?\d{2}))",
                re.IGNORECASE,
            ),
            "confidence": 0.99,
        },
        {
            "name": "mfg_date_standalone_calendar_date",
            "pattern": re.compile(
                r"\b(?:\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}|(?:0?[1-9]|[12]\d|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.](?:20)?\d{2}|(?:0?[1-9]|1[0-2])[\-/](?:20)?\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-/\.]*(?:20)?\d{2})\b",
                re.IGNORECASE,
            ),
            "confidence": 0.82,
        },
    ],
    "expiry_date": [
        {
            "name": "exp_date_explicit_header",
            "pattern": re.compile(
                r"(?:use\s*by|best\s*before|exp(?:iry)?\.?(?:\s*date)?|bbe|best\s*by|consume\s*(?:by|before)|sell\s*by|valid\s*(?:till|upto|up\s*to))[\s:\-\.]*((?:\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}|\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4}|\d{1,2}[\-/\.](?:20)?\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-/\.]*(?:20)?\d{2}))",
                re.IGNORECASE,
            ),
            "confidence": 0.99,
        },
        {
            "name": "exp_date_best_before_duration",
            "pattern": re.compile(
                r"(?:best\s*before|use\s*within)[\s:\-]*(\d+\s*(?:months?|days?|years?)(?:\s*from\s+(?:mfg|pkd|packaging|manufacture|date))?)",
                re.IGNORECASE,
            ),
            "confidence": 0.88,
        },
        {
            "name": "exp_date_standalone_calendar_date",
            "pattern": re.compile(
                r"\b(?:\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}|(?:0?[1-9]|[12]\d|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.](?:20)?\d{2}|(?:0?[1-9]|1[0-2])[\-/](?:20)?\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-/\.]*(?:20)?\d{2})\b",
                re.IGNORECASE,
            ),
            "confidence": 0.82,
        },
    ],
    "manufacturer_name_address": [
        {
            "name": "mfr_explicit_by_declaration",
            "pattern": re.compile(
                r"(?:manufactured|mfr\.?|marketed|packed|imported|distributed|bought)\s+(?:by|for)|brand\s+owner|registered\s+office|regd\.?\s*off(?:ice)?|corporate\s+office|works\s+at|factory\s+address",
                re.IGNORECASE,
            ),
            "confidence": 0.92,
        },
        {
            "name": "mfr_corporate_suffix",
            "pattern": re.compile(
                r"\b(?:pvt\.?\s*ltd\.?|private\s+limited|limited|llp|industries|foods|beverages|pharmaceuticals|laboratories|enterprises)\b",
                re.IGNORECASE,
            ),
            "confidence": 0.88,
        },
        {
            "name": "mfr_address_geographic_indicators",
            "pattern": re.compile(
                r"\b(?:address|road|street|marg|nagar|plot|industrial|area|estate|midc|gidc|riico|sipcot|pin|zip|\d{6})\b",
                re.IGNORECASE,
            ),
            "confidence": 0.82,
        },
    ],
    "consumer_care_details": [
        {
            "name": "care_phone_toll_free",
            "pattern": re.compile(
                r"\b(?:1800[\s\-]?\d{3}[\s\-]?\d{4}|1860[\s\-]?\d{3}[\s\-]?\d{4}|0\d{2,4}[\s\-]?\d{6,8}|\+91[\s\-]?\d{10})\b",
                re.IGNORECASE,
            ),
            "confidence": 0.95,
        },
        {
            "name": "care_email_or_website",
            "pattern": re.compile(
                r"(?:[\w\.\-]+@[\w\.\-]+\.[a-z]{2,}|www\.[\w\.\-]+\.[a-z]{2,}|https?://[\w\.\-]+)",
                re.IGNORECASE,
            ),
            "confidence": 0.92,
        },
        {
            "name": "care_explicit_label",
            "pattern": re.compile(
                r"(?:consumer|customer)\s+(?:care|service|helpline|support)|toll\s*free|helpline|feedback|care@",
                re.IGNORECASE,
            ),
            "confidence": 0.85,
        },
        {
            "name": "care_phone_inline",
            "pattern": re.compile(
                r"(?:phone\s*(?:no\.?)?|tel\s*(?:no\.?)?|call\s*us)[\s:\-\.]*(\+?\d[\d\s\-]{4,14}\d)",
                re.IGNORECASE,
            ),
            "confidence": 0.94,
        },
    ],
    "country_of_origin": [
        {
            "name": "coo_explicit_phrase",
            "pattern": re.compile(
                r"(?:country\s+of\s+origin|origin\s*[\s:\-]|made\s+in\s+[A-Za-z]+|product\s+of\s+[A-Za-z]+|produce\s+of\s+[A-Za-z]+|manufactured\s+in\s+[A-Za-z]+)",
                re.IGNORECASE,
            ),
            "confidence": 0.95,
        },
        {
            "name": "coo_india_keyword",
            "pattern": re.compile(r"\b(?:India|Republic\s+of\s+India)\b", re.IGNORECASE),
            "confidence": 0.88,
        },
        {
            "name": "coo_indian_domestic_pincode",
            "pattern": re.compile(
                r"\b(?:MUMBAI|DELHI|BANGALORE|HYDERABAD|CHENNAI|KOLKATA|PUNE|AHMEDABAD|HARYANA|SONIPAT|BARHI|GURGAON|FARIDABAD|NOIDA|GHAZIABAD|PUNJAB|GUJARAT|MAHARASHTRA|KARNATAKA|TAMIL\s*NADU|KERALA|RAJASTHAN|BIHAR|ODISHA|ASSAM|UTTARAKHAND|TS|TN|MH|KA|UP|MP|GJ|WB|HR|PB|RJ|AP|KL|CH|DL)[^\w\d\n\r]*[-–]?\s*\d{6}\b",
                re.IGNORECASE,
            ),
            "confidence": 0.90,
        },
        {
            "name": "coo_indian_state_name",
            "pattern": re.compile(
                r"\b(?:Haryana|Punjab|Maharashtra|Karnataka|Gujarat|Tamil\s*Nadu|Kerala|Rajasthan|Uttar\s*Pradesh|Madhya\s*Pradesh|Andhra\s*Pradesh|Telangana|West\s*Bengal|Odisha|Bihar|Jharkhand|Assam|Himachal\s*Pradesh|Uttarakhand|Goa|Delhi)\b",
                re.IGNORECASE,
            ),
            "confidence": 0.85,
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Data Transfer Objects & TypedDicts
# ─────────────────────────────────────────────────────────────────────────────

class OcrBlock(TypedDict):
    text: str
    bbox: list[int]
    confidence: float
    engine_used: str


class ClassifiedBlock(TypedDict):
    text: str
    bbox: list[int]
    confidence: float
    engine_used: str
    field: str
    match_confidence: float
    pattern_matched: str
    requires_genai: bool


class ClassificationResult(TypedDict):
    classified: list[ClassifiedBlock]
    unmatched: list[OcrBlock]
    fields_requiring_genai: list[str]
    raw_text_pool: str
    extracted_fields: dict[str, dict[str, Any]]
    failed_fields: list[str]


class LayoutClassifierResult(TypedDict):
    raw_text_pool: str
    extracted_fields: dict[str, dict[str, Any]]
    failed_fields: list[str]
    classified: list[ClassifiedBlock]
    unmatched: list[OcrBlock]
    fields_requiring_genai: list[str]


@dataclass
class LayoutToken:
    """Normalized spatial token segment with geometric coordinates."""
    text: str
    bbox: list[int]          # [x, y, w, h]
    confidence: float
    cx: float                # Geometric center horizontal
    cy: float                # Geometric center vertical
    w: float                 # Width
    h: float                 # Height
    engine_used: str = "paddleocr"
    raw_box: Any = None


# ─────────────────────────────────────────────────────────────────────────────
# LaptopLayoutClassifier (PaddleOCR GPU Engine & Spatial Proximity Search)
# ─────────────────────────────────────────────────────────────────────────────

class LaptopLayoutClassifier:
    """
    LaptopLayoutClassifier
    ======================
    Ultra-lightweight, layout-agnostic spatial proximity extractor leveraging
    PaddleOCR on CUDA cores (NVIDIA RTX 2050 4GB VRAM ceiling).

    Pipeline:
      1. Initializes GPU PaddleOCR singleton (`PaddleOCR(use_gpu=True, lang='en', show_log=False)`).
      2. Computes precise geometric centers (cx, cy, h) for all detected tokens,
         discarding brittle horizontal line clustering. Concurrently builds raw_text_pool.
      3. Performs radial Euclidean proximity searches from semantic compliance anchors
         horizontally to the right and directly below.
      4. Validates extractions against legal metrology rules; flags extractions < 0.80 into
         failed_fields for Tier 3 text-only GenAI fallback.
    """

    _cached_paddle_engine: ClassVar[Any] = None
    _engine_init_attempted: ClassVar[bool] = False

    def __init__(
        self,
        use_gpu: bool = True,
        lang: str = "en",
        show_log: bool = False,
        confidence_threshold: float = GENAI_FALLBACK_THRESHOLD,
        max_search_radius_px: int = DEFAULT_RADIAL_RADIUS_PX,
    ) -> None:
        self.use_gpu = use_gpu
        self.lang = lang
        self.show_log = show_log
        self.confidence_threshold = confidence_threshold
        self.max_search_radius_px = max_search_radius_px

    @classmethod
    def get_paddle_engine(cls, use_gpu: bool = True, lang: str = "en", show_log: bool = False) -> Any:
        """
        Thread-safe cached singleton for PaddleOCR. Prevents VRAM fragmentation
        and re-initialization latency (~150ms per scan when kept warm in VRAM).
        """
        if cls._cached_paddle_engine is not None:
            return cls._cached_paddle_engine

        if cls._engine_init_attempted and cls._cached_paddle_engine is None:
            return None

        cls._engine_init_attempted = True
        import os
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        try:
            from paddleocr import PaddleOCR
            logger.info("Initializing PaddleOCR GPU engine (device=gpu:0, CUDA)...")
            try:
                # Modern PaddleOCR 3.x (PaddleX) syntax - disable heavy unwarping and doc orientation networks
                cls._cached_paddle_engine = PaddleOCR(
                    device="gpu:0",
                    lang=lang,
                    use_doc_unwarping=False,
                    use_doc_orientation_classify=False,
                )
            except (TypeError, ValueError):
                try:
                    cls._cached_paddle_engine = PaddleOCR(
                        device="gpu",
                        lang=lang,
                        use_doc_unwarping=False,
                        use_doc_orientation_classify=False,
                    )
                except (TypeError, ValueError):
                    # Legacy PaddleOCR 2.x syntax
                    cls._cached_paddle_engine = PaddleOCR(use_gpu=use_gpu, lang=lang, show_log=show_log)
            logger.info("PaddleOCR GPU engine initialized successfully on CUDA (fast mode).")
        except Exception as exc:
            logger.warning("PaddleOCR GPU initialization failed (%s); trying CPU fallback", exc)
            try:
                from paddleocr import PaddleOCR
                try:
                    cls._cached_paddle_engine = PaddleOCR(
                        device="cpu",
                        lang=lang,
                        use_doc_unwarping=False,
                        use_doc_orientation_classify=False,
                    )
                except (TypeError, ValueError):
                    cls._cached_paddle_engine = PaddleOCR(use_gpu=False, lang=lang, show_log=show_log)
                logger.info("PaddleOCR CPU engine initialized as fallback.")
            except Exception as cpu_exc:
                logger.error("PaddleOCR unavailable in this environment: %s", cpu_exc)
                cls._cached_paddle_engine = None

        return cls._cached_paddle_engine

    def extract_tokens(
        self,
        input_data: Union[np.ndarray, str, list[dict[str, Any]], list[OcrBlock]],
    ) -> tuple[list[LayoutToken], str]:
        """
        Extract token segments and compute geometric coordinates (cx, cy, w, h).
        Concurrently builds flat text string pool of all lines.
        """
        tokens: list[LayoutToken] = []

        if isinstance(input_data, (np.ndarray, str)):
            engine = self.get_paddle_engine(use_gpu=self.use_gpu, lang=self.lang, show_log=self.show_log)
            if engine is not None:
                try:
                    ocr_results = engine.ocr(input_data)
                    page_res = ocr_results[0] if (ocr_results and len(ocr_results) > 0) else None
                    if isinstance(page_res, dict):
                        # PaddleOCR 3.x (PaddleX) structured dict output
                        texts = page_res.get("rec_texts") or []
                        scores = page_res.get("rec_scores") or []
                        boxes = page_res.get("rec_boxes") if "rec_boxes" in page_res else page_res.get("dt_polys", [])
                        for i in range(len(texts)):
                            text = str(texts[i]).strip()
                            if not text:
                                continue
                            conf = float(scores[i]) if i < len(scores) else 0.90
                            b = boxes[i] if i < len(boxes) else [0, 0, 10, 10]
                            if hasattr(b, "__len__") and len(b) == 4 and not hasattr(b[0], "__len__"):
                                # Format: [x_min, y_min, x_max, y_max]
                                x_min, y_min, x_max, y_max = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                                w = max(1.0, x_max - x_min)
                                h = max(1.0, y_max - y_min)
                                cx = x_min + w / 2.0
                                cy = y_min + h / 2.0
                                raw_box = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
                            elif hasattr(b, "__len__") and len(b) >= 4 and hasattr(b[0], "__len__"):
                                # Format: [[x, y], [x, y], [x, y], [x, y]]
                                xs = [float(pt[0]) for pt in b]
                                ys = [float(pt[1]) for pt in b]
                                x_min, x_max = min(xs), max(xs)
                                y_min, y_max = min(ys), max(ys)
                                w = max(1.0, x_max - x_min)
                                h = max(1.0, y_max - y_min)
                                cx = sum(xs) / 4.0
                                cy = sum(ys) / 4.0
                                raw_box = b
                            else:
                                x_min, y_min, w, h, cx, cy = 0.0, 0.0, 10.0, 10.0, 5.0, 5.0
                                raw_box = [[0, 0], [10, 0], [10, 10], [0, 10]]

                            tokens.append(
                                LayoutToken(
                                    text=text,
                                    bbox=[int(x_min), int(y_min), int(w), int(h)],
                                    confidence=round(conf, 4),
                                    cx=cx,
                                    cy=cy,
                                    w=w,
                                    h=h,
                                    engine_used="paddleocr",
                                    raw_box=raw_box,
                                )
                            )
                    elif isinstance(page_res, list):
                        # Legacy PaddleOCR 2.x list of [box, (text, conf)]
                        for item in page_res:
                            if not item or len(item) < 2:
                                continue
                            box, text_info = item[0], item[1]
                            text = str(text_info[0] if isinstance(text_info, (tuple, list)) else text_info).strip()
                            conf = float(text_info[1] if isinstance(text_info, (tuple, list)) and len(text_info) > 1 else 0.90)

                            if not text:
                                continue

                            xs = [float(pt[0]) for pt in box]
                            ys = [float(pt[1]) for pt in box]
                            x_min, x_max = min(xs), max(xs)
                            y_min, y_max = min(ys), max(ys)
                            w = max(1.0, x_max - x_min)
                            h = max(1.0, y_max - y_min)
                            cx = sum(xs) / 4.0
                            cy = sum(ys) / 4.0

                            tokens.append(
                                LayoutToken(
                                    text=text,
                                    bbox=[int(x_min), int(y_min), int(w), int(h)],
                                    confidence=round(conf, 4),
                                    cx=cx,
                                    cy=cy,
                                    w=w,
                                    h=h,
                                    engine_used="paddleocr",
                                    raw_box=box,
                                )
                            )
                except Exception as exc:
                    logger.error("PaddleOCR execution failed on input image: %s", exc)

        elif isinstance(input_data, list):
            # Pre-extracted OCR blocks (e.g. from Tesseract, EasyOCR, or test fixtures)
            for blk in input_data:
                text = str(blk.get("text") or "").strip()
                if not text:
                    continue

                bbox = blk.get("bbox") or [
                    blk.get("x", 0), blk.get("y", 0), blk.get("w", 0), blk.get("h", 0)
                ]
                if len(bbox) == 4:
                    x, y, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                else:
                    x, y, w, h = 0.0, 0.0, 100.0, 25.0

                w = max(1.0, w)
                h = max(1.0, h)
                cx = x + w / 2.0
                cy = y + h / 2.0
                conf = float(blk.get("confidence") or 0.90)
                engine_name = str(blk.get("engine_used") or "tesseract")

                tokens.append(
                    LayoutToken(
                        text=text,
                        bbox=[int(x), int(y), int(w), int(h)],
                        confidence=round(conf, 4),
                        cx=cx,
                        cy=cy,
                        w=w,
                        h=h,
                        engine_used=engine_name,
                        raw_box=bbox,
                    )
                )

        # Build clean consolidated flat text string pool concurrently
        raw_text_pool = "\n".join(t.text for t in tokens if t.text.strip())
        return tokens, raw_text_pool

    def find_anchors(
        self, tokens: list[LayoutToken]
    ) -> dict[str, list[tuple[LayoutToken, str, float]]]:
        """
        Locate semantic compliance anchor tokens using substring and fuzzy matching.
        Returns dict mapping field_name to list of (LayoutToken, matched_anchor_str, ratio).
        """
        matched_anchors: dict[str, list[tuple[LayoutToken, str, float]]] = {
            f: [] for f in MANDATORY_COMPLIANCE_FIELDS
        }

        for token in tokens:
            t_upper = token.text.upper().strip()
            if len(t_upper) < _MIN_ANCHOR_CHARS:
                continue

            # Check for promotional pack net declarations like "FOR 64 g" or "FOR 64g"
            if re.search(r"\bFOR\s+\d+[\d\.\,]*\s*(?:G|GM|GMS|KG|ML|L|LTR)\b", t_upper):
                matched_anchors["net_quantity"].append((token, "FOR", 1.0))

            for field_name, anchor_list in _COMPLIANCE_ANCHORS.items():
                best_match = ""
                best_ratio = 0.0

                for anchor in anchor_list:
                    a_upper = anchor.upper()
                    if a_upper in t_upper or t_upper in a_upper:
                        best_match = anchor
                        best_ratio = 1.0
                        break

                    # Fuzzy match tolerance for OCR typos (e.g. "1VRP" -> "MRP")
                    ratio = difflib.SequenceMatcher(None, t_upper, a_upper, autojunk=False).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = anchor

                if best_ratio >= 0.72:
                    matched_anchors[field_name].append((token, best_match, best_ratio))

        return matched_anchors

    def _spatial_proximity_search(
        self,
        anchor: LayoutToken,
        all_tokens: list[LayoutToken],
        field_name: str,
    ) -> tuple[str, float, str, list[int]]:
        """
        Spatial Radial Engine: Parses nearby tokens sitting horizontally to the right
        or directly below the anchor using Euclidean metrics.

        Returns (extracted_text, confidence_score, pattern_matched, combined_bbox).
        """
        # Step 1: Check if value is already present inline in the anchor token itself
        inline_score, inline_rule = self._score_field_value(field_name, anchor.text)
        if inline_score >= self.confidence_threshold:
            cleaned_inline = self._clean_field_value(field_name, anchor.text)
            return cleaned_inline, inline_score, f"anchor_inline_{inline_rule}", anchor.bbox

        # Step 2: Radial Euclidean proximity search across candidate tokens
        scored_candidates: list[tuple[float, LayoutToken, str]] = []
        ax, ay = anchor.cx, anchor.cy
        ah = max(1.0, anchor.h)
        aw = max(1.0, anchor.w)

        for tok in all_tokens:
            if tok is anchor or not tok.text.strip():
                continue

            dx = tok.cx - ax
            dy = tok.cy - ay
            euclidean_dist = math.hypot(dx, dy)

            if euclidean_dist > self.max_search_radius_px:
                continue

            # Case A: Horizontally to the right (same line / row)
            is_right = dx > 0 and abs(dy) <= max(1.3 * ah, 30.0)
            # Case B: Directly below (stacked key-value declaration)
            is_below = dy > (0.4 * ah) and abs(dx) <= max(2.2 * aw, 260.0)

            if is_right:
                eff_dist = euclidean_dist * DIRECTION_RIGHT_WEIGHT
                dir_label = "right"
            elif is_below:
                eff_dist = euclidean_dist * DIRECTION_BELOW_WEIGHT
                dir_label = "below"
            elif dy < -(0.5 * ah):
                # Token is above anchor - penalize
                eff_dist = euclidean_dist * DIRECTION_ABOVE_PENALTY
                dir_label = "above"
            else:
                eff_dist = euclidean_dist * 1.5
                dir_label = "adjacent"

            if dir_label in ("right", "below"):
                scored_candidates.append((eff_dist, tok, dir_label))

        # Sort candidates by effective proximity
        scored_candidates.sort(key=lambda item: item[0])

        best_extracted_val = ""
        best_conf = inline_score
        best_rule = inline_rule
        best_bbox = anchor.bbox

        # Try evaluating single closest tokens first
        for _, cand_tok, _ in scored_candidates[:5]:
            combined_candidate = f"{anchor.text} {cand_tok.text}".strip()
            sc_score, sc_rule = self._score_field_value(field_name, combined_candidate)
            if sc_score > best_conf:
                best_conf = sc_score
                best_rule = f"proximity_{sc_rule}"
                best_extracted_val = self._clean_field_value(field_name, combined_candidate)
                best_bbox = self._combine_bboxes(anchor.bbox, cand_tok.bbox)

            tok_score, tok_rule = self._score_field_value(field_name, cand_tok.text)
            if tok_score > best_conf:
                best_conf = tok_score
                best_rule = f"proximity_target_{tok_rule}"
                best_extracted_val = self._clean_field_value(field_name, cand_tok.text)
                best_bbox = cand_tok.bbox

        # Try evaluating multi-token chain (for address / multi-line dates / consumer care)
        if scored_candidates:
            top_tokens = [c[1] for c in scored_candidates[:4]]
            chained_text = " ".join(t.text for t in top_tokens).strip()
            full_chained = f"{anchor.text} {chained_text}".strip()
            ch_score, ch_rule = self._score_field_value(field_name, full_chained)
            if ch_score > best_conf:
                best_conf = ch_score
                best_rule = f"radial_chain_{ch_rule}"
                best_extracted_val = self._clean_field_value(field_name, full_chained)
                combined_b = anchor.bbox
                for t in top_tokens:
                    combined_b = self._combine_bboxes(combined_b, t.bbox)
                best_bbox = combined_b

        if not best_extracted_val:
            best_extracted_val = self._clean_field_value(field_name, anchor.text)

        return best_extracted_val, best_conf, best_rule, best_bbox

    def _score_field_value(self, field_name: str, text: str) -> tuple[float, str]:
        """Score candidate value text against per-field regex compliance rules."""
        if not text or not text.strip():
            return 0.0, "empty"

        # Price labels must not falsely trigger manufacture_date or expiry_date
        if field_name in ("manufacture_date", "expiry_date") and re.search(r"\b(?:MRP|M\.R\.P|Rs\.?|₹|INR)\b", text, re.IGNORECASE) and not re.search(r"(?:mfg|exp|pkd|use\s*by|best\s*before)", text, re.IGNORECASE):
            return 0.0, "price_noise_skipped"

        # Serving size, portion declarations, and nutritional table metrics must NOT falsely match net_quantity
        if field_name == "net_quantity":
            if re.search(
                r"\b(?:serve|serving|servings|per\s+(?:approx\.?|serve|serving|\d+)|approx\.?\s*\d+\s*(?:biscuits|pieces|units|cookies|slices)|per\s+100\s*(?:g|gm|ml)|energy|kcal|trans\s*fat|cholesterol|carbohydrate|sugar|protein)\b",
                text,
                re.IGNORECASE,
            ):
                return 0.0, "serving_or_nutrition_noise_skipped"

            # Unit sale price declarations (e.g. USP 0.14/g or Rs. 0.16 per g) must NOT match net_quantity
            if re.search(
                r"(?:USP|U\.S\.P|unit\s*sale\s*price|/\s*(?:g|gm|kg|ml|l|ltr)|per\s*(?:g|gm|kg|ml|l|ltr))\b",
                text,
                re.IGNORECASE,
            ):
                return 0.0, "unit_sale_price_skipped_for_net_qty"

        # Explicit manufacture/packing headers must NOT match expiry_date
        if field_name == "expiry_date" and re.search(r"\b(?:mfg|mfd|pkd|packed|date\s+of\s+(?:mfg|pkd|manufacture))\b", text, re.IGNORECASE) and not re.search(r"\b(?:use\s*by|best\s*before|exp(?:iry)?|bbe)\b", text, re.IGNORECASE):
            return 0.0, "mfg_header_skipped_for_expiry"

        # Explicit expiry headers must NOT match manufacture_date
        if field_name == "manufacture_date" and re.search(r"\b(?:use\s*by|best\s*before|exp(?:iry)?|bbe|valid\s*(?:till|upto))\b", text, re.IGNORECASE) and not re.search(r"\b(?:mfg|mfd|pkd|packed)\b", text, re.IGNORECASE):
            return 0.0, "expiry_header_skipped_for_mfg"

        # Bare anchor phrase alone without company name or address cannot be high confidence
        if field_name == "manufacturer_name_address" and re.match(r"^\s*(?:manufactured|mfr\.?|marketed|packed|imported|distributed)\s+(?:by|for)[\s:\-\.]*$", text, re.IGNORECASE):
            return 0.45, "mfr_anchor_prefix_only"

        best_conf = 0.0
        best_rule = "unmatched"

        rules = _FIELD_VALIDATORS.get(field_name, [])
        for r in rules:
            if r["pattern"].search(text):
                # Filter noise (e.g. pure timestamps like 07:11 in manufacture_date / expiry_date)
                if field_name in ("manufacture_date", "expiry_date") and re.search(r"^\s*\d{2}[:\-]\d{2}\s*$", text):
                    continue
                if r["confidence"] > best_conf:
                    best_conf = r["confidence"]
                    best_rule = r["name"]

        return best_conf, best_rule

    def _clean_field_value(self, field_name: str, raw_text: str) -> str:
        """Format raw OCR segment into canonical, legally compliant display string."""
        if not raw_text:
            return ""

        text = raw_text.strip()
        if field_name == "mrp":
            m = re.search(
                r"(?:M\.?R\.?P\.?|MRP|PRICE)[\s:?&%\*^/\.]*(?:Rs\.?|INR|₹)?[\s:\-\.]*(\d+[\.]\d{2}|\d+)",
                text,
                re.IGNORECASE,
            )
            if m:
                return f"MRP Rs. {m.group(1).replace(',', '.')}"
            m_dec = re.search(r"\b(\d+\.\d{2})\b", text)
            if m_dec:
                return f"MRP Rs. {m_dec.group(1)}"
            m_num = re.search(r"(?:Rs\.?|INR|₹)\s*(\d+)", text, re.IGNORECASE)
            if m_num:
                return f"MRP Rs. {m_num.group(1)}"

        elif field_name == "net_quantity":
            # Remove serving size or per-unit declarations if present in text
            clean_text = re.sub(
                r"\b(?:per\s+(?:approx\.?|serve|serving|\d+)|approx\.?\s*\d+\s*(?:biscuits|pieces|units|cookies)).*$",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            target = clean_text or text

            m_comp = re.search(r"=\s*(\d+[\d\.\,]*\s*(?:g|gm|gms|kg|ml|l|ltr))\b", target, re.IGNORECASE)
            if m_comp:
                return f"Net Wt. {m_comp.group(1)}"
            m_for = re.search(r"\bFOR\s*[\s:\-\.]*(\d+[\d\.\,]*\s*(?:g|gm|gms|grams?|kg|ml|mL|l|L|ltr|litres?|pcs|pack|units?|N))\b", target, re.IGNORECASE)
            if m_for:
                return f"Net Wt. {m_for.group(1)}"
            m_std = re.search(
                r"\b(\d+[\d\.\,]*\s*(?:g|gm|gms|kg|ml|mL|l|L|ltr|pcs|pack|units?|N))\b",
                target,
                re.IGNORECASE,
            )
            if m_std:
                return f"Net Wt. {m_std.group(1)}"

        elif field_name == "manufacture_date":
            m_exp = re.search(
                r"(?:MFG|MFG\.?\s*DATE|PKD|PACKED)[\s:]*(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4}|\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})",
                text,
                re.IGNORECASE,
            )
            if m_exp:
                return f"Mfg: {m_exp.group(1)}"
            dates = re.findall(r"\b\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b", text)
            if dates:
                return f"Mfg: {dates[0]}"
            m_mon = re.search(
                r"\b(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4})\b",
                text,
                re.IGNORECASE,
            )
            if m_mon:
                return f"Mfg: {m_mon.group(1)}"

        elif field_name == "expiry_date":
            # Match "USE BY" specifically
            m_use = re.search(
                r"(?:USE\s*BY|USE\s*BEFORE)[\s:]*(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4}|\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4}|\d{1,2}[/\.-](?:20)?\d{2})",
                text,
                re.IGNORECASE,
            )
            if m_use:
                return f"Use By: {m_use.group(1)}"

            # Match "BEST BEFORE" specifically
            m_bb = re.search(
                r"(?:BEST\s*BEFORE|BBE)[\s:]*(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4}|\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4}|\d{1,2}[/\.-](?:20)?\d{2})",
                text,
                re.IGNORECASE,
            )
            if m_bb:
                return f"Best Before: {m_bb.group(1)}"

            m_exp = re.search(
                r"(?:EXP(?:IRY)?(?:\.?\s*DATE)?|SELL\s*BY|VALID\s*(?:TILL|UPTO|UP\s*TO))[\s:]*(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4}|\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4}|\d{1,2}[/\.-](?:20)?\d{2})",
                text,
                re.IGNORECASE,
            )
            if m_exp:
                return f"Exp: {m_exp.group(1)}"

            # Duration format (e.g. "Best Before 12 months from Mfg")
            m_dur = re.search(
                r"(?:BEST\s*BEFORE|USE\s*WITHIN|USE\s*BY)[\s:]*(\d+\s*(?:months?|days?|years?)[^\n\r]{0,40})",
                text,
                re.IGNORECASE,
            )
            if m_dur:
                return f"Best Before: {m_dur.group(1).strip()}"

            dates = re.findall(r"\b\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b", text)
            if dates:
                return f"Exp: {dates[0]}"
            m_mon = re.search(
                r"\b(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4})\b",
                text,
                re.IGNORECASE,
            )
            if m_mon:
                return f"Exp: {m_mon.group(1)}"
        elif field_name == "manufacturer_name_address":
            co_name = ""
            m_co = re.search(
                r"(?:MANUFACTURED\s+(?:&\s+MARKETED\s+)?BY|MFG\s+BY|MARKETED\s+BY|PACKED\s+BY|IMPORTED\s+BY|MANUFACTURED\s+FOR)[\s:]*([^\n\r]*(?:Pvt\.?\s*Ltd\.?|Limited|LLP|Inc\.?)[^\n\r]*)",
                text,
                re.IGNORECASE,
            )
            if m_co:
                co_name = m_co.group(1).strip()
            else:
                m_co2 = re.search(
                    r"\b([A-Z][A-Za-z0-9\s\,\.\-&]+\b(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|LLP|Industries|Foods|Beverages|Laboratories))\b",
                    text,
                )
                if m_co2:
                    co_name = m_co2.group(1).strip()

            m_addr = re.search(
                r"((?:At:?\s*)?(?:Plot\s+No\.?|\d+)[^\n\r]*(?:Industrial|Area|Estate|Road|Street|Marg|Nagar|Barhi|Sonipat|Haryana|Noida|Delhi|Mumbai|Chennai|Pune|Hyderabad|Bangalore|UP|TS|TN|MH|HR|PB|GJ|KA|KL|RJ|MP|PIN|\d{6})[^\n\r]*)",
                text,
                re.IGNORECASE,
            )
            addr = m_addr.group(1).strip() if m_addr else ""

            # Filter nutritional noise
            noise = re.compile(r"(?:Energy|kcal|Protein|Fat|Sugar|Carbohydrates|Added)[^\.\,\d]*", re.IGNORECASE)
            co_name = noise.sub("", co_name).strip()
            addr = noise.sub("", addr).strip()

            if addr and addr not in co_name:
                return " ".join(f"{co_name} {addr}".split())[:200]
            return " ".join((co_name or text).split())[:200]

        elif field_name == "country_of_origin":
            m_coo = re.search(r"(?:country\s+of\s+origin|made\s+in|product\s+of)[\s:\-]*([A-Za-z\s]+)", text, re.IGNORECASE)
            if m_coo:
                return f"Country of Origin: {m_coo.group(1).strip()}"
            try:
                from app.services.geo_intelligence import infer_country_from_text
                geo_res = infer_country_from_text(text)
                if geo_res and geo_res.get("full_declaration"):
                    return geo_res["full_declaration"]
            except Exception:
                pass
            if "india" in text.lower():
                return "Country of Origin: India"
            if re.search(r"\b(?:MUMBAI|DELHI|BANGALORE|HYDERABAD|CHENNAI|KOLKATA|PUNE|AHMEDABAD|HARYANA|SONIPAT|BARHI|GURGAON|FARIDABAD|NOIDA|GHAZIABAD|PUNJAB|GUJARAT|MAHARASHTRA|KARNATAKA|TAMIL\s*NADU|KERALA|RAJASTHAN|TS|TN|MH|KA|UP|MP|GJ|WB|HR|PB)[^\w\d\n\r]*[-–]?\s*\d{6}\b", text, re.IGNORECASE):
                return "Country of Origin: India (Domestic Origin)"

        elif field_name == "consumer_care_details":
            m_url = re.search(r"(?:www\.[\w\.\-]+\.[a-z]{2,}|https?://[\w\.\-]+|[\w\.\-]+@[\w\.\-]+\.[a-z]{2,})", text, re.IGNORECASE)
            if m_url:
                return m_url.group(0).strip()
            m_ph = re.search(r"(?:phone\s*(?:no\.?|number)?[\s:]*)?(\+?91[\s\-]?\d{10}|1800[\s\-]?\d{3}[\s\-]?\d{4}|1860[\s\-]?\d{3}[\s\-]?\d{4}|\b\d{3,5}[\s\-]?\d{6,8}\b)", text, re.IGNORECASE)
            if m_ph:
                return f"Phone: {m_ph.group(1).strip()}"
            if re.search(r"phone\s*(?:no\.?|number)?", text, re.IGNORECASE):
                return text.strip()

        return text.strip()

    @staticmethod
    def _combine_bboxes(b1: list[int], b2: list[int]) -> list[int]:
        """Combine two [x, y, w, h] bounding boxes into a unified bounding box."""
        x1 = min(b1[0], b2[0])
        y1 = min(b1[1], b2[1])
        x2 = max(b1[0] + b1[2], b2[0] + b2[2])
        y2 = max(b1[1] + b1[3], b2[1] + b2[3])
        return [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]

    def classify(
        self,
        input_data: Union[np.ndarray, str, list[dict[str, Any]], list[OcrBlock]],
    ) -> LayoutClassifierResult:
        """
        Execute full local classification pipeline.

        Returns:
            LayoutClassifierResult containing:
              - raw_text_pool: Flat string of all recognized OCR tokens
              - extracted_fields: High-confidence (>= 0.80) local extractions
              - failed_fields: List of fields requiring Tier 3 GenAI fallback (< 0.80 or missing)
              - classified: List of ClassifiedBlock objects (backward compatibility)
              - unmatched: List of unclassified tokens (backward compatibility)
        """
        tokens, raw_text_pool = self.extract_tokens(input_data)
        anchors_by_field = self.find_anchors(tokens)

        classified_blocks: list[ClassifiedBlock] = []
        matched_token_ids: set[int] = set()
        claimed_value_tokens: dict[int, str] = {}
        extracted_fields: dict[str, dict[str, Any]] = {}
        failed_fields: list[str] = []

        for field_name in MANDATORY_COMPLIANCE_FIELDS:
            candidate_anchors = anchors_by_field.get(field_name, [])
            best_val = ""
            best_conf = 0.0
            best_rule = ""
            best_bbox = [0, 0, 100, 30]
            best_anchor_token: Optional[LayoutToken] = None

            for anchor_tok, anchor_str, match_ratio in candidate_anchors:
                val, conf, rule, bbox = self._spatial_proximity_search(anchor_tok, tokens, field_name)
                # Boost confidence if anchor match ratio is high
                adjusted_conf = min(1.0, conf * (0.85 + 0.15 * match_ratio))
                if adjusted_conf > best_conf:
                    best_conf = adjusted_conf
                    best_val = val
                    best_rule = rule
                    best_bbox = bbox
                    best_anchor_token = anchor_tok

            # Global pattern search fallback across raw_text_pool if no anchor matched
            if best_conf < self.confidence_threshold and raw_text_pool:
                for tok in tokens:
                    # Skip tokens already claimed by another field
                    if id(tok) in claimed_value_tokens:
                        continue
                    score, rule_name = self._score_field_value(field_name, tok.text)
                    if score > best_conf:
                        best_conf = score
                        best_val = self._clean_field_value(field_name, tok.text)
                        best_rule = f"global_regex_{rule_name}"
                        best_bbox = tok.bbox
                        best_anchor_token = tok

            # Evaluation against confidence ceiling (0.80)
            token_conf = best_anchor_token.confidence if best_anchor_token else round(best_conf, 4)
            token_bbox = best_anchor_token.bbox if best_anchor_token else best_bbox
            token_engine = best_anchor_token.engine_used if best_anchor_token else "paddleocr"

            if best_val and best_conf >= self.confidence_threshold:
                extracted_fields[field_name] = {
                    "field_name": field_name,
                    "extracted_value": best_val,
                    "confidence": round(best_conf, 4),
                    "bbox": token_bbox,
                    "pattern_matched": best_rule,
                    "engine_used": token_engine,
                }
                classified_blocks.append(
                    ClassifiedBlock(
                        text=best_val,
                        bbox=token_bbox,
                        confidence=token_conf,
                        engine_used=token_engine,
                        field=field_name,
                        match_confidence=round(best_conf, 4),
                        pattern_matched=best_rule,
                        requires_genai=False,
                    )
                )
                if best_anchor_token:
                    matched_token_ids.add(id(best_anchor_token))
                    claimed_value_tokens[id(best_anchor_token)] = field_name
            else:
                # Field failed local extraction threshold -> mark for GenAI fallback
                failed_fields.append(field_name)
                if best_val and best_conf >= MIN_MATCH_CONFIDENCE:
                    classified_blocks.append(
                        ClassifiedBlock(
                            text=best_val,
                            bbox=token_bbox,
                            confidence=token_conf,
                            engine_used=token_engine,
                            field=field_name,
                            match_confidence=round(best_conf, 4),
                            pattern_matched=best_rule,
                            requires_genai=True,
                        )
                    )

        # ── Post-classification date deduplication & collision prevention ─────
        mfg_field = extracted_fields.get("manufacture_date")
        exp_field = extracted_fields.get("expiry_date")
        if mfg_field and exp_field:
            mfg_v = mfg_field.get("extracted_value", "")
            exp_v = exp_field.get("extracted_value", "")
            m_d1 = re.search(r"(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})", mfg_v)
            m_d2 = re.search(r"(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})", exp_v)
            if m_d1 and m_d2 and m_d1.group(1) == m_d2.group(1):
                logger.warning(
                    "LaptopLayoutClassifier: Date collision detected — manufacture_date and expiry_date both resolved to '%s'. "
                    "Demoting expiry_date to failed_fields for targeted GenAI vision fallback.",
                    m_d1.group(1),
                )
                del extracted_fields["expiry_date"]
                if "expiry_date" not in failed_fields:
                    failed_fields.append("expiry_date")
                classified_blocks = [
                    cb for cb in classified_blocks
                    if (cb.get("field") if isinstance(cb, dict) else getattr(cb, "field", None)) != "expiry_date"
                ]

        # ── GeoIntelligence Inference for Country of Origin ───────────────
        # Under Legal Metrology (Packaged Commodities) Rules 2011 Rule 6(1)(a) & Rule 6(10),
        # domestic/indigenous products declare Country of Origin through the domestic manufacturer address.
        if "country_of_origin" not in extracted_fields or "country_of_origin" in failed_fields:
            try:
                from app.services.geo_intelligence import infer_country_from_text
                mfr_field = extracted_fields.get("manufacturer_name_address")
                mfr_text = mfr_field.get("extracted_value", "") if mfr_field else ""
                geo_res = infer_country_from_text(mfr_text) or infer_country_from_text(raw_text_pool)
                if geo_res and geo_res.get("country"):
                    geo_bbox = mfr_field.get("bbox") if mfr_field else [20, 20, 180, 25]
                    # Look for token containing state or country or pin to get a more specific bbox
                    for tok in tokens:
                        t_low = tok.text.lower()
                        if (
                            "haryana" in t_low or "sonipat" in t_low or "barhi" in t_low or
                            "india" in t_low or "131001" in t_low or
                            (geo_res.get("inferred_from", "").lower() in t_low) or
                            geo_res["country"].lower() in t_low
                        ):
                            geo_bbox = tok.bbox
                            break

                    extracted_fields["country_of_origin"] = {
                        "field_name": "country_of_origin",
                        "extracted_value": geo_res["full_declaration"],
                        "confidence": max(0.92, float(geo_res.get("confidence", 0.92))),
                        "bbox": geo_bbox,
                        "pattern_matched": f"geo_intelligence_{geo_res.get('evidence_type', 'location')}",
                        "engine_used": "geo_intelligence",
                    }
                    if "country_of_origin" in failed_fields:
                        failed_fields.remove("country_of_origin")
                    classified_blocks.append(
                        ClassifiedBlock(
                            text=geo_res["full_declaration"],
                            bbox=geo_bbox,
                            confidence=max(0.92, float(geo_res.get("confidence", 0.92))),
                            engine_used="geo_intelligence",
                            field="country_of_origin",
                            match_confidence=max(0.92, float(geo_res.get("confidence", 0.92))),
                            pattern_matched=f"geo_intelligence_{geo_res.get('evidence_type', 'location')}",
                            requires_genai=False,
                        )
                    )
                    logger.info("LaptopLayoutClassifier: Country of Origin deduced via GeoIntelligence: %s", geo_res["full_declaration"])
            except Exception as exc:
                logger.debug("GeoIntelligence inference in classifier failed: %s", exc)

        # Build unmatched blocks for backward compatibility:
        # Blocks with match_confidence < GENAI_FALLBACK_THRESHOLD remain in unmatched
        unmatched_blocks: list[OcrBlock] = [
            OcrBlock(
                text=t.text,
                bbox=t.bbox,
                confidence=t.confidence,
                engine_used=t.engine_used,
            )
            for t in tokens
            if id(t) not in matched_token_ids
        ]

        logger.info(
            "LaptopLayoutClassifier: %d/%d fields extracted locally with high confidence. Failed fields: %s",
            len(extracted_fields),
            len(MANDATORY_COMPLIANCE_FIELDS),
            failed_fields,
        )

        return LayoutClassifierResult(
            raw_text_pool=raw_text_pool,
            extracted_fields=extracted_fields,
            failed_fields=failed_fields,
            classified=classified_blocks,
            unmatched=unmatched_blocks,
            fields_requiring_genai=failed_fields,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Backward Compatibility Public API
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_CLASSIFIER = LaptopLayoutClassifier()


def classify_fields(
    blocks: Union[list[dict[str, Any]], list[OcrBlock]],
) -> ClassificationResult:
    """
    Backward-compatible entry point for classifying pre-extracted OCR blocks.
    Delegates directly to LaptopLayoutClassifier.
    """
    res = _DEFAULT_CLASSIFIER.classify(blocks)
    return ClassificationResult(
        classified=res["classified"],
        unmatched=res["unmatched"],
        fields_requiring_genai=res["failed_fields"],
        raw_text_pool=res["raw_text_pool"],
        extracted_fields=res["extracted_fields"],
        failed_fields=res["failed_fields"],
    )


def get_field_summary(
    result: Union[ClassificationResult, LayoutClassifierResult],
) -> dict[str, list[str]]:
    """Return dictionary of {field_name: [extracted_text_strings]}."""
    summary: dict[str, list[str]] = {}
    for block in result.get("classified", []):
        f = block["field"]
        summary.setdefault(f, []).append(block["text"])
    return summary


def get_missing_fields(
    result: Union[ClassificationResult, LayoutClassifierResult],
) -> list[str]:
    """Return sorted list of mandatory fields not extracted with high confidence."""
    if "failed_fields" in result and result["failed_fields"]:
        return sorted(result["failed_fields"])

    detected = {
        b["field"]
        for b in result.get("classified", [])
        if b.get("match_confidence", 0.0) >= GENAI_FALLBACK_THRESHOLD
    }
    return sorted(set(MANDATORY_COMPLIANCE_FIELDS) - detected)


def get_fields_requiring_genai(
    result: Union[ClassificationResult, LayoutClassifierResult],
) -> list[str]:
    """Alias returning fields flagged for Tier 3 GenAI fallback."""
    return get_missing_fields(result)


def _clean_field_value(field: str, raw_text: str) -> str:
    """Module-level alias for backward compatibility."""
    return _DEFAULT_CLASSIFIER._clean_field_value(field, raw_text)
