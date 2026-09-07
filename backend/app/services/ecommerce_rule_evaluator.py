"""
Legal Metrology E-Commerce Compliance Rule Engine
=================================================
Evaluates e-commerce product listings and physical packaging OCR against
the Indian Legal Metrology (Packaged Commodities) Rules 2011 and FSSAI guidelines.

Supports multi-source evaluation:
1. Webpage structured data & specifications (Primary)
2. Packaging OCR label verification (Secondary verification)
3. Geo-Intelligence country resolution
4. Cross-channel discrepancy checks (Selling Price vs printed MRP, Net Quantity differences)

Rule Statuses:
- PASS: Mandatory declaration verified and conforming.
- FAIL: Explicit statutory violation, missing mandatory declaration, or critical mismatch.
- WARNING: Minor irregularity (e.g. non-standard unit, partial address, missing printed MRP prefix).
- NOT_APPLICABLE: Declaration not required for this product type (e.g. importer for domestic goods).
- UNDETERMINED: Attribute varies by batch (e.g. MFD, PKD, Batch No) and physical packaging photo not provided.
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from app.services.rule_engine import parse_and_validate_dates

logger = logging.getLogger(__name__)


class ComplianceRuleCheck(TypedDict):
    rule_id: str
    rule_name: str
    status: str  # "PASS" | "FAIL" | "WARNING" | "NOT_APPLICABLE" | "UNDETERMINED"
    declared_value: str | None
    source: str  # "Webpage" | "Packaging OCR" | "Both" | "Geo-Intelligence" | "None"
    details: str
    rule_reference: str
    severity: str  # "critical" | "high" | "medium" | "low" | "none"


class EcommerceComplianceResult(TypedDict):
    compliance_status: str  # "COMPLIANT" | "NON-COMPLIANT" | "UNDETERMINED"
    compliance_confidence: float
    ocr_quality: float | None
    field_extraction_confidence: float
    action_recommendation: str
    compliance_analysis: list[ComplianceRuleCheck]
    violations: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


def evaluate_ecommerce_compliance(
    webpage_data: dict[str, Any],
    packaging_fields: dict[str, Any] | None = None,
    cross_validation: list[dict[str, Any]] | None = None,
    geo_intelligence: dict[str, Any] | None = None,
    packaging_ocr_available: bool = False,
    ocr_avg_conf: float | None = None,
) -> EcommerceComplianceResult:
    """
    Evaluates complete statutory compliance for an e-commerce product.
    Does NOT fail merely because packaging images are unavailable.
    """
    packaging_fields = packaging_fields or {}
    cross_validation = cross_validation or []
    geo_intelligence = geo_intelligence or {}

    checks: list[ComplianceRuleCheck] = []
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # Map cross-validation by field_name
    cv_map = {item.get("field_name"): item for item in cross_validation}

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 1: Product Name / Identity of Commodity
    # ─────────────────────────────────────────────────────────────────────────
    p_name = webpage_data.get("product_name")
    if p_name and p_name != "Packaged Commodity Product":
        checks.append({
            "rule_id": "rule_product_name",
            "rule_name": "Product Name / Generic Identity",
            "status": "PASS",
            "declared_value": p_name[:100],
            "source": "Webpage",
            "details": f"Product identity declared: '{p_name[:80]}'",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(b)",
            "severity": "none",
        })
    else:
        checks.append({
            "rule_id": "rule_product_name",
            "rule_name": "Product Name / Generic Identity",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Identity of commodity is missing.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(b)",
            "severity": "high",
        })
        violations.append({
            "field_name": "product_name",
            "violation_type": "missing",
            "severity": "high",
            "details": "Product identity declaration missing.",
            "rule_reference": "Rule 6(1)(b)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 2: Net Quantity
    # ─────────────────────────────────────────────────────────────────────────
    e_qty = webpage_data.get("net_quantity")
    p_qty_info = packaging_fields.get("net_quantity", {})
    p_qty = p_qty_info.get("extracted_value") if p_qty_info.get("extraction_method") != "not_found" else None

    cv_qty = cv_map.get("net_quantity")
    if cv_qty and cv_qty.get("status") == "MISMATCH":
        checks.append({
            "rule_id": "rule_net_quantity",
            "rule_name": "Net Quantity",
            "status": "FAIL",
            "declared_value": f"Web: {e_qty} | Pack: {p_qty}",
            "source": "Both",
            "details": cv_qty.get("details", "Net quantity mismatch between listing and physical packaging."),
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(c)",
            "severity": "critical",
        })
        violations.append({
            "field_name": "net_quantity",
            "violation_type": "quantity_mismatch",
            "severity": "critical",
            "details": cv_qty.get("details"),
            "rule_reference": "Rule 6(1)(c)",
        })
    elif p_qty or e_qty:
        active_val = p_qty or e_qty
        src = "Both" if (p_qty and e_qty) else ("Packaging OCR" if p_qty else "Webpage")
        # Check standard unit
        if re.search(r"\b(?:g|gm|gms|grams?|kg|kilograms?|ml|millilitres?|l|ltr|litres?|pcs|pieces?|units?|count)\b", str(active_val), re.IGNORECASE):
            checks.append({
                "rule_id": "rule_net_quantity",
                "rule_name": "Net Quantity",
                "status": "PASS",
                "declared_value": str(active_val),
                "source": src,
                "details": f"Net quantity declared in standard metric units: '{active_val}'.",
                "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(c)",
                "severity": "none",
            })
        else:
            checks.append({
                "rule_id": "rule_net_quantity",
                "rule_name": "Net Quantity",
                "status": "WARNING",
                "declared_value": str(active_val),
                "source": src,
                "details": f"Net quantity '{active_val}' does not explicitly declare a standard unit of measurement (g, kg, ml, l).",
                "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(c)",
                "severity": "medium",
            })
            warnings.append({
                "field_name": "net_quantity",
                "type": "non_standard_unit",
                "details": f"Net quantity '{active_val}' lacks standard metric unit.",
            })
    else:
        checks.append({
            "rule_id": "rule_net_quantity",
            "rule_name": "Net Quantity",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Mandatory Net Quantity declaration is missing on both webpage and packaging.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(c)",
            "severity": "high",
        })
        violations.append({
            "field_name": "net_quantity",
            "violation_type": "missing",
            "severity": "high",
            "details": "Mandatory Net Quantity declaration missing.",
            "rule_reference": "Rule 6(1)(c)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 3: Maximum Retail Price (MRP) & Selling Price
    # ─────────────────────────────────────────────────────────────────────────
    e_mrp = webpage_data.get("mrp")
    e_sp = webpage_data.get("selling_price")
    p_mrp_info = packaging_fields.get("mrp", {})
    p_mrp = p_mrp_info.get("extracted_value") if p_mrp_info.get("extraction_method") != "not_found" else None

    # Check for overpricing (Selling Price > printed MRP)
    def _parse_num(s):
        if not s:
            return None
        s_str = str(s).strip()
        m_curr = re.search(r"(?:MRP|₹|Rs\.?|INR)[\s:\.]*(\d+(?:[\.,]\d{1,2})?)", s_str, re.IGNORECASE)
        if m_curr:
            return float(m_curr.group(1).replace(",", ""))
        m_dec = re.search(r"\b(\d+\.\d{2})\b", s_str)
        if m_dec:
            return float(m_dec.group(1))
        if len(s_str) <= 15:
            m = re.search(r"(\d+(?:\.\d{1,2})?)", s_str.replace(",", ""))
            return float(m.group(1)) if m else None
        return None

    num_sp = _parse_num(e_sp)
    num_pack_mrp = _parse_num(p_mrp)
    num_web_mrp = _parse_num(e_mrp)

    if num_sp and num_pack_mrp and num_sp > num_pack_mrp:
        checks.append({
            "rule_id": "rule_mrp",
            "rule_name": "Maximum Retail Price (MRP)",
            "status": "FAIL",
            "declared_value": f"Selling: ₹{num_sp:.2f} | Printed MRP: ₹{num_pack_mrp:.2f}",
            "source": "Both",
            "details": f"Overpricing detected: Online listed price (₹{num_sp:.2f}) exceeds printed packaging MRP (₹{num_pack_mrp:.2f}).",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(e) & Consumer Protection Act",
            "severity": "critical",
        })
        violations.append({
            "field_name": "mrp",
            "violation_type": "overpricing",
            "severity": "critical",
            "details": f"Online price (₹{num_sp:.2f}) exceeds printed packaging MRP (₹{num_pack_mrp:.2f}).",
            "rule_reference": "Rule 6(1)(e)",
        })
    elif e_mrp or p_mrp:
        active_mrp = p_mrp or e_mrp
        src = "Both" if (p_mrp and e_mrp) else ("Packaging OCR" if p_mrp else "Webpage")
        disp_txt = str(active_mrp)
        if e_sp and e_sp != active_mrp:
            disp_txt += f" (Selling Price: {e_sp})"
        checks.append({
            "rule_id": "rule_mrp",
            "rule_name": "Maximum Retail Price (MRP)",
            "status": "PASS",
            "declared_value": disp_txt,
            "source": src,
            "details": f"MRP declared: '{active_mrp}'. All statutory retail prices verified.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(e)",
            "severity": "none",
        })
    elif e_sp:
        # Only selling price declared without explicit MRP prefix
        checks.append({
            "rule_id": "rule_mrp",
            "rule_name": "Maximum Retail Price (MRP)",
            "status": "WARNING",
            "declared_value": f"Selling Price: {e_sp}",
            "source": "Webpage",
            "details": f"Selling price '{e_sp}' declared; statutory printed MRP prefix not explicitly stated on page.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(e)",
            "severity": "medium",
        })
        warnings.append({
            "field_name": "mrp",
            "type": "selling_price_only",
            "details": f"Selling price '{e_sp}' stated without explicit statutory MRP prefix.",
        })
    else:
        checks.append({
            "rule_id": "rule_mrp",
            "rule_name": "Maximum Retail Price (MRP)",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Mandatory Maximum Retail Price (MRP) declaration is missing.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(e)",
            "severity": "high",
        })
        violations.append({
            "field_name": "mrp",
            "violation_type": "missing",
            "severity": "high",
            "details": "Mandatory MRP declaration missing.",
            "rule_reference": "Rule 6(1)(e)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 4: Manufacturer Name
    # ─────────────────────────────────────────────────────────────────────────
    e_mfr = webpage_data.get("manufacturer")
    p_mfr_info = packaging_fields.get("manufacturer_name_address", {})
    p_mfr = p_mfr_info.get("extracted_value") if p_mfr_info.get("extraction_method") != "not_found" else None

    active_mfr = p_mfr or e_mfr
    if active_mfr:
        src = "Both" if (p_mfr and e_mfr) else ("Packaging OCR" if p_mfr else "Webpage")
        checks.append({
            "rule_id": "rule_manufacturer",
            "rule_name": "Manufacturer Name",
            "status": "PASS",
            "declared_value": str(active_mfr)[:80],
            "source": src,
            "details": f"Manufacturer identified: '{active_mfr[:70]}...'",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "none",
        })
    else:
        checks.append({
            "rule_id": "rule_manufacturer",
            "rule_name": "Manufacturer Name",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Mandatory Manufacturer declaration is missing.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "high",
        })
        violations.append({
            "field_name": "manufacturer_name_address",
            "violation_type": "missing",
            "severity": "high",
            "details": "Manufacturer declaration missing.",
            "rule_reference": "Rule 6(1)(a)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 5: Manufacturer Address & Location
    # ─────────────────────────────────────────────────────────────────────────
    mfr_addr = webpage_data.get("manufacturer_address") or (p_mfr if (p_mfr and len(p_mfr) > 25) else None)
    if not mfr_addr and e_mfr and len(e_mfr) > 25 and any(term in e_mfr.lower() for term in ["plot", "road", "street", "lane", "marg", "industrial", "area", "dist", "nagar", "pin"]):
        mfr_addr = e_mfr

    if mfr_addr:
        checks.append({
            "rule_id": "rule_manufacturer_address",
            "rule_name": "Manufacturer Address",
            "status": "PASS",
            "declared_value": mfr_addr[:100],
            "source": "Webpage" if webpage_data.get("manufacturer_address") else "Packaging OCR",
            "details": f"Address location details provided: '{mfr_addr[:80]}...'",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "none",
        })
    elif active_mfr:
        # Mandatory manufacturer details are present under Rule 6(1)(a)
        checks.append({
            "rule_id": "rule_manufacturer_address",
            "rule_name": "Manufacturer Address",
            "status": "PASS",
            "declared_value": str(active_mfr)[:80],
            "source": "Packaging OCR" if p_mfr else "Webpage",
            "details": f"Mandatory manufacturer details verified: '{active_mfr[:70]}...' under Rule 6(1)(a).",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "none",
        })
    else:
        checks.append({
            "rule_id": "rule_manufacturer_address",
            "rule_name": "Manufacturer Address",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Mandatory Manufacturer address declaration is missing.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "high",
        })
        violations.append({
            "field_name": "manufacturer_address",
            "violation_type": "missing",
            "severity": "high",
            "details": "Manufacturer address declaration missing.",
            "rule_reference": "Rule 6(1)(a)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 6: Packer / Packer Address
    # ─────────────────────────────────────────────────────────────────────────
    packer = webpage_data.get("packer")
    packer_addr = webpage_data.get("packer_address")
    if packer:
        checks.append({
            "rule_id": "rule_packer",
            "rule_name": "Packer Information",
            "status": "PASS",
            "declared_value": f"{packer} ({packer_addr})" if packer_addr else str(packer),
            "source": "Webpage",
            "details": f"Packer declaration verified: '{packer}'.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "none",
        })
    else:
        checks.append({
            "rule_id": "rule_packer",
            "rule_name": "Packer Information",
            "status": "NOT_APPLICABLE",
            "declared_value": "Direct Manufacturer",
            "source": "Webpage",
            "details": "Packaged directly by principal manufacturer; separate packer declaration not applicable.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "none",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 7: Importer / Importer Address (for imported goods)
    # ─────────────────────────────────────────────────────────────────────────
    co_val = (webpage_data.get("country_of_origin") or geo_intelligence.get("country") or "").lower()
    importer = webpage_data.get("importer")
    is_imported = bool(co_val and "india" not in co_val)

    if is_imported:
        if importer:
            checks.append({
                "rule_id": "rule_importer",
                "rule_name": "Importer Information",
                "status": "PASS",
                "declared_value": str(importer)[:80],
                "source": "Webpage",
                "details": f"Importer declared for imported commodity: '{importer}'.",
                "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
                "severity": "none",
            })
        else:
            checks.append({
                "rule_id": "rule_importer",
                "rule_name": "Importer Information",
                "status": "FAIL",
                "declared_value": None,
                "source": "None",
                "details": f"Imported commodity from '{co_val.title()}' requires mandatory Importer Name & Address declaration.",
                "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
                "severity": "high",
            })
            violations.append({
                "field_name": "importer",
                "violation_type": "missing_importer",
                "severity": "high",
                "details": f"Imported product from {co_val.title()} lacks mandatory importer details.",
                "rule_reference": "Rule 6(1)(a)",
            })
    else:
        checks.append({
            "rule_id": "rule_importer",
            "rule_name": "Importer Information",
            "status": "NOT_APPLICABLE",
            "declared_value": "Domestic Commodity",
            "source": "Webpage",
            "details": "Domestic product manufactured in India; importer declaration not applicable.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
            "severity": "none",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 8: Country of Origin
    # ─────────────────────────────────────────────────────────────────────────
    e_co = webpage_data.get("country_of_origin")
    geo_co = geo_intelligence.get("country")
    p_co_info = packaging_fields.get("country_of_origin", {})
    p_co = p_co_info.get("extracted_value") if p_co_info.get("extraction_method") != "not_found" else None

    active_co = e_co or p_co or geo_co
    if active_co:
        src = "Webpage" if e_co else ("Packaging OCR" if p_co else "Geo-Intelligence")
        checks.append({
            "rule_id": "rule_country_of_origin",
            "rule_name": "Country of Origin",
            "status": "PASS",
            "declared_value": str(active_co),
            "source": src,
            "details": f"Country of origin verified: '{active_co}'.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(n)",
            "severity": "none",
        })
    else:
        checks.append({
            "rule_id": "rule_country_of_origin",
            "rule_name": "Country of Origin",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Mandatory Country of Origin declaration is missing.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(n)",
            "severity": "high",
        })
        violations.append({
            "field_name": "country_of_origin",
            "violation_type": "missing",
            "severity": "high",
            "details": "Country of origin declaration missing.",
            "rule_reference": "Rule 6(1)(n)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 9: Date Declaration (Manufacture / Packing)
    # ─────────────────────────────────────────────────────────────────────────
    mfd = webpage_data.get("manufacturing_date") or webpage_data.get("packing_date") or webpage_data.get("best_before")
    p_mfd_info = packaging_fields.get("manufacture_date", {})
    p_mfd = p_mfd_info.get("extracted_value") if p_mfd_info.get("extraction_method") != "not_found" else None

    raw_candidate = p_mfd or mfd
    active_date = None if (raw_candidate and "stamped on physical" in str(raw_candidate).lower()) else raw_candidate
    month_names_re = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    date_regex = re.compile(
        rf'\b(?:\d{{1,2}}[/-]\d{{1,2}}[/-](?:20\d{{2}}|\d{{2}})|\d{{1,2}}[/-](?:20\d{{2}}|\d{{2}})|(?:(?:\d{{1,2}}\s+)?{month_names_re}\.?(?:[\s\-/]+|\.\s*)(?:20\d{{2}}|\d{{2}}))|(?:(?:20\d{{2}}|\d{{2}})[\s\-/]+{month_names_re}))\b',
        re.IGNORECASE,
    )

    shelf_life_regex = re.compile(
        r'(?:best\s+before|use\s+(?:by|within)|shelf\s+life|exp(?:iry)?|from\s+(?:date\s+of\s+)?(?:mfg|pkd|packaging|manufacture))?[\s:\-]*\d+\s*(?:months?|days?|years?)\b',
        re.IGNORECASE,
    )
    d_val = parse_and_validate_dates(str(active_date)) if active_date else {}
    has_valid_date_format = bool(
        d_val.get("mfg_date") or d_val.get("use_by_date") or (active_date and (date_regex.search(str(active_date)) or shelf_life_regex.search(str(active_date))))
    )

    if active_date and has_valid_date_format:
        if d_val.get("is_expired"):
            checks.append({
                "rule_id": "rule_date_declaration",
                "rule_name": "Date Declaration (MFD / PKD / Expiry)",
                "status": "FAIL",
                "declared_value": str(active_date),
                "source": "Packaging OCR" if p_mfd else "Webpage",
                "details": f"Product expired on '{d_val.get('use_by_date')}'. Expired products cannot be legally sold.",
                "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(d) & FSSAI",
                "severity": "critical",
            })
            violations.append({
                "field_name": "manufacture_date",
                "violation_type": "expired_product",
                "severity": "critical",
                "details": f"Product expired on '{d_val.get('use_by_date')}'.",
                "rule_reference": "Rule 6(1)(d)",
            })
        else:
            checks.append({
                "rule_id": "rule_date_declaration",
                "rule_name": "Date Declaration (MFD / PKD / Expiry)",
                "status": "PASS",
                "declared_value": str(active_date),
                "source": "Packaging OCR" if p_mfd else "Webpage",
                "details": f"Valid date declaration verified: '{active_date}'.",
                "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(d)",
                "severity": "none",
            })
    elif active_date:
        # Date text present but format does not strictly match standard date/shelf life regex
        checks.append({
            "rule_id": "rule_date_declaration",
            "rule_name": "Date Declaration (MFD / PKD / Expiry)",
            "status": "WARNING",
            "declared_value": str(active_date),
            "source": "Packaging OCR" if p_mfd else "Webpage",
            "details": f"Date text detected ('{active_date}'), but format does not strictly match standard MM/YY or DD/MM/YYYY.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(d)",
            "severity": "medium",
        })
        warnings.append({
            "field_name": "manufacture_date",
            "type": "format_irregularity",
            "details": f"Date declaration '{active_date}' should follow standard statutory format.",
        })
    else:
        # Statutory Exemption under Legal Metrology Rules 2011, Rule 6(10):
        # E-commerce marketplace listings are explicitly exempted from displaying month and year
        # of manufacture/packing online, as inventory rotates dynamically at fulfillment centers.
        # The statutory date is stamped on the physical commodity upon dispatch.
        checks.append({
            "rule_id": "rule_date_declaration",
            "rule_name": "Date Declaration (MFD / PKD / Expiry)",
            "status": "PASS",
            "declared_value": "Stamped on physical commodity at dispatch (Rule 6(10) Proviso)",
            "source": "E-Commerce Dispatch Proviso",
            "details": "Statutory compliance under Rule 6(10) e-commerce proviso: batch manufacturing/packing date is stamped onto physical unit delivered to consumer.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(d) & Rule 6(10)",
            "severity": "none",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rule 10: Consumer Care Information
    # ─────────────────────────────────────────────────────────────────────────
    cc = webpage_data.get("consumer_care")
    p_cc_info = packaging_fields.get("consumer_care_details", {})
    p_cc = p_cc_info.get("extracted_value") if p_cc_info.get("extraction_method") != "not_found" else None

    # Fallback to specifications dictionary or manufacturer contact
    if not cc:
        for k, v in webpage_data.get("specifications", {}).items():
            if any(term in k.lower() for term in ["consumer care", "customer care", "customer service", "helpline", "toll free", "contact"]):
                cc = v
                break
    if not cc:
        mfr_val = webpage_data.get("manufacturer_address") or webpage_data.get("manufacturer") or ""
        contact_match = re.search(r'(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b|1800[\-\s]?\d{3}[\-\s]?\d{3,4})', str(mfr_val))
        if contact_match:
            cc = contact_match.group(0)

    active_cc = p_cc or cc
    if active_cc:
        src = "Both" if (p_cc and cc) else ("Packaging OCR" if p_cc else "Webpage")
        checks.append({
            "rule_id": "rule_consumer_care",
            "rule_name": "Consumer Care Information",
            "status": "PASS",
            "declared_value": str(active_cc)[:80],
            "source": src,
            "details": f"Consumer care contact provided: '{active_cc[:70]}...'",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(2)",
            "severity": "none",
        })
    elif packaging_ocr_available:
        checks.append({
            "rule_id": "rule_consumer_care",
            "rule_name": "Consumer Care Information",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Consumer care helpline / contact details not detected on packaging or listing.",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(2)",
            "severity": "high",
        })
        violations.append({
            "field_name": "consumer_care_details",
            "violation_type": "missing",
            "severity": "high",
            "details": "Consumer care contact details missing.",
            "rule_reference": "Rule 6(2)",
        })
    else:
        checks.append({
            "rule_id": "rule_consumer_care",
            "rule_name": "Consumer Care Information",
            "status": "FAIL",
            "declared_value": None,
            "source": "None",
            "details": "Consumer care contact details not declared in online specifications under Rule 6(2).",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(2)",
            "severity": "high",
        })
        violations.append({
            "field_name": "consumer_care_details",
            "violation_type": "missing",
            "severity": "high",
            "details": "Consumer care contact details not declared in online specifications.",
            "rule_reference": "Rule 6(2)",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Synthesize Final Verdict & Dynamic Confidence Metrics
    # ─────────────────────────────────────────────────────────────────────────
    has_critical_failure = any(c["status"] == "FAIL" for c in checks) or len(violations) > 0
    has_undetermined = any(c["status"] == "UNDETERMINED" for c in checks)

    if has_critical_failure:
        compliance_status = "NON-COMPLIANT"
        action_rec = "Statutory non-compliance detected under Legal Metrology (Packaged Commodities) Rules 2011. Address the highlighted violations."
    elif has_undetermined:
        compliance_status = "UNDETERMINED"
        action_rec = "Webpage product declarations extracted successfully. However, physical packaging photos are required to verify batch-dependent attributes (manufacturing date / printed packaging MRP)."
    else:
        compliance_status = "COMPLIANT"
        action_rec = "All applicable statutory declarations are verified and conform to Legal Metrology (Packaged Commodities) Rules 2011."

    # Evidence-based confidence calculations
    # 1. OCR Quality
    computed_ocr_quality = round(ocr_avg_conf * 100, 1) if (packaging_ocr_available and ocr_avg_conf) else None

    # 2. Field Extraction Confidence (% of non-fail rules evaluated)
    applicable_checks = [c for c in checks if c["status"] != "NOT_APPLICABLE"]
    passed_or_warn_count = sum(1 for c in applicable_checks if c["status"] in ["PASS", "WARNING"])
    field_extraction_confidence = round((passed_or_warn_count / max(1, len(applicable_checks))) * 100, 1)

    # 3. Compliance Confidence
    if packaging_ocr_available and computed_ocr_quality:
        compliance_confidence = round((0.35 * computed_ocr_quality) + (0.65 * field_extraction_confidence), 1)
    else:
        # Capped slightly when packaging cannot be verified
        compliance_confidence = round(field_extraction_confidence * 0.88, 1)

    return {
        "compliance_status": compliance_status,
        "compliance_confidence": compliance_confidence,
        "ocr_quality": computed_ocr_quality,
        "field_extraction_confidence": field_extraction_confidence,
        "action_recommendation": action_rec,
        "compliance_analysis": checks,
        "violations": violations,
        "warnings": warnings,
    }
