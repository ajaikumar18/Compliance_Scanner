"""
Tests for backend/app/services/rule_engine.py

Tests cover:
- load_legal_metrology_rules config loading
- Compliant extraction result -> status "compliant", 0 violations
- Missing mandatory field -> violation_type="missing", status "non_compliant"
- Incorrect format -> violation_type="incorrect_format", status "non_compliant"
- Undersized font -> violation_type="undersized_font", status "non_compliant"
- GenAI fallback / low confidence -> status "partial_review_needed"
- Schema compliance with ViolationType and ViolationSeverity enums

Run with:
    cd backend
    python -m pytest tests/test_rule_engine.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.models.violation import ViolationType, ViolationSeverity
from app.services.rule_engine import (
    load_legal_metrology_rules,
    evaluate_compliance,
)


def _mock_compliant_extraction() -> dict:
    return {
        "fields": {
            "mrp": {
                "field_name": "mrp",
                "extracted_value": "MRP Rs. 120.00 (Inclusive of all taxes)",
                "extraction_method": "ocr_tesseract",
                "confidence": 0.95,
                "bbox": [10, 40, 80, 20],
            },
            "net_quantity": {
                "field_name": "net_quantity",
                "extracted_value": "Net Wt. 500 g",
                "extraction_method": "ocr_tesseract",
                "confidence": 0.92,
                "bbox": [10, 10, 100, 20],
            },
            "manufacture_date": {
                "field_name": "manufacture_date",
                "extracted_value": "Mfg Date: 01/2026",
                "extraction_method": "ocr_tesseract",
                "confidence": 0.90,
                "bbox": [10, 70, 80, 20],
            },
            "manufacturer_name_address": {
                "field_name": "manufacturer_name_address",
                "extracted_value": "Manufactured by XYZ Foods Pvt. Ltd., Industrial Area, Mumbai - 400001",
                "extraction_method": "ocr_tesseract",
                "confidence": 0.88,
                "bbox": [10, 100, 200, 40],
            },
            "consumer_care_details": {
                "field_name": "consumer_care_details",
                "extracted_value": "Consumer Care: 1800-123-4567 (Toll Free) care@xyz.com",
                "extraction_method": "ocr_tesseract",
                "confidence": 0.89,
                "bbox": [10, 150, 150, 20],
            },
            "country_of_origin": {
                "field_name": "country_of_origin",
                "extracted_value": "Country of Origin: India",
                "extraction_method": "ocr_tesseract",
                "confidence": 0.91,
                "bbox": [10, 180, 100, 20],
            },
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Rules Config Loader Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadRules:
    def test_load_legal_metrology_rules(self):
        config = load_legal_metrology_rules()
        assert "mandatory_declarations" in config
        assert isinstance(config["mandatory_declarations"], list)
        assert len(config["mandatory_declarations"]) >= 6


# ─────────────────────────────────────────────────────────────────────────────
# 2. Compliance Evaluation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateCompliance:
    def test_fully_compliant_label(self):
        extraction = _mock_compliant_extraction()
        res = evaluate_compliance(extraction_result=extraction)

        assert res["compliance_status"] == "compliant"
        assert len(res["violations"]) == 0
        assert res["summary"]["total_violations"] == 0

    def test_missing_mandatory_field_violation(self):
        extraction = _mock_compliant_extraction()
        # Remove MRP
        extraction["fields"]["mrp"]["extracted_value"] = None
        extraction["fields"]["mrp"]["extraction_method"] = "not_found"

        res = evaluate_compliance(extraction_result=extraction)

        assert res["compliance_status"] == "non_compliant"
        assert len(res["violations"]) >= 1

        mrp_violations = [v for v in res["violations"] if v["field_name"] == "mrp"]
        assert mrp_violations
        assert mrp_violations[0]["violation_type"] == ViolationType.missing
        assert mrp_violations[0]["severity"] == ViolationSeverity.high

    def test_incorrect_format_violation(self):
        extraction = _mock_compliant_extraction()
        # Invalid MRP format (bare number without MRP prefix or currency)
        extraction["fields"]["mrp"]["extracted_value"] = "120"

        res = evaluate_compliance(extraction_result=extraction)

        assert res["compliance_status"] == "non_compliant"
        mrp_violations = [v for v in res["violations"] if v["field_name"] == "mrp"]
        assert mrp_violations
        assert mrp_violations[0]["violation_type"] == ViolationType.incorrect_format

    def test_undersized_font_violation(self):
        extraction = _mock_compliant_extraction()
        font_analysis = {
            "net_quantity": {
                "field_name": "net_quantity",
                "compliant": False,
                "measured_mm": 1.2,
                "required_mm": 4.0,
                "tolerance_note": "+/-0.2mm estimated tolerance",
            }
        }

        res = evaluate_compliance(
            extraction_result=extraction,
            font_analysis_result=font_analysis,
        )

        assert res["compliance_status"] == "non_compliant"
        net_violations = [v for v in res["violations"] if v["field_name"] == "net_quantity"]
        assert net_violations
        assert net_violations[0]["violation_type"] == ViolationType.undersized_font
        assert net_violations[0]["severity"] == ViolationSeverity.medium

    def test_partial_review_needed_when_genai_fallback_used(self):
        extraction = _mock_compliant_extraction()
        # Mark one field as extracted via GenAI fallback
        extraction["fields"]["manufacture_date"]["extraction_method"] = "genai_fallback"

        res = evaluate_compliance(extraction_result=extraction)

        assert res["compliance_status"] == "partial_review_needed"
        assert len(res["violations"]) == 0
        assert res["summary"]["genai_fallback_used"] is True

    def test_partial_review_needed_when_low_confidence(self):
        extraction = _mock_compliant_extraction()
        extraction["fields"]["country_of_origin"]["confidence"] = 0.50  # low confidence

        res = evaluate_compliance(extraction_result=extraction)

        assert res["compliance_status"] == "partial_review_needed"
        assert len(res["violations"]) == 0

    def test_violation_types_and_severities_match_db_enums(self):
        extraction = _mock_compliant_extraction()
        extraction["fields"]["mrp"]["extracted_value"] = None

        res = evaluate_compliance(extraction_result=extraction)
        for v in res["violations"]:
            # Must be valid Enum values
            assert v["violation_type"] in [e.value for e in ViolationType]
            assert v["severity"] in [e.value for e in ViolationSeverity]
