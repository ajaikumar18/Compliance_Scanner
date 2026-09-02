"""
Tests for app/routers/scans.py and scraper/ecommerce_scraper.py

Tests cover:
- Scans API router (POST /scans/batch & POST /scan/batch)
- Scrapy Spider parsing for Amazon, Flipkart, BigBasket, and Generic HTML responses
- Scrapy settings compliance (ROBOTSTXT_OBEY, DOWNLOAD_DELAY)
- Image staging & batch submission helpers

Run with:
    cd backend
    python -m pytest tests/test_scans_and_scraper.py -v
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from scrapy.http import HtmlResponse

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE_DIR = os.path.dirname(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, _WORKSPACE_DIR)

from app.main import app
from scraper.ecommerce_scraper import (
    EcommerceCategorySpider,
    download_and_stage_images,
    submit_batch_to_backend,
)

client = TestClient(app)


def _make_dummy_image_bytes() -> bytes:
    """Create a dummy BGR JPEG image bytes buffer."""
    img = np.full((100, 200, 3), 200, dtype=np.uint8)
    cv2.putText(img, "MRP Rs. 100", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Scans API Router Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScansApiRouter:
    @patch("app.routers.scans._process_single_scan_image")
    def test_post_scans_batch_success(self, mock_process):
        mock_process.return_value = {
            "scan_id": 1,
            "product_id": 10,
            "product_name": "Test Product",
            "source_url": "http://amazon.in/test",
            "compliance_status": "compliant",
            "violations_count": 0,
            "violations": [],
            "extraction_summary": {},
        }

        img_bytes = _make_dummy_image_bytes()
        files = [("files", ("test_img.jpg", img_bytes, "image/jpeg"))]
        data = {
            "scan_type": "ecommerce",
            "source_url": "http://amazon.in/test",
            "category": "Biscuits",
        }

        response = client.post("/scans/batch", files=files, data=data)

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "success"
        assert json_res["total_processed"] == 1
        assert len(json_res["results"]) == 1

    @patch("app.routers.scans._process_single_scan_image")
    def test_post_scan_batch_alias_success(self, mock_process):
        """Test /scan/batch alias endpoint."""
        mock_process.return_value = {
            "scan_id": 2,
            "product_id": 11,
            "product_name": "Test Alias Product",
            "source_url": "http://flipkart.com/test",
            "compliance_status": "non_compliant",
            "violations_count": 1,
            "violations": [],
            "extraction_summary": {},
        }

        img_bytes = _make_dummy_image_bytes()
        files = [("files", ("test_img.jpg", img_bytes, "image/jpeg"))]
        data = {"scan_type": "ecommerce"}

        response = client.post("/scan/batch", files=files, data=data)

        assert response.status_code == 200
        json_res = response.json()
        assert json_res["status"] == "success"
        assert json_res["results"][0]["scan_id"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 2. Scrapy Spider Selector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEcommerceCategorySpider:
    def test_spider_settings_compliance(self):
        settings = EcommerceCategorySpider.custom_settings
        assert settings["ROBOTSTXT_OBEY"] is True
        assert settings["DOWNLOAD_DELAY"] == 2.0
        assert settings["RANDOMIZE_DOWNLOAD_DELAY"] is True

    def test_parse_amazon_html(self):
        amazon_html = """
        <html>
        <body>
            <div class="s-result-item" data-component-type="s-search-result">
                <h2><a><span class="a-text-normal">Amazon Product 1</span></a></h2>
                <img class="s-image" src="https://m.media-amazon.com/images/I/71xyz.jpg" />
            </div>
            <a class="s-pagination-next" href="/s?k=biscuits&page=2">Next</a>
        </body>
        </html>
        """
        response = HtmlResponse(
            url="https://www.amazon.in/s?k=biscuits",
            body=amazon_html,
            encoding="utf-8",
        )

        staged_items = []
        spider = EcommerceCategorySpider(
            start_url="https://www.amazon.in/s?k=biscuits",
            max_pages=2,
            staged_items=staged_items,
        )

        # Execute parse generator
        results = list(spider.parse(response))

        assert len(staged_items) == 1
        assert staged_items[0]["name"] == "Amazon Product 1"
        assert staged_items[0]["image_url"] == "https://m.media-amazon.com/images/I/71xyz.jpg"
        assert len(results) == 1  # 1 pagination request generated

    def test_parse_flipkart_html(self):
        flipkart_html = """
        <html>
        <body>
            <div class="_1AtVbE">
                <div class="_4rR01T">Flipkart Snack Pack</div>
                <img class="_396cs4" src="https://rukminim1.flixcart.com/image/snack.jpg" />
            </div>
        </body>
        </html>
        """
        response = HtmlResponse(
            url="https://www.flipkart.com/search?q=snacks",
            body=flipkart_html,
            encoding="utf-8",
        )

        staged_items = []
        spider = EcommerceCategorySpider(
            start_url="https://www.flipkart.com/search?q=snacks",
            max_pages=1,
            staged_items=staged_items,
        )

        list(spider.parse(response))

        assert len(staged_items) == 1
        assert staged_items[0]["name"] == "Flipkart Snack Pack"
        assert staged_items[0]["image_url"] == "https://rukminim1.flixcart.com/image/snack.jpg"

    def test_parse_generic_html_fallback(self):
        generic_html = """
        <html>
        <body>
            <div class="product-card">
                <h3>Generic Almond Milk</h3>
                <img src="/images/almond_milk.jpg" />
            </div>
        </body>
        </html>
        """
        response = HtmlResponse(
            url="https://www.myshop.com/category/beverages",
            body=generic_html,
            encoding="utf-8",
        )

        staged_items = []
        spider = EcommerceCategorySpider(
            start_url="https://www.myshop.com/category/beverages",
            max_pages=1,
            staged_items=staged_items,
        )

        list(spider.parse(response))

        assert len(staged_items) == 1
        assert staged_items[0]["name"] == "Generic Almond Milk"
        assert staged_items[0]["image_url"] == "https://www.myshop.com/images/almond_milk.jpg"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Image Download & Submission Helper Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScraperHelpers:
    @patch("requests.get")
    def test_download_and_stage_images(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"X" * 500  # valid image content
        mock_get.return_value = mock_resp

        staged_items = [
            {"name": "Test Milk", "image_url": "http://example.com/milk.jpg", "page_url": "http://example.com"},
        ]

        downloaded = download_and_stage_images(staged_items, staging_dir=tmp_path)

        assert len(downloaded) == 1
        assert "local_path" in downloaded[0]
        assert Path(downloaded[0]["local_path"]).exists()

    @patch("requests.post")
    def test_submit_batch_to_backend(self, mock_post, tmp_path):
        # Create a temp file
        img_file = tmp_path / "test_stage.jpg"
        img_file.write_bytes(b"X" * 500)

        staged_downloaded = [
            {"name": "Test Milk", "local_path": str(img_file), "filename": "test_stage.jpg"},
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "total_processed": 1}
        mock_post.return_value = mock_resp

        res = submit_batch_to_backend(staged_downloaded, source_url="http://example.com")

        assert res["status"] == "success"
        assert res["total_processed"] == 1
