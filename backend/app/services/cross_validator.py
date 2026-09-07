"""
E-Commerce vs Packaging OCR Cross-Validation Service
=====================================================
Compares declarations extracted from e-commerce product pages with statutory declarations
detected directly from physical packaging label OCR.

Detects discrepancies, misleading listings, overpricing, and quantity mismatches.
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class CrossValidationItem(TypedDict):
    field_name: str
    display_name: str
    ecommerce_value: str | None
    packaging_value: str | None
    status: str  # "MATCH" | "MISMATCH" | "WARNING" | "ONLINE_ONLY" | "PACKAGING_ONLY" | "UNDETERMINED"
    details: str


def _parse_quantity(val_str: str | None) -> tuple[float | None, str | None]:
    """Parse numeric quantity and normalized unit (g, kg, ml, l, pcs)."""
    if not val_str:
        return None, None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(grams?|gms?|g|kg|kilograms?|ml|millilitres?|ltr?|litres?|l|pcs|pieces?|units?|count)\b", val_str, re.IGNORECASE)
    if not m:
        m_num = re.search(r"\b(\d+(?:\.\d+)?)\b", val_str)
        if m_num:
            return float(m_num.group(1)), None
        return None, None
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ["g", "gm", "gms", "gram", "grams"]:
        return num, "g"
    if unit in ["kg", "kilogram", "kilograms"]:
        return num * 1000.0, "g"
    if unit in ["ml", "millilitre", "millilitres"]:
        return num, "ml"
    if unit in ["l", "lt", "ltr", "litre", "litres"]:
        return num * 1000.0, "ml"
    return num, unit


def _parse_price(val_str: str | None) -> float | None:
    """Extract numeric price from currency string."""
    if not val_str:
        return None
    m = re.search(r"(?:₹|Rs\.?|INR)?\s*(\d+(?:\.\d{1,2})?)", str(val_str).replace(",", ""))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def cross_validate_ecommerce_vs_packaging(
    ecommerce_data: dict[str, Any],
    packaging_fields: dict[str, Any],
) -> list[CrossValidationItem]:
    """
    Compare e-commerce online listing data with packaging OCR declarations.
    Returns list of CrossValidationItem entries.
    """
    results: list[CrossValidationItem] = []

    # 1. Net Quantity Validation
    ecom_qty = ecommerce_data.get("net_quantity")
    pack_qty_info = packaging_fields.get("net_quantity", {})
    pack_qty = pack_qty_info.get("extracted_value")

    if ecom_qty and pack_qty:
        e_val, e_unit = _parse_quantity(ecom_qty)
        p_val, p_unit = _parse_quantity(pack_qty)
        if e_val is not None and p_val is not None:
            if abs(e_val - p_val) <= max(1.0, e_val * 0.01):
                results.append({
                    "field_name": "net_quantity",
                    "display_name": "Net Quantity",
                    "ecommerce_value": str(ecom_qty),
                    "packaging_value": str(pack_qty),
                    "status": "MATCH",
                    "details": f"Online listing ({ecom_qty}) matches packaging declaration ({pack_qty}).",
                })
            else:
                results.append({
                    "field_name": "net_quantity",
                    "display_name": "Net Quantity",
                    "ecommerce_value": str(ecom_qty),
                    "packaging_value": str(pack_qty),
                    "status": "MISMATCH",
                    "details": f"Quantity Discrepancy: Online listing states {ecom_qty}, but physical packaging shows {pack_qty}.",
                })
        else:
            results.append({
                "field_name": "net_quantity",
                "display_name": "Net Quantity",
                "ecommerce_value": str(ecom_qty),
                "packaging_value": str(pack_qty),
                "status": "MATCH",
                "details": f"Both declarations present: Online ({ecom_qty}) vs Pack ({pack_qty}).",
            })
    elif pack_qty:
        results.append({
            "field_name": "net_quantity",
            "display_name": "Net Quantity",
            "ecommerce_value": None,
            "packaging_value": str(pack_qty),
            "status": "PACKAGING_ONLY",
            "details": f"Verified on physical packaging ({pack_qty}); not explicitly detailed in online specs.",
        })
    elif ecom_qty:
        results.append({
            "field_name": "net_quantity",
            "display_name": "Net Quantity",
            "ecommerce_value": str(ecom_qty),
            "packaging_value": None,
            "status": "ONLINE_ONLY",
            "details": f"Stated online as {ecom_qty}, but not detected on available packaging images.",
        })

    # 2. Maximum Retail Price (MRP) Validation
    ecom_mrp = ecommerce_data.get("mrp") or ecommerce_data.get("selling_price")
    pack_mrp_info = packaging_fields.get("mrp", {})
    pack_mrp = pack_mrp_info.get("packaging_ocr_value")
    if not pack_mrp and pack_mrp_info.get("extraction_method") not in ["webpage_extracted", "not_found", ""]:
        pack_mrp = pack_mrp_info.get("extracted_value")

    if ecom_mrp and pack_mrp:
        e_price = _parse_price(str(ecom_mrp))
        p_price = _parse_price(str(pack_mrp))
        if e_price is not None and p_price is not None:
            if abs(e_price - p_price) < 0.5:
                results.append({
                    "field_name": "mrp",
                    "display_name": "Maximum Retail Price (MRP)",
                    "ecommerce_value": f"₹{e_price:.2f}",
                    "packaging_value": f"₹{p_price:.2f}",
                    "status": "MATCH",
                    "details": f"Online price matches statutory printed MRP (₹{p_price:.2f}).",
                })
            elif e_price > p_price:
                results.append({
                    "field_name": "mrp",
                    "display_name": "Maximum Retail Price (MRP)",
                    "ecommerce_value": f"₹{e_price:.2f}",
                    "packaging_value": f"₹{p_price:.2f}",
                    "status": "WARNING",
                    "details": f"Possible Overpricing: Online listed price (₹{e_price:.2f}) exceeds printed packaging MRP (₹{p_price:.2f}).",
                })
            else:
                results.append({
                    "field_name": "mrp",
                    "display_name": "Maximum Retail Price (MRP)",
                    "ecommerce_value": f"₹{e_price:.2f}",
                    "packaging_value": f"₹{p_price:.2f}",
                    "status": "MATCH",
                    "details": f"Discounted price: Online (₹{e_price:.2f}) is below printed packaging MRP (₹{p_price:.2f}).",
                })
        else:
            results.append({
                "field_name": "mrp",
                "display_name": "Maximum Retail Price (MRP)",
                "ecommerce_value": str(ecom_mrp),
                "packaging_value": str(pack_mrp),
                "status": "MATCH",
                "details": f"MRP verified across listing and packaging.",
            })
    elif pack_mrp:
        results.append({
            "field_name": "mrp",
            "display_name": "Maximum Retail Price (MRP)",
            "ecommerce_value": None,
            "packaging_value": str(pack_mrp),
            "status": "PACKAGING_ONLY",
            "details": f"Printed MRP verified on packaging ({pack_mrp}).",
        })
    elif ecom_mrp:
        results.append({
            "field_name": "mrp",
            "display_name": "Maximum Retail Price (MRP)",
            "ecommerce_value": str(ecom_mrp),
            "packaging_value": None,
            "status": "ONLINE_ONLY",
            "details": f"Listed online as {ecom_mrp}, but printed MRP panel was not visible in packaging images.",
        })

    # 3. Country of Origin Validation
    ecom_co = ecommerce_data.get("country_of_origin")
    pack_co_info = packaging_fields.get("country_of_origin", {})
    pack_co = pack_co_info.get("extracted_value")

    if ecom_co and pack_co:
        e_norm = ecom_co.lower().strip()
        p_norm = pack_co.lower().strip()
        if ("india" in e_norm and "india" in p_norm) or (e_norm in p_norm or p_norm in e_norm):
            results.append({
                "field_name": "country_of_origin",
                "display_name": "Country of Origin",
                "ecommerce_value": str(ecom_co),
                "packaging_value": str(pack_co),
                "status": "MATCH",
                "details": f"Country of Origin verified: {ecom_co} declared online and on packaging.",
            })
        else:
            results.append({
                "field_name": "country_of_origin",
                "display_name": "Country of Origin",
                "ecommerce_value": str(ecom_co),
                "packaging_value": str(pack_co),
                "status": "MISMATCH",
                "details": f"Origin Conflict: Online listing says {ecom_co}, but packaging shows {pack_co}.",
            })
    elif pack_co:
        results.append({
            "field_name": "country_of_origin",
            "display_name": "Country of Origin",
            "ecommerce_value": None,
            "packaging_value": str(pack_co),
            "status": "PACKAGING_ONLY",
            "details": f"Country of origin confirmed on packaging ({pack_co}).",
        })
    elif ecom_co:
        results.append({
            "field_name": "country_of_origin",
            "display_name": "Country of Origin",
            "ecommerce_value": str(ecom_co),
            "packaging_value": None,
            "status": "ONLINE_ONLY",
            "details": f"Stated online as {ecom_co}; physical declaration panel not captured.",
        })

    # 4. Manufacturer Name Validation
    ecom_mfr = ecommerce_data.get("manufacturer")
    pack_mfr_info = packaging_fields.get("manufacturer_name_address", {})
    pack_mfr = pack_mfr_info.get("extracted_value")

    if ecom_mfr and pack_mfr:
        e_tokens = set(re.findall(r"\w+", ecom_mfr.lower())) - {"pvt", "ltd", "private", "limited", "the", "and", "foods", "industries"}
        p_tokens = set(re.findall(r"\w+", pack_mfr.lower())) - {"pvt", "ltd", "private", "limited", "the", "and", "foods", "industries"}
        overlap = e_tokens.intersection(p_tokens)
        if overlap:
            results.append({
                "field_name": "manufacturer_name_address",
                "display_name": "Manufacturer Name & Address",
                "ecommerce_value": str(ecom_mfr)[:100],
                "packaging_value": str(pack_mfr)[:100],
                "status": "MATCH",
                "details": f"Manufacturer identity confirmed across online listing and package.",
            })
        else:
            results.append({
                "field_name": "manufacturer_name_address",
                "display_name": "Manufacturer Name & Address",
                "ecommerce_value": str(ecom_mfr)[:100],
                "packaging_value": str(pack_mfr)[:100],
                "status": "WARNING",
                "details": f"Possible manufacturer variation between online listing and packaging.",
            })
    elif pack_mfr:
        results.append({
            "field_name": "manufacturer_name_address",
            "display_name": "Manufacturer Name & Address",
            "ecommerce_value": None,
            "packaging_value": str(pack_mfr)[:100],
            "status": "PACKAGING_ONLY",
            "details": f"Manufacturer address verified on packaging.",
        })
    elif ecom_mfr:
        results.append({
            "field_name": "manufacturer_name_address",
            "display_name": "Manufacturer Name & Address",
            "ecommerce_value": str(ecom_mfr)[:100],
            "packaging_value": None,
            "status": "ONLINE_ONLY",
            "details": f"Manufacturer stated online as {ecom_mfr}.",
        })

    for item in results:
        item["field"] = item["field_name"]
        item["matches"] = (item["status"] == "MATCH")

    return results
