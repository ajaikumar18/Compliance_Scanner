"""
Reports API Router
==================
Exposes endpoints to download certified PDF and Word (.docx) compliance reports
for individual packaging specimens and multi-specimen batch dockets.

Endpoints
---------
    GET  /reports/batch/pdf           (Download batch PDF docket for recent/specified scans)
    POST /reports/batch/pdf           (Download batch PDF docket for specified scan_ids or objects)
    POST /reports/pdf                 (Generate single scan PDF on-the-fly from JSON payload)
    GET  /reports/{scan_id}/pdf       (Download single scan PDF report, supports LM-2026-XXXX UIDs and numeric IDs)
    GET  /reports/{scan_id}/docx      (Download single scan DOCX editable report)
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_viewer
from app.core.database import get_db
from app.models.user import User
from app.services.report_generator import (
    generate_batch_pdf_report,
    generate_editable_report,
    generate_pdf_from_data,
    generate_pdf_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Request Models ─────────────────────────────────────────────────────────────

class SingleReportPayload(BaseModel):
    scan: dict[str, Any]


class BatchReportPayload(BaseModel):
    scan_ids: list[str] | None = None
    scans: list[dict[str, Any]] | None = None
    batch_title: str = "Multi-Specimen Compliance Audit Docket"
    batch_id: str | None = None


# ── Batch Scan Report Endpoints (Declared First to Prevent Route Shadowing) ────

@router.get(
    "/batch/pdf",
    summary="Download Batch PDF Compliance Audit Docket (GET)",
    response_description="Consolidated multi-specimen batch PDF audit docket",
)
async def get_batch_pdf_report(
    limit: int = Query(25, ge=1, le=100, description="Max specimens to include in batch audit"),
    category: str | None = Query(None, description="Filter batch by product category"),
    scan_ids: str | None = Query(None, description="Comma-separated scan UIDs e.g. LM-2026-000030,LM-2026-000029"),
    batch_title: str = Query("Multi-Specimen Compliance Audit Docket", description="Title printed on docket cover"),
    current_user: User = Depends(require_viewer),
):
    """
    Download a consolidated multi-specimen batch PDF audit report.
    Pulls specimens from the unified database or by specific scan IDs.
    """
    from app.core.scan_repository import ScanRepository

    scans_to_include = []
    if scan_ids:
        for sid in scan_ids.split(","):
            s_clean = sid.strip()
            if s_clean:
                item = ScanRepository.get_scan(s_clean)
                if item:
                    scans_to_include.append(item)
    else:
        repo_res = ScanRepository.list_scans(limit=limit, category=category or "all")
        scans_to_include = repo_res.get("items", [])

    if not scans_to_include:
        # Fallback to recent in-memory scans
        from app.routers.scans import RECENT_SCANS
        scans_to_include = RECENT_SCANS[:limit]

    if not scans_to_include:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No packaging scan records found to compile batch compliance docket.",
        )

    try:
        pdf_bytes = generate_batch_pdf_report(
            scans_data=scans_to_include,
            batch_title=batch_title,
            batch_id=f"DOCKET-LM-{datetime.now(timezone.utc).strftime('%m%d%H%M')}",
        )
        filename = f"batch_compliance_docket_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as exc:
        logger.error("Failed to compile batch PDF docket: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch report compilation error: {exc}",
        )


@router.post(
    "/batch/pdf",
    summary="Download Batch PDF Compliance Audit Docket (POST)",
    response_description="Consolidated multi-specimen batch PDF audit docket",
)
async def post_batch_pdf_report(
    payload: BatchReportPayload,
    current_user: User = Depends(require_viewer),
):
    """
    Compile and stream a multi-specimen batch compliance audit docket from a list of
    scan IDs or scan result objects.
    """
    from app.core.scan_repository import ScanRepository

    scans_to_include: list[dict[str, Any]] = []

    # 1. Collect from scan_ids
    if payload.scan_ids:
        for sid in payload.scan_ids:
            item = ScanRepository.get_scan(sid)
            if item:
                scans_to_include.append(item)

    # 2. Collect from payload.scans
    if payload.scans:
        scans_to_include.extend(payload.scans)

    # 3. If empty, fall back to recent scans
    if not scans_to_include:
        repo_res = ScanRepository.list_scans(limit=25, category="all")
        scans_to_include = repo_res.get("items", [])

    if not scans_to_include:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scan specimens provided or found to compile batch compliance docket.",
        )

    try:
        pdf_bytes = generate_batch_pdf_report(
            scans_data=scans_to_include,
            batch_title=payload.batch_title,
            batch_id=payload.batch_id,
        )
        clean_batch_name = (payload.batch_id or "batch_docket").replace(" ", "_")
        filename = f"{clean_batch_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as exc:
        logger.error("Failed to compile batch PDF report: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch report compilation error: {exc}",
        )


# ── On-the-Fly Single PDF Endpoint ────────────────────────────────────────────

@router.post(
    "/pdf",
    summary="Generate PDF Compliance Report from Payload",
    response_description="Formatted PDF compliance report file generated on-the-fly",
)
async def post_generate_pdf_from_payload(
    payload: SingleReportPayload,
    current_user: User = Depends(require_viewer),
):
    """
    Generate and download a formatted PDF compliance report directly from a scan JSON object.
    Provides instantaneous report generation even before records are written to disk.
    """
    try:
        pdf_bytes = generate_pdf_from_data(payload.scan)
        scan_id = payload.scan.get("scan_id") or payload.scan.get("scan_uid") or "specimen"
        clean_id = str(scan_id).replace(" ", "_").replace("/", "_")
        filename = f"compliance_report_{clean_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as exc:
        logger.error("Failed to generate PDF from payload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {exc}",
        )


# ── Parameterized Single Scan Report Endpoints ────────────────────────────────

@router.get(
    "/{scan_id}/pdf",
    summary="Download PDF Compliance Report",
    response_description="Formatted PDF compliance report file",
)
async def get_pdf_report(
    scan_id: str,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download a formatted PDF compliance report for the specified scan ID.
    Supports both formatted UIDs (e.g. 'LM-2026-000030') and integer IDs.
    """
    logger.info("Generating PDF report for scan_id=%s requested by user=%s", scan_id, current_user.username)
    try:
        pdf_bytes = await generate_pdf_report(scan_id=scan_id, db=db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Failed to generate PDF report for scan_id=%s: %s", scan_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation error: {exc}",
        )

    clean_id = scan_id.replace(" ", "_").replace("/", "_")
    filename = f"compliance_report_{clean_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get(
    "/{scan_id}/docx",
    summary="Download Word (.docx) Compliance Report",
    response_description="Editable Word compliance report file",
)
async def get_docx_report(
    scan_id: str,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download an editable Microsoft Word (.docx) compliance report for the specified scan ID.
    """
    logger.info("Generating DOCX report for scan_id=%s requested by user=%s", scan_id, current_user.username)
    try:
        docx_bytes = await generate_editable_report(scan_id=scan_id, db=db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Failed to generate DOCX report for scan_id=%s: %s", scan_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Word report generation error: {exc}",
        )

    clean_id = scan_id.replace(" ", "_").replace("/", "_")
    filename = f"compliance_report_{clean_id}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
