"""
Report Generator Service
========================
Generates formatted PDF reports (via ReportLab) and editable Word reports (via python-docx)
summarising product compliance scan results, declarations check tables, and legal violations.

Public API
----------
    generate_pdf_report(scan_id, db=None) -> bytes
    generate_editable_report(scan_id, db=None) -> bytes
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan, ScanStatus
from app.models.violation import Violation, ViolationSeverity, ViolationType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DB Fetch Helper
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_scan_data(scan_id: int, db: AsyncSession | None) -> dict[str, Any]:
    """
    Fetch Scan, Product, and Violation records for scan_id from database.
    Returns structured data dictionary.
    """
    if db is None:
        raise ValueError(f"Database session required to fetch Scan ID {scan_id}")

    stmt = select(Scan).where(Scan.id == scan_id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()

    if not scan:
        raise ValueError(f"Scan with ID {scan_id} not found.")

    product = scan.product
    violations = list(scan.violations or [])

    # Derive overall status
    if not violations:
        verdict = "VERDICT: COMPLIANT"
        verdict_color = "green"
    else:
        has_format_or_font_err = any(
            (hasattr(v, "violation_type") and getattr(v.violation_type, "value", str(v.violation_type)) in ["incorrect_format", "undersized_font"])
            or (isinstance(v, dict) and v.get("violation_type") in ["incorrect_format", "undersized_font"])
            for v in violations
        )
        if has_format_or_font_err:
            verdict = "VERDICT: NON-COMPLIANT"
            verdict_color = "red"
        else:
            verdict = "VERDICT: INCONCLUSIVE (PARTIAL CROP)"
            verdict_color = "amber"

    calib_tier = "dpi_estimated"
    calib_label = "DPI Estimated (±0.5mm)"
    for v in violations:
        det = (v.details or "") if hasattr(v, "details") else ""
        if "AR verification" in det or "ar_verified" in det or "on-device AR" in det:
            calib_tier = "ar_verified"
            calib_label = "AR Verified (WebXR On-Device ±0.05mm)"
            break
        elif "circular reference" in det or "reference_object" in det:
            calib_tier = "reference_object"
            calib_label = "Reference Object (Calibrated ±0.2mm)"
        elif "manual package width" in det or "package_dimension" in det:
            calib_tier = "package_dimension"
            calib_label = "Package Dimension (Manual ±0.3mm)"

    return {
        "scan_id": scan.id,
        "scan_type": scan.scan_type.value if hasattr(scan.scan_type, "value") else str(scan.scan_type),
        "scan_status": scan.status.value if hasattr(scan.status, "value") else str(scan.status),
        "created_at": scan.created_at or datetime.now(timezone.utc),
        "product_id": product.id if product else "N/A",
        "product_name": product.name if product else "Unknown Product",
        "product_category": product.category if product else "General",
        "scanned_image_url": (product.scanned_image_url if product else None) or scan.raw_image_url,
        "verdict": verdict,
        "verdict_color": verdict_color,
        "calibration_tier": calib_tier,
        "calibration_label": calib_label,
        "violations": [
            {
                "field_name": v.field_name,
                "violation_type": v.violation_type.value if hasattr(v.violation_type, "value") else str(v.violation_type),
                "severity": v.severity.value if hasattr(v.severity, "value") else str(v.severity),
                "details": v.details or "N/A",
            }
            for v in violations
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. PDF Report Generator (ReportLab)
# ─────────────────────────────────────────────────────────────────────────────

def _build_pdf_bytes(data: dict[str, Any]) -> bytes:
    """Build PDF binary buffer using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E293B"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#64748B"),
    )
    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    bold_body = ParagraphStyle(
        "BoldBody",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    story = []

    # Title Banner
    story.append(Paragraph("Legal Metrology Compliance Report", title_style))
    story.append(Paragraph(f"labelGuard AI • Scan #{data['scan_id']}", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E1"), spaceAfter=12))

    # Overall Verdict Banner
    verdict_colors_map = {
        "green": (colors.HexColor("#DCFCE7"), colors.HexColor("#15803D")),
        "red": (colors.HexColor("#FEE2E2"), colors.HexColor("#B91C1C")),
        "amber": (colors.HexColor("#FEF3C7"), colors.HexColor("#B45309")),
    }
    bg_c, text_c = verdict_colors_map.get(data["verdict_color"], (colors.HexColor("#F1F5F9"), colors.HexColor("#334155")))

    verdict_text_style = ParagraphStyle(
        "VerdictText",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=text_c,
        alignment=1,  # Centered
    )

    verdict_table = Table(
        [[Paragraph(f"VERDICT: {data['verdict']}", verdict_text_style)]],
        colWidths=[540],
    )
    verdict_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_c),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 1, text_c),
        ])
    )
    story.append(verdict_table)
    story.append(Spacer(1, 12))

    # Metadata Grid
    created_str = data["created_at"].strftime("%Y-%m-%d %H:%M UTC") if isinstance(data["created_at"], datetime) else str(data["created_at"])
    meta_table_data = [
        [
            Paragraph("<b>Product Name:</b>", body_style), Paragraph(str(data["product_name"]), body_style),
            Paragraph("<b>Scan ID:</b>", body_style), Paragraph(str(data["scan_id"]), body_style),
        ],
        [
            Paragraph("<b>Category:</b>", body_style), Paragraph(str(data["product_category"]), body_style),
            Paragraph("<b>Scan Type:</b>", body_style), Paragraph(str(data["scan_type"]).upper(), body_style),
        ],
        [
            Paragraph("<b>Processed Date:</b>", body_style), Paragraph(created_str, body_style),
            Paragraph("<b>Scan Status:</b>", body_style), Paragraph(str(data["scan_status"]).upper(), body_style),
        ],
        [
            Paragraph("<b>Scale Calibration:</b>", body_style), Paragraph(str(data.get("calibration_label", "DPI Estimated (±0.5mm)")), bold_body),
            Paragraph("<b>Legal Standard:</b>", body_style), Paragraph("Legal Metrology 2011", body_style),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[100, 170, 100, 170])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(Paragraph("Scan Metadata", header_style))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Violations Table
    story.append(Paragraph("Compliance Violations Detail", header_style))

    if not data["violations"]:
        story.append(Paragraph("🎉 <i>No compliance violations detected. Label satisfies mandatory declarations!</i>", body_style))
    else:
        v_rows = [
            [
                Paragraph("<b>#</b>", bold_body),
                Paragraph("<b>Field Name</b>", bold_body),
                Paragraph("<b>Violation Type</b>", bold_body),
                Paragraph("<b>Severity</b>", bold_body),
                Paragraph("<b>Details</b>", bold_body),
            ]
        ]
        for idx, v in enumerate(data["violations"], 1):
            sev = v["severity"].upper()
            v_rows.append([
                Paragraph(str(idx), body_style),
                Paragraph(v["field_name"], bold_body),
                Paragraph(v["violation_type"].replace("_", " ").title(), body_style),
                Paragraph(f"<b>{sev}</b>", body_style),
                Paragraph(v["details"], body_style),
            ])

        v_table = Table(v_rows, colWidths=[25, 110, 105, 70, 230])
        v_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(v_table)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=8))
    story.append(
        Paragraph(
            "<i>Note: Evaluated under Indian Legal Metrology (Packaged Commodities) Rules 2011 & FSSAI guidelines. "
            "Generated automatically by labelGuard AI.</i>",
            subtitle_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()


async def generate_pdf_report(scan_id: int, db: AsyncSession | None = None) -> bytes:
    """Generate PDF report for scan_id as raw bytes."""
    data = await _fetch_scan_data(scan_id, db)
    return _build_pdf_bytes(data)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Editable Word Report Generator (python-docx)
# ─────────────────────────────────────────────────────────────────────────────

def _set_cell_background(cell, hex_color: str):
    """Set table cell background color in python-docx."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)


def _build_docx_bytes(data: dict[str, Any]) -> bytes:
    """Build Word (.docx) binary buffer using python-docx."""
    doc = Document()

    # Set page margins (0.75 in)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Title & Subtitle
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("Legal Metrology Compliance Report")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(30, 41, 59)

    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run(f"labelGuard AI • Scan #{data['scan_id']}")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(10)
    sub_run.font.color.rgb = RGBColor(100, 116, 139)

    # Verdict Banner Paragraph
    doc.add_paragraph()
    verdict_p = doc.add_paragraph()
    verdict_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    verdict_run = verdict_p.add_run(f"OVERALL VERDICT: {data['verdict']}")
    verdict_run.font.name = "Calibri"
    verdict_run.font.size = Pt(14)
    verdict_run.font.bold = True

    if data["verdict_color"] == "green":
        verdict_run.font.color.rgb = RGBColor(21, 128, 61)
    elif data["verdict_color"] == "red":
        verdict_run.font.color.rgb = RGBColor(185, 28, 28)
    else:
        verdict_run.font.color.rgb = RGBColor(180, 83, 9)

    # Metadata Heading
    h1 = doc.add_heading("1. Scan & Product Metadata", level=1)

    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.style = "Table Grid"

    created_str = data["created_at"].strftime("%Y-%m-%d %H:%M UTC") if isinstance(data["created_at"], datetime) else str(data["created_at"])
    meta_pairs = [
        ("Product Name:", str(data["product_name"])),
        ("Scan ID:", str(data["scan_id"])),
        ("Category:", str(data["product_category"])),
        ("Scan Type:", str(data["scan_type"]).upper()),
        ("Processed Date:", created_str),
        ("Status:", str(data["scan_status"]).upper()),
        ("Scale Calibration:", str(data.get("calibration_label", "DPI Estimated (±0.5mm)"))),
        ("Legal Standard:", "Legal Metrology 2011 (Rule 6/7)"),
    ]

    for idx, (label, val) in enumerate(meta_pairs):
        r_idx = idx // 2
        c_idx = idx % 2
        cell = meta_table.cell(r_idx, c_idx)
        p = cell.paragraphs[0]
        r1 = p.add_run(f"{label} ")
        r1.font.bold = True
        p.add_run(val)

    doc.add_paragraph()

    # Violations Heading
    doc.add_heading("2. Compliance Violations Detail", level=1)

    if not data["violations"]:
        p = doc.add_paragraph()
        r = p.add_run("No compliance violations detected. Label satisfies mandatory declarations!")
        r.font.italic = True
    else:
        v_table = doc.add_table(rows=1, cols=5)
        v_table.style = "Table Grid"
        hdr_cells = v_table.rows[0].cells
        headers = ["#", "Field Name", "Violation Type", "Severity", "Details"]

        for idx, text in enumerate(headers):
            cell = hdr_cells[idx]
            _set_cell_background(cell, "1E293B")
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

        for v_idx, v in enumerate(data["violations"], 1):
            row_cells = v_table.add_row().cells
            row_cells[0].paragraphs[0].text = str(v_idx)
            row_cells[1].paragraphs[0].text = v["field_name"]
            row_cells[2].paragraphs[0].text = v["violation_type"].replace("_", " ").title()
            row_cells[3].paragraphs[0].text = v["severity"].upper()
            row_cells[4].paragraphs[0].text = v["details"]

    doc.add_paragraph()
    footer_p = doc.add_paragraph()
    footer_run = footer_p.add_run(
        "Evaluated under Legal Metrology (Packaged Commodities) Rules 2011. Generated by labelGuard AI."
    )
    footer_run.font.italic = True
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor(148, 163, 184)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


async def generate_editable_report(scan_id: int, db: AsyncSession | None = None) -> bytes:
    """Generate Word (.docx) editable report for scan_id as raw bytes."""
    data = await _fetch_scan_data(scan_id, db)
    return _build_docx_bytes(data)
