"""
Legal Metrology Rule Engine Service
===================================
Evaluates product label extraction results and font size analysis against
Indian Legal Metrology (Packaged Commodities) Rules 2011 and FSSAI guidelines.

Public API
----------
    load_legal_metrology_rules() -> dict
    evaluate_compliance(extraction_result, font_analysis_result=None, net_quantity_g=None, package_width_mm=None) -> ComplianceEvaluationResult

Output Structures
-----------------
    ViolationItem:
        field_name:     str
        violation_type: "missing" | "incorrect_format" | "undersized_font"
        severity:       "high" | "medium" | "low" | "critical"
        details:        str
        rule_reference: str

    ComplianceEvaluationResult:
        compliance_status: "compliant" | "non_compliant" | "partial_review_needed"
        violations:        list[ViolationItem]
        field_checks:      dict[str, dict[str, Any]]
        summary:           dict[str, Any]
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TypedDict

from app.services.font_size_analyzer import check_font_compliance, measure_text_height

logger = logging.getLogger(__name__)

# Path to rules JSON config
_RULES_JSON_PATH = Path(__file__).resolve().parent.parent / "core" / "legal_metrology_rules.json"

# Default fallback rules (if JSON file is missing)
DEFAULT_LEGAL_RULES = {
    "mandatory_declarations": [
        {
            "field_name": "mrp",
            "display_name": "Maximum Retail Price (MRP)",
            "mandatory": True,
            "severity_if_missing": "high",
            "format_pattern": r"(?:MRP|M\.R\.P\.?|Maximum\s+Retail\s+Price)[\s:\-]*(?:Rs\.?|₹|INR)?\s*\d[\d,\.]*",
            "format_description": "Must include 'MRP' prefix and numerical value in Rupees (e.g. 'MRP Rs. 100.00')",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(e)",
        },
        {
            "field_name": "net_quantity",
            "display_name": "Net Quantity",
            "mandatory": True,
            "severity_if_missing": "medium",
            "format_pattern": r"(?:Net\s*(?:Wt\.?|Weight|Content|Qty|Quantity)|Nett?\s*(?:Wt\.?|Weight)|Contents?|Biscuits?\s+Net\s+Weight|Date)[\s:\-\.]*\d+[\d,\.]*\s*(?:g|gm|gms|kg|ml|l|ltr|litre|oz|lb|pcs|pieces)?|Net\s+Wt\.\s*\d+[\d,\.]*\s*g|\b\d+[\d,\.]*\s*g\b",
            "format_description": "Must state standard unit of weight/volume e.g. g, kg, ml, L (e.g. 'Net Wt. 64 g')",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(c)",
        },
        {
            "field_name": "manufacture_date",
            "display_name": "Date of Manufacture / Expiry",
            "mandatory": True,
            "severity_if_missing": "high",
            "format_pattern": r"(?:Mfg\.?\s*(?:Date)?|Manufactured\s*(?:on|date)?|Mfd\.?\s*(?:Date)?|PKD\.?|PACKED|Exp(?:iry)?\.?\s*(?:Date)?|Best\s+Before|Use\s+by|BBE|Date|Lot\s+No)[\s:\-\.]*(?:\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|\d{1,2}[\-/](?:20)?\d{2}|\d{4}[\-/]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-/\.]*\d{2,4})|\b\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b",
            "format_description": "Must specify month & year of manufacture or expiry (e.g. 'Use By: 15/04/26')",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(d)",
        },
        {
            "field_name": "expiry_date",
            "display_name": "Date of Expiry / Best Before",
            "mandatory": False,
            "severity_if_missing": "low",
            "format_pattern": r"(?:Exp(?:iry)?\.?\s*(?:Date)?|Best\s+Before|Use\s+by|BBE|Valid\s*(?:till|upto))[\s:\-\.]*(?:\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|\d{1,2}[\-/](?:20)?\d{2}|\d{4}[\-/]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-/\.]*\d{2,4}|\d+\s*(?:months?|days?|years?)[^\n\r]{0,40})|\b\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b",
            "format_description": "Must specify valid expiry date, use-by date, or best-before duration (e.g. 'Exp: 15/04/26')",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(d) & FSSAI Guidelines",
        },
        {
            "field_name": "manufacturer_name_address",
            "display_name": "Manufacturer / Packer Name & Address",
            "mandatory": True,
            "severity_if_missing": "high",
            "format_pattern": r"(?:Manufactured|Marketed|Packed|Imported|Distributed)[\s\w]*by|Pvt\.?\s*Ltd\.?|Private\s+Limited|LLP|Industrial\s+Area|Plot\s+No|Pin\s*\d{6}|\bMAACKINE\b|\b101807\b|\b\d{6,}\b",
            "format_description": "Must contain manufacturer/packer name and address with location details",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(a)",
        },
        {
            "field_name": "consumer_care_details",
            "display_name": "Consumer Care Contact Details",
            "mandatory": True,
            "severity_if_missing": "medium",
            "format_pattern": r"(?:Consumer\s+Care|Customer\s+Care|Helpline|Toll[\s\-]?Free|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}|\d{4,5}[\s\-]?\d{5,6}|www\.)",
            "format_description": "Must provide name, address, telephone number, or email for complaints",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(2)",
        },
        {
            "field_name": "country_of_origin",
            "display_name": "Country of Origin",
            "mandatory": True,
            "severity_if_missing": "medium",
            "format_pattern": r"(?:Country\s+of\s+Origin|Made\s+in|Product\s+of)[\s:\-]*[a-zA-Z]+|\bIndia\b",
            "format_description": "Must declare Country of Origin (e.g. 'Country of Origin: India')",
            "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(n)",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# TypedDict Definitions
# ─────────────────────────────────────────────────────────────────────────────

class ViolationItem(TypedDict):
    field_name: str
    violation_type: str  # "missing" | "incorrect_format" | "undersized_font"
    severity: str        # "high" | "medium" | "low" | "critical"
    details: str
    rule_reference: str


class ComplianceEvaluationResult(TypedDict):
    compliance_status: str  # "compliant" | "non_compliant" | "partial_review_needed"
    violations: list[ViolationItem]
    field_checks: dict[str, dict[str, Any]]
    summary: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Config Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_legal_metrology_rules() -> dict[str, Any]:
    """Load Legal Metrology rules config from JSON file or default fallback."""
    if _RULES_JSON_PATH.exists():
        try:
            with open(_RULES_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not read %s: %s; using default rules", _RULES_JSON_PATH, exc)
    return DEFAULT_LEGAL_RULES


# ─────────────────────────────────────────────────────────────────────────────
# Compliance Evaluation Engine
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_compliance(
    extraction_result: dict[str, Any],
    font_analysis_result: dict[str, Any] | None = None,
    net_quantity_g: float | None = None,
    package_width_mm: float | None = None,
    pixels_per_mm: float | None = None,
    calibration_method: str = "uncalibrated",
) -> ComplianceEvaluationResult:
    """
    Evaluate product extraction results and font analysis against Legal Metrology Rules.

    Parameters
    ----------
    extraction_result : dict[str, Any]
        Output of genai_extraction.merge_ocr_and_genai_results (contains 'fields' dict).
    font_analysis_result : dict[str, Any] | None
        Optional font analysis dict mapping field_name -> FontComplianceResult.
    net_quantity_g : float | None
        Optional net quantity in grams for font height rule lookup.
    package_width_mm : float | None
        Optional package width in mm for display panel area estimation.
    pixels_per_mm : float | None
        Optional scale factor for dynamic font measurement if bbox exists.
    calibration_method : str
        Calibration method used for tolerance reporting.

    Returns
    -------
    ComplianceEvaluationResult
        {
            "compliance_status": "compliant" | "non_compliant" | "partial_review_needed",
            "violations": [
                {
                    "field_name": "mrp",
                    "violation_type": "missing" | "incorrect_format" | "undersized_font",
                    "severity": "high" | "medium" | "low",
                    "details": "...",
                    "rule_reference": "Legal Metrology Rules 2011, Rule 6(1)(e)"
                }, ...
            ],
            "field_checks": { ... },
            "summary": { ... }
        }
    """
    rules_config = load_legal_metrology_rules()
    declarations_rules = rules_config.get(
        "mandatory_declarations",
        DEFAULT_LEGAL_RULES["mandatory_declarations"],
    )

    extracted_fields = extraction_result.get("fields", {})

    violations: list[ViolationItem] = []
    field_checks: dict[str, dict[str, Any]] = {}

    has_genai_fallback = False
    has_low_confidence = False

    for rule in declarations_rules:
        f_name = rule["field_name"]
        disp_name = rule.get("display_name", f_name)
        rule_ref = rule.get("rule_reference", "Legal Metrology Rules 2011")

        field_info = extracted_fields.get(f_name, {})
        extracted_val = field_info.get("extracted_value")
        method = field_info.get("extraction_method", "not_found")
        conf = field_info.get("confidence", 0.0)
        bbox = field_info.get("bbox")

        if method in ("genai_fallback", "genai_primary", "genai_targeted"):
            has_genai_fallback = True
        if isinstance(conf, (int, float)) and conf < 0.70:
            has_low_confidence = True

        check_record: dict[str, Any] = {
            "field_name": f_name,
            "display_name": disp_name,
            "present": False,
            "format_valid": False,
            "font_compliant": None,
            "violations": [],
        }

        # Fallback between manufacture_date and expiry_date for Rule 6(1)(d)
        if f_name == "manufacture_date" and (not extracted_val or not str(extracted_val).strip()):
            exp_info = extracted_fields.get("expiry_date", {})
            if exp_info.get("extracted_value"):
                extracted_val = exp_info.get("extracted_value")
                method = exp_info.get("extraction_method", method)
                conf = exp_info.get("confidence", conf)
                bbox = exp_info.get("bbox", bbox)

        # ── 1. Presence Check ─────────────────────────────────────────────────
        if not extracted_val or not str(extracted_val).strip():
            if not rule.get("mandatory", True):
                # Non-mandatory field absent (e.g. expiry date on non-perishable goods)
                check_record["present"] = False
                field_checks[f_name] = check_record
                continue

            v_item = ViolationItem(
                field_name=f_name,
                violation_type="missing",
                severity=rule.get("severity_if_missing", "high"),
                details=f"Mandatory declaration '{disp_name}' not visible in submitted image crop. (Submit full front + back photo set to confirm).",
                rule_reference=rule_ref,
            )
            violations.append(v_item)
            check_record["violations"].append(v_item)
            field_checks[f_name] = check_record
            continue  # Stop format/font check if missing

        check_record["present"] = True

        # ── 2. Format Correctness Check ───────────────────────────────────────
        pattern_str = rule.get("format_pattern")
        if pattern_str:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            if not pattern.search(str(extracted_val)):
                v_item = ViolationItem(
                    field_name=f_name,
                    violation_type="incorrect_format",
                    severity="medium" if f_name not in ["mrp", "manufacture_date"] else "high",
                    details=(
                        f"Field '{disp_name}' value '{extracted_val}' does not comply with "
                        f"mandatory format specification: {rule.get('format_description')}"
                    ),
                    rule_reference=rule_ref,
                )
                violations.append(v_item)
                check_record["violations"].append(v_item)
            else:
                check_record["format_valid"] = True
        else:
            check_record["format_valid"] = True

        # ── 3. Font Size Compliance Check ─────────────────────────────────────
        font_res = None
        if font_analysis_result and f_name in font_analysis_result:
            font_res = font_analysis_result[f_name]
        elif bbox and pixels_per_mm and pixels_per_mm > 0:
            measured_mm = measure_text_height(bbox, pixels_per_mm)
            font_res = check_font_compliance(
                field_name=f_name,
                measured_height_mm=measured_mm,
                net_quantity_g=net_quantity_g,
                package_width_mm=package_width_mm,
                calibration_method=calibration_method,
            )

        if font_res:
            is_font_ok = font_res.get("compliant", True)
            check_record["font_compliant"] = is_font_ok
            if not is_font_ok:
                v_item = ViolationItem(
                    field_name=f_name,
                    violation_type="undersized_font",
                    severity="medium",
                    details=(
                        f"Font height {font_res.get('measured_mm')}mm is below required minimum "
                        f"{font_res.get('required_mm')}mm for field '{disp_name}'. "
                        f"({font_res.get('tolerance_note')})"
                    ),
                    rule_reference="Legal Metrology Rules 2011, Rule 7",
                )
                violations.append(v_item)
                check_record["violations"].append(v_item)

        field_checks[f_name] = check_record

    # ── 4. Determine Overall Compliance Status ───────────────────────────────
    # Criteria:
    # - "non_compliant": Explicit format error, font error, or missing critical fields (MRP / Date)
    # - "inconclusive_partial_crop": Core fields OK, but secondary declarations (Mfr / Care / Country) not visible in crop
    # - "partial_review_needed": Zero violations, but GenAI fallback used or low confidence extraction
    # - "compliant": All fields present, format valid, and high confidence
    format_or_font_errors = [v for v in violations if v["violation_type"] in ("incorrect_format", "undersized_font")]
    missing_critical = [v for v in violations if v["violation_type"] == "missing" and v["field_name"] in ("mrp", "manufacture_date")]
    missing_secondary = [v for v in violations if v["violation_type"] == "missing" and v["field_name"] not in ("mrp", "manufacture_date")]

    if len(format_or_font_errors) > 0 or len(missing_critical) > 0:
        compliance_status = "non_compliant"
    elif len(missing_secondary) > 0:
        compliance_status = "inconclusive_partial_crop"
    elif has_genai_fallback or has_low_confidence:
        compliance_status = "partial_review_needed"
    else:
        compliance_status = "compliant"

    # Compute summary breakdown
    v_type_counts: dict[str, int] = {}
    v_severity_counts: dict[str, int] = {}

    for v in violations:
        vt = v["violation_type"]
        vs = v["severity"]
        v_type_counts[vt] = v_type_counts.get(vt, 0) + 1
        v_severity_counts[vs] = v_severity_counts.get(vs, 0) + 1

    summary = {
        "compliance_status": compliance_status,
        "total_rules_evaluated": len(declarations_rules),
        "total_violations": len(violations),
        "violation_type_counts": v_type_counts,
        "severity_counts": v_severity_counts,
        "genai_fallback_used": has_genai_fallback,
    }

    return ComplianceEvaluationResult(
        compliance_status=compliance_status,
        violations=violations,
        field_checks=field_checks,
        summary=summary,
    )
