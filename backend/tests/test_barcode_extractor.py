"""
Test Suite for Barcode, QR Code, GTIN, and Batch Code Extraction
================================================================
Validates EAN-13, UPC-A, and QR code detection, GTIN standardization,
OCR proximity-based batch/lot code extraction, and Scan model persistence.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.scan import Scan, ScanStatus, ScanType
from app.schemas.scan import ScanBase, ScanRead
from app.services.barcode_extractor import (
    decode_barcodes,
    extract_batch_code,
    extract_gtin_from_text,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Barcode and QR Code Decoding Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBarcodeDecoding:
    """Test suite for decode_barcodes engine."""

    def test_decode_synthetic_qr_code(self):
        """Generate a synthetic QR code via OpenCV and decode via decode_barcodes."""
        encoder = cv2.QRCodeEncoder.create()
        qr_matrix = encoder.encode("8901030383456")
        assert qr_matrix is not None and qr_matrix.size > 0

        # Scale up and embed into white canvas
        qr_scaled = cv2.resize(qr_matrix, (200, 200), interpolation=cv2.INTER_NEAREST)
        canvas = np.ones((300, 300), dtype=np.uint8) * 255
        canvas[50:250, 50:250] = qr_scaled
        canvas_bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)

        results = decode_barcodes(canvas_bgr)
        assert len(results) >= 1
        decoded = results[0]
        assert decoded["text"] == "8901030383456"
        assert decoded["gtin"] == "8901030383456"
        assert "QR" in decoded["format"]
        assert decoded["bbox"] is not None
        assert len(decoded["bbox"]) == 4
        assert decoded["bbox"][2] > 0 and decoded["bbox"][3] > 0

    def test_decode_empty_or_blank_image(self):
        """Blank images or None should safely return an empty list."""
        assert decode_barcodes(None) == []
        assert decode_barcodes(np.array([])) == []

        blank = np.zeros((100, 100, 3), dtype=np.uint8)
        assert decode_barcodes(blank) == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. GTIN Extraction & Standardization Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGtinExtraction:
    """Test standardizing GTIN across multiple formats and symbologies."""

    def test_extract_ean13(self):
        gtin = extract_gtin_from_text("8901030383456", "EAN-13")
        assert gtin == "8901030383456"

        gtin_raw = extract_gtin_from_text("8901030383456", "EAN13")
        assert gtin_raw == "8901030383456"

    def test_extract_upca(self):
        gtin = extract_gtin_from_text("012345678905", "UPC-A")
        assert gtin == "012345678905"

        gtin_raw = extract_gtin_from_text("012345678905", "UPCA")
        assert gtin_raw == "012345678905"

    def test_extract_ean8_and_itf14(self):
        assert extract_gtin_from_text("12345670", "EAN-8") == "12345670"
        assert extract_gtin_from_text("10012345678902", "ITF-14") == "10012345678902"

    def test_extract_gs1_digital_link_url(self):
        url = "https://id.gs1.org/01/08901030383456"
        assert extract_gtin_from_text(url, "QR Code") == "08901030383456"

    def test_extract_gs1_element_string(self):
        elem_str = "(01)08901030383456(10)LOT4208(17)261231"
        assert extract_gtin_from_text(elem_str, "QR Code") == "08901030383456"

    def test_extract_plain_numeric_qr(self):
        assert extract_gtin_from_text("8901030383456", "QR Code") == "8901030383456"

    def test_non_gtin_url_returns_none(self):
        assert extract_gtin_from_text("https://example.com/product/info", "QR Code") is None
        assert extract_gtin_from_text("Random non-numeric text", "CODE128") is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Batch / Lot Code Extraction & Proximity Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchCodeExtraction:
    """Test proximity-based and regex extraction of batch/lot codes."""

    def test_extract_explicit_batch_patterns(self):
        cases = [
            ({"text": "Batch No: B4208", "bbox": [10, 10, 50, 15]}, "B4208"),
            ({"text": "B.No. : 99-ABC", "bbox": [10, 10, 50, 15]}, "99-ABC"),
            ({"text": "Lot No. 12/2026", "bbox": [10, 10, 50, 15]}, "12/2026"),
            ({"text": "B/N: LOTX100", "bbox": [10, 10, 50, 15]}, "LOTX100"),
            ({"text": "BATCH: L24-001", "bbox": [10, 10, 50, 15]}, "L24-001"),
        ]
        for block, expected in cases:
            res = extract_batch_code([block])
            assert res == expected, f"Failed for text '{block['text']}', got '{res}'"

    def test_proximity_sorting_to_barcode(self):
        """
        When multiple candidate blocks exist, select the one physically closest
        to the barcode bounding box.
        """
        barcode_bbox = [100, 100, 80, 50]  # Center at (140, 125)

        # Block A: Close to barcode (center at 150, 160 -> dist ~ 36px)
        block_near = {"text": "Batch No: NEAR123", "bbox": [130, 150, 40, 20]}

        # Block B: Far from barcode (center at 800, 900 -> dist ~ 1000px)
        block_far = {"text": "Batch No: FAR999", "bbox": [780, 890, 40, 20]}

        # When far is listed first in OCR blocks, proximity should still pick near
        res = extract_batch_code([block_far, block_near], barcode_bbox=barcode_bbox)
        assert res == "NEAR123"

    def test_raw_text_pool_fallback(self):
        """When OCR blocks list is empty, extract from raw text pool."""
        pool = "Mfg Date: 01/2026\nExpiry: 01/2028\nBatch No: BATCH_FALLBACK_77\nMRP: Rs. 150"
        res = extract_batch_code(ocr_blocks=[], barcode_bbox=None, raw_text_pool=pool)
        assert res == "BATCH_FALLBACK_77"

    def test_reject_false_positives(self):
        """Words like 'date', 'mfg', 'exp', 'mrp' should not be picked as batch numbers."""
        block = {"text": "Batch No: EXP", "bbox": [10, 10, 50, 15]}
        res = extract_batch_code([block])
        assert res is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Scan ORM Model & Schema Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScanModelAndSchema:
    """Verify Scan model and Pydantic schemas include gtin and batch_code."""

    def test_scan_orm_model_columns(self):
        scan = Scan(
            product_id=1,
            scan_type=ScanType.batch,
            raw_image_url="https://example.com/pkg.jpg",
            status=ScanStatus.completed,
            gtin="8901030383456",
            batch_code="B4208",
        )
        assert scan.gtin == "8901030383456"
        assert scan.batch_code == "B4208"
        assert scan.product_id == 1
        assert scan.scan_type == ScanType.batch

    def test_scan_pydantic_schemas(self):
        data = {
            "product_id": 42,
            "scan_type": "batch",
            "raw_image_url": "https://example.com/label.png",
            "gtin": "8901030383456",
            "batch_code": "LOT-9988",
        }
        base_schema = ScanBase(**data)
        assert base_schema.gtin == "8901030383456"
        assert base_schema.batch_code == "LOT-9988"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Scan Pipeline End-to-End Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestScanPipelineFlow:
    """Verify _process_single_scan_image integrates barcode and batch code extraction."""

    @pytest.mark.asyncio
    async def test_pipeline_populates_gtin_and_batch_code(self):
        from app.routers.scans import _process_single_scan_image

        # Create a synthetic image with a QR code
        encoder = cv2.QRCodeEncoder.create()
        qr_matrix = encoder.encode("8901030383456")
        qr_scaled = cv2.resize(qr_matrix, (150, 150), interpolation=cv2.INTER_NEAREST)

        canvas = np.ones((400, 400), dtype=np.uint8) * 255
        canvas[50:200, 50:200] = qr_scaled
        canvas_bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
        _, img_encoded = cv2.imencode(".png", canvas_bgr)
        img_bytes = img_encoded.tobytes()

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        # Mock OCR classifier to provide a batch code
        with patch("app.routers.scans.LaptopLayoutClassifier") as mock_classifier_cls:
            mock_inst = MagicMock()
            mock_inst.classify.return_value = {
                "classified": [
                    {
                        "field": "net_quantity",
                        "text": "100 g",
                        "bbox": [50, 220, 60, 20],
                        "match_confidence": 0.95,
                    }
                ],
                "unmatched": [
                    {
                        "text": "Batch No: LOT-2026-X",
                        "bbox": [50, 250, 100, 20],
                    }
                ],
                "raw_text_pool": "Net Qty: 100 g\nBatch No: LOT-2026-X\nMRP Rs. 50",
            }
            mock_classifier_cls.return_value = mock_inst

            result = await _process_single_scan_image(
                image_bytes=img_bytes,
                filename="test_pkg.png",
                scan_type_str="batch",
                source_url="https://example.com/test_pkg.png",
                category="Food",
                package_width_mm=100.0,
                net_quantity_g=100.0,
                db=mock_db,
            )

            # Check that GTIN was extracted from the synthetic QR code
            assert result["gtin"] == "8901030383456"
            # Check that Batch Code was extracted from OCR block
            assert result["batch_code"] == "LOT-2026-X"
            # Check barcodes list
            assert len(result["barcodes"]) >= 1
            # Check product name tagging with GTIN
            assert "GTIN-8901030383456" in result["product_name"]

            # Verify that Scan ORM object was created with gtin and batch_code
            added_objects = [call[0][0] for call in mock_db.add.call_args_list]
            scan_instances = [obj for obj in added_objects if isinstance(obj, Scan)]
            assert len(scan_instances) == 1
            saved_scan = scan_instances[0]
            assert saved_scan.gtin == "8901030383456"
            assert saved_scan.batch_code == "LOT-2026-X"
