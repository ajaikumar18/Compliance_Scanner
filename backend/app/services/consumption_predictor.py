"""
Product Consumption Frequency & Depletion Predictor
===================================================
Estimates household consumption rate, expected depletion timeline,
and pantry replenishment schedule based on product category, declared net quantity,
and household member size.

IMPORTANT DISCLAIMER:
All predictions are mathematical behavioral estimates to assist in pantry management
and food wastage prevention. They do not constitute nutritional or dietary prescriptions.
"""

from __future__ import annotations

import re
import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Standard adult daily consumption rates in grams or ml per person
CATEGORY_DAILY_SERVING = {
    "packaged foods": 25.0,     # Biscuits, snacks
    "biscuits": 25.0,
    "cookies": 25.0,
    "beverages": 200.0,
    "dairy": 150.0,
    "staples": 100.0,          # Flour, rice
    "edible oil": 20.0,
    "tea": 5.0,
    "coffee": 4.0,
    "general": 30.0,
}


def parse_quantity_in_grams(quantity_str: str | float | None) -> float:
    """Extract numeric quantity in grams/ml from text or float."""
    if isinstance(quantity_str, (int, float)):
        return float(quantity_str)
    if not quantity_str:
        return 100.0

    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|l|litre|liter)", str(quantity_str), re.I)
    if m:
        return float(m.group(1)) * 1000.0

    m = re.search(r"(\d+(?:\.\d+)?)\s*(g|gm|gram|ml)", str(quantity_str), re.I)
    if m:
        return float(m.group(1))

    m = re.search(r"(\d+(?:\.\d+)?)", str(quantity_str))
    if m:
        return float(m.group(1))

    return 100.0


def predict_consumption(
    category: str = "Packaged Foods",
    net_quantity: str | float = 75.0,
    household_size: int = 2,
    expiry_date_str: str | None = None,
    reference_today: date | None = None,
) -> dict[str, Any]:
    """
    Predict household consumption timeline and verify expiry safety buffer.
    """
    today = reference_today or date.today()
    h_size = max(1, min(10, int(household_size)))
    total_qty_g = parse_quantity_in_grams(net_quantity)

    cat_key = (category or "general").lower().strip()
    rate_per_person = 25.0
    for k, v in CATEGORY_DAILY_SERVING.items():
        if k in cat_key:
            rate_per_person = v
            break

    daily_household_rate = rate_per_person * h_size
    estimated_days = max(1, round(total_qty_g / daily_household_rate))
    expected_depletion = today + timedelta(days=estimated_days)

    # Check against expiry date if provided
    waste_risk = False
    warning_message = None

    if expiry_date_str:
        try:
            from app.services.expiry_intelligence import parse_date_string
            exp = parse_date_string(expiry_date_str)
            if exp and expected_depletion > exp:
                waste_risk = True
                days_over = (expected_depletion - exp).days
                warning_message = (
                    f"At current household consumption pace, this product will deplete {days_over} days AFTER its expiry date ({exp.strftime('%d/%m/%Y')}). "
                    "Consider consuming more frequently or opting for a smaller packaging size."
                )
        except Exception:
            pass

    return {
        "household_size": h_size,
        "net_quantity_g": total_qty_g,
        "daily_consumption_rate_g": round(daily_household_rate, 1),
        "estimated_duration_days": estimated_days,
        "expected_depletion_date": expected_depletion.strftime("%d/%m/%Y"),
        "waste_risk_detected": waste_risk,
        "warning_message": warning_message,
        "summary": (
            f"Based on a household of {h_size} person{'s' if h_size > 1 else ''}, this {int(total_qty_g)}g package "
            f"is estimated to last approximately {estimated_days} day{'s' if estimated_days > 1 else ''} "
            f"(depleting around {expected_depletion.strftime('%d %B %Y')})."
        ),
        "disclaimer": "ESTIMATED PREDICTION - For grocery planning and food waste reduction only; not a medical or nutritional claim.",
    }
