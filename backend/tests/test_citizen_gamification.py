"""
Tests for Citizen Confirmation Messaging, Gamification (Trust XP), and Negative-XP Fraud Filter
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.citizen_notification import CitizenNotification, NotificationType
from app.routers.auth import get_reputation_tier
from app.routers.scans import _process_single_scan_image, batch_scan_images


def test_user_xp_defaults_and_tier_calculation():
    user = User(id=1, username="citizen_alice", role=UserRole.citizen, hashed_password="pw")
    assert getattr(user, "xp", None) == 100

    assert get_reputation_tier(600) == "Master Metrologist"
    assert get_reputation_tier(250) == "Vigilant Citizen"
    assert get_reputation_tier(100) == "Citizen Scout"
    assert get_reputation_tier(20) == "Probationary Citizen"
    assert get_reputation_tier(-10) == "Restricted Submitter"


@pytest.mark.asyncio
async def test_negative_xp_blocked_at_batch_endpoint():
    bad_actor = User(id=99, username="spammer", role=UserRole.citizen, hashed_password="pw", xp=-30)
    mock_file = MagicMock()
    mock_file.filename = "label.jpg"
    mock_file.read = AsyncMock(return_value=b"fake-bytes")

    with pytest.raises(HTTPException) as exc:
        await batch_scan_images(
            files=[mock_file],
            scan_type="manual",
            submitter_role="citizen",
            current_user=bad_actor,
            db=AsyncMock(),
        )
    assert exc.value.status_code == 403
    assert "Submission blocked: Account has negative trust XP" in exc.value.detail


@pytest.mark.asyncio
async def test_tampering_deducts_100_xp():
    import numpy as np
    import cv2
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    raw_bytes = encoded.tobytes()

    citizen = User(id=20, username="test_citizen", role=UserRole.citizen, hashed_password="pw", xp=100)
    bad_hash = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await _process_single_scan_image(
            image_bytes=raw_bytes,
            filename="tampered.png",
            scan_type_str="manual",
            source_url=None,
            category="Food",
            package_width_mm=100.0,
            net_quantity_g=100.0,
            image_sha256=bad_hash,
            submitter_role="citizen",
            current_user=citizen,
            db=mock_db,
        )

    assert exc.value.status_code == 400
    assert "Evidence tamper verification failed" in exc.value.detail
    # Verify 100 XP was deducted
    assert citizen.xp == 0


@pytest.mark.asyncio
async def test_correct_violation_claim_awards_50_xp():
    import numpy as np
    import cv2
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    raw_bytes = encoded.tobytes()
    valid_hash = hashlib.sha256(raw_bytes).hexdigest()

    citizen = User(id=30, username="good_citizen", role=UserRole.citizen, hashed_password="pw", xp=100)
    mock_db = AsyncMock()

    # Mock priority check and rule evaluator to confirm violation
    with patch("app.routers.scans.check_font_compliance", return_value={
        "compliant": False,
        "measured_mm": 1.0,
        "required_mm": 3.0,
        "rule_reference": "Rule 7",
    }):
        with patch("app.routers.scans.evaluate_compliance", return_value={
            "compliance_status": "non_compliant",
            "violations": [{"field": "net_quantity", "type": "undersized_font", "description": "Undersized font"}],
        }):
            res = await _process_single_scan_image(
                image_bytes=raw_bytes,
                filename="undersized.png",
                scan_type_str="manual",
                source_url=None,
                category="Food",
                package_width_mm=100.0,
                net_quantity_g=100.0,
                claimed_violation_type="undersized_font",
                submitter_role="citizen",
                image_sha256=valid_hash,
                current_user=citizen,
                db=mock_db,
            )

    assert res["xp_awarded"] == 50
    assert res["current_xp"] == 150
    assert citizen.xp == 150
    assert "Violation Confirmed" in res["confirmation_message"]
    assert "+50 Trust XP awarded" in res["confirmation_message"]


@pytest.mark.asyncio
async def test_false_violation_claim_deducts_25_xp():
    import numpy as np
    import cv2
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    raw_bytes = encoded.tobytes()
    valid_hash = hashlib.sha256(raw_bytes).hexdigest()

    citizen = User(id=40, username="mistaken_citizen", role=UserRole.citizen, hashed_password="pw", xp=100)
    mock_db = AsyncMock()

    # Priority check finds font compliant, and overall evaluation compliant
    with patch("app.routers.scans.check_font_compliance", return_value={
        "compliant": True,
        "measured_mm": 4.0,
        "required_mm": 3.0,
        "rule_reference": "Rule 7",
    }):
        with patch("app.routers.scans.evaluate_compliance", return_value={
            "compliance_status": "compliant",
            "violations": [],
        }):
            res = await _process_single_scan_image(
                image_bytes=raw_bytes,
                filename="compliant.png",
                scan_type_str="manual",
                source_url=None,
                category="Food",
                package_width_mm=100.0,
                net_quantity_g=100.0,
                claimed_violation_type="undersized_font",
                submitter_role="citizen",
                image_sha256=valid_hash,
                current_user=citizen,
                db=mock_db,
            )

    assert res["xp_awarded"] == -25
    assert res["current_xp"] == 75
    assert citizen.xp == 75
    assert "Claim Refuted" in res["confirmation_message"]
    assert "-25 Trust XP deducted" in res["confirmation_message"]
