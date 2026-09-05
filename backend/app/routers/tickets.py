"""
Re-Inspection Tickets Router.
Exposes endpoints to view, prioritize, filter, and resolve automated discrepancy tickets.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.re_inspection_ticket import (
    ReInspectionTicketRead,
    ReInspectionTicketUpdate,
    TicketSummaryStats,
)
from app.services.compliance_ledger import (
    get_re_inspection_ticket_by_id,
    get_ticket_summary_stats,
    list_re_inspection_tickets,
    update_re_inspection_ticket,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["Re-Inspection Tickets"])


def _serialize_ticket(ticket: Any) -> dict[str, Any]:
    """Helper to convert ReInspectionTicket ORM object into response dictionary."""
    violations = []
    if ticket.trigger_scan and hasattr(ticket.trigger_scan, "violations") and ticket.trigger_scan.violations:
        for v in ticket.trigger_scan.violations:
            violations.append({
                "field_name": v.field_name,
                "violation_type": v.violation_type.value if hasattr(v.violation_type, "value") else str(v.violation_type),
                "severity": v.severity.value if hasattr(v.severity, "value") else str(v.severity),
                "details": v.details or "",
            })

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "gtin": ticket.gtin,
        "product_name": ticket.product_name,
        "batch_code": ticket.batch_code,
        "trigger_scan_id": ticket.trigger_scan_id,
        "prior_verdict": ticket.prior_verdict,
        "prior_confidence": ticket.prior_confidence,
        "prior_calibration_tier": ticket.prior_calibration_tier,
        "new_verdict": ticket.new_verdict,
        "new_confidence": ticket.new_confidence,
        "new_calibration_tier": ticket.new_calibration_tier,
        "conflict_type": ticket.conflict_type,
        "discrepancy_reason": ticket.discrepancy_reason,
        "priority": ticket.priority,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to,
        "resolution_notes": ticket.resolution_notes,
        "resolved_at": ticket.resolved_at,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "trigger_scan_violations": violations,
    }


@router.get(
    "/summary/stats",
    response_model=TicketSummaryStats,
    summary="Get re-inspection ticket KPI summary counts",
)
async def get_summary_stats(
    db: AsyncSession = Depends(get_db),
) -> TicketSummaryStats:
    """Returns aggregated KPI counters for open, critical, high, and resolved tickets."""
    stats = await get_ticket_summary_stats(db)
    return TicketSummaryStats(**stats)


@router.get(
    "",
    response_model=list[ReInspectionTicketRead],
    summary="List re-inspection tickets prioritized by urgency",
)
async def list_tickets(
    status: str | None = Query(default=None, description="Filter by status: open, investigating, resolved, dismissed, or all"),
    priority: str | None = Query(default=None, description="Filter by priority: critical, high, medium, low"),
    gtin: str | None = Query(default=None, description="Filter by product GTIN barcode"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ReInspectionTicketRead]:
    """
    Returns prioritized re-inspection tickets ordered by priority:
    Critical -> High -> Medium -> Low, then newest creation timestamp.
    """
    tickets = await list_re_inspection_tickets(
        db=db,
        status=status,
        priority=priority,
        gtin=gtin,
        limit=limit,
        offset=offset,
    )
    return [ReInspectionTicketRead(**_serialize_ticket(t)) for t in tickets]


@router.get(
    "/{ticket_id}",
    response_model=ReInspectionTicketRead,
    summary="Get a single re-inspection ticket by ID",
)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReInspectionTicketRead:
    """Fetches details for a specific ticket including trigger scan violations."""
    ticket = await get_re_inspection_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Re-inspection ticket {ticket_id} not found",
        )
    return ReInspectionTicketRead(**_serialize_ticket(ticket))


@router.patch(
    "/{ticket_id}",
    response_model=ReInspectionTicketRead,
    summary="Update ticket status, officer assignment, or resolution notes",
)
async def update_ticket(
    ticket_id: int,
    payload: ReInspectionTicketUpdate,
    db: AsyncSession = Depends(get_db),
) -> ReInspectionTicketRead:
    """
    Updates the enforcement status (open -> investigating -> resolved / dismissed),
    assigns an officer, or attaches inspection resolution notes.
    """
    ticket = await update_re_inspection_ticket(
        db=db,
        ticket_id=ticket_id,
        status=payload.status,
        assigned_to=payload.assigned_to,
        resolution_notes=payload.resolution_notes,
    )
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Re-inspection ticket {ticket_id} not found",
        )
    return ReInspectionTicketRead(**_serialize_ticket(ticket))
