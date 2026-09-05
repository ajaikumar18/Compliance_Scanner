"""
E-Commerce Legal Metrology Metadata & Specifications Extractor
=============================================================
Extracts mandatory legal declarations from e-commerce product listings:
- Amazon India (Detail Bullets, Tech Spec tables, Pricing blocks)
- Flipkart (Specification tables, Features blocks, Pricing blocks)
- Generic / Schema.org (JSON-LD structured data)

Fulfills compliance verification under Rule 6(10) of the
Legal Metrology (Packaged Commodities) Amendment Rules 2017 & 2021.
"""

import json
import logging
import re
from typing import Any
import bs4

logger = logging.getLogger(__name__)


def extract_product_specs(html: str) -> dict[str, str]:
    """
    Extract Legal Metrology mandatory declarations from product detail HTML.

    Returns a dict with canonical keys:
    - country_of_origin
    - manufacturer_name_address
    - net_quantity
    - mrp
    - consumer_care_details
    - generic_name
    """
    soup = bs4.BeautifulSoup(html, "html.parser")
    raw_specs: dict[str, str] = {}

    # ── 1. Amazon: Detail Bullets (#detailBullets_feature_div) ────────────────
    bullets = soup.select("#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li")
    for b in bullets:
        text = b.get_text(" ", strip=True)
        if ":" in text:
            k, v = text.split(":", 1)
            clean_k = re.sub(r"[\u200e\u200f]", "", k).strip().lower()
            clean_v = re.sub(r"[\u200e\u200f]", "", v).strip()
            if clean_k and clean_v:
                raw_specs[clean_k] = clean_v

    # ── 2. Amazon: Technical Details Tables (#productDetails_techSpec_section_1)
    rows = soup.select("table#productDetails_techSpec_section_1 tr, table.prodDetTable tr, div#prodDetails tr")
    for r in rows:
        th = r.select_one("th")
        td = r.select_one("td")
        if th and td:
            k = th.get_text(strip=True).lower()
            v = td.get_text(strip=True)
            k = re.sub(r"[\u200e\u200f]", "", k).strip()
            v = re.sub(r"[\u200e\u200f]", "", v).strip()
            if k and v:
                raw_specs[k] = v

    # ── 3. Flipkart: Specifications Tables (div._1AtVbE table, div._3k-BhJ) ───
    fk_rows = soup.select("div._1AtVbE tr, div._3k-BhJ tr, table._14cfVK tr, div.x352Pt tr")
    for r in fk_rows:
        tds = r.select("td")
        if len(tds) >= 2:
            k = tds[0].get_text(strip=True).lower()
            v = tds[1].get_text(strip=True)
            if k and v:
                raw_specs[k] = v

    # ── 4. JSON-LD Structured Data (<script type="application/ld+json">) ──────
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                items = data
            else:
                items = [data]

            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("Product", "IndividualProduct"):
                    if "countryOfOrigin" in item:
                        co = item["countryOfOrigin"]
                        raw_specs["country of origin"] = co.get("name", co) if isinstance(co, dict) else str(co)
                    if "manufacturer" in item:
                        mfg = item["manufacturer"]
                        raw_specs["manufacturer"] = mfg.get("name", mfg) if isinstance(mfg, dict) else str(mfg)
                    if "offers" in item:
                        offers = item["offers"]
                        if isinstance(offers, dict) and "price" in offers:
                            raw_specs["mrp"] = f"₹{offers['price']}"
                        elif isinstance(offers, list) and len(offers) > 0 and "price" in offers[0]:
                            raw_specs["mrp"] = f"₹{offers[0]['price']}"
        except Exception:
            pass

    # ── 5. Pricing Extraction (Amazon & Flipkart price blocks) ─────────────────
    if "mrp" not in raw_specs:
        price_selectors = [
            "span.a-price span.a-offscreen",
            "span#priceblock_ourprice",
            "span.priceToPay span.a-offscreen",
            "div._30jeq3._16J0da",
            "div._30jeq3",
            "span#priceblock_dealprice",
            "span.apexPriceToPay span.a-offscreen",
        ]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                price_text = el.get_text(strip=True)
                raw_specs["mrp"] = price_text
                break

    # ── 6. Normalize into Canonical Compliance Fields ─────────────────────────
    canonical: dict[str, str] = {}

    # Country of Origin
    for k, v in raw_specs.items():
        if any(term in k for term in ["country of origin", "origin", "country"]):
            canonical["country_of_origin"] = v
            break

    # Manufacturer / Packer / Importer
    mfg_parts = []
    for k, v in raw_specs.items():
        if any(term in k for term in ["manufacturer", "packer", "importer", "packed by", "marketed by"]):
            if v and v not in mfg_parts:
                mfg_parts.append(f"{k.capitalize()}: {v}")
    if mfg_parts:
        canonical["manufacturer_name_address"] = " | ".join(mfg_parts)

    # Net Quantity / Item Weight
    for k, v in raw_specs.items():
        if any(term in k for term in ["net quantity", "net weight", "item weight", "quantity", "unit count"]):
            canonical["net_quantity"] = v
            break

    # MRP (Maximum Retail Price)
    if "mrp" in raw_specs:
        canonical["mrp"] = raw_specs["mrp"]
    else:
        for k, v in raw_specs.items():
            if any(term in k for term in ["m.r.p.", "mrp", "price"]):
                canonical["mrp"] = v
                break

    # Customer Care / Contact Information
    for k, v in raw_specs.items():
        if any(term in k for term in ["customer care", "contact", "manufacturer contact", "feedback"]):
            canonical["consumer_care_details"] = v
            break

    # Generic Name
    for k, v in raw_specs.items():
        if any(term in k for term in ["generic name", "item type name"]):
            canonical["generic_name"] = v
            break

    return canonical


def extract_product_gallery_images(html: str) -> list[str]:
    """
    Extract high-resolution product gallery images from e-commerce product page.
    """
    soup = bs4.BeautifulSoup(html, "html.parser")
    images: list[str] = []

    # 1. Amazon dynamic colorImages JSON block
    for script in soup.find_all("script"):
        content = script.string or ""
        if "colorImages" in content and "initial" in content:
            # Find hiRes or large URLs
            hires = re.findall(r'"hiRes"\s*:\s*"(https://[^"]+)"', content)
            large = re.findall(r'"large"\s*:\s*"(https://[^"]+)"', content)
            for u in (hires or large):
                u_clean = u.replace("\\/", "/")
                if u_clean not in images:
                    images.append(u_clean)

    # 2. Main image fallback (Amazon landingImage / Flipkart main image)
    if not images:
        main_img = soup.select_one("img#landingImage, img._396cs4._2amPTt, img.q6DClP")
        if main_img:
            src = main_img.get("data-old-hires") or main_img.get("src") or main_img.get("data-src")
            if src and src.startswith("http"):
                # Upgrade Amazon thumbnail to 1500px
                src = re.sub(r"\._[A-Z0-9_,]+_\.", "._SL1500_.", src)
                images.append(src)

    return images


def parse_search_card_links(html: str, base_url: str) -> list[dict[str, str]]:
    """
    Extract product detail URLs and thumbnails from e-commerce search/category pages.
    """
    soup = bs4.BeautifulSoup(html, "html.parser")
    products: list[dict[str, str]] = []
    domain = base_url.lower()

    if "amazon" in domain:
        cards = soup.select("div[data-component-type='s-search-result']")
        for c in cards:
            title_el = c.select_one("h2 span, span.a-text-normal")
            link_el = c.select_one("h2 a, a.a-link-normal.s-no-outline")
            img_el = c.select_one("img.s-image")

            if link_el and link_el.get("href"):
                href = link_el["href"]
                if not href.startswith("http"):
                    href = "https://www.amazon.in" + href
                # Strip affiliate or tracking click wraps
                clean_href = href.split("/ref=")[0] if "/ref=" in href else href
                title = title_el.get_text(strip=True) if title_el else "Amazon Product"
                img_url = img_el.get("src", "") if img_el else ""
                img_url = re.sub(r"\._[A-Z0-9_,]+_\.", "._SL1500_.", img_url)

                products.append({
                    "title": title,
                    "url": clean_href,
                    "image_url": img_url,
                })

    elif "flipkart" in domain:
        cards = soup.select("div._1AtVbE, div._1xHGKw, div._2kHMtA, div._4ddW1b")
        for c in cards:
            title_el = c.select_one("div._4rR01T, a.s1Q98W, a.IRpwTa")
            link_el = c.select_one("a._1fQZEK, a.s1Q98W, a.IRpwTa, a._2rpwqI")
            img_el = c.select_one("img._396cs4, img._2r_T1d")

            if link_el and link_el.get("href"):
                href = link_el["href"]
                if not href.startswith("http"):
                    href = "https://www.flipkart.com" + href
                title = title_el.get_text(strip=True) if title_el else "Flipkart Product"
                img_url = img_el.get("src", "") if img_el else ""
                img_url = re.sub(r"/image/\d+/\d+/", "/image/832/832/", img_url)

                products.append({
                    "title": title,
                    "url": href,
                    "image_url": img_url,
                })

    return products
