"""
Test Suite for Re-Inspection Ticket Generation and Discrepancy Queue
===================================================================
Validates automated ticket generation on verdict conflict, sensor tier escalation
(AR-verified contradicting DPI-estimated baselines), priority scoring, and REST API endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.compliance_ledger import ComplianceLedger
from app.models.re_inspection_ticket import ReInspectionTicket, TicketPriority, TicketStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.services.compliance_ledger import (
    ConflictThresholdConfig,
    evaluate_verdict_conflict,
    record_scan_in_ledger,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Discrepancy & Conflict Evaluation Algorithm Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConflictDetectionAlgorithm:
    """Validates conflict classification, threshold rules, and priority assignment."""

    def test_sensor_tier_escalation_triggers_critical_ticket(self):
        """
        AR-verified non-compliant scan contradicting prior DPI-estimated compliant consensus
        MUST trigger a CRITICAL re-inspection ticket.
        """
        prior_tiers = {"dpi_estimated": 3, "ar_verified": 0, "reference_object": 0}
        result = evaluate_verdict_conflict(
            prior_verdict="compliant",
            prior_confidence=0.88,
            prior_calibration_tier_counts=prior_tiers,
            new_scan_status="non_compliant",
            new_calibration_tier="ar_verified",
            new_verdict="disputed",
            new_confidence=0.62,
            user_role="inspector",
        )

        assert result is not None
        assert result.has_conflict is True
        assert result.priority == "critical"
        assert result.conflict_type == "sensor_tier_escalation"
        assert "CRITICAL DISCREPANCY" in result.discrepancy_reason
        assert "AR-Verified 3D Depth" in result.discrepancy_reason

    def test_sensor_tier_escalation_disputes_prior_non_compliant(self):
        """
        AR-verified compliant scan contradicting prior DPI-estimated non-compliant baseline
        MUST trigger a HIGH priority ticket to review possible false positives.
        """
        prior_tiers = {"dpi_estimated": 2, "ar_verified": 0}
        result = evaluate_verdict_conflict(
            prior_verdict="non_compliant",
            prior_confidence=0.80,
            prior_calibration_tier_counts=prior_tiers,
            new_scan_status="compliant",
            new_calibration_tier="ar_verified",
            new_verdict="disputed",
            new_confidence=0.55,
            user_role="inspector",
        )

        assert result is not None
        assert result.has_conflict is True
        assert result.priority == "high"
        assert result.conflict_type == "sensor_tier_escalation"
        assert "disputing prior DPI-estimated non-compliant flags" in result.discrepancy_reason

    def test_verdict_flip_compliant_to_non_compliant(self):
        """
        When established compliant product receives non-compliant scan from inspector,
        must flag as critical verdict inversion.
        """
        prior_tiers = {"ar_verified": 1, "reference_object": 1}
        result = evaluate_verdict_conflict(
            prior_verdict="compliant",
            prior_confidence=0.92,
            prior_calibration_tier_counts=prior_tiers,
            new_scan_status="non_compliant",
            new_calibration_tier="reference_object",
            new_verdict="non_compliant",
            new_confidence=0.75,
            user_role="inspector",
        )

        assert result is not None
        assert result.has_conflict is True
        assert result.priority == "critical"
        assert result.conflict_type == "verdict_inversion"

    def test_consensus_disputed_triggers_ticket(self):
        """
        Contradictory scan forcing status from compliant into 'disputed' deadlock.
        """
        prior_tiers = {"package_dimension": 2}
        result = evaluate_verdict_conflict(
            prior_verdict="compliant",
            prior_confidence=0.82,
            prior_calibration_tier_counts=prior_tiers,
            new_scan_status="non_compliant",
            new_calibration_tier="package_dimension",
            new_verdict="disputed",
            new_confidence=0.50,
            user_role="viewer",
        )

        assert result is not None
        assert result.has_conflict is True
        assert result.conflict_type in ("verdict_inversion", "consensus_disputed")

    def test_confidence_drop_triggers_ticket(self):
        """
        Confidence dropping by >= 20% on contradictory evidence.
        """
        prior_tiers = {"dpi_estimated": 5}
        result = evaluate_verdict_conflict(
            prior_verdict="compliant",
            prior_confidence=0.90,
            prior_calibration_tier_counts=prior_tiers,
            new_scan_status="non_compliant",
            new_calibration_tier="dpi_estimated",
            new_verdict="compliant",
            new_confidence=0.65,  # 0.90 - 0.65 = 0.25 drop
            user_role="anonymous",
        )

        assert result is not None
        assert result.has_conflict is True
        assert result.priority in ("critical", "high", "medium")

    def test_agreement_does_not_trigger_ticket(self):
        """
        When a new scan agrees with aggregate verdict, no ticket should be spawned.
        """
        prior_tiers = {"dpi_estimated": 2}
        result = evaluate_verdict_conflict(
            prior_verdict="compliant",
            prior_confidence=0.85,
            prior_calibration_tier_counts=prior_tiers,
            new_scan_status="compliant",
            new_calibration_tier="dpi_estimated",
            new_verdict="compliant",
            new_confidence=0.90,
            user_role="inspector",
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Database Integration & Ticket Spawning
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketCreationInLedgerFlow:
    """Verifies that record_scan_in_ledger automatically creates ReInspectionTicket."""

    @pytest.mark.asyncio
    async def test_record_scan_in_ledger_spawns_ticket_on_ar_escalation(self):
        now_utc = datetime.now(timezone.utc)
        existing_ledger = ComplianceLedger(
            id=1,
            gtin="8901030383456",
            product_name="Sample Biscuit",
            category="Biscuits",
            total_scans=2,
            compliant_scans=2,
            non_compliant_scans=0,
            ar_verified_count=0,
            reference_object_count=0,
            package_dimension_count=0,
            dpi_estimated_count=2,
            current_verdict="compliant",
            rolling_confidence=0.85,
            batch_breakdown={"LOT-01": {"total_scans": 2, "compliant_scans": 2, "non_compliant_scans": 0}},
            last_scanned_at=now_utc,
        )

        mock_res1 = MagicMock()
        mock_res1.scalars.return_value.first.return_value = existing_ledger

        mock_res2 = MagicMock()
        mock_res2.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_res1, mock_res2])

        # New scan is AR-verified NON-COMPLIANT
        scan = Scan(id=999, product_id=1, scan_type=ScanType.manual, status=ScanStatus.completed)

        updated_ledger = await record_scan_in_ledger(
            db=mock_db,
            scan=scan,
            gtin="8901030383456",
            batch_code="LOT-02",
            compliance_status="non_compliant",
            calibration_tier="ar_verified",
            user_role="inspector",
            scan_confidence=0.98,
        )

        assert updated_ledger is not None
        # Verify db.add was called for the ReInspectionTicket
        added_objs = [call.args[0] for call in mock_db.add.call_args_list]
        tickets = [obj for obj in added_objs if isinstance(obj, ReInspectionTicket)]
        assert len(tickets) == 1
        ticket = tickets[0]
        assert ticket.gtin == "8901030383456"
        assert ticket.priority == "critical"
        assert ticket.conflict_type == "sensor_tier_escalation"
        assert ticket.status == "open"
        assert ticket.trigger_scan_id == 999


# ─────────────────────────────────────────────────────────────────────────────
# 3. REST API Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestReInspectionTicketsAPI:
    """Validates /tickets endpoints."""

    @pytest.mark.asyncio
    async def test_get_ticket_summary_stats(self):
        mock_stats = {
            "total_tickets": 10,
            "open_tickets": 6,
            "critical_tickets": 3,
            "high_tickets": 2,
            "investigating_tickets": 2,
            "resolved_tickets": 2,
        }

        with patch("app.routers.tickets.get_ticket_summary_stats", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = mock_stats

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/tickets/summary/stats")

            assert res.status_code == 200
            data = res.json()
            assert data["open_tickets"] == 6
            assert data["critical_tickets"] == 3

    @pytest.mark.asyncio
    async def test_list_tickets_ordered(self):
        now = datetime.now(timezone.utc)
        mock_ticket = ReInspectionTicket(
            id=1,
            ticket_number="RIT-890103-20260905120000",
            gtin="8901030383456",
            product_name="Sample Cookies",
            batch_code="LOT-10",
            trigger_scan_id=50,
            prior_verdict="compliant",
            prior_confidence=0.88,
            prior_calibration_tier="dpi_estimated",
            new_verdict="non_compliant",
            new_confidence=0.95,
            new_calibration_tier="ar_verified",
            conflict_type="sensor_tier_escalation",
            discrepancy_reason="AR audit flagged non-compliant",
            priority="critical",
            status="open",
            created_at=now,
            updated_at=now,
        )
        mock_ticket.trigger_scan = None

        with patch("app.routers.tickets.list_re_inspection_tickets", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [mock_ticket]

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/tickets?status=open")

            assert res.status_code == 200
            items = res.json()
            assert len(items) == 1
            assert items[0]["ticket_number"] == "RIT-890103-20260905120000"
            assert items[0]["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_patch_ticket_status(self):
        now = datetime.now(timezone.utc)
        mock_ticket = ReInspectionTicket(
            id=1,
            ticket_number="RIT-890103-20260905120000",
            gtin="8901030383456",
            product_name="Sample Cookies",
            batch_code="LOT-10",
            trigger_scan_id=50,
            prior_verdict="compliant",
            prior_confidence=0.88,
            prior_calibration_tier="dpi_estimated",
            new_verdict="non_compliant",
            new_confidence=0.95,
            new_calibration_tier="ar_verified",
            conflict_type="sensor_tier_escalation",
            discrepancy_reason="AR audit flagged non-compliant",
            priority="critical",
            status="investigating",
            assigned_to="Inspector Verma",
            resolution_notes="Initiated on-site sample collection",
            created_at=now,
            updated_at=now,
        )
        mock_ticket.trigger_scan = None

        with patch("app.routers.tickets.update_re_inspection_ticket", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_ticket

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.patch(
                    "/tickets/1",
                    json={
                        "status": "investigating",
                        "assigned_to": "Inspector Verma",
                        "resolution_notes": "Initiated on-site sample collection",
                    },
                )

            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "investigating"
            assert data["assigned_to"] == "Inspector Verma"
