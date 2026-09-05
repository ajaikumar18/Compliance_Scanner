"""
Tests for backend/app/services/field_classifier.py

Tests cover:
- All 6 mandatory field types with realistic label text
- High / medium / low confidence thresholds
- GenAI fallback triage
- Missing fields detection
- Field summary helper
- Edge cases: empty input, blank text, multi-field text

Run with:
    cd backend
    python -m pytest tests/test_field_classifier.py -v
"""

from __future__ import annotations

import sys
import os

import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.field_classifier import (
    OcrBlock,
    ClassifiedBlock,
    classify_fields,
    get_field_summary,
    get_missing_fields,
    MIN_MATCH_CONFIDENCE,
    GENAI_FALLBACK_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _blk(text: str, conf: float = 0.90) -> OcrBlock:
    return OcrBlock(
        text=text,
        bbox=[0, 0, 200, 30],
        confidence=conf,
        engine_used="tesseract",
    )


MANDATORY_FIELDS = {
    "manufacturer_name_address",
    "net_quantity",
    "mrp",
    "manufacture_date",
    "expiry_date",
    "consumer_care_details",
    "country_of_origin",
}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures – one realistic text block per mandatory field
# ─────────────────────────────────────────────────────────────────────────────

# Each tuple is (expected_field, realistic_ocr_text_from_label)
FIELD_SAMPLES: list[tuple[str, str]] = [
    # MRP
    ("mrp", "MRP Rs. 120.00 (Inclusive of all taxes)"),
    ("mrp", "M.R.P. ₹ 49"),
    ("mrp", "Maximum Retail Price: Rs.250"),

    # Net Quantity
    ("net_quantity", "Net Wt. 500 g"),
    ("net_quantity", "Net Weight: 1 kg"),
    ("net_quantity", "Contents: 200 ml"),
    ("net_quantity", "Nett Wt 250gms"),

    # Manufacture Date
    ("manufacture_date", "Mfg. Date: 12/2025"),
    ("manufacture_date", "Manufactured on Jan 2026"),
    ("manufacture_date", "Packed on 15/03/2025"),
    ("manufacture_date", "Date of Mfg: 10/2025"),

    # Expiry Date
    ("expiry_date", "Use By: 15/04/2026"),
    ("expiry_date", "Best Before: 06-2026"),
    ("expiry_date", "Expiry Date: 31/12/2026"),
    ("expiry_date", "BBE: Oct 2025"),

    # Manufacturer Name & Address
    ("manufacturer_name_address", "Manufactured by XYZ Foods Pvt. Ltd."),
    ("manufacturer_name_address", "Marketed by ABC Beverages Private Limited"),
    ("manufacturer_name_address", "Packed by Sunshine Industries, Mumbai"),
    ("manufacturer_name_address", "Plot No. 45, Industrial Area, Pune"),

    # Consumer Care Details
    ("consumer_care_details", "Consumer Care: 1800-123-4567 (Toll Free)"),
    ("consumer_care_details", "Customer Helpline No. 022-66778899"),
    ("consumer_care_details", "support@example.com"),
    ("consumer_care_details", "www.brand.in"),

    # Country of Origin
    ("country_of_origin", "Country of Origin: India"),
    ("country_of_origin", "Made in India"),
    ("country_of_origin", "Product of India"),
]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Per-field classification accuracy
# ─────────────────────────────────────────────────────────────────────────────

class TestFieldClassification:
    @pytest.mark.parametrize("expected_field,text", FIELD_SAMPLES)
    def test_field_classified_correctly(self, expected_field: str, text: str):
        """Each realistic label text must be classified into the correct field."""
        result = classify_fields([_blk(text)])
        classified = result["classified"]
        assert len(classified) >= 1, (
            f"No classification for text={text!r} (expected field={expected_field})"
        )
        fields_found = {b["field"] for b in classified}
        assert expected_field in fields_found, (
            f"Expected field={expected_field!r}, got {fields_found!r} for text={text!r}"
        )

    def test_all_six_fields_present_in_samples(self):
        """Verify our sample list covers all 6 mandatory fields."""
        covered = {f for f, _ in FIELD_SAMPLES}
        assert covered == MANDATORY_FIELDS


# ─────────────────────────────────────────────────────────────────────────────
# 2. Confidence scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceScoring:
    def test_match_confidence_is_float_0_to_1(self):
        result = classify_fields([_blk("MRP Rs. 99")])
        for b in result["classified"]:
            assert 0.0 <= b["match_confidence"] <= 1.0

    def test_explicit_label_has_high_confidence(self):
        """Explicit labels like 'MRP Rs. 120' should score >= 0.90."""
        result = classify_fields([_blk("MRP Rs. 120.00 (Inclusive of all taxes)")])
        assert result["classified"]
        top = max(result["classified"], key=lambda b: b["match_confidence"])
        assert top["match_confidence"] >= 0.90, (
            f"Expected >= 0.90, got {top['match_confidence']}"
        )

    def test_pattern_matched_field_present(self):
        result = classify_fields([_blk("Net Wt. 500 g")])
        for b in result["classified"]:
            assert isinstance(b["pattern_matched"], str)
            assert len(b["pattern_matched"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. GenAI fallback triage
# ─────────────────────────────────────────────────────────────────────────────

class TestGenAiFallback:
    def test_unknown_text_goes_to_unmatched(self):
        """Random noise text should land in unmatched."""
        result = classify_fields([_blk("xyzzy foobar 12345 random")])
        assert len(result["unmatched"]) >= 1

    def test_low_confidence_match_also_in_unmatched(self):
        """
        Blocks with match_confidence < GENAI_FALLBACK_THRESHOLD should appear
        in unmatched even if a field was found (for GenAI cross-checking).
        """
        # "India" alone → country_of_origin but low confidence (0.55)
        result = classify_fields([_blk("India")])
        # This should be in unmatched since 0.55 < GENAI_FALLBACK_THRESHOLD (0.60)
        if result["classified"]:
            low_conf = [
                b for b in result["classified"]
                if b["match_confidence"] < GENAI_FALLBACK_THRESHOLD
            ]
            if low_conf:
                assert len(result["unmatched"]) >= 1

    def test_high_confidence_not_duplicated_in_unmatched(self):
        """
        A high-confidence block (e.g. explicit MRP) should NOT appear in
        unmatched — it's already handled.
        """
        result = classify_fields([_blk("MRP Rs. 120.00 (Inclusive of all taxes)")])
        # Verify the MRP block is classified with high confidence
        mrp_blocks = [b for b in result["classified"] if b["field"] == "mrp"]
        assert mrp_blocks
        high_conf_mrp = [b for b in mrp_blocks if b["match_confidence"] >= GENAI_FALLBACK_THRESHOLD]
        # Such blocks should NOT be in unmatched
        unmatched_texts = {b["text"] for b in result["unmatched"]}
        for b in high_conf_mrp:
            assert b["text"] not in unmatched_texts

    def test_empty_input_returns_empty_result(self):
        result = classify_fields([])
        assert result["classified"] == []
        assert result["unmatched"] == []

    def test_blank_text_block_skipped(self):
        """Blocks with only whitespace should be silently skipped."""
        result = classify_fields([_blk("   ")])
        assert result["classified"] == []
        assert result["unmatched"] == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Output schema
# ─────────────────────────────────────────────────────────────────────────────

class TestOutputSchema:
    def test_classified_block_has_all_keys(self):
        required_keys = {"text", "bbox", "confidence", "engine_used",
                         "field", "match_confidence", "pattern_matched"}
        result = classify_fields([_blk("Net Wt. 500 g")])
        for b in result["classified"]:
            assert required_keys.issubset(b.keys()), (
                f"Missing keys: {required_keys - b.keys()!r}"
            )

    def test_field_values_are_valid_mandatory_fields(self):
        texts = [text for _, text in FIELD_SAMPLES]
        blocks = [_blk(t) for t in texts]
        result = classify_fields(blocks)
        for b in result["classified"]:
            assert b["field"] in MANDATORY_FIELDS, (
                f"Unexpected field: {b['field']!r}"
            )

    def test_bbox_is_list_of_four_ints(self):
        result = classify_fields([_blk("MRP Rs.99")])
        for b in result["classified"]:
            assert isinstance(b["bbox"], list)
            assert len(b["bbox"]) == 4
            assert all(isinstance(v, int) for v in b["bbox"])

    def test_result_has_classified_and_unmatched_keys(self):
        result = classify_fields([_blk("hello world")])
        assert "classified" in result
        assert "unmatched" in result


# ─────────────────────────────────────────────────────────────────────────────
# 5. Helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestHelperFunctions:
    def _full_result(self):
        texts = [text for _, text in FIELD_SAMPLES]
        return classify_fields([_blk(t) for t in texts])

    def test_get_field_summary_returns_dict(self):
        summary = get_field_summary(self._full_result())
        assert isinstance(summary, dict)

    def test_get_field_summary_keys_are_valid_fields(self):
        summary = get_field_summary(self._full_result())
        for key in summary:
            assert key in MANDATORY_FIELDS

    def test_get_field_summary_values_are_lists_of_str(self):
        summary = get_field_summary(self._full_result())
        for texts in summary.values():
            assert isinstance(texts, list)
            assert all(isinstance(t, str) for t in texts)

    def test_get_missing_fields_returns_list(self):
        result = classify_fields([_blk("unknown garbage text")])
        missing = get_missing_fields(result)
        assert isinstance(missing, list)

    def test_get_missing_fields_all_missing_on_empty(self):
        result = classify_fields([])
        missing = get_missing_fields(result)
        assert set(missing) == MANDATORY_FIELDS

    def test_get_missing_fields_mrp_not_missing(self):
        result = classify_fields([_blk("MRP Rs. 120.00 (Inclusive of all taxes)")])
        missing = get_missing_fields(result)
        assert "mrp" not in missing

    def test_get_missing_fields_returns_sorted(self):
        result = classify_fields([])
        missing = get_missing_fields(result)
        assert missing == sorted(missing)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_multiple_blocks_different_fields(self):
        blocks = [
            _blk("MRP Rs. 99"),
            _blk("Net Wt. 500 g"),
            _blk("Manufactured by XYZ Pvt. Ltd., Mumbai"),
            _blk("Mfg. Date: Jan 2026"),
            _blk("Use By: 15/04/2026"),
            _blk("Consumer Care: 1800-123-4567"),
            _blk("Country of Origin: India"),
        ]
        result = classify_fields(blocks)
        fields_found = {b["field"] for b in result["classified"]}
        assert fields_found == MANDATORY_FIELDS, (
            f"Missing fields: {MANDATORY_FIELDS - fields_found}"
        )

    def test_same_field_multiple_blocks(self):
        """Multiple blocks may map to the same field (e.g. address spans lines)."""
        blocks = [
            _blk("Manufactured by XYZ Pvt. Ltd."),
            _blk("Plot No. 12, Industrial Area, Pune"),
        ]
        result = classify_fields(blocks)
        mfr_blocks = [b for b in result["classified"]
                      if b["field"] == "manufacturer_name_address"]
        assert len(mfr_blocks) >= 1

    def test_noisy_text_around_known_keyword(self):
        """Keyword buried in noise should still be found."""
        result = classify_fields([_blk("#### MRP Rs. 45.00 (incl. all taxes) ####")])
        assert any(b["field"] == "mrp" for b in result["classified"])

    def test_email_in_consumer_care(self):
        result = classify_fields([_blk("reach us at care@brand.com")])
        classified = result["classified"]
        assert any(b["field"] == "consumer_care_details" for b in classified)

    def test_website_in_consumer_care(self):
        result = classify_fields([_blk("Visit www.brand.in for details")])
        classified = result["classified"]
        assert any(b["field"] == "consumer_care_details" for b in classified)

    def test_pvt_ltd_matches_manufacturer(self):
        result = classify_fields([_blk("Sunrise Foods Pvt. Ltd.")])
        assert any(b["field"] == "manufacturer_name_address"
                   for b in result["classified"])

    def test_ocr_block_fields_preserved(self):
        """Classified block must preserve original bbox, confidence, engine_used."""
        blk = OcrBlock(
            text="MRP Rs. 99",
            bbox=[5, 10, 150, 25],
            confidence=0.88,
            engine_used="easyocr",
        )
        result = classify_fields([blk])
        assert result["classified"]
        cb = result["classified"][0]
        assert cb["bbox"] == [5, 10, 150, 25]
        assert cb["confidence"] == 0.88
        assert cb["engine_used"] == "easyocr"

    def test_date_collision_prevention(self):
        """When an OCR pool has only one date, manufacture_date and expiry_date must never collide."""
        blocks = [
            _blk("PKD. 16/10/25"),
            _blk("USE BY"),
        ]
        result = classify_fields(blocks)
        mfg = [b for b in result["classified"] if b["field"] == "manufacture_date"]
        exp = [b for b in result["classified"] if b["field"] == "expiry_date"]
        assert len(mfg) == 1
        assert "16/10/25" in mfg[0]["text"]
        # Expiry date must not steal the manufacture date
        assert len(exp) == 0 or exp[0]["text"] != mfg[0]["text"]

    def test_serving_size_not_classified_as_net_quantity(self):
        """Serving size and nutritional noise like 'Per approx. 15 g serve' must never be selected over net quantity."""
        blocks = [
            _blk("Per approx. 15 g serve"),
            _blk("(Approx. 3 Biscuits)"),
            _blk("Energy 67 kcal"),
            _blk("FOR 64 g~"),
            _blk("BISCUITS NET WEIGHT 64 g"),
            _blk("MRP Rs. 10.00"),
        ]
        result = classify_fields(blocks)
        net_qty = result.get("extracted_fields", {}).get("net_quantity", {})
        assert net_qty
        # Must resolve to 64g, never 15g
        assert "64" in net_qty.get("extracted_value", "")
        assert "15" not in net_qty.get("extracted_value", "")

    def test_serving_size_alone_does_not_claim_net_quantity(self):
        """When only serving size is in OCR text without total net weight, it must not falsely classify as net quantity."""
        blocks = [
            _blk("Per approx. 15 g serve"),
            _blk("(Approx. 3 Biscuits)"),
            _blk("Energy 67 kcal"),
        ]
        result = classify_fields(blocks)
        net_qty = result.get("extracted_fields", {}).get("net_quantity")
        assert net_qty is None or "15" not in net_qty.get("extracted_value", "")


