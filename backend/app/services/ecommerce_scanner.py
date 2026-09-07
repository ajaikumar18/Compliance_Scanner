"""
Universal E-Commerce Scraper Service
====================================
Scrapes product listing images, packaging photos, and metadata from:
- Amazon India & Global (single product /dp/ pages and /s? search/category pages)
- Flipkart (single product /p/ pages and /search category pages)
- BigBasket (product and category pages)
- Blinkit, Zepto, JioMart
- Generic E-Commerce (Schema.org Product JSON-LD, OpenGraph, high-res image galleries)
- Direct image links (.jpg, .png, .webp)

Extracts full-resolution packaging and label photos suitable for Legal Metrology compliance verification.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Standard browser headers to avoid automated-request blocking
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def is_direct_image_url(url: str) -> bool:
    """Check if the URL directly points to an image file."""
    clean_url = url.split("?")[0].lower()
    return any(clean_url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"])


def clean_amazon_image_url(url: str, high_res: bool = False) -> str:
    """
    Remove Amazon dynamic dimension modifiers to retrieve original photo.
    e.g. 'https://m.media-amazon.com/images/I/51sqR5lcuqL._SX38_SY50_CR,0,0,38,50_.jpg'
    becomes 'https://m.media-amazon.com/images/I/51sqR5lcuqL.jpg' (or _UL1500_ if high_res=True).
    """
    if "media-amazon.com/images/I/" in url or "images-amazon.com/images/I/" in url:
        m = re.search(r'/images/I/([A-Za-z0-9\+\-]+)', url)
        if m:
            img_id = m.group(1)
            if high_res:
                return f"https://m.media-amazon.com/images/I/{img_id}._UL1500_.jpg"
            return f"https://m.media-amazon.com/images/I/{img_id}.jpg"
        return re.sub(r"\._[A-Z0-9,._-]+_\.", ".", url)
    return url


def clean_flipkart_image_url(url: str) -> str:
    """
    Upscale Flipkart image URLs to maximum resolution (1664x1664 or original).
    e.g. 'https://rukminim2.flixcart.com/image/128/128/xif0q/...' -> '.../image/1664/1664/xif0q/...'
    """
    return re.sub(r"/image/\d+/\d+/", "/image/1664/1664/", url)


class ScrapedProductItem:
    def __init__(
        self,
        title: str,
        image_url: str,
        source_url: str,
        brand: str | None = None,
        is_packaging_photo: bool = False,
        priority: int = 2,
        ecommerce_data: dict[str, Any] | None = None,
    ):
        self.title = title
        self.image_url = image_url
        self.source_url = source_url
        self.brand = brand
        self.is_packaging_photo = is_packaging_photo
        self.priority = priority
        self.ecommerce_data = ecommerce_data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "image_url": self.image_url,
            "source_url": self.source_url,
            "brand": self.brand,
            "is_packaging_photo": self.is_packaging_photo,
            "priority": self.priority,
            "ecommerce_data": self.ecommerce_data,
        }


def extract_ecommerce_metadata(soup: BeautifulSoup, html_text: str, page_url: str, domain: str = "") -> dict[str, Any]:
    """
    Extract structured e-commerce product declarations from HTML, JSON-LD, tables, and meta tags.
    """
    meta: dict[str, Any] = {
        "product_name": None,
        "brand": None,
        "category": "Packaged Foods",
        "description": None,
        "mrp": None,
        "selling_price": None,
        "net_quantity": None,
        "manufacturer": None,
        "packer": None,
        "importer": None,
        "country_of_origin": None,
        "consumer_care": None,
        "ingredients": None,
        "specifications": {},
    }

    # 1. JSON-LD structured data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items_to_check = data if isinstance(data, list) else [data]
            for it in items_to_check:
                if isinstance(it, dict) and it.get("@type") in ["Product", "IndividualProduct"]:
                    if it.get("name"):
                        meta["product_name"] = it["name"]
                    if it.get("brand"):
                        b = it["brand"]
                        meta["brand"] = b.get("name") if isinstance(b, dict) else str(b)
                    if it.get("description"):
                        meta["description"] = it["description"][:250]
                    if it.get("category"):
                        meta["category"] = it["category"]
                    offers = it.get("offers")
                    if isinstance(offers, dict):
                        meta["selling_price"] = str(offers.get("price") or offers.get("lowPrice") or "")
                        meta["mrp"] = str(offers.get("highPrice") or offers.get("price") or "")
        except Exception:
            pass

    # 2. OpenGraph Meta Fallbacks
    og_title = soup.find("meta", property="og:title")
    if not meta["product_name"] and og_title and og_title.get("content"):
        meta["product_name"] = og_title["content"].strip()

    og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    if not meta["description"] and og_desc and og_desc.get("content"):
        meta["description"] = og_desc["content"].strip()[:250]

    og_price = soup.find("meta", property="product:price:amount")
    if not meta["selling_price"] and og_price and og_price.get("content"):
        meta["selling_price"] = f"₹{og_price['content']}"

    # 3. Amazon DOM Specifics
    if "amazon" in domain:
        t_el = soup.find(id="productTitle") or soup.find(id="title")
        if t_el:
            meta["product_name"] = t_el.get_text(strip=True)

        b_el = soup.find(id="bylineInfo")
        if b_el:
            b_text = b_el.get_text(strip=True)
            meta["brand"] = re.sub(r"^(?:Brand:\s*|Visit the\s*|\s*Store)", "", b_text, flags=re.IGNORECASE).strip()

        # Pricing is extracted accurately via extract_mrp_and_selling_price below
        # Specs Table & Details Bullets
        for tr in soup.select("table.a-normal tr, #productDetails_techSpec_section_1 tr, div.po-country_of_origin, div.po-net_quantity, div.po-manufacturer"):
            cells = tr.find_all(["th", "td", "span"])
            if len(cells) >= 2:
                k = cells[0].get_text(" ", strip=True).lower()
                v = cells[1].get_text(" ", strip=True)
                meta["specifications"][k] = v
                if "country of origin" in k or "origin" in k:
                    meta["country_of_origin"] = v
                elif "net quantity" in k or "item weight" in k or "weight" in k:
                    meta["net_quantity"] = v
                elif "manufacturer" in k and "packer" not in k and "importer" not in k:
                    meta["manufacturer"] = v
                elif "packer" in k:
                    meta["packer"] = v
                elif "importer" in k:
                    meta["importer"] = v
                elif any(term in k for term in ["consumer care", "customer care", "customer service", "helpline", "toll free", "contact"]):
                    meta["consumer_care"] = v
                elif "ingredient" in k:
                    meta["ingredients"] = v

        for li in soup.select("#detailBullets_feature_div li"):
            txt = li.get_text(" ", strip=True)
            if ":" in txt:
                parts = [x.strip() for x in txt.split(":", 1)]
                kl = parts[0].lower()
                meta["specifications"][kl] = parts[1]
                if "country of origin" in kl or "origin" in kl:
                    meta["country_of_origin"] = parts[1]
                elif "net quantity" in kl or "weight" in kl:
                    meta["net_quantity"] = parts[1]
                elif "manufacturer" in kl:
                    meta["manufacturer"] = parts[1]
                elif "packer" in kl:
                    meta["packer"] = parts[1]
                elif "importer" in kl:
                    meta["importer"] = parts[1]
                elif any(term in kl for term in ["consumer care", "customer care", "customer service", "helpline", "toll free", "contact"]):
                    meta["consumer_care"] = parts[1]

    # 4. Flipkart DOM Specifics
    elif "flipkart" in domain:
        t_el = soup.select_one("h1.yhB1nd, h1.B_NuCI, h1._6EBuvd")
        if t_el:
            meta["product_name"] = t_el.get_text(strip=True)

        for tr in soup.select("table._14cfVK tr, div._3k-ww- tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True).lower()
                v = tds[1].get_text(strip=True)
                meta["specifications"][k] = v
                if "country of origin" in k:
                    meta["country_of_origin"] = v
                elif "net quantity" in k or "weight" in k:
                    meta["net_quantity"] = v
                elif "manufacturing" in k or "manufacturer" in k:
                    meta["manufacturer"] = v

    # 5. Extract accurate MRP and Selling Price with unit-price discrimination
    from app.services.webpage_extractor import extract_mrp_and_selling_price, _parse_float_price

    ecom_mrp, ecom_sp = extract_mrp_and_selling_price(
        soup=soup,
        html_text=html_text,
        domain=domain,
        page_url=page_url,
        product_title=meta.get("product_name"),
        net_quantity=meta.get("net_quantity"),
    )
    if ecom_mrp:
        meta["mrp"] = ecom_mrp
    if ecom_sp:
        meta["selling_price"] = ecom_sp

    # Legal Metrology price reconciliation
    if not meta["mrp"] and meta["selling_price"]:
        meta["mrp"] = meta["selling_price"]
    elif meta["mrp"] and meta["selling_price"]:
        m_val = _parse_float_price(meta["mrp"])
        s_val = _parse_float_price(meta["selling_price"])
        if m_val and s_val and m_val < s_val:
            meta["mrp"] = meta["selling_price"]

    return meta


def scrape_amazon_product_page(soup: BeautifulSoup, html_text: str, page_url: str) -> list[ScrapedProductItem]:
    """Extract product title, brand, metadata, and all distinct high-res packaging/label images from Amazon product page."""
    items: list[ScrapedProductItem] = []
    seen_ids: set[str] = set()

    ecom_meta = extract_ecommerce_metadata(soup, html_text, page_url, domain="amazon")
    title = ecom_meta.get("product_name") or "Amazon Packaged Product"
    brand = ecom_meta.get("brand")

    # Helper to add image by unique Amazon image ID with packaging priority classification
    def _add_by_url(raw_url: str, hint_text: str = ""):
        if not raw_url or not isinstance(raw_url, str):
            return
        if "media-amazon.com/images/I/" not in raw_url and "images-amazon.com/images/I/" not in raw_url:
            return
        m = re.search(r'/images/I/([A-Za-z0-9\+\-]+)', raw_url)
        if not m:
            return
        img_id = m.group(1)
        if any(x in img_id.lower() for x in ["icon", "sprite", "play", "video", "transparent", "pixel", "badge"]):
            return
        if img_id not in seen_ids:
            seen_ids.add(img_id)
            hi_url = f"https://m.media-amazon.com/images/I/{img_id}._UL1500_.jpg"

            # Check if hint contains packaging / statutory declaration signals
            hint_low = hint_text.lower()
            if any(k in hint_low for k in ["nutrition", "ingredient", "facts", "back", "details", "panel", "table", "label", "statutory"]):
                priority = 1
            else:
                priority = 2

            items.append(
                ScrapedProductItem(
                    title=title,
                    image_url=hi_url,
                    source_url=page_url,
                    brand=brand,
                    is_packaging_photo=True,
                    priority=priority,
                    ecommerce_data=ecom_meta,
                )
            )

    # 1. Primary priority: Thumbnails in #altImages & #imageBlock (represents all distinct packaging sides)
    for img_tag in soup.select("#altImages img, #imageBlock img, li.imageThumbnail img, div.imageThumbnail img, ul.regularAltImageViewLayout img"):
        src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-old-hires")
        alt = img_tag.get("alt") or ""
        _add_by_url(src, hint_text=alt)

    # 2. Extract colorImages JSON from scripts
    color_matches = re.findall(r'\"colorImages\":\s*\{\s*\"initial\":\s*(\[.*?\])\s*\}', html_text)
    if not color_matches:
        color_matches = re.findall(r'\'colorImages\':\s*\{\s*\'initial\':\s*(\[.*?\])\s*\}', html_text)
    for cm in color_matches:
        try:
            arr = json.loads(cm)
            for it in arr:
                hi = it.get("hiRes") or it.get("large") or it.get("thumb")
                alt_txt = str(it.get("variant") or "")
                if hi:
                    _add_by_url(hi, hint_text=alt_txt)
                main_dict = it.get("main", {})
                if isinstance(main_dict, dict):
                    for k in main_dict.keys():
                        _add_by_url(k, hint_text=alt_txt)
        except Exception:
            pass

    # 3. Landing image & dynamic images
    landing = soup.find(id="landingImage") or soup.find(id="imgBlkFront")
    if landing:
        landing_alt = landing.get("alt") or ""
        dyn = landing.get("data-a-dynamic-image")
        if dyn:
            try:
                dyn_dict = json.loads(dyn)
                for k in dyn_dict.keys():
                    _add_by_url(k, hint_text=landing_alt)
            except Exception:
                pass
        _add_by_url(landing.get("src"), hint_text=landing_alt)
        _add_by_url(landing.get("data-old-hires"), hint_text=landing_alt)

    # 4. A+ Content / Product Description images (often contains nutrition/statutory tables)
    for ap_img in soup.select("#aplus img, #aplus_feature_div img, #productDescription img"):
        src = ap_img.get("data-src") or ap_img.get("src")
        alt = ap_img.get("alt") or ""
        if src:
            _add_by_url(src, hint_text=alt)

    # Sort items so highest priority packaging / declaration panels are scanned first
    items.sort(key=lambda x: x.priority)
    return items


def scrape_amazon_search_page(soup: BeautifulSoup, page_url: str, max_items: int = 20) -> list[ScrapedProductItem]:
    """Extract product listings from Amazon search/category page."""
    items: list[ScrapedProductItem] = []
    seen: set[str] = set()

    cards = soup.select("div.s-result-item[data-component-type='s-search-result'], div.s-card-container")
    for card in cards:
        if len(items) >= max_items:
            break
        title_el = card.select_one("h2 a span, span.a-text-normal")
        img_el = card.select_one("img.s-image")
        link_el = card.select_one("h2 a, a.a-link-normal")

        if title_el and img_el:
            title = title_el.get_text(strip=True)
            img_src = img_el.get("src")
            clean_img = clean_amazon_image_url(img_src)
            prod_link = urljoin(page_url, link_el.get("href")) if link_el else page_url

            if clean_img and clean_img not in seen:
                seen.add(clean_img)
                items.append(
                    ScrapedProductItem(
                        title=title,
                        image_url=clean_img,
                        source_url=prod_link,
                        is_packaging_photo=True,
                    )
                )

    return items


def scrape_flipkart_page(soup: BeautifulSoup, html_text: str, page_url: str, max_items: int = 20) -> list[ScrapedProductItem]:
    """Extract product title and high-res images from Flipkart product or search page."""
    items: list[ScrapedProductItem] = []
    seen: set[str] = set()

    is_product_page = "/p/" in page_url or bool(soup.select_one("h1.yhB1nd, h1.B_NuCI, h1._6EBuvd"))

    if is_product_page:
        title_el = soup.select_one("h1.yhB1nd, h1.B_NuCI, h1._6EBuvd, h1")
        title = title_el.get_text(strip=True) if title_el else "Flipkart Packaged Product"

        # Gallery images
        gallery_imgs = soup.select("img._0DkuPH, img._396cs4, img._2r_T1d, div._3kidBo img, ul._3GnUWp img")
        for img in gallery_imgs:
            src = img.get("src")
            if src and "flixcart.com" in src:
                clean_img = clean_flipkart_image_url(src)
                if clean_img not in seen:
                    seen.add(clean_img)
                    items.append(
                        ScrapedProductItem(
                            title=title,
                            image_url=clean_img,
                            source_url=page_url,
                            is_packaging_photo=True,
                        )
                    )

        # Fallback to OpenGraph
        if not items:
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                items.append(
                    ScrapedProductItem(
                        title=title,
                        image_url=clean_flipkart_image_url(og_img["content"]),
                        source_url=page_url,
                        is_packaging_photo=True,
                    )
                )
    else:
        # Search/Category listing page
        cards = soup.select("div._1AtVbE, div._1xHGKw, div._2kHMtA, div._4ddW1b, div._75nlfW")
        for card in cards:
            if len(items) >= max_items:
                break
            title_el = card.select_one("div._4rR01T, a.s1Q98W, a.IRpwTa, div.KzDlHZ, a.wjcEIp")
            img_el = card.select_one("img._396cs4, img._2r_T1d, img.DByuf4")
            link_el = card.select_one("a._1fQZEK, a.s1Q98W, a.IRpwTa, a.CGtC58")

            if title_el and img_el:
                title = title_el.get_text(strip=True)
                src = img_el.get("src")
                if src and "flixcart.com" in src:
                    clean_img = clean_flipkart_image_url(src)
                    prod_link = urljoin(page_url, link_el.get("href")) if link_el else page_url
                    if clean_img not in seen:
                        seen.add(clean_img)
                        items.append(
                            ScrapedProductItem(
                                title=title,
                                image_url=clean_img,
                                source_url=prod_link,
                                is_packaging_photo=True,
                            )
                        )

    return items


def scrape_generic_ecommerce_page(soup: BeautifulSoup, html_text: str, page_url: str, max_items: int = 20) -> list[ScrapedProductItem]:
    """
    Extract product info from generic e-commerce sites (BigBasket, Blinkit, Zepto, Shopify, WooCommerce).
    Uses JSON-LD schema, OpenGraph tags, and HTML heuristics.
    """
    items: list[ScrapedProductItem] = []
    seen: set[str] = set()

    # 1. Schema.org Product JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                candidates = data
            else:
                candidates = [data]

            for cand in candidates:
                if isinstance(cand, dict) and cand.get("@type") in ["Product", "IndividualProduct"]:
                    title = cand.get("name") or "E-Commerce Product"
                    img_data = cand.get("image")
                    img_urls = []
                    if isinstance(img_data, str):
                        img_urls = [img_data]
                    elif isinstance(img_data, list):
                        img_urls = [x for x in img_data if isinstance(x, str)]
                    elif isinstance(img_data, dict):
                        if img_data.get("url"):
                            img_urls = [img_data["url"]]

                    for u in img_urls:
                        abs_u = urljoin(page_url, u)
                        if abs_u not in seen:
                            seen.add(abs_u)
                            items.append(
                                ScrapedProductItem(
                                    title=title,
                                    image_url=abs_u,
                                    source_url=page_url,
                                    brand=cand.get("brand", {}).get("name") if isinstance(cand.get("brand"), dict) else cand.get("brand"),
                                    is_packaging_photo=True,
                                )
                            )
        except Exception:
            pass

    if items:
        return items[:max_items]

    # 2. OpenGraph Meta Tags
    og_title_el = soup.find("meta", property="og:title")
    og_img_el = soup.find("meta", property="og:image")
    title = og_title_el.get("content") if og_title_el else (soup.title.string if soup.title else "Product")

    if og_img_el and og_img_el.get("content"):
        img_url = urljoin(page_url, og_img_el["content"])
        seen.add(img_url)
        items.append(
            ScrapedProductItem(
                title=title,
                image_url=img_url,
                source_url=page_url,
                is_packaging_photo=True,
            )
        )

    # 3. Find prominent product gallery or card images
    gallery_imgs = soup.select(
        "[data-gallery] img, .product-media img, .product-images img, "
        ".product-single__photo img, .carousel img, .swiper-slide img, "
        "div[class*='product'] img, div[class*='item'] img"
    )
    for img in gallery_imgs:
        if len(items) >= max_items:
            break
        src = img.get("data-src") or img.get("data-large") or img.get("src")
        if src:
            abs_url = urljoin(page_url, src)
            if abs_url.startswith("http") and abs_url not in seen:
                if not any(x in abs_url.lower() for x in [".gif", ".svg", "logo", "icon", "badge", "avatar"]):
                    seen.add(abs_url)
                    alt_title = img.get("alt") or title
                    items.append(
                        ScrapedProductItem(
                            title=alt_title,
                            image_url=abs_url,
                            source_url=page_url,
                            is_packaging_photo=True,
                        )
                    )

    return items


def fetch_ecommerce_page(url: str) -> tuple[BeautifulSoup, str, str]:
    """
    Fetches the HTML of an e-commerce product or category URL with anti-bot bypass.
    Returns (BeautifulSoup, html_text, effective_url).
    """
    domain = urlparse(url).netloc.lower()
    effective_url = url

    # Canonicalize Amazon product URLs to avoid tracking parameter timeouts and bot checks
    if "amazon" in domain:
        m = re.search(r"/(?:dp|gp/product|d)/([A-Za-z0-9]{10})", url)
        if m:
            asin = m.group(1)
            effective_url = f"https://{domain}/dp/{asin}"
            logger.info("Canonicalized Amazon product URL to: %s", effective_url)

    html_text = ""
    # Try requests first
    try:
        resp = requests.get(effective_url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code == 200:
            text = resp.text
            if "api-services-support" not in text and "To discuss automated access" not in text and len(text) > 8000:
                html_text = text
    except Exception as req_exc:
        logger.warning("Requests fetch failed for %s: %s (will try curl fallback)", effective_url, req_exc)

    # Fallback to system curl for anti-bot/TLS bypass
    if not html_text:
        try:
            cmd = [
                "curl", "-s", "-L", "--max-time", "15",
                "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "-H", "Accept-Language: en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                effective_url
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=18)
            if res.returncode == 0 and len(res.stdout) > 500:
                html_text = res.stdout.decode("utf-8", errors="replace")
        except Exception as curl_exc:
            logger.warning("Curl fallback failed for %s: %s", effective_url, curl_exc)

    if not html_text:
        raise ValueError(f"Could not connect to or retrieve webpage: {effective_url}")

    soup = BeautifulSoup(html_text, "html.parser")
    return soup, html_text, effective_url


def scrape_ecommerce_category_urls(category_url: str, max_items: int = 10) -> list[str]:
    """
    Extracts individual product URLs from an e-commerce category or search results page.
    Supports Amazon, Flipkart, Blinkit, Zepto, BigBasket, and generic platforms.
    """
    soup, html_text, eff_url = fetch_ecommerce_page(category_url)
    domain = urlparse(eff_url).netloc.lower()
    product_urls: list[str] = []
    seen_ids: set[str] = set()

    if "amazon" in domain:
        # 1. Look for ASINs in links or data attributes
        for a in soup.select("a[href*='/dp/'], a[href*='/gp/product/'], div[data-asin] h2 a"):
            href = a.get("href") or ""
            m = re.search(r"/(?:dp|gp/product)/([A-Za-z0-9]{10})", href)
            if m:
                asin = m.group(1)
                if asin not in seen_ids and not any(x in asin.lower() for x in ["prime", "video"]):
                    seen_ids.add(asin)
                    product_urls.append(f"https://www.amazon.in/dp/{asin}")
                    if len(product_urls) >= max_items:
                        break

    elif "flipkart" in domain:
        for a in soup.select("a[href*='/p/'], a._1fQZEK, a.s1Q9rs, a._2UzuFa"):
            href = a.get("href") or ""
            m = re.search(r"(/[^/?]+/p/[^/?]+)", href)
            if m:
                path = m.group(1)
                if path not in seen_ids:
                    seen_ids.add(path)
                    product_urls.append(f"https://www.flipkart.com{path}")
                    if len(product_urls) >= max_items:
                        break

    # Generic fallback
    if len(product_urls) < max_items:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(x in href for x in ["/dp/", "/product/", "/p/", "/item/"]) and not any(x in href for x in ["login", "cart", "help", "review"]):
                full_url = urljoin(eff_url, href)
                clean_url = full_url.split("?")[0]
                if clean_url not in seen_ids and clean_url != eff_url:
                    seen_ids.add(clean_url)
                    product_urls.append(clean_url)
                    if len(product_urls) >= max_items:
                        break

    logger.info("Discovered %d product URLs from category page %s", len(product_urls), eff_url)
    return product_urls


def scrape_ecommerce_images(
    soup: BeautifulSoup,
    html_text: str,
    effective_url: str,
    max_items: int = 20,
    webpage_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Extracts high-resolution packaging and label images from a parsed e-commerce page.
    """
    domain = urlparse(effective_url).netloc.lower()
    items: list[ScrapedProductItem] = []

    if "amazon" in domain:
        if "/dp/" in effective_url or "/gp/product/" in effective_url or "/d/" in effective_url:
            logger.info("Detected Amazon Single Product Page: %s", effective_url)
            items = scrape_amazon_product_page(soup, html_text, effective_url)
        else:
            logger.info("Detected Amazon Search/Category Page: %s", effective_url)
            items = scrape_amazon_search_page(soup, effective_url, max_items=max_items)

    elif "flipkart" in domain:
        logger.info("Detected Flipkart Page: %s", effective_url)
        items = scrape_flipkart_page(soup, html_text, effective_url, max_items=max_items)

    else:
        logger.info("Detected Generic/Other E-Commerce Page: %s (%s)", domain, effective_url)
        items = scrape_generic_ecommerce_page(soup, html_text, effective_url, max_items=max_items)

    if not items:
        items = scrape_generic_ecommerce_page(soup, html_text, effective_url, max_items=max_items)

    # Attach webpage_data to items if provided
    if webpage_data:
        for it in items:
            it.ecommerce_data = webpage_data

    # Also incorporate any images discovered from JSON-LD / OpenGraph
    if webpage_data and webpage_data.get("image_urls"):
        seen_urls = {it.image_url for it in items}
        for u in webpage_data["image_urls"]:
            if u and u.startswith("http") and u not in seen_urls:
                seen_urls.add(u)
                items.append(
                    ScrapedProductItem(
                        title=webpage_data.get("product_name") or "Product Image",
                        image_url=u,
                        source_url=effective_url,
                        brand=webpage_data.get("brand"),
                        is_packaging_photo=True,
                        priority=2,
                        ecommerce_data=webpage_data,
                    )
                )

    if not items:
        # Emergency fallback: grab any reasonable product img tag
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http") and not any(x in src.lower() for x in [".gif", ".svg", "icon", "logo", "avatar", "sprite"]):
                items.append(
                    ScrapedProductItem(
                        title="E-Commerce Product Image",
                        image_url=src,
                        source_url=effective_url,
                        is_packaging_photo=True,
                        ecommerce_data=webpage_data or {},
                    )
                )
                if len(items) >= 3:
                    break

    logger.info("Extracted %d packaging/product images from %s", len(items), effective_url)
    return [it.to_dict() for it in items[:max_items]]


def scrape_ecommerce_url(url: str, max_items: int = 20) -> list[dict[str, Any]]:
    """
    Scrapes an e-commerce product URL.
    Extracts complete webpage metadata and all available packaging images.
    If no packaging images are available, returns a metadata carrier so compliance
    can still be evaluated directly on the webpage declarations.
    """
    logger.info("Scraping e-commerce URL: %s (max_items=%d)", url, max_items)

    if is_direct_image_url(url):
        filename = os.path.basename(url.split("?")[0])
        return [{
            "title": f"Direct Product Image ({filename})",
            "image_url": url,
            "source_url": url,
            "brand": None,
            "is_packaging_photo": True,
            "priority": 1,
            "ecommerce_data": {
                "product_name": f"Direct Product Image ({filename})",
                "category": "Packaged Foods",
                "data_sources": {"webpage": False, "structured_data": False, "product_specifications": False, "packaging_ocr": True, "geo_intelligence": False},
            },
        }]

    from app.services.webpage_extractor import extract_webpage_content

    soup, html_text, effective_url = fetch_ecommerce_page(url)
    webpage_data = extract_webpage_content(soup, html_text, effective_url)
    items = scrape_ecommerce_images(soup, html_text, effective_url, max_items=max_items, webpage_data=webpage_data)

    if not items:
        # Packaging images unavailable; return metadata carrier so analysis continues
        logger.info("No packaging images detected on %s; proceeding with webpage declarations", effective_url)
        return [{
            "title": webpage_data.get("product_name") or "E-Commerce Packaged Product",
            "image_url": None,
            "source_url": effective_url,
            "brand": webpage_data.get("brand"),
            "is_packaging_photo": False,
            "priority": 99,
            "ecommerce_data": webpage_data,
        }]

    return items


def download_image_bytes(image_url: str, timeout: int = 15) -> tuple[bytes, str]:
    """Download image bytes from an image URL with standard browser headers and resolution fallback."""
    try:
        resp = requests.get(image_url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as err:
        if "._UL1500_.jpg" in image_url:
            fallback_url = image_url.replace("._UL1500_.jpg", ".jpg")
            resp = requests.get(fallback_url, headers=DEFAULT_HEADERS, timeout=timeout)
            resp.raise_for_status()
        else:
            raise err

    # Determine filename
    clean_path = urlparse(image_url).path
    filename = os.path.basename(clean_path) or "product_image.jpg"
    if not any(filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
        filename = f"{filename}.jpg"

    return resp.content, filename
