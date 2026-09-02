"""
Scans API Router
================
Handles single and batch compliance scan requests (synchronous file uploads and asynchronous Celery tasks).

Endpoints
---------
    POST /scans/batch
    POST /scan/batch                      (Queues Celery task or processes file uploads)
    POST /scans/batch/queue
    POST /scan/batch/queue                (Queues Celery task with JSON payload)
    GET  /scans/batch/{batch_id}/status
    GET  /scan/batch/{batch_id}/status    (Returns Celery batch progress e.g. "45/100 processed")
"""

import logging
from typing import Any

import cv2
import numpy as np
from celery.result import AsyncResult
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_inspector, require_viewer
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import get_db
from app.models.product import Product
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.user import User
from app.models.violation import Violation, ViolationSeverity, ViolationType
from app.services.field_classifier import classify_fields
from app.services.font_size_analyzer import calibrate_scale, check_font_compliance, measure_text_height
from app.services.genai_extraction import merge_ocr_and_genai_results
from app.services.image_preprocessing import preprocess_pipeline
from app.services.ocr_engine import run_ocr
from app.services.rule_engine import evaluate_compliance
from app.tasks.scan_tasks import process_scan_batch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scans"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class BatchScanRequest(BaseModel):
    image_urls: list[str]
    scan_type: str = "ecommerce"
    source_url: str | None = None
    category: str = "General"
    package_width_mm: float | None = None
    net_quantity_g: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Core Pipeline Processing Helper
# ─────────────────────────────────────────────────────────────────────────────

async def _process_single_scan_image(
    image_bytes: bytes,
    filename: str,
    scan_type_str: str,
    source_url: str | None,
    category: str,
    package_width_mm: float | None,
    net_quantity_g: float | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Process a single image array through the full compliance scanner pipeline and save to DB."""
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None or img_bgr.size == 0:
        raise ValueError(f"Could not decode image file '{filename}'.")

    # Step 2: Image Preprocessing Pipeline
    try:
        preprocessed = preprocess_pipeline(img_bgr)
    except Exception as exc:
        logger.warning("Preprocessing failed for %s: %s; using raw image", filename, exc)
        preprocessed = img_bgr

    # Step 3: Fast Parallel OCR (Tesseract)
    ocr_blocks = run_ocr(preprocessed, use_easyocr=False)

    # Step 4: Field Classification
    classification_res = classify_fields(ocr_blocks)
    classified = classification_res["classified"]
    unmatched = classification_res["unmatched"]

    # Step 5: Fast 1-Pass Gemini Vision AI Fallback Merger
    unified_extraction = merge_ocr_and_genai_results(
        image=preprocessed,
        classified_blocks=classified,
        unmatched_blocks=unmatched,
        api_key=settings.GEMINI_API_KEY,
    )

    # Step 6: Scale Calibration & Font Measurement
    scale_res = calibrate_scale(preprocessed, package_width_mm=package_width_mm)
    px_per_mm = scale_res["pixels_per_mm"]

    font_analysis: dict[str, Any] = {}
    for f_name, f_info in unified_extraction["fields"].items():
        bbox = f_info.get("bbox")
        if bbox:
            measured_mm = measure_text_height(bbox, px_per_mm)
            font_analysis[f_name] = check_font_compliance(
                field_name=f_name,
                measured_height_mm=measured_mm,
                net_quantity_g=net_quantity_g,
                package_width_mm=package_width_mm,
                calibration_method=scale_res["calibration_method"],
            )

    # Step 7: Legal Metrology Compliance Rule Engine
    eval_res = evaluate_compliance(
        extraction_result=unified_extraction,
        font_analysis_result=font_analysis,
        net_quantity_g=net_quantity_g,
        package_width_mm=package_width_mm,
        pixels_per_mm=px_per_mm,
        calibration_method=scale_res["calibration_method"],
    )

    # Step 8: Save to PostgreSQL ORM (with in-memory fallback if DB is offline)
    prod_name = filename
    mfr_block = unified_extraction["fields"].get("manufacturer_name_address", {}).get("extracted_value")
    if mfr_block:
        prod_name = f"{filename} ({mfr_block[:40]}...)"

    scan_id = 1
    product_id = 1

    try:
        product = Product(
            name=prod_name[:250],
            category=category[:95],
            scanned_image_url=source_url or filename,
        )
        db.add(product)
        await db.flush()
        product_id = product.id

        st_enum = ScanType.ecommerce if scan_type_str.lower() == "ecommerce" else ScanType.batch
        scan = Scan(
            product_id=product.id,
            scan_type=st_enum,
            raw_image_url=source_url or filename,
            status=ScanStatus.completed,
        )
        db.add(scan)
        await db.flush()
        scan_id = scan.id

        for v_item in eval_res["violations"]:
            try:
                v_type_enum = ViolationType(v_item["violation_type"])
            except ValueError:
                v_type_enum = ViolationType.missing

            try:
                v_sev_enum = ViolationSeverity(v_item["severity"])
            except ValueError:
                v_sev_enum = ViolationSeverity.medium

            viol = Violation(
                scan_id=scan.id,
                field_name=v_item["field_name"],
                violation_type=v_type_enum,
                severity=v_sev_enum,
                details=v_item["details"],
            )
            db.add(viol)

        await db.commit()
    except Exception as db_exc:
        logger.warning("Database persistence offline/bypassed (%s) - returning scan results in-memory", db_exc)

    return {
        "scan_id": scan_id,
        "product_id": product_id,
        "product_name": prod_name,
        "product_category": category,
        "scan_type": scan_type_str,
        "source_url": source_url or filename,
        "scanned_image_url": source_url or filename,
        "compliance_status": eval_res["compliance_status"],
        "violations_count": len(eval_res["violations"]),
        "violations": eval_res["violations"],
        "fields": unified_extraction["fields"],
        "extraction_summary": unified_extraction["summary"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch Queue & Upload Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/scans/batch/queue", summary="Queue Asynchronous Batch Scan Task via Celery")
@router.post("/scan/batch/queue", summary="Queue Asynchronous Batch Scan Task (Alias)")
async def queue_batch_scan_url_list(
    payload: BatchScanRequest = Body(...),
    current_user: User = Depends(require_inspector),
):
    """
    Queue an asynchronous batch scan task using Celery and Redis.

    Accepts a JSON payload with a list of image URLs (`image_urls`).
    Returns a `batch_id` (Celery Task ID) immediately for polling progress.
    """
    if not payload.image_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_urls list cannot be empty.",
        )

    task = process_scan_batch.delay(
        image_urls=payload.image_urls,
        scan_type=payload.scan_type,
        source_url=payload.source_url,
        category=payload.category,
        package_width_mm=payload.package_width_mm,
        net_quantity_g=payload.net_quantity_g,
    )

    logger.info("Queued Celery batch task %s for %d images", task.id, len(payload.image_urls))

    return {
        "batch_id": task.id,
        "status": "queued",
        "total_images": len(payload.image_urls),
        "message": f"Queued {len(payload.image_urls)} images for background scanning.",
    }


@router.post("/scans/batch", summary="Batch Process Product Label Scans")
@router.post("/scan/batch", summary="Batch Process Product Label Scans (Files or Queue)")
async def batch_scan_images(
    files: list[UploadFile] = File(None),
    scan_type: str = Form("ecommerce"),
    source_url: str = Form(None),
    category: str = Form("General"),
    package_width_mm: float = Form(None),
    net_quantity_g: float = Form(None),
    current_user: User = Depends(require_inspector),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch process uploaded product label images synchronously.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files uploaded in batch request. For URL batch scanning, use POST /scan/batch/queue.",
        )

    logger.info("Received batch scan request: %d files, scan_type=%s", len(files), scan_type)

    results = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            res = await _process_single_scan_image(
                image_bytes=content,
                filename=file.filename or "image.jpg",
                scan_type_str=scan_type,
                source_url=source_url,
                category=category,
                package_width_mm=package_width_mm,
                net_quantity_g=net_quantity_g,
                db=db,
            )
            results.append(res)
        except Exception as exc:
            logger.error("Failed to process batch image %s: %s", file.filename, exc)
            errors.append({"filename": file.filename, "error": str(exc)})

    return {
        "status": "success" if results else "failed",
        "total_processed": len(results),
        "total_failed": len(errors),
        "results": results,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Celery Batch Progress Status Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/scans/batch/{batch_id}/status", summary="Get Asynchronous Batch Task Status & Progress")
@router.get("/scan/batch/{batch_id}/status", summary="Get Asynchronous Batch Task Status (Alias)")
async def get_batch_scan_status(batch_id: str):
    """
    Query the progress and status of a Celery batch scan task by batch_id.

    Returns progress e.g. "45/100 processed", progress percentage, and final results when completed.
    """
    task_result = AsyncResult(batch_id, app=celery_app)
    task_state = task_result.state

    if task_state == "PENDING":
        return {
            "batch_id": batch_id,
            "status": "queued",
            "processed": 0,
            "total": 0,
            "progress_percent": 0.0,
            "message": "Task queued, waiting for worker to begin processing.",
        }

    elif task_state == "PROGRESS":
        info = task_result.info or {}
        current = info.get("current", 0)
        total = info.get("total", 0)
        percent = round((current / total) * 100.0, 1) if total > 0 else 0.0

        return {
            "batch_id": batch_id,
            "status": "processing",
            "processed": current,
            "total": total,
            "progress_percent": percent,
            "message": f"{current}/{total} processed",
        }

    elif task_state == "SUCCESS":
        res_data = task_result.result or {}
        processed = res_data.get("processed", 0)
        total = res_data.get("total", processed)

        return {
            "batch_id": batch_id,
            "status": "completed",
            "processed": processed,
            "total": total,
            "progress_percent": 100.0,
            "message": f"{processed}/{total} processed",
            "result": res_data,
        }

    elif task_state == "FAILURE":
        return {
            "batch_id": batch_id,
            "status": "failed",
            "processed": 0,
            "total": 0,
            "progress_percent": 0.0,
            "message": "Batch processing failed.",
            "error": str(task_result.info),
        }

    else:
        return {
            "batch_id": batch_id,
            "status": str(task_state).lower(),
            "processed": 0,
            "total": 0,
            "progress_percent": 0.0,
            "message": f"Task state: {task_state}",
        }
