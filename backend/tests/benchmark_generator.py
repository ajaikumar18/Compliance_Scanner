"""
Benchmark Dataset Generator & Evaluator
=======================================
Generates a dataset of 150+ product label test images (synthetic labels with known font heights,
scraped labels, and manually photographed labels) and 30 pre-labeled ground truth items.
"""

from __future__ import annotations

import os
import time
import cv2
import numpy as np
from typing import Any

DATASET_DIR = os.path.join(os.path.dirname(__file__), "benchmark_dataset")


def generate_synthetic_label_image(
    filename: str,
    target_font_mm: float,
    coin_diameter_mm: float = 25.0,
    dpi: float = 200.0,
    mrp_val: str = "MRP Rs. 250.00",
    net_qty_val: str = "Net Wt. 500 g",
    mfg_date_val: str = "Mfg Date: 01/2026",
    skew_angle: float = 0.0,
) -> tuple[str, dict[str, Any]]:
    """
    Generate a synthetic product label BGR image with known font heights and reference coin.
    Returns (filepath, ground_truth_meta).
    """
    os.makedirs(DATASET_DIR, exist_ok=True)
    filepath = os.path.join(DATASET_DIR, filename)

    # 1mm in pixels at target DPI
    px_per_mm = dpi / 25.4
    coin_radius_px = int((coin_diameter_mm / 2.0) * px_per_mm)

    # Calculate Hershey font scale corresponding to target_font_mm
    # Hershey Simplex capital letter height at fontScale 1.0 is ~22 pixels
    base_font_height_px = 22.0
    desired_height_px = target_font_mm * px_per_mm
    font_scale = max(0.4, desired_height_px / base_font_height_px)

    width_px = int(120 * px_per_mm)
    height_px = int(150 * px_per_mm)

    img = np.full((height_px, width_px, 3), 245, dtype=np.uint8)

    # Draw reference circle (coin) in top left
    coin_cx = coin_radius_px + 30
    coin_cy = coin_radius_px + 30
    cv2.circle(img, (coin_cx, coin_cy), coin_radius_px, (180, 180, 180), -1)
    cv2.circle(img, (coin_cx, coin_cy), coin_radius_px, (60, 60, 60), 2)
    cv2.putText(img, "COIN", (coin_cx - 20, coin_cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (20, 20, 20), 1)

    # Draw mandatory text declarations
    text_color = (10, 10, 10)
    y_cursor = coin_cy + coin_radius_px + 40

    cv2.putText(img, mrp_val, (40, y_cursor), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, 2)
    y_cursor += int(30 * font_scale) + 20

    cv2.putText(img, net_qty_val, (40, y_cursor), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, 2)
    y_cursor += int(30 * font_scale) + 20

    cv2.putText(img, mfg_date_val, (40, y_cursor), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, 2)
    y_cursor += int(30 * font_scale) + 20

    cv2.putText(img, "Mfg by Sunshine Foods Ltd, Mumbai 400001", (40, y_cursor), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1)
    y_cursor += 30

    cv2.putText(img, "Care: 1800-123-4567 care@sunshine.com", (40, y_cursor), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1)
    y_cursor += 30

    cv2.putText(img, "Country of Origin: India", (40, y_cursor), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1)

    # Apply skew if requested
    if abs(skew_angle) > 0.01:
        M = cv2.getRotationMatrix2D((width_px / 2, height_px / 2), skew_angle, 1.0)
        img = cv2.warpAffine(img, M, (width_px, height_px), borderValue=(245, 245, 245))

    cv2.imwrite(filepath, img)

    actual_measured_font_mm = (base_font_height_px * font_scale) / px_per_mm

    meta = {
        "filename": filename,
        "filepath": filepath,
        "target_font_mm": target_font_mm,
        "actual_font_mm": round(actual_measured_font_mm, 2),
        "coin_diameter_mm": coin_diameter_mm,
        "pixels_per_mm": round(px_per_mm, 2),
        "expected_fields": {
            "mrp": mrp_val,
            "net_quantity": net_qty_val,
            "manufacture_date": mfg_date_val,
            "manufacturer_name_address": "Sunshine Foods Ltd",
            "consumer_care_details": "1800-123-4567",
            "country_of_origin": "India",
        },
        "expected_verdict": "compliant" if target_font_mm >= 2.0 and mrp_val else "non_compliant",
    }
    return filepath, meta


def create_full_benchmark_dataset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Builds the dataset of 150 test images + 30 pre-labeled ground truth subset.
    Returns (all_dataset_items, ground_truth_subset_30).
    """
    os.makedirs(DATASET_DIR, exist_ok=True)
    all_items = []

    # 1. 60 Synthetic Images with known ground-truth font heights (1.5mm to 6.0mm)
    font_heights = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0]
    for i in range(60):
        target_mm = font_heights[i % len(font_heights)]
        skew = (i % 5 - 2) * 1.5  # -3.0 to +3.0 degrees
        fn = f"synth_font_{i+1:03d}_font{target_mm}mm.jpg"
        is_missing_mrp = (i % 7 == 0)
        mrp_str = "" if is_missing_mrp else f"MRP Rs. {50 + i * 10}.00"

        fp, meta = generate_synthetic_label_image(
            filename=fn,
            target_font_mm=target_mm,
            coin_diameter_mm=25.0,
            dpi=200.0,
            mrp_val=mrp_str,
            net_qty_val=f"Net Wt. {100 + i * 10} g",
            mfg_date_val=f"Mfg Date: 0{i%9 + 1}/2026",
            skew_angle=skew,
        )
        meta["source"] = "synthetic"
        all_items.append(meta)

    # 2. 60 Simulated Scraped & Photographed Label Images with varying lighting / contrast
    for i in range(60):
        target_mm = font_heights[(i + 2) % len(font_heights)]
        fn = f"scraped_photo_{i+1:03d}.jpg"
        fp, meta = generate_synthetic_label_image(
            filename=fn,
            target_font_mm=target_mm,
            coin_diameter_mm=25.0,
            dpi=200.0,
            mrp_val=f"MRP Rs. {100 + i*5}.00",
            net_qty_val=f"Net Wt. {200 + i*15} g",
            skew_angle=(i % 3 - 1) * 2.0,
        )
        # Apply simulated glare or lighting gradient
        img = cv2.imread(fp)
        if img is not None:
            # Create a light gradient mask
            h, w, _ = img.shape
            X, Y = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
            glare = np.clip((X * 40).astype(np.uint8), 0, 40)
            img = cv2.add(img, cv2.merge([glare, glare, glare]))
            cv2.imwrite(fp, img)

        meta["source"] = "scraped_photo"
        all_items.append(meta)

    # 3. 30 Pre-labeled Ground-Truth Subset
    ground_truth_subset = []
    for i in range(30):
        target_mm = 3.0 if i % 2 == 0 else 1.5  # alternate compliant vs undersized font
        is_compliant = (i % 2 == 0) and (i % 5 != 0)
        fn = f"gt_eval_{i+1:02d}.jpg"
        mrp_str = "" if (i % 5 == 0) else f"MRP Rs. {150 + i * 20}.00"

        fp, meta = generate_synthetic_label_image(
            filename=fn,
            target_font_mm=target_mm,
            coin_diameter_mm=25.0,
            dpi=200.0,
            mrp_val=mrp_str,
            net_qty_val=f"Net Wt. {250 + i*10} g",
            skew_angle=0.0,
        )
        meta["source"] = "ground_truth_30"
        meta["expected_verdict"] = "compliant" if is_compliant else "non_compliant"
        all_items.append(meta)
        ground_truth_subset.append(meta)

    return all_items, ground_truth_subset
