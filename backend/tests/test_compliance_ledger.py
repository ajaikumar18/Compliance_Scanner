"""
Test Suite for Compliance Ledger and GTIN Aggregation Service
============================================================
Validates rolling confidence scoring, sensor quality weighting, consensus verdict
transitions (compliant, non-compliant, disputed), per-batch tracking, atomic upsert,
and GET /ledger/{gtin} API endpoints.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.compliance_ledger import ComplianceLedger
from app.models.scan import Scan, ScanStatus, ScanType
from app.services.compliance_ledger import (
    CALIBRATION_TIER_WEIGHTS,
    USER_ROLE_WEIGHTS,
    compute_rolling_verdict_and_confidence,
    get_ledger_for_gtin,
    list_ledger_entries,
    record_scan_in_ledger,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Rolling Verdict & Confidence Algorithm Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRollingVerdictAndConfidenceAlgorithm:
    """Validates multi-evidence weighted consensus and confidence scoring."""

    def test_unanimous_compliant_high_confidence(self):
        evidence = [
            {"compliance_status": "compliant", "calibration_tier": "ar_verified", "user_role": "inspector", "confidence": 0.98},
            {"compliance_status": "compliant", "calibration_tier": "reference_object", "user_role": "inspector", "confidence": 0.95},
            {"compliance_status": "compliant", "calibration_tier": "dpi_estimated", "user_role": "anonymous", "confidence": 0.90},
        ]
        verdict, conf = compute_rolling_verdict_and_confidence(evidence)
        assert verdict == "compliant"
        assert conf >= 0.70

    def test_unanimous_non_compliant(self):
        evidence = [
            {"compliance_status": "non_compliant", "calibration_tier": "ar_verified", "user_role": "inspector", "confidence": 0.95},
            {"compliance_status": "non_compliant", "calibration_tier": "dpi_estimated", "user_role": "anonymous", "confidence": 0.85},
        ]
        verdict, conf = compute_rolling_verdict_and_confidence(evidence)
        assert verdict == "non_compliant"
        assert conf >= 0.60

    def test_disputed_verdict_on_conflicting_evidence(self):
        """When compliant and non-compliant evidence is split, verdict must transition to 'disputed'."""
        evidence = [
            {"compliance_status": "compliant", "calibration_tier": "package_dimension", "user_role": "viewer", "confidence": 0.95},
            {"compliance_status": "non_compliant", "calibration_tier": "package_dimension", "user_role": "viewer", "confidence": 0.95},
        ]
        verdict, conf = compute_rolling_verdict_and_confidence(evidence)
        assert verdict == "disputed"

    def test_ar_inspector_overrules_uncalibrated_public_scans(self):
        """
        1 AR-verified inspector audit (weight = 2.0 * 1.6 = 3.2)
        vs.
        2 uncalibrated anonymous DPI scans (weight = 2 * (0.7 * 0.8) = 1.12).
        The AR inspector non-compliant verdict dominates the score.
        """
        evidence = [
            {"compliance_status": "compliant", "calibration_tier": "dpi_estimated", "user_role": "anonymous", "confidence": 0.90},
            {"compliance_status": "compliant", "calibration_tier": "dpi_estimated", "user_role": "anonymous", "confidence": 0.90},
            {"compliance_status": "non_compliant", "calibration_tier": "ar_verified", "user_role": "inspector", "confidence": 0.98},
        ]
        verdict, conf = compute_rolling_verdict_and_confidence(evidence)
        # AR Inspector non-compliant weighted score (3.2 * 0.98 = 3.136) > compliant (1.12 * 0.9 = 1.008)
        # Ratio compliant ~ 1.008 / 4.144 = 24.3% (< 25%), so verdict is non_compliant
        assert verdict == "non_compliant"

    def test_empty_evidence_defaults(self):
        verdict, conf = compute_rolling_verdict_and_confidence([])
        assert verdict == "compliant"
        assert conf == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Ledger Database Upsert & Batch Breakdown Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestComplianceLedgerUpsert:
    """Validates atomic ledger creation and updates."""

    @pytest.mark.asyncio
    async def test_initial_scan_creates_ledger_row(self):
        mock_res = MagicMock()
        mock_res.scalars.return_value.first.return_value = None
        mock_res.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_res)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()


        scan = Scan(id=101, product_id=1, scan_type=ScanType.manual, status=ScanStatus.completed)

        entry = await record_scan_in_ledger(
            db=mock_db,
            scan=scan,
            gtin="8901030383456",
            batch_code="B4208",
            compliance_status="compliant",
            calibration_tier="ar_verified",
            user_role="inspector",
            scan_confidence=0.98,
            product_name="Sample Cookies",
            category="Food",
        )

        assert entry.gtin == "8901030383456"
        assert entry.total_scans == 1
        assert entry.compliant_scans == 1
        assert entry.non_compliant_scans == 0
        assert entry.ar_verified_count == 1
        assert entry.current_verdict == "compliant"
        assert "B4208" in entry.batch_breakdown
        assert entry.batch_breakdown["B4208"]["ar_verified_count"] == 1
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_subsequent_scan_updates_existing_ledger_row(self):
        """Second scan for same GTIN updates existing row without duplicate."""
        existing_entry = ComplianceLedger(
            id=1,
            gtin="8901030383456",
            product_name="Sample Cookies",
            category="Food",
            total_scans=1,
            compliant_scans=1,
            non_compliant_scans=0,
            ar_verified_count=1,
            reference_object_count=0,
            package_dimension_count=0,
            dpi_estimated_count=0,
            current_verdict="compliant",
            rolling_confidence=0.85,
            batch_breakdown={"B4208": {"total_scans": 1, "compliant_scans": 1, "non_compliant_scans": 0, "ar_verified_count": 1, "reference_object_count": 0, "package_dimension_count": 0, "dpi_estimated_count": 0, "current_verdict": "compliant"}},
        )

        mock_res1 = MagicMock()
        mock_res1.scalars.return_value.first.return_value = existing_entry

        mock_res2 = MagicMock()
        mock_res2.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_res1, mock_res2])


        scan2 = Scan(id=102, product_id=1, scan_type=ScanType.batch, status=ScanStatus.completed)

        updated = await record_scan_in_ledger(
            db=mock_db,
            scan=scan2,
            gtin="8901030383456",
            batch_code="LOT-99",
            compliance_status="non_compliant",
            calibration_tier="dpi_estimated",
            user_role="anonymous",
            scan_confidence=0.90,
        )

        assert updated.total_scans == 2
        assert updated.compliant_scans == 1
        assert updated.non_compliant_scans == 1
        assert updated.dpi_estimated_count == 1
        assert updated.ar_verified_count == 1
        assert "LOT-99" in updated.batch_breakdown
        assert updated.batch_breakdown["LOT-99"]["current_verdict"] == "non_compliant"


# ─────────────────────────────────────────────────────────────────────────────
# 3. API Endpoints Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestComplianceLedgerEndpoints:
    """Test GET /ledger/{gtin} and GET /ledger."""

    @pytest.mark.asyncio
    async def test_get_ledger_by_gtin_success(self):
        mock_ledger = {
            "gtin": "8901030383456",
            "product_name": "NutriChoice Biscuits",
            "category": "Biscuits",
            "total_scans": 5,
            "compliant_scans": 4,
            "non_compliant_scans": 1,
            "current_verdict": "compliant",
            "rolling_confidence": 0.88,
            "calibration_breakdown": {
                "ar_verified": 2,
                "reference_object": 1,
                "package_dimension": 1,
                "dpi_estimated": 1,
            },
            "batch_breakdown": {
                "B4208": {"total_scans": 3, "compliant_scans": 3, "non_compliant_scans": 0, "current_verdict": "compliant"}
            },
            "last_scanned_at": "2026-09-05T12:00:00Z",
            "scan_history": [
                {
                    "scan_id": 101,
                    "scan_type": "manual",
                    "status": "completed",
                    "compliance_status": "compliant",
                    "calibration_tier": "ar_verified",
                    "batch_code": "B4208",
                    "violations_count": 0,
                    "violations": [],
                    "created_at": "2026-09-05T12:00:00Z",
                }
            ],
        }

        with patch("app.routers.ledger.get_ledger_for_gtin", AsyncMock(return_value=mock_ledger)):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/ledger/8901030383456")

            assert resp.status_code == 200
            data = resp.json()
            assert data["gtin"] == "8901030383456"
            assert data["current_verdict"] == "compliant"
            assert data["total_scans"] == 5
            assert data["calibration_breakdown"]["ar_verified"] == 2
            assert len(data["scan_history"]) == 1

    @pytest.mark.asyncio
    async def test_get_ledger_by_gtin_not_found(self):
        with patch("app.routers.ledger.get_ledger_for_gtin", AsyncMock(return_value=None)):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/ledger/9999999999999")

            assert resp.status_code == 404
            assert "No compliance ledger records found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_all_compliance_ledgers(self):
        sample_entries = [
            ComplianceLedger(
                id=1,
                gtin="8901030383456",
                product_name="Product A",
                category="Food",
                total_scans=3,
                compliant_scans=3,
                non_compliant_scans=0,
                current_verdict="compliant",
                rolling_confidence=0.92,
            ),
            ComplianceLedger(
                id=2,
                gtin="8901030383999",
                product_name="Product B",
                category="Cosmetics",
                total_scans=2,
                compliant_scans=0,
                non_compliant_scans=2,
                current_verdict="non_compliant",
                rolling_confidence=0.88,
            ),
        ]

        with patch("app.routers.ledger.list_ledger_entries", AsyncMock(return_value=sample_entries)):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/ledger")

            assert resp.status_code == 200
            items = resp.json()
            assert len(items) == 2
            assert items[0]["gtin"] == "8901030383456"
            assert items[1]["gtin"] == "8901030383999"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Scan Pipeline End-to-End Ledger Integration
# ─────────────────────────────────────────────────────────────────────────────

class TestScanPipelineLedgerIntegration:
    """Verifies that _process_single_scan_image updates the ledger and returns ledger fields."""

    @pytest.mark.asyncio
    async def test_pipeline_records_in_ledger(self):
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

        mock_res = MagicMock()
        mock_res.scalars.return_value.first.return_value = None
        mock_res.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_res)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()


        # Mock OCR and ledger recording
        with patch("app.routers.scans.LaptopLayoutClassifier") as mock_classifier_cls:
            mock_inst = MagicMock()
            mock_inst.classify.return_value = {
                "classified": [{"field": "net_quantity", "text": "100 g", "bbox": [50, 220, 60, 20], "match_confidence": 0.95}],
                "unmatched": [{"text": "Batch No: LOT-2026-X", "bbox": [50, 250, 100, 20]}],
                "raw_text_pool": "Net Qty: 100 g\nBatch No: LOT-2026-X\nMRP Rs. 50",
            }
            mock_classifier_cls.return_value = mock_inst

            result = await _process_single_scan_image(
                image_bytes=img_bytes,
                filename="test_product.png",
                scan_type_str="manual",
                source_url="https://example.com/test_product.png",
                category="Food",
                package_width_mm=100.0,
                net_quantity_g=100.0,
                db=mock_db,
                ar_pixels_per_mm=12.5,  # AR-verified tier
            )

            # Check that scan response contains GTIN, Batch Code, and Ledger fields
            assert result["gtin"] == "8901030383456"
            assert result["batch_code"] == "LOT-2026-X"
            assert result["ledger_verdict"] in ("compliant", "non_compliant", "disputed")
            assert result["ledger_confidence"] is not None
            assert 0.0 <= result["ledger_confidence"] <= 1.0
