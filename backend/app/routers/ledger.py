"""
Compliance Ledger API Router
============================
Endpoints for querying GTIN-level aggregated compliance history, sensor evidence tiers,
consensus verdicts (compliant, non-compliant, disputed), and rolling confidence scores.

Endpoints:
----------
    GET /ledger/{gtin}      - Aggregate compliance status, calibration breakdown, and scan history for a GTIN
    GET /ledger             - List all tracked GTIN ledger entries with optional verdict filtering
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.compliance_ledger import ComplianceLedgerResponse, ComplianceLedgerSummaryItem
from app.services.compliance_ledger import get_ledger_for_gtin, list_ledger_entries

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ledger", tags=["Compliance Ledger"])


@router.get(
    "/{gtin}",
    response_model=ComplianceLedgerResponse,
    summary="Get Aggregate Compliance Ledger & History by GTIN",
    description=(
        "Returns the aggregate compliance verdict (compliant, non-compliant, or disputed), "
        "rolling confidence score weighted higher for AR-verified and inspector scans, "
        "sensor calibration breakdown, batch breakdown, and complete scan audit history for the GTIN."
    ),
)
async def get_product_compliance_ledger(
    gtin: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Query compliance ledger by product GTIN (EAN-13, UPC-A, etc.).
    """
    clean_gtin = gtin.strip()
    ledger_data = await get_ledger_for_gtin(db, clean_gtin)
    if not ledger_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No compliance ledger records found for GTIN '{clean_gtin}'. Scan a product label with this barcode first.",
        )
    return ledger_data


@router.get(
    "",
    response_model=list[ComplianceLedgerSummaryItem],
    summary="List All GTIN Compliance Ledger Entries",
    description="List all tracked products in the compliance ledger with current verdicts and confidence scores.",
)
async def list_all_compliance_ledgers(
    verdict: str | None = Query(default=None, description="Filter by verdict: 'compliant', 'non_compliant', 'disputed'"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List all aggregated GTIN ledger records.
    """
    entries = await list_ledger_entries(db, verdict=verdict, limit=limit, offset=offset)
    return entries
