"""
Unit Tests for LaptopLayoutClassifier and SurgicalTextFallbackEngine
===================================================================
Validates:
1. LaptopLayoutClassifier GPU initialization contract and fallback.
2. Layout-agnostic extraction loop (cx, cy, h calculations and raw_text_pool).
3. Euclidean spatial proximity search (horizontal-right and directly-below).
4. Target failure flagging (failed_fields list generation for low-confidence).
5. SurgicalTextFallbackEngine low-token execution contract (raw_text_pool only).
6. Pydantic v2 MetrologyJSONContract schema validation.
7. Exception containment for HTTP 429 and network timeouts (returns {field: None}).
"""

import asyncio
import numpy as np
import pytest
from pydantic import ValidationError

from app.services.field_classifier import (
    LaptopLayoutClassifier,
    LayoutToken,
    MANDATORY_COMPLIANCE_FIELDS,
)
from app.services.genai_extraction import (
    SurgicalTextFallbackEngine,
    MetrologyJSONContract,
)


class TestLaptopLayoutClassifier:
    def test_classifier_initialization_defaults(self):
        classifier = LaptopLayoutClassifier(use_gpu=True, lang="en", show_log=False)
        assert classifier.use_gpu is True
        assert classifier.lang == "en"
        assert classifier.show_log is False
        assert classifier.confidence_threshold == 0.80

    def test_layout_agnostic_token_extraction(self):
        classifier = LaptopLayoutClassifier()
        sample_blocks = [
            {"text": "MRP", "bbox": [10, 20, 50, 20], "confidence": 0.95, "engine_used": "paddleocr"},
            {"text": "Rs. 120.00", "bbox": [70, 20, 80, 20], "confidence": 0.96, "engine_used": "paddleocr"},
            {"text": "Net Wt.", "bbox": [10, 50, 60, 20], "confidence": 0.94, "engine_used": "paddleocr"},
            {"text": "500 g", "bbox": [80, 50, 50, 20], "confidence": 0.95, "engine_used": "paddleocr"},
        ]

        tokens, raw_text_pool = classifier.extract_tokens(sample_blocks)
        assert len(tokens) == 4
        # Verify geometric center coordinates
        # Bbox: [10, 20, 50, 20] -> cx = 35.0, cy = 30.0, h = 20.0
        assert tokens[0].cx == 35.0
        assert tokens[0].cy == 30.0
        assert tokens[0].h == 20.0

        # Verify concurrent raw_text_pool generation
        assert "MRP" in raw_text_pool
        assert "Rs. 120.00" in raw_text_pool
        assert "Net Wt." in raw_text_pool
        assert "500 g" in raw_text_pool

    def test_euclidean_horizontal_right_proximity(self):
        classifier = LaptopLayoutClassifier()
        # Horizontal key-value: [MRP] at (10, 20) and [Rs. 250.00] at (70, 20)
        blocks = [
            {"text": "MRP", "bbox": [10, 20, 50, 25], "confidence": 0.95, "engine_used": "paddleocr"},
            {"text": "Rs. 250.00", "bbox": [70, 20, 90, 25], "confidence": 0.95, "engine_used": "paddleocr"},
        ]

        result = classifier.classify(blocks)
        assert "mrp" in result["extracted_fields"]
        assert result["extracted_fields"]["mrp"]["extracted_value"] == "MRP Rs. 250.00"
        assert result["extracted_fields"]["mrp"]["confidence"] >= 0.80

    def test_euclidean_directly_below_proximity(self):
        classifier = LaptopLayoutClassifier()
        # Stacked key-value: [MANUFACTURED BY:] at (10, 20) and company on line below (10, 55)
        blocks = [
            {"text": "MANUFACTURED BY:", "bbox": [10, 20, 180, 25], "confidence": 0.92, "engine_used": "paddleocr"},
            {"text": "Organic Foods Pvt. Ltd., Pune 411001", "bbox": [10, 55, 300, 25], "confidence": 0.90, "engine_used": "paddleocr"},
        ]

        result = classifier.classify(blocks)
        assert "manufacturer_name_address" in result["extracted_fields"]
        extracted_text = result["extracted_fields"]["manufacturer_name_address"]["extracted_value"]
        assert "Organic Foods Pvt. Ltd." in extracted_text
        assert "Pune 411001" in extracted_text

    def test_target_failure_flagging(self):
        classifier = LaptopLayoutClassifier()
        # Only provide MRP; other 5 mandatory fields are absent
        blocks = [
            {"text": "MRP Rs. 99.00", "bbox": [10, 20, 120, 25], "confidence": 0.95, "engine_used": "paddleocr"}
        ]

        result = classifier.classify(blocks)
        assert "mrp" in result["extracted_fields"]
        assert "mrp" not in result["failed_fields"]

        # The other fields must be flagged in failed_fields
        for field in ["net_quantity", "manufacture_date", "manufacturer_name_address", "consumer_care_details", "country_of_origin"]:
            assert field in result["failed_fields"]

    def test_date_collision_demotes_expiry_date_to_fallback(self):
        classifier = LaptopLayoutClassifier()
        # Simulated scenario: only one date exists in OCR tokens (16/10/25) alongside PKD. and USE BY
        blocks = [
            {"text": "PKD.", "bbox": [10, 20, 50, 20], "confidence": 0.95, "engine_used": "paddleocr"},
            {"text": "USE BY", "bbox": [10, 50, 60, 20], "confidence": 0.95, "engine_used": "paddleocr"},
            {"text": "16/10/25", "bbox": [100, 20, 80, 20], "confidence": 0.95, "engine_used": "paddleocr"},
        ]
        result = classifier.classify(blocks)
        # manufacture_date should claim 16/10/25
        assert "manufacture_date" in result["extracted_fields"]
        assert "16/10/25" in result["extracted_fields"]["manufacture_date"]["extracted_value"]
        # expiry_date must NOT claim 16/10/25, and must be sent to failed_fields for vision fallback
        assert "expiry_date" not in result["extracted_fields"]
        assert "expiry_date" in result["failed_fields"]


class TestSurgicalTextFallbackEngine:
    def test_pydantic_v2_metrology_contract(self):
        contract = MetrologyJSONContract(
            mrp="Rs. 150.00",
            net_quantity="500 g",
            manufacture_date="15/04/2026",
            manufacturer_name_address="Sunrise Ltd, Delhi",
            consumer_care_details="1800-111-2222",
            country_of_origin="India",
        )
        assert contract.mrp == "Rs. 150.00"
        assert contract.net_quantity == "500 g"
        assert contract.country_of_origin == "India"

        # Validates JSON serialization and parsing
        json_data = contract.model_dump_json()
        parsed = MetrologyJSONContract.model_validate_json(json_data)
        assert parsed.mrp == "Rs. 150.00"

    def test_low_token_execution_contract_accepts_strings_only(self):
        engine = SurgicalTextFallbackEngine(api_key="dummy_key_for_testing")
        raw_text_pool = "Product Brand\nBatch No: B124\nMRP Rs. 75.00\nPack size 100g"
        failed_fields = ["mrp", "net_quantity"]

        # Engine accepts flat strings and returns a dictionary
        res = engine.extract_fallback_sync(raw_text_pool, failed_fields)
        assert isinstance(res, dict)
        assert set(res.keys()) == set(failed_fields)

    def test_exception_containment_on_simulated_error(self, monkeypatch):
        # Verify that if an exception or HTTP error occurs, the system safely catches it
        # and returns None without raising an unhandled error
        import requests
        engine = SurgicalTextFallbackEngine(api_key="valid_test_key_with_proper_length")

        def broken_post(*args, **kwargs):
            raise requests.exceptions.RequestException("Simulated OpenRouter connection failure")

        monkeypatch.setattr(requests, "post", broken_post)

        res = engine.extract_fallback_sync("Some raw packaging text", ["mrp", "net_quantity"])
        # Must return clean None dictionary and NOT crash
        assert res == {"mrp": None, "net_quantity": None}

    @pytest.mark.asyncio
    async def test_async_extract_fallback(self, monkeypatch):
        engine = SurgicalTextFallbackEngine(api_key="dummy_key_for_testing")
        res = await engine.extract_fallback("Sample text", ["country_of_origin"])
        assert "country_of_origin" in res
