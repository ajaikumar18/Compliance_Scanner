"""
Tests for Citizen Ingestion, Priority Check Branch, Tamper Verification, and Review Queue
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.core.auth import require_citizen_or_above, RoleChecker
from app.models.user import User, UserRole
from app.models.violation import ViolationType
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.re_inspection_ticket import ReInspectionTicket
from app.routers.tickets import _serialize_ticket
from app.routers.scans import _process_single_scan_image


def test_user_role_citizen_exists():
    assert UserRole.citizen.value == "citizen"
    assert UserRole("citizen") == UserRole.citizen


def test_require_citizen_or_above():
    citizen_user = User(id=10, username="citizen_jane", role=UserRole.citizen, hashed_password="pw")
    inspector_user = User(id=11, username="officer_bob", role=UserRole.inspector, hashed_password="pw")
    admin_user = User(id=12, username="admin_alice", role=UserRole.admin, hashed_password="pw")
    viewer_user = User(id=13, username="guest", role=UserRole.viewer, hashed_password="pw")

    # Allowed roles
    assert require_citizen_or_above(citizen_user) == citizen_user
    assert require_citizen_or_above(inspector_user) == inspector_user
    assert require_citizen_or_above(admin_user) == admin_user

    # Disallowed role
    with pytest.raises(HTTPException) as exc:
        require_citizen_or_above(viewer_user)
    assert exc.value.status_code == 403


def test_serialize_ticket_citizen_metadata():
    scan = Scan(
        id=42,
        product_id=1,
        scan_type=ScanType.batch,
        status=ScanStatus.completed,
        source="citizen",
        claimed_violation_type="undersized_font",
    )
    ticket = MagicMock(spec=ReInspectionTicket)
    ticket.id = 1
    ticket.ticket_number = "RIT-12345"
    ticket.gtin = "8901030383456"
    ticket.product_name = "Test Product"
    ticket.batch_code = "LOT-01"
    ticket.trigger_scan_id = 42
    ticket.prior_verdict = "compliant"
    ticket.prior_confidence = 0.95
    ticket.prior_calibration_tier = "ar_verified"
    ticket.new_verdict = "non_compliant"
    ticket.new_confidence = 0.85
    ticket.new_calibration_tier = "dpi_estimated"
    ticket.conflict_type = "sensor_tier_escalation"
    ticket.discrepancy_reason = "Test conflict"
    ticket.priority = "high"
    ticket.status = "open"
    ticket.assigned_to = None
    ticket.resolution_notes = None
    ticket.resolved_at = None
    ticket.created_at = "2026-09-18T12:00:00Z"
    ticket.updated_at = "2026-09-18T12:00:00Z"
    ticket.trigger_scan = scan

    data = _serialize_ticket(ticket)
    assert data["source"] == "citizen"
    assert data["claimed_violation_type"] == "undersized_font"


@pytest.mark.asyncio
async def test_sha256_tamper_detection_failure():
    # Synthetic small image
    import numpy as np
    import cv2
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    raw_bytes = encoded.tobytes()

    bad_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(HTTPException) as exc:
        await _process_single_scan_image(
            image_bytes=raw_bytes,
            filename="test.png",
            scan_type_str="manual",
            source_url=None,
            category="Food",
            package_width_mm=100.0,
            net_quantity_g=100.0,
            image_sha256=bad_hash,
        )
    assert exc.value.status_code == 400
    assert "Evidence tamper verification failed" in exc.value.detail


@pytest.mark.asyncio
async def test_priority_check_branch_and_auto_report():
    import numpy as np
    import cv2
    img = np.ones((120, 120, 3), dtype=np.uint8) * 255
    _, encoded = cv2.imencode(".png", img)
    raw_bytes = encoded.tobytes()
    correct_hash = hashlib.sha256(raw_bytes).hexdigest()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.routers.scans.LaptopLayoutClassifier") as mock_classifier:
        mock_inst = MagicMock()
        mock_inst.classify.return_value = {
            "classified": [],
            "unmatched": [],
            "raw_text_pool": "Sample Packaged Food 100g",
        }
        mock_classifier.return_value = mock_inst

        with patch("app.routers.scans.evaluate_compliance") as mock_eval:
            mock_eval.return_value = {
                "compliance_status": "compliant",
                "violations": [],
                "field_checks": {},
            }

            res = await _process_single_scan_image(
                image_bytes=raw_bytes,
                filename="citizen_specimen.png",
                scan_type_str="manual",
                source_url=None,
                category="Packaged Foods",
                package_width_mm=100.0,
                net_quantity_g=100.0,
                db=mock_db,
                claimed_violation_type="missing_mrp",
                submitter_role="citizen",
                image_sha256=correct_hash,
            )

            assert res["source"] == "citizen"
            assert res["submitter_role"] == "citizen"
            assert res["claimed_violation_type"] == "missing_mrp"
            assert res["priority_check_result"] is not None
            assert res["priority_check_result"]["field_name"] == "mrp"
            assert res["priority_check_result"]["violation_type"] in [ViolationType.missing.value, ViolationType.incorrect_format.value]
            assert res["image_sha256"] == correct_hash
