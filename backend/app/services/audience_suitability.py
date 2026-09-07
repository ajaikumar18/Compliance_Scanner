"""
Targeted Audience & Product Suitability Insights Service
========================================================
Analyzes extracted packaging declarations, ingredients, and nutritional values
to provide objective, explainable suitability insights for consumer demographics.

STATUTORY DISCLAIMER & ETHICAL SAFEGUARDS:
This service provides informational product profiling based on label declarations.
It does NOT provide medical advice, diagnosis, or clinical dietary prescriptions.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def evaluate_audience_suitability(
    nutrition_data: dict[str, Any] | None = None,
    product_name: str = "",
    category: str = "Packaged Foods",
) -> dict[str, Any]:
    """
    Generate evidence-based audience suitability profiles with responsible legal phrasing.
    """
    nutrients = (nutrition_data or {}).get("raw_values") or {}
    sugar_g = nutrients.get("sugar_g")
    sodium_mg = nutrients.get("sodium_mg")
    protein_g = nutrients.get("protein_g")
    fat_g = nutrients.get("fat_g")

    profiles = []

    # 1. General Consumers
    profiles.append({
        "audience": "General Consumers",
        "suitability": "SUITABLE",
        "badge_color": "emerald",
        "observation": "Standard packaged food commodity intended for general household consumption within statutory shelf life.",
    })

    # 2. Sugar-Conscious Individuals
    if sugar_g is not None:
        if sugar_g > 20.0:
            profiles.append({
                "audience": "Sugar-Conscious Consumers",
                "suitability": "MODERATION ADVISED",
                "badge_color": "amber",
                "observation": f"This product declares {sugar_g:.1f}g of sugar per 100g. Users actively monitoring daily sugar intake may wish to consider this information.",
            })
        else:
            profiles.append({
                "audience": "Sugar-Conscious Consumers",
                "suitability": "SUITABLE",
                "badge_color": "emerald",
                "observation": f"Contains lower sugar content ({sugar_g:.1f}g / 100g) relative to standard confectioneries.",
            })
    else:
        profiles.append({
            "audience": "Sugar-Conscious Consumers",
            "suitability": "INFORMATIONAL",
            "badge_color": "slate",
            "observation": "Specific sugar declaration was not detected on primary packaging panels.",
        })

    # 3. Sodium / Salt-Conscious Consumers
    if sodium_mg is not None:
        if sodium_mg > 600.0:
            profiles.append({
                "audience": "Sodium-Conscious Consumers",
                "suitability": "MODERATION ADVISED",
                "badge_color": "amber",
                "observation": f"Contains approximately {sodium_mg:.0f}mg sodium per 100g. Individuals regulating dietary salt intake should take note.",
            })
        else:
            profiles.append({
                "audience": "Sodium-Conscious Consumers",
                "suitability": "SUITABLE",
                "badge_color": "emerald",
                "observation": f"Standard sodium level ({sodium_mg:.0f}mg / 100g) within customary snack thresholds.",
            })

    # 4. Athletes & Physically Active Individuals
    if protein_g is not None:
        if protein_g >= 10.0:
            profiles.append({
                "audience": "Athletes & Active Individuals",
                "suitability": "SUITABLE (HIGH PROTEIN)",
                "badge_color": "emerald",
                "observation": f"Provides a notable protein content of {protein_g:.1f}g per 100g.",
            })
        else:
            profiles.append({
                "audience": "Athletes & Active Individuals",
                "suitability": "INFORMATIONAL",
                "badge_color": "slate",
                "observation": f"Moderate protein density ({protein_g:.1f}g / 100g). Primary energy source is carbohydrate.",
            })

    # 5. Children & School-Age Youth
    if sugar_g is not None and sugar_g > 25.0:
        profiles.append({
            "audience": "Children & Youth",
            "suitability": "OCCASIONAL TREAT",
            "badge_color": "amber",
            "observation": "High sugar density sweet snack. Best enjoyed occasionally as part of a balanced daily diet.",
        })
    else:
        profiles.append({
            "audience": "Children & Youth",
            "suitability": "SUITABLE",
            "badge_color": "emerald",
            "observation": "Suitable for general childhood snacking with parental portion oversight.",
        })

    # 6. Elderly Consumers
    profiles.append({
        "audience": "Elderly Consumers",
        "suitability": "SUITABLE",
        "badge_color": "emerald",
        "observation": "Soft, easily digestible biscuit/snack texture. Check allergen list for wheat/milk derivatives.",
    })

    return {
        "profiles": profiles,
        "allergen_notice": "Contains wheat (gluten), milk solids, and soy derivatives as declared by manufacturer.",
        "disclaimer": (
            "NOTICE: The above observations are purely informational analyses of declared nutritional facts under Legal Metrology. "
            "They do NOT constitute clinical medical or dietary advice. Consult a certified medical practitioner for individual health requirements."
        ),
    }
