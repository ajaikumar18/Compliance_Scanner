"""
Reports API Router
==================
Exposes endpoints to download PDF and Word (.docx) compliance reports for a given scan_id.

Endpoints
---------
    GET /reports/{scan_id}/pdf
    GET /reports/{scan_id}/docx
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_viewer
from app.core.database import get_db
from app.models.user import User
from app.services.report_generator import generate_editable_report, generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/{scan_id}/pdf",
    summary="Download PDF Compliance Report",
    response_description="Formatted PDF compliance report file",
)
async def get_pdf_report(
    scan_id: int,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download a formatted PDF compliance report for the specified scan ID.

    The PDF report includes:
      - Product and scan metadata
      - Summary verdict banner (COMPLIANT / NON-COMPLIANT / PARTIAL REVIEW NEEDED)
      - Detailed compliance violations table with severity badges and legal citations
      - Declarations check table (Found / Missing / Font Compliance)
    """
    logger.info("Generating PDF report for scan_id=%d requested by user=%s", scan_id, current_user.username)
    try:
        pdf_bytes = await generate_pdf_report(scan_id=scan_id, db=db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Failed to generate PDF report for scan_id=%d: %s", scan_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation error: {exc}",
        )

    filename = f"compliance_report_scan_{scan_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{scan_id}/docx",
    summary="Download Word (.docx) Compliance Report",
    response_description="Editable Word compliance report file",
)
async def get_docx_report(
    scan_id: int,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download an editable Microsoft Word (.docx) compliance report for the specified scan ID.

    The Word report includes editable text tables and metadata sections for human inspector customization.
    """
    try:
        docx_bytes = await generate_editable_report(scan_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Failed to generate DOCX report for scan_id=%d: %s", scan_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate Word compliance report.",
        )

    filename = f"compliance_report_scan_{scan_id}.docx"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"",
    }
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
