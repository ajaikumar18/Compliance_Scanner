"""
Unit Tests for E-Commerce Legal Metrology Extractor
===================================================
Tests extraction of mandatory declarations from Amazon, Flipkart, and JSON-LD structured data.
"""

from app.services.ecommerce_extractor import (
    extract_product_specs,
    extract_product_gallery_images,
    parse_search_card_links,
)

SAMPLE_AMAZON_HTML = """
<html>
<body>
<div id="detailBullets_feature_div">
  <ul>
    <li><span>Country of Origin: India</span></li>
    <li><span>Manufacturer: Britannia Industries Ltd., 5/1A Hungerford St, Kolkata 700017</span></li>
    <li><span>Packer: Britannia Industries Ltd.</span></li>
    <li><span>Net Quantity: 120.0 gram</span></li>
    <li><span>Generic Name: Biscuit</span></li>
    <li><span>Customer Care: feedback@britindia.com / 1800-425-4449</span></li>
  </ul>
</div>
<span class="a-price"><span class="a-offscreen">₹35.00</span></span>
<div id="imageBlock">
  <img id="landingImage" src="https://m.media-amazon.com/images/I/71h8i9SxFtL._AC_UL320_.jpg" />
</div>
</body>
</html>
"""

SAMPLE_FLIPKART_HTML = """
<html>
<body>
<div class="_1AtVbE">
  <table>
    <tr><td>Country of Origin</td><td>India</td></tr>
    <tr><td>Manufacturer Details</td><td>Nestle India Limited, 100/101 World Trade Centre, New Delhi</td></tr>
    <tr><td>Net Quantity</td><td>250 g</td></tr>
  </table>
</div>
<div class="_30jeq3">₹120</div>
</body>
</html>
"""

SAMPLE_SEARCH_PAGE_HTML = """
<html>
<body>
<div data-component-type="s-search-result">
  <h2><a class="a-link-normal" href="/dp/B08XYZ1234/ref=sr_1_1"><span>Oreo Original Vanilla Creme Biscuits 120g</span></a></h2>
  <img class="s-image" src="https://m.media-amazon.com/images/I/71h8i9SxFtL._AC_UL320_.jpg" />
</div>
</body>
</html>
"""


def test_extract_amazon_specs():
    specs = extract_product_specs(SAMPLE_AMAZON_HTML)
    assert specs.get("country_of_origin") == "India"
    assert "Britannia" in specs.get("manufacturer_name_address", "")
    assert "120" in specs.get("net_quantity", "")
    assert "35" in specs.get("mrp", "")
    assert "feedback@britindia.com" in specs.get("consumer_care_details", "")


def test_extract_flipkart_specs():
    specs = extract_product_specs(SAMPLE_FLIPKART_HTML)
    assert specs.get("country_of_origin") == "India"
    assert "Nestle" in specs.get("manufacturer_name_address", "")
    assert "250" in specs.get("net_quantity", "")
    assert "120" in specs.get("mrp", "")


def test_parse_search_card_links():
    cards = parse_search_card_links(SAMPLE_SEARCH_PAGE_HTML, base_url="https://www.amazon.in/s?k=biscuits")
    assert len(cards) == 1
    assert cards[0]["title"] == "Oreo Original Vanilla Creme Biscuits 120g"
    assert "amazon.in/dp/B08XYZ1234" in cards[0]["url"]
    assert "._SL1500_." in cards[0]["image_url"]


import pytest
import numpy as np
import cv2
from unittest.mock import AsyncMock
from app.routers.scans import _process_single_scan_image


@pytest.mark.asyncio
async def test_ecommerce_html_specs_merged_into_scan_result():
    """Verify that e-commerce HTML specs fulfill Legal Metrology Rule 6(10) requirements."""
    # Create a blank synthetic image
    blank_img = np.zeros((300, 300, 3), dtype=np.uint8)
    _, img_bytes = cv2.imencode(".jpg", blank_img)

    html_specs = {
        "country_of_origin": "India",
        "manufacturer_name_address": "Britannia Industries Ltd, Kolkata",
        "net_quantity": "120 g",
        "mrp": "Rs. 35.00",
        "consumer_care_details": "care@example.com",
    }

    mock_session = AsyncMock()
    mock_session.add = lambda x: None
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    res = await _process_single_scan_image(
        image_bytes=img_bytes.tobytes(),
        filename="test_cookie.jpg",
        scan_type_str="ecommerce",
        source_url="https://example.com/item.jpg",
        category="Biscuits",
        package_width_mm=100.0,
        net_quantity_g=120.0,
        db=mock_session,
        html_specs=html_specs,
    )

    fields = res["fields"]
    # Check that fields from HTML specs are populated under ecommerce_html_spec
    assert fields["country_of_origin"]["extracted_value"] == "India"
    assert fields["country_of_origin"]["extraction_method"] == "ecommerce_html_spec"
    assert fields["manufacturer_name_address"]["extraction_method"] == "ecommerce_html_spec"
    assert fields["mrp"]["extraction_method"] == "ecommerce_html_spec"

    # Because mandatory declarations were fulfilled via HTML specs under Rule 6(10),
    # they are not missing violations!
    missing_viol_fields = [v["field_name"] for v in res["violations"] if v["violation_type"] == "missing"]
    assert "country_of_origin" not in missing_viol_fields
    assert "manufacturer_name_address" not in missing_viol_fields
    assert "mrp" not in missing_viol_fields

