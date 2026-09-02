"""
Celery Asynchronous Scan Tasks
==============================
Defines background Celery tasks to process product label scans asynchronously.

Tasks
-----
    process_scan_batch(image_urls, ...) -> dict
"""

from __future__ import annotations

import asyncio
import logging
import os
import requests
from typing import Any

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _run_pipeline_for_image(
    image_bytes: bytes,
    filename: str,
    scan_type: str,
    source_url: str | None,
    category: str,
    package_width_mm: float | None,
    net_quantity_g: float | None,
) -> dict[str, Any]:
    """Helper to run DB scan pipeline inside async session."""
    from app.routers.scans import _process_single_scan_image

    async with AsyncSessionLocal() as db:
        return await _process_single_scan_image(
            image_bytes=image_bytes,
            filename=filename,
            scan_type_str=scan_type,
            source_url=source_url,
            category=category,
            package_width_mm=package_width_mm,
            net_quantity_g=net_quantity_g,
            db=db,
        )


@celery_app.task(bind=True, name="process_scan_batch")
def process_scan_batch(
    self,
    image_urls: list[str],
    scan_type: str = "ecommerce",
    source_url: str | None = None,
    category: str = "General",
    package_width_mm: float | None = None,
    net_quantity_g: float | None = None,
) -> dict[str, Any]:
    """
    Celery task to asynchronously process a batch of product image URLs or file paths.

    Updates task state with progress ('current' / 'total') after processing each item.
    """
    total = len(image_urls)
    logger.info("Starting background Celery batch task %s: %d images", self.request.id, total)

    results = []
    errors = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36 ComplianceScannerCelery/1.0"
        )
    }

    for idx, url_or_path in enumerate(image_urls, 1):
        # Update Celery task state with current progress if Redis broker available
        try:
            progress_meta = {
                "current": idx,
                "total": total,
                "status": f"{idx}/{total} processed",
                "message": f"{idx}/{total} processed",
            }
            self.update_state(state="PROGRESS", meta=progress_meta)
        except Exception as exc:
            logger.debug("Redis state update skipped: %s", exc)

        try:
            # Step 1: Obtain image bytes from HTTP URL or local file path
            if url_or_path.startswith(("http://", "https://")):
                resp = requests.get(url_or_path, headers=headers, timeout=20)
                resp.raise_for_status()
                img_bytes = resp.content
                filename = os.path.basename(url_or_path.split("?")[0]) or f"batch_{idx}.jpg"
            else:
                with open(url_or_path, "rb") as f:
                    img_bytes = f.read()
                filename = os.path.basename(url_or_path)

            # Step 2: Execute scan pipeline
            res = asyncio.run(
                _run_pipeline_for_image(
                    image_bytes=img_bytes,
                    filename=filename,
                    scan_type=scan_type,
                    source_url=source_url or url_or_path,
                    category=category,
                    package_width_mm=package_width_mm,
                    net_quantity_g=net_quantity_g,
                )
            )
            results.append(res)
            logger.info("Batch task %s: processed item %d/%d (%s)", self.request.id, idx, total, filename)

        except Exception as exc:
            logger.error("Batch task %s: error on item %d/%d (%s): %s", self.request.id, idx, total, url_or_path, exc)
            errors.append({"url": url_or_path, "error": str(exc)})

    final_result = {
        "status": "completed",
        "processed": len(results),
        "total": total,
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }
    return final_result
