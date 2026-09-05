"""
Tests for Celery task process_scan_batch and async scan status endpoints

Tests cover:
- Celery app & Redis configuration
- process_scan_batch Celery task execution & progress updates
- POST /scan/batch/queue endpoint queuing task and returning batch_id
- GET /scan/batch/{batch_id}/status endpoint querying PENDING, PROGRESS ("45/100 processed"), and SUCCESS states

Run with:
    cd backend
    python -m pytest tests/test_celery_scans.py -v
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.celery_app import celery_app
from app.main import app
from app.tasks.scan_tasks import process_scan_batch

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Celery App Config Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCeleryAppConfig:
    def test_celery_broker_configured(self):
        assert celery_app.conf.broker_url.startswith("redis://")

    def test_celery_result_backend_configured(self):
        assert celery_app.conf.result_backend.startswith("redis://")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Celery Task Execution Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCeleryTaskExecution:
    @patch("app.tasks.scan_tasks._run_pipeline_for_image")
    @patch("requests.get")
    def test_process_scan_batch_progress_updates(self, mock_get, mock_pipeline):
        # Mock HTTP image fetch
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.content = b"X" * 100
        mock_get.return_value = mock_http_resp

        # Mock DB pipeline execution
        mock_pipeline.return_value = {
            "scan_id": 1,
            "product_name": "Test Image",
            "compliance_status": "compliant",
            "violations_count": 0,
        }

        image_urls = ["http://example.com/img1.jpg", "http://example.com/img2.jpg"]

        # Run task eagerly
        celery_app.conf.task_always_eager = True
        try:
            res = process_scan_batch.apply(args=[image_urls]).get()
        finally:
            celery_app.conf.task_always_eager = False

        assert res["status"] == "completed"
        assert res["processed"] == 2
        assert res["failed"] == 0
        assert len(res["results"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. FastAPI Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAsyncBatchEndpoints:
    @patch("app.routers.scans.process_scan_batch.delay")
    def test_queue_batch_scan_url_list(self, mock_delay):
        mock_task = MagicMock()
        mock_task.id = "batch-task-uuid-12345"
        mock_delay.return_value = mock_task

        payload = {
            "image_urls": ["http://example.com/a.jpg", "http://example.com/b.jpg"],
            "scan_type": "ecommerce",
            "category": "Snacks",
        }

        response = client.post("/scan/batch/queue", json=payload)

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "queued"
        assert json_res["batch_id"] == "batch-task-uuid-12345"
        assert json_res["total_images"] == 2

    @patch("app.routers.scans.AsyncResult")
    def test_get_batch_status_pending(self, mock_async_result):
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_async_result.return_value = mock_result

        response = client.get("/scan/batch/task-123/status")

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "queued"
        assert json_res["processed"] == 0

    @patch("app.routers.scans.AsyncResult")
    def test_get_batch_status_progress(self, mock_async_result):
        """Test progress response format e.g. '45/100 processed'."""
        mock_result = MagicMock()
        mock_result.state = "PROGRESS"
        mock_result.info = {"current": 45, "total": 100, "status": "45/100 processed"}
        mock_async_result.return_value = mock_result

        response = client.get("/scan/batch/task-123/status")

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "processing"
        assert json_res["processed"] == 45
        assert json_res["total"] == 100
        assert json_res["progress_percent"] == 45.0
        assert json_res["message"] == "45/100 processed"

    @patch("app.routers.scans.AsyncResult")
    def test_get_batch_status_success(self, mock_async_result):
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"status": "completed", "processed": 10, "total": 10, "results": []}
        mock_async_result.return_value = mock_result

        response = client.get("/scan/batch/task-123/status")

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "completed"
        assert json_res["processed"] == 10
        assert json_res["progress_percent"] == 100.0
        assert json_res["message"] == "10/10 processed"

    @patch("app.routers.scans.AsyncResult")
    def test_get_batch_status_failure(self, mock_async_result):
        mock_result = MagicMock()
        mock_result.state = "FAILURE"
        mock_result.info = RuntimeError("Download error")
        mock_async_result.return_value = mock_result

        response = client.get("/scan/batch/task-123/status")

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "failed"
        assert "Download error" in json_res["error"]

    @patch("app.routers.scans.process_scan_batch.delay")
    def test_queue_batch_scan_local_fallback_when_celery_offline(self, mock_delay):
        """When Celery/Redis connection fails, endpoint must seamlessly run locally without error."""
        mock_delay.side_effect = ConnectionError("Error 10061 connecting to localhost:6379")

        payload = {
            "image_urls": ["http://example.com/item1.jpg"],
            "scan_type": "ecommerce",
            "category": "Snacks",
        }

        response = client.post("/scan/batch/queue", json=payload)
        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "queued"
        assert json_res["batch_id"].startswith("batch_")
        assert json_res["total_images"] == 1

        # Check status endpoint retrieves the local job
        status_resp = client.get(f"/scan/batch/{json_res['batch_id']}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["batch_id"] == json_res["batch_id"]
        assert status_data["status"] in ("queued", "processing", "completed")

    def test_list_recent_scans_endpoint(self):
        """GET /scans and GET /scan/history must return recent scans from DB or memory."""
        from app.routers.scans import RECENT_SCANS
        RECENT_SCANS.append({
            "scan_id": 999,
            "product_name": "Test Product",
            "product_category": "Snacks",
            "compliance_status": "compliant",
            "violations_count": 0,
            "violations": [],
            "fields": {},
        })
        response = client.get("/scans")
        assert response.status_code == 200
        data = response.json()
        assert "scans" in data
        assert "total" in data
        assert isinstance(data["scans"], list)
        assert data["total"] >= 1

        alias_resp = client.get("/scan/history")
        assert alias_resp.status_code == 200
        alias_data = alias_resp.json()
        assert "scans" in alias_data
        assert alias_data["total"] >= 1



