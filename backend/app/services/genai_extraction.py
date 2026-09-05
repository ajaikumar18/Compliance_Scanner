"""
GenAI Extraction Service
========================
OpenRouter Vision Extraction Engine for Indian Legal Metrology compliance.
Uses OpenRouter API (google/gemini-2.5-flash or any vision model) as the sole
cloud AI provider. Gemini SDK is NOT used in any live scan path.

Key Components:
---------------
- extract_via_openrouter_sync:
    * Sends resized image (max 900px, JPEG q70) + OCR text pool to OpenRouter vision API
    * Returns structured JSON for all 6 mandatory Legal Metrology fields
    * 12s timeout; robust JSON parsing (direct → regex fallback)
- SurgicalTextFallbackEngine:
    * Text-only fallback when no image is available
    * Routes exclusively to OpenRouter (no Gemini SDK)
- Unified Result Merger:
    * Merges Tier 1 & 2 local OCR extractions with OpenRouter results
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from typing import Any, Callable, Optional, TypedDict

import requests

import cv2
import numpy as np
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default mandatory fields per Indian Legal Metrology Rules 2011 and FSSAI packaging guidelines
DEFAULT_MANDATORY_FIELDS: list[str] = [
    "manufacturer_name_address",
    "net_quantity",
    "mrp",
    "manufacture_date",
    "expiry_date",
    "consumer_care_details",
    "country_of_origin",
]


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic v2 Structured Outputs Contract
# ─────────────────────────────────────────────────────────────────────────────

class MetrologyJSONContract(BaseModel):
    """
    Pydantic v2 schema defining the strict JSON contract for Indian Legal
    Metrology (Packaged Commodities) Rules 2011 and FSSAI declarations.

    Passed directly to Gemini's Structured Outputs mechanism
    (response_mime_type='application/json' and response_schema=MetrologyJSONContract)
    to guarantee reliable, typed structure on the first attempt without formatting errors.
    """
    mrp: Optional[str] = Field(
        default=None,
        description=(
            "Maximum Retail Price inclusive of all taxes, formatted with currency symbol "
            "(e.g. 'MRP Rs. 120.00', 'Rs. 45.00', '₹ 99.00'). Disregard nutritional values. "
            "Return null if not present in the text."
        ),
    )
    net_quantity: Optional[str] = Field(
        default=None,
        description=(
            "Net weight, volume, or piece count with legal metric unit "
            "(e.g. 'Net Wt. 500 g', '1 kg', '200 ml', '1 L', '10 units', '250 g'). "
            "Return null if not present in the text."
        ),
    )
    manufacture_date: Optional[str] = Field(
        default=None,
        description=(
            "Manufacturing date, packaging date, or date of manufacture "
            "(e.g. '15/04/2026', 'Mfg Date: 12/2025', 'MAR 2026'). "
            "Disregard machine timestamps like 07:11. Return null if not present in the text."
        ),
    )
    expiry_date: Optional[str] = Field(
        default=None,
        description=(
            "Expiry date, use-by date, or best-before declaration "
            "(e.g. 'Exp: 15/04/2026', 'Use By: 15/04/26', 'Best Before: 6 months'). "
            "Return null if not present in the text."
        ),
    )
    manufacturer_name_address: Optional[str] = Field(
        default=None,
        description=(
            "Full legal name of the manufacturing, packaging, or marketing company (e.g. Pvt Ltd, Ltd, LLP) "
            "and complete postal address including state and PIN code. Return null if not present in the text."
        ),
    )
    consumer_care_details: Optional[str] = Field(
        default=None,
        description=(
            "Customer helpline phone number (e.g. toll-free 1800-xxx-xxxx), support email address, "
            "or consumer care URL. Return null if not present in the text."
        ),
    )
    country_of_origin: Optional[str] = Field(
        default=None,
        description=(
            "Country of origin declaration (e.g. 'India', 'Country of Origin: India', 'Made in India'). "
            "Return null if not present in the text."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TypedDict Return Types
# ─────────────────────────────────────────────────────────────────────────────

class GenAiExtractionResult(TypedDict):
    field_name: str
    extracted_value: str | None
    extraction_method: str
    confidence: float | str


class FieldExtraction(TypedDict):
    field_name: str
    extracted_value: str | None
    extraction_method: str
    confidence: float | str
    bbox: list[int] | None


class UnifiedExtractionResult(TypedDict):
    fields: dict[str, FieldExtraction]
    summary: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# SurgicalTextFallbackEngine (Tier 3 Low-Token Gemini Fallback)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter High-Speed Extraction Engine (Vision + Text)
# ─────────────────────────────────────────────────────────────────────────────

# Structured prompt template for Legal Metrology field extraction
_SYSTEM_INSTRUCTION = (
    "You are an expert Legal Metrology Compliance Auditor specializing in Indian Legal Metrology "
    "(Packaged Commodities) Rules 2011 and FSSAI packaging declarations.\n"
    "Extract ONLY the requested fields from the product packaging image and/or OCR text pool.\n"
    "RULES:\n"
    "1. Extract values EXACTLY as printed. Do NOT invent, guess, or hallucinate.\n"
    "2. If a field is genuinely absent or not visible, set its value to null.\n"
    "3. For MRP: look for keywords MRP, M.R.P., Rs., ₹, Incl. of all taxes.\n"
    "   Extract the numeric price. Example output: 'MRP Rs. 10.00'.\n"
    "4. For net_quantity: look for Net Wt, Net Weight, Net Content, FOR <qty>, g, gm, kg, ml, L.\n"
    "   Include units. Example: '64 g', '90 g', '500 ml', '80 g + 10 g EXTRA = 90 g'.\n"
    "   CRITICAL: Disregard serving sizes or nutritional declarations (e.g. 'Per approx. 15 g serve', 'approx 3 biscuits', 'serving size 15g').\n"
    "   Extract ONLY the total net quantity / net weight of the entire package.\n"
    "5. For manufacture_date: look for Mfg, Mfd, Pkd, Packed, Date of Mfg.\n"
    "   Include the label prefix. Example: 'Mfg: 10/2025'.\n"
    "6. For expiry_date: look for Exp, Expiry Date, Best Before, Use By, BBE, Valid Till.\n"
    "   Include the label prefix. Example: 'Exp: 06/2026', 'Use By: 15/04/26', 'Best Before: 6 months'.\n"
    "7. For manufacturer_name_address: look for Manufactured By, Mktd By, Pvt Ltd,\n"
    "   Ltd., address, pincode. Include company name AND address if both visible.\n"
    "8. For consumer_care_details: look for phone numbers (1800-, 1860-, +91-), email,\n"
    "   website, 'Consumer Care', 'Customer Care'. Return the full contact string.\n"
    "9. For country_of_origin: look for 'Made in India', 'Country of Origin: India'.\n"
    "10. Return ONLY a raw JSON object with the requested keys. No markdown, no explanation."
)

_FIELD_DESCRIPTIONS: dict[str, str] = {
    "manufacturer_name_address": "manufacturer/packer name AND full postal address with state and pincode",
    "net_quantity": "total net weight or volume of entire package with unit (e.g. '64 g', '90 g'). Disregard serving sizes like 'Per approx 15 g serve'",
    "mrp": "Maximum Retail Price inclusive of all taxes with currency (e.g. 'MRP Rs. 10.00', '₹ 45')",
    "manufacture_date": "Date of manufacture/packing as printed (e.g. 'Mfg: 10/2025', 'Pkd: 01/2026')",
    "expiry_date": "Expiry/Use By/Best Before date or duration as printed (e.g. 'Exp: 06/2026', 'Use By: 15/04/26', 'Best Before: 6 months')",
    "consumer_care_details": "consumer helpline phone, toll-free number (1800-/1860-), email, or website URL",
    "country_of_origin": "country of origin declaration (e.g. 'Made in India', 'India')",
}


def extract_via_openrouter_sync(
    missing_fields: list[str],
    image: np.ndarray | None = None,
    raw_text_pool: str = "",
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = 12.0,
) -> dict[str, Optional[str]]:
    """
    Extract missing mandatory Legal Metrology fields via OpenRouter vision/text API.

    Strategy:
    - If image is provided: send resized image (max 900px, JPEG q70) + OCR text pool
      as supplementary context alongside a structured extraction prompt.
    - If no image: send text-only extraction from raw_text_pool.
    - Robust JSON parsing: try direct json.loads first, then regex fallback.
    - Timeout: 12s (gemini-2.5-flash typically responds in ~2.5s).
    """
    if not missing_fields:
        return {}

    fallback_result: dict[str, Optional[str]] = {f: None for f in missing_fields}

    effective_key = (api_key or settings.OPENROUTER_API_KEY or "").strip()
    if not effective_key or "your_" in effective_key.lower() or len(effective_key) < 8:
        logger.info("OpenRouter API key unconfigured; skipping OpenRouter extraction.")
        return fallback_result

    target_model = (model or settings.OPENROUTER_MODEL or "google/gemini-2.5-flash").strip()
    endpoint = (settings.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/") + "/chat/completions"

    # Build structured field extraction table
    fields_table = "\n".join(
        f'  "{f}": "{_FIELD_DESCRIPTIONS.get(f, f)}"' for f in missing_fields
    )
    user_text = (
        f"EXTRACT these {len(missing_fields)} field(s) from the product packaging.\n"
        f"Return a JSON object with EXACTLY these keys (null if not found):\n"
        f"{{\n{fields_table}\n}}\n\n"
    )

    # Append OCR text pool as supplementary context (always, even when image available)
    if raw_text_pool and raw_text_pool.strip():
        user_text += (
            f"SUPPLEMENTARY OCR TEXT (use this to cross-check the image reading):\n"
            f'"""\n{raw_text_pool.strip()[:3000]}\n"""\n'
        )

    headers = {
        "Authorization": f"Bearer {effective_key}",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "labelGuard AI",
        "Content-Type": "application/json",
    }

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_INSTRUCTION},
    ]

    # Vision payload: compress to max 900px longest edge, JPEG quality 70
    if image is not None and image.size > 0:
        h, w = image.shape[:2]
        max_dim = max(h, w)
        if max_dim > 900:
            scale = 900.0 / max_dim
            prep_img = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            prep_img = image

        success_enc, buf = cv2.imencode(".jpg", prep_img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if success_enc:
            b64_img = base64.b64encode(buf.tobytes()).decode("utf-8")
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                ],
            })
        else:
            # Encoding failed — fall back to text-only
            messages.append({"role": "user", "content": user_text})
    else:
        # Text-only mode
        messages.append({"role": "user", "content": user_text})

    payload: dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.05,
        "max_tokens": 350,
    }

    try:
        t0 = time.time()
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        dur = time.time() - t0

        if resp.status_code == 200:
            data = resp.json()
            content_str = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            ) or ""
            content_str = content_str.strip()

            # Strip markdown code fences if present
            content_str = re.sub(r"^```(?:json)?\s*", "", content_str)
            content_str = re.sub(r"\s*```$", "", content_str).strip()

            # Try direct JSON parse first, then regex fallback
            parsed: dict[str, Any] | None = None
            try:
                parsed = json.loads(content_str)
            except (json.JSONDecodeError, ValueError):
                m_json = re.search(r"\{.*\}", content_str, re.DOTALL)
                if m_json:
                    try:
                        parsed = json.loads(m_json.group(0))
                    except (json.JSONDecodeError, ValueError):
                        pass

            if parsed:
                resolved = 0
                for f in missing_fields:
                    val = parsed.get(f)
                    if val is not None and str(val).strip().upper() not in (
                        "NOT_FOUND", "NONE", "NULL", "N/A", "NA", ""
                    ):
                        fallback_result[f] = str(val).strip().strip("\"'")
                        resolved += 1
                logger.info(
                    "OpenRouter (%s) resolved %d/%d fields in %.2fs",
                    target_model, resolved, len(missing_fields), dur,
                )
            else:
                logger.warning("OpenRouter returned non-parseable text in %.2fs: %s", dur, content_str[:200])

        else:
            logger.warning(
                "OpenRouter error %d in %.2fs: %s",
                resp.status_code, dur, resp.text[:300],
            )
    except requests.Timeout:
        logger.warning("OpenRouter call timed out after %.1fs", timeout)
    except Exception as exc:
        logger.warning("OpenRouter call failed: %s", exc)

    return fallback_result


async def extract_via_openrouter(
    missing_fields: list[str],
    image: np.ndarray | None = None,
    raw_text_pool: str = "",
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = 6.0,
) -> dict[str, Optional[str]]:
    """Asynchronous execution wrapper for OpenRouter extraction."""
    return await asyncio.to_thread(
        extract_via_openrouter_sync,
        missing_fields=missing_fields,
        image=image,
        raw_text_pool=raw_text_pool,
        api_key=api_key,
        model=model,
        timeout=timeout,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SurgicalTextFallbackEngine (Tier 3 Low-Token Fallback)
# ─────────────────────────────────────────────────────────────────────────────

class SurgicalTextFallbackEngine:
    """
    SurgicalTextFallbackEngine
    ===========================
    Tier 3 Text-Only Fallback Engine using OpenRouter exclusively.
    Routes to extract_via_openrouter_sync; no Gemini SDK dependency.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 12.0,
    ) -> None:
        self.api_key = api_key  # Kept for interface compatibility; not used (OpenRouter key from settings)
        self.model = model or settings.OPENROUTER_MODEL or "google/gemini-2.5-flash"
        self.timeout = timeout

    def extract_fallback_sync(
        self,
        raw_text_pool: str,
        failed_fields: list[str],
    ) -> dict[str, Optional[str]]:
        """
        Synchronously extract failed fields from unstructured OCR text pool via OpenRouter.
        """
        if not failed_fields:
            return {}

        if not raw_text_pool or not raw_text_pool.strip():
            logger.info("Empty text pool; skipping SurgicalTextFallbackEngine for %s", failed_fields)
            return {f: None for f in failed_fields}

        or_key = settings.OPENROUTER_API_KEY.strip()
        if not or_key or "your_" in or_key.lower() or len(or_key) < 8:
            logger.info("OpenRouter key not configured; skipping text fallback for %s", failed_fields)
            return {f: None for f in failed_fields}

        return extract_via_openrouter_sync(
            missing_fields=failed_fields,
            image=None,
            raw_text_pool=raw_text_pool,
            api_key=or_key,
            model=self.model,
            timeout=self.timeout,
        )

    async def extract_fallback(
        self,
        raw_text_pool: str,
        failed_fields: list[str],
    ) -> dict[str, Optional[str]]:
        """Asynchronous execution interface for FastAPI integration."""
        return await asyncio.to_thread(self.extract_fallback_sync, raw_text_pool, failed_fields)


# ─────────────────────────────────────────────────────────────────────────────
# Image Cropping Helper (Preserved for compatibility)
# ─────────────────────────────────────────────────────────────────────────────

def crop_image_region(
    image: np.ndarray,
    bbox: list[int] | None,
    padding: int = 15,
) -> np.ndarray:
    """Crop image region corresponding to bbox [x, y, w, h] with optional padding."""
    if image is None or image.size == 0:
        raise ValueError("crop_image_region received an empty or None image.")

    if not bbox or len(bbox) != 4:
        return image

    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return image

    h_img, w_img = image.shape[:2]
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(w_img, x + w + padding)
    y2 = min(h_img, y + h + padding)

    if x2 <= x1 or y2 <= y1:
        return image

    return image[y1:y2, x1:x2]


# ─────────────────────────────────────────────────────────────────────────────
# Single Field GenAI Extraction (Preserved with Mock & Text Fallback Support)
# ─────────────────────────────────────────────────────────────────────────────

def extract_field_via_genai(
    image: np.ndarray,
    field_name: str,
    bbox: list[int] | None = None,
    api_key: str | None = None,
    provider: str | None = None,
    mock_fn: Callable[[str, np.ndarray], str] | None = None,
) -> GenAiExtractionResult:
    """
    Extract a single product label field. Uses mock_fn if provided, or routes
    through fallback engine. Raises ValueError if image is empty.
    """
    if image is None or image.size == 0:
        raise ValueError("extract_field_via_genai received an empty or None image.")

    crop = crop_image_region(image, bbox)

    if mock_fn is not None:
        raw_response = mock_fn(field_name, crop)
        cleaned = raw_response.strip() if raw_response else ""
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip("`\"'\n ")

        if not cleaned or "NOT_FOUND" in cleaned.upper():
            return GenAiExtractionResult(
                field_name=field_name,
                extracted_value=None,
                extraction_method="genai_fallback",
                confidence=0.0,
            )

        return GenAiExtractionResult(
            field_name=field_name,
            extracted_value=cleaned,
            extraction_method="genai_fallback",
            confidence=0.85,
        )

    # Production path: text fallback engine
    engine = SurgicalTextFallbackEngine(api_key=api_key)
    res = engine.extract_fallback_sync(raw_text_pool="", failed_fields=[field_name])
    val = res.get(field_name)

    return GenAiExtractionResult(
        field_name=field_name,
        extracted_value=val,
        extraction_method="genai_fallback",
        confidence=0.90 if val else 0.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Unified Result Merger
# ─────────────────────────────────────────────────────────────────────────────

def _map_ocr_engine_method(engine_used: str) -> str:
    """Map OCR engine string to canonical extraction_method."""
    engine_lower = engine_used.lower()
    if "easyocr" in engine_lower:
        return "ocr_easyocr"
    if "paddle" in engine_lower:
        return "ocr_paddle"
    return "ocr_tesseract"


def merge_ocr_and_genai_results(
    image: np.ndarray,
    classified_blocks: list[dict[str, Any]],
    unmatched_blocks: list[dict[str, Any]],
    mandatory_fields: list[str] | None = None,
    api_key: str | None = None,
    mock_fn: Callable[[str, np.ndarray], str] | None = None,
    raw_text_pool: str | None = None,
    skip_genai: bool = False,
) -> UnifiedExtractionResult:
    """
    Merge Tier 1 & 2 local OCR extractions with Tier 3 surgical text fallback
    into a unified per-product compliance structure.
    """
    fields_to_check = mandatory_fields or DEFAULT_MANDATORY_FIELDS
    unified_fields: dict[str, FieldExtraction] = {}

    ocr_by_field: dict[str, list[dict[str, Any]]] = {}
    for block in classified_blocks:
        f_name = block.get("field")
        if f_name:
            ocr_by_field.setdefault(f_name, []).append(block)

    all_blocks = classified_blocks + unmatched_blocks

    # 1. Map confident local extractions (match_confidence >= 0.60)
    for field in fields_to_check:
        candidates = ocr_by_field.get(field, [])
        high_conf = [
            b for b in candidates
            if (b.get("match_confidence") or b.get("confidence") or 0.0) >= 0.60
        ]

        cleaned_text = None
        best_block = None

        if field == "mrp":
            for b in all_blocks:
                txt = str(b.get("text") or "")
                m = re.search(
                    r"(?:M[\.\s\w]*R[\.\s\w]*P|MRP|PRICE|RS\.?)[\s:₹\?&%\*^/\.]*(?:Rs\.?|₹|INR)?[\s:\-\.]*(\d+[\.\,]\d{2})",
                    txt,
                    re.IGNORECASE,
                )
                if m:
                    cleaned_text = f"MRP Rs. {m.group(1)}"
                    best_block = b
                    break
                m2 = re.search(r"\b(\d+[\.\,]\d{2})\b", txt)
                if m2:
                    try:
                        if float(m2.group(1).replace(",", ".")) > 1.0:
                            cleaned_text = f"MRP Rs. {m2.group(1)}"
                            best_block = b
                            break
                    except ValueError:
                        pass

        elif field == "manufacturer_name_address":
            co_name = ""
            addr = ""
            co_block = None
            for b in all_blocks:
                txt = str(b.get("text") or "").strip()
                if not co_name:
                    m_co = re.search(
                        r"\b([A-Z][A-Za-z0-9\s\,\.\-&]+\b(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|LLP|Industries|Foods))\b",
                        txt,
                    )
                    if m_co:
                        co_name = m_co.group(1).strip()
                        co_block = b
                if not addr:
                    m_addr = re.search(
                        r"(\d+[\w\s\,\.\-]+\b(?:Industrial|Area|Road|Street|Noida|Delhi|Mumbai|UP|PIN|\d{6})\b[^\n\r]*)",
                        txt,
                        re.IGNORECASE,
                    )
                    if m_addr and "kcal" not in txt.lower():
                        raw_addr = m_addr.group(1).strip()
                        addr = re.sub(r"^\d+[\.\,]\d+\s*", "", raw_addr).strip()

            if co_name and addr:
                cleaned_text = f"{co_name} {addr}".strip()
                best_block = co_block
            elif co_name:
                cleaned_text = co_name
                best_block = co_block

        if not cleaned_text and high_conf:
            best_block = max(
                high_conf,
                key=lambda b: float(b.get("match_confidence") or b.get("confidence") or 0.0),
            )
            cleaned_text = str(best_block.get("text") or "").strip()

        if cleaned_text and best_block:
            method = _map_ocr_engine_method(best_block.get("engine_used", "tesseract"))
            unified_fields[field] = FieldExtraction(
                field_name=field,
                extracted_value=cleaned_text,
                extraction_method=method,
                confidence=float(best_block.get("match_confidence") or best_block.get("confidence") or 0.90),
                bbox=best_block.get("bbox"),
            )

    # 2. Identify missing fields requiring Tier 3 fallback
    missing_fields = [f for f in fields_to_check if f not in unified_fields]

    # 3. Trigger Tier 3 Surgical Text Fallback
    if missing_fields and not skip_genai:
        if mock_fn is not None:
            for mf in missing_fields:
                low_conf = ocr_by_field.get(mf, [None])[0]
                target_bbox = low_conf.get("bbox") if low_conf else None
                genai_res = extract_field_via_genai(
                    image=image,
                    field_name=mf,
                    bbox=target_bbox,
                    api_key=api_key,
                    mock_fn=mock_fn,
                )
                if genai_res["extracted_value"] is not None:
                    unified_fields[mf] = FieldExtraction(
                        field_name=mf,
                        extracted_value=genai_res["extracted_value"],
                        extraction_method="genai_fallback",
                        confidence=genai_res["confidence"],
                        bbox=target_bbox,
                    )
        else:
            # Build flat text pool from OCR blocks if not explicitly provided
            pool_text = raw_text_pool or "\n".join(
                str(b.get("text") or "").strip()
                for b in (classified_blocks + unmatched_blocks)
                if str(b.get("text") or "").strip()
            )
            fallback_engine = SurgicalTextFallbackEngine(api_key=api_key)
            fallback_extractions = fallback_engine.extract_fallback_sync(pool_text, missing_fields)

            for mf, val in fallback_extractions.items():
                if val:
                    low_conf = ocr_by_field.get(mf, [None])[0]
                    unified_fields[mf] = FieldExtraction(
                        field_name=mf,
                        extracted_value=val,
                        extraction_method="genai_fallback",
                        confidence=0.92,
                        bbox=low_conf.get("bbox") if low_conf else None,
                    )

    # 4. Final pass: mark any remaining missing fields as not_found
    for field in fields_to_check:
        if field not in unified_fields:
            unified_fields[field] = FieldExtraction(
                field_name=field,
                extracted_value=None,
                extraction_method="not_found",
                confidence=0.0,
                bbox=None,
            )

    # 5. Compute summary statistics
    method_counts: dict[str, int] = {}
    for f_info in unified_fields.values():
        m = f_info["extraction_method"]
        method_counts[m] = method_counts.get(m, 0) + 1

    summary = {
        "total_fields": len(fields_to_check),
        "fields_found": sum(1 for f in unified_fields.values() if f["extracted_value"] is not None),
        "fields_missing": sum(1 for f in unified_fields.values() if f["extracted_value"] is None),
        "method_breakdown": method_counts,
    }

    return UnifiedExtractionResult(fields=unified_fields, summary=summary)
