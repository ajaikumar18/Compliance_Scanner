"""
E-Commerce Category Scraper Service
===================================
Scrapes product listing images and names from Amazon, Flipkart, BigBasket, or generic
e-commerce category pages using Scrapy, stages images locally, and sends them in batch
to the backend Compliance Scanner API (/scan/batch).

Features
--------
  1. Multi-platform selector support (Amazon, Flipkart, BigBasket, Generic fallback)
  2. Category page pagination handling (configurable max_pages)
  3. Polite scraping: ROBOTSTXT_OBEY=True, DOWNLOAD_DELAY=2.0s, randomized delays, custom User-Agent
  4. Automatic local image downloading & staging
  5. Automatic batch API submission to backend POST /scan/batch with scan_type="ecommerce"

Usage CLI
---------
    python scraper/ecommerce_scraper.py --url "https://www.amazon.in/s?k=biscuits" --max-pages 2 --backend-url "http://localhost:8000/scan/batch"

Usage Python
------------
    from scraper.ecommerce_scraper import run_ecommerce_scraper
    run_ecommerce_scraper("https://www.amazon.in/s?k=biscuits", max_pages=1)
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import scrapy
from scrapy.crawler import CrawlerProcess

logger = logging.getLogger(__name__)

# Staging directory for downloaded product images
STAGING_DIR = Path(__file__).resolve().parent / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Scrapy Spider
# ─────────────────────────────────────────────────────────────────────────────

class EcommerceCategorySpider(scrapy.Spider):
    name = "ecommerce_category_spider"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 2.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36 ComplianceScannerScraper/1.0"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "LOG_LEVEL": "INFO",
    }

    def __init__(
        self,
        start_url: str,
        max_pages: int = 1,
        staged_items: list[dict] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.max_pages = max_pages
        self.page_count = 0
        self.staged_items = staged_items if staged_items is not None else []
        self.domain = urlparse(start_url).netloc.lower()

    def parse(self, response):
        self.page_count += 1
        logger.info("Scraping page %d: %s (domain: %s)", self.page_count, response.url, self.domain)

        items_found = 0

        # ── 1. Selectors by E-Commerce Platform ─────────────────────────────────
        if "amazon" in self.domain:
            cards = response.css("div.s-result-item[data-component-type='s-search-result'], div.s-card-container")
            for card in cards:
                title = card.css("h2 a span::text, span.a-text-normal::text").get()
                img_url = card.css("img.s-image::attr(src)").get()
                if title and img_url:
                    self._add_staged_item(title.strip(), img_url, response.url)
                    items_found += 1

            next_page = response.css("a.s-pagination-next::attr(href)").get()

        elif "flipkart" in self.domain:
            cards = response.css("div._1AtVbE, div._1xHGKw, div._2kHMtA, div._4ddW1b")
            for card in cards:
                title = card.css("div._4rR01T::text, a.s1Q98W::text, a.IRpwTa::text").get()
                img_url = card.css("img._396cs4::attr(src), img._2r_T1d::attr(src)").get()
                if title and img_url:
                    self._add_staged_item(title.strip(), img_url, response.url)
                    items_found += 1

            next_page = response.css("a._1LKp35::attr(href)").get()

        elif "bigbasket" in self.domain:
            cards = response.css("div.product-deck, li.paginated-item, div.SKUContainer-sc")
            for card in cards:
                title = card.css("a.ng-binding::text, h3::text, div[class*='name']::text").get()
                img_url = card.css("img::attr(src)").get()
                if title and img_url:
                    self._add_staged_item(title.strip(), img_url, response.url)
                    items_found += 1

            next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()

        else:
            # Generic E-Commerce Fallback
            cards = response.css("article, div[class*='product'], div[class*='item'], div[class*='card']")
            for card in cards:
                title = card.css("h2::text, h3::text, h4::text, a::text, img::attr(alt)").get()
                img_url = card.css("img::attr(src), img::attr(data-src)").get()
                if title and img_url:
                    self._add_staged_item(title.strip(), img_url, response.url)
                    items_found += 1

            next_page = response.css("a[rel='next']::attr(href), a.next::attr(href)").get()

        logger.info("Page %d complete: %d items extracted", self.page_count, items_found)

        # ── 2. Handle Pagination ──────────────────────────────────────────────
        if next_page and self.page_count < self.max_pages:
            next_url = response.urljoin(next_page)
            logger.info("Following pagination to page %d: %s", self.page_count + 1, next_url)
            yield scrapy.Request(next_url, callback=self.parse)

    def _add_staged_item(self, name: str, img_url: str, page_url: str):
        """Clean and append extracted item to staged list."""
        if not img_url.startswith(("http://", "https://")):
            img_url = urljoin(page_url, img_url)

        self.staged_items.append({
            "name": name,
            "image_url": img_url,
            "page_url": page_url,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Local Image Downloader & Backend Submission Helper
# ─────────────────────────────────────────────────────────────────────────────

def download_and_stage_images(staged_items: list[dict], staging_dir: Path = STAGING_DIR) -> list[dict]:
    """
    Download product images to staging_dir and record local filepath.
    """
    logger.info("Downloading %d product images to staging directory %s ...", len(staged_items), staging_dir)
    downloaded = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36 ComplianceScannerScraper/1.0"
        )
    }

    for idx, item in enumerate(staged_items, 1):
        img_url = item["image_url"]
        clean_name = re.sub(r"[^\w\-]", "_", item["name"])[:30]
        filename = f"staged_{idx:03d}_{clean_name}.jpg"
        filepath = staging_dir / filename

        try:
            resp = requests.get(img_url, headers=headers, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 100:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                item["local_path"] = str(filepath)
                item["filename"] = filename
                downloaded.append(item)
                logger.debug("Successfully downloaded image %d: %s", idx, filename)
            else:
                logger.warning("Failed image download HTTP %d for %s", resp.status_code, img_url)
        except Exception as exc:
            logger.warning("Error downloading image %s: %s", img_url, exc)

    logger.info("Downloaded %d / %d images to staging.", len(downloaded), len(staged_items))
    return downloaded


def submit_batch_to_backend(
    staged_downloaded: list[dict],
    source_url: str,
    backend_url: str = "http://localhost:8000/scan/batch",
    category: str = "E-Commerce Scraped",
) -> dict:
    """
    Send staged product images in a single multipart POST batch to backend /scan/batch.
    """
    if not staged_downloaded:
        logger.warning("No staged images available to submit to backend.")
        return {"status": "failed", "detail": "No staged images available."}

    logger.info("Submitting %d images to backend API at %s ...", len(staged_downloaded), backend_url)

    files_payload = []
    opened_files = []

    try:
        for item in staged_downloaded:
            fpath = item["local_path"]
            fname = item["filename"]
            f_obj = open(fpath, "rb")
            opened_files.append(f_obj)
            files_payload.append(("files", (fname, f_obj, "image/jpeg")))

        form_data = {
            "scan_type": "ecommerce",
            "source_url": source_url,
            "category": category,
        }

        resp = requests.post(backend_url, files=files_payload, data=form_data, timeout=120)
        if resp.status_code == 200:
            result_json = resp.json()
            logger.info(
                "Batch submission successful! Processed %d items.",
                result_json.get("total_processed", 0),
            )
            return result_json
        else:
            logger.error("Backend batch API returned status %d: %s", resp.status_code, resp.text)
            return {"status": "failed", "http_status": resp.status_code, "text": resp.text}
    except Exception as exc:
        logger.error("Error submitting batch to backend API %s: %s", backend_url, exc)
        return {"status": "failed", "error": str(exc)}
    finally:
        for f_obj in opened_files:
            f_obj.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main Scraper Runner Function
# ─────────────────────────────────────────────────────────────────────────────

def run_ecommerce_scraper(
    category_url: str,
    max_pages: int = 1,
    backend_url: str = "http://localhost:8000/scan/batch",
    submit_to_backend: bool = True,
) -> dict:
    """
    Programmatic entrypoint to run the Scrapy e-commerce spider, download images,
    and submit to the backend Compliance Scanner API.
    """
    staged_items: list[dict] = []

    process = CrawlerProcess()
    process.crawl(
        EcommerceCategorySpider,
        start_url=category_url,
        max_pages=max_pages,
        staged_items=staged_items,
    )
    process.start()  # blocks until crawling finishes

    logger.info("Scrapy spider completed. Extracted %d total listing items.", len(staged_items))

    # Download images locally
    downloaded = download_and_stage_images(staged_items)

    # Submit batch to backend API
    api_response = {}
    if submit_to_backend and downloaded:
        api_response = submit_batch_to_backend(downloaded, source_url=category_url, backend_url=backend_url)

    return {
        "category_url": category_url,
        "max_pages": max_pages,
        "total_extracted": len(staged_items),
        "total_downloaded": len(downloaded),
        "backend_response": api_response,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape e-commerce category page and submit to Compliance Scanner API")
    parser.add_argument("--url", required=True, help="Category page URL (Amazon, Flipkart, BigBasket, etc.)")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum category pages to scrape (default: 1)")
    parser.add_argument("--backend-url", default="http://localhost:8000/scan/batch", help="Backend /scan/batch endpoint URL")
    parser.add_argument("--no-submit", action="store_true", help="Only download/stage images without submitting to backend")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
    )

    result = run_ecommerce_scraper(
        category_url=args.url,
        max_pages=args.max_pages,
        backend_url=args.backend_url,
        submit_to_backend=not args.no_submit,
    )

    print("\n" + "=" * 60)
    print("SCRAPER SUMMARY")
    print("=" * 60)
    print(f"Category URL:    {result['category_url']}")
    print(f"Max Pages:       {result['max_pages']}")
    print(f"Extracted Items: {result['total_extracted']}")
    print(f"Downloaded:      {result['total_downloaded']}")
    print(f"Backend Status:  {result['backend_response'].get('status', 'N/A')}")
    print("=" * 60)
