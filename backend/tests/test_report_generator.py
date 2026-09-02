"""
Tests for backend/app/services/report_generator.py and app/routers/reports.py

Tests cover:
- ReportLab PDF byte generation & formatting
- python-docx Word (.docx) byte generation & formatting
- Database model fetching for Scan, Product, and Violation
- 404 handling when Scan ID does not exist
- FastAPI HTTP GET /reports/{scan_id}/pdf & /reports/{scan_id}/docx endpoint responses

Run with:
    cd backend
    python -m pytest tests/test_report_generator.py -v
"""

from __future__ import annotations

import datetime
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.main import app
from app.services.report_generator import (
    _build_docx_bytes,
    _build_pdf_bytes,
    generate_editable_report,
    generate_pdf_report,
)


def _mock_scan_data(scan_id=1, with_violations=True) -> dict:
    violations = []
    if with_violations:
        violations = [
            {
                "field_name": "mrp",
                "violation_type": "missing",
                "severity": "high",
                "details": "Mandatory declaration 'Maximum Retail Price (MRP)' is missing.",
            },
            {
                "field_name": "net_quantity",
                "violation_type": "undersized_font",
                "severity": "medium",
                "details": "Font height 1.20mm is below required minimum 2.00mm.",
            },
        ]
    return {
        "scan_id": scan_id,
        "scan_type": "manual",
        "scan_status": "completed",
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "product_id": 101,
        "product_name": "Organic Almond Milk 1L",
        "product_category": "Beverages",
        "scanned_image_url": "http://minio/labels/almond_milk.jpg",
        "verdict": "NON-COMPLIANT" if with_violations else "COMPLIANT",
        "verdict_color": "red" if with_violations else "green",
        "violations": violations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Report Builder Pure Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestReportBuilders:
    def test_build_pdf_bytes_returns_valid_pdf_header(self):
        data = _mock_scan_data(scan_id=42, with_violations=True)
        pdf_bytes = _build_pdf_bytes(data)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 500
        # Valid PDF files start with %PDF- header
        assert pdf_bytes.startswith(b"%PDF-")

    def test_build_pdf_bytes_compliant_no_violations(self):
        data = _mock_scan_data(scan_id=43, with_violations=False)
        pdf_bytes = _build_pdf_bytes(data)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")

    def test_build_docx_bytes_returns_valid_zip_header(self):
        data = _mock_scan_data(scan_id=42, with_violations=True)
        docx_bytes = _build_docx_bytes(data)

        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 1000
        # DOCX is a ZIP archive; starts with PK header (0x50, 0x4B)
        assert docx_bytes.startswith(b"PK")

    def test_build_docx_bytes_compliant_no_violations(self):
        data = _mock_scan_data(scan_id=43, with_violations=False)
        docx_bytes = _build_docx_bytes(data)

        assert isinstance(docx_bytes, bytes)
        assert docx_bytes.startswith(b"PK")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Async Report Generator Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestReportGeneratorService:
    @pytest.mark.asyncio
    async def test_generate_pdf_report_with_mocked_db(self):
        data = _mock_scan_data(scan_id=10)
        with patch("app.services.report_generator._fetch_scan_data", new_callable=AsyncMock, return_value=data):
            pdf_bytes = await generate_pdf_report(scan_id=10, db=AsyncMock())

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")

    @pytest.mark.asyncio
    async def test_generate_editable_report_with_mocked_db(self):
        data = _mock_scan_data(scan_id=10)
        with patch("app.services.report_generator._fetch_scan_data", new_callable=AsyncMock, return_value=data):
            docx_bytes = await generate_editable_report(scan_id=10, db=AsyncMock())

        assert isinstance(docx_bytes, bytes)
        assert docx_bytes.startswith(b"PK")

    @pytest.mark.asyncio
    async def test_generate_pdf_report_not_found_raises(self):
        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = result_mock

        with pytest.raises(ValueError, match="not found"):
            await generate_pdf_report(scan_id=999, db=db_mock)


# ─────────────────────────────────────────────────────────────────────────────
# 3. FastAPI Endpoint Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

client = TestClient(app)


class TestReportsEndpoints:
    def test_get_pdf_endpoint_success(self):
        data = _mock_scan_data(scan_id=5)
        with patch("app.routers.reports.generate_pdf_report", new_callable=AsyncMock, return_value=_build_pdf_bytes(data)):
            response = client.get("/reports/5/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert 'attachment; filename="compliance_report_scan_5.pdf"' in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF-")

    def test_get_docx_endpoint_success(self):
        data = _mock_scan_data(scan_id=5)
        with patch("app.routers.reports.generate_editable_report", new_callable=AsyncMock, return_value=_build_docx_bytes(data)):
            response = client.get("/reports/5/docx")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert 'attachment; filename="compliance_report_scan_5.docx"' in response.headers["content-disposition"]
        assert response.content.startswith(b"PK")

    def test_get_pdf_endpoint_not_found(self):
        with patch("app.routers.reports.generate_pdf_report", side_effect=ValueError("Scan with ID 999 not found.")):
            response = client.get("/reports/999/pdf")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_docx_endpoint_not_found(self):
        with patch("app.routers.reports.generate_editable_report", side_effect=ValueError("Scan with ID 999 not found.")):
            response = client.get("/reports/999/docx")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
