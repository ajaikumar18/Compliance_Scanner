"""
Geographic Knowledge & Country of Origin Inference Engine
========================================================
Intelligently deduces the Country of Origin from manufacturer addresses,
plant locations, states, union territories, cities, industrial corridors,
and postal codes (including Indian states & PIN codes, US states, and international regions).

Complies with Indian Legal Metrology (Packaged Commodities) Rules 2011, Rule 6(1)(n).
"""

from __future__ import annotations

import re
from typing import TypedDict


class GeoInferenceResult(TypedDict):
    country: str
    inferred_from: str
    evidence_type: str  # "state" | "city" | "pincode" | "explicit_label"
    confidence: float
    full_declaration: str


# ─────────────────────────────────────────────────────────────────────────────
# Geographic Knowledge Base
# ─────────────────────────────────────────────────────────────────────────────

# 1. India: All 28 States & 8 Union Territories
INDIAN_STATES = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "uttaranchal": "Uttarakhand",
    "west bengal": "West Bengal",
    # Union Territories
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "national capital region": "Delhi",
    "ncr": "Delhi",
    "chandigarh": "Chandigarh",
    "puducherry": "Puducherry",
    "pondicherry": "Puducherry",
    "jammu and kashmir": "Jammu & Kashmir",
    "jammu & kashmir": "Jammu & Kashmir",
    "ladakh": "Ladakh",
    "andaman and nicobar": "Andaman & Nicobar",
    "dadra and nagar haveli": "Dadra & Nagar Haveli",
    "daman and diu": "Daman & Diu",
    "lakshadweep": "Lakshadweep",
}

# Indian State standard 2-letter postal abbreviations (used in addresses e.g. "HR-123501", "MH - 400057")
INDIAN_STATE_CODES = {
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "UA": "Uttarakhand",
    "WB": "West Bengal",
    "DL": "Delhi",
    "CH": "Chandigarh",
    "PY": "Puducherry",
    "JK": "Jammu & Kashmir",
    "LA": "Ladakh",
}

# Major Indian Cities & Industrial manufacturing hubs mapped to state
INDIAN_CITIES = {
    # Haryana
    "rewari": "Haryana",
    "bawal": "Haryana",
    "sonipat": "Haryana",
    "sonepat": "Haryana",
    "barhi": "Haryana",
    "kundli": "Haryana",
    "panipat": "Haryana",
    "gurgaon": "Haryana",
    "gurugram": "Haryana",
    "faridabad": "Haryana",
    "manesar": "Haryana",
    "dharuhera": "Haryana",
    "rohtak": "Haryana",
    "ambala": "Haryana",
    "karnal": "Haryana",
    "hisar": "Haryana",
    # Maharashtra
    "mumbai": "Maharashtra",
    "bombay": "Maharashtra",
    "pune": "Maharashtra",
    "thane": "Maharashtra",
    "navi mumbai": "Maharashtra",
    "raigad": "Maharashtra",
    "taloja": "Maharashtra",
    "nagpur": "Maharashtra",
    "nashik": "Maharashtra",
    "aurangabad": "Maharashtra",
    "kolhapur": "Maharashtra",
    "solapur": "Maharashtra",
    "bhiwandi": "Maharashtra",
    "vile parle": "Maharashtra",
    "andheri": "Maharashtra",
    # Karnataka
    "bengaluru": "Karnataka",
    "bangalore": "Karnataka",
    "hubli": "Karnataka",
    "hubballi": "Karnataka",
    "dharwad": "Karnataka",
    "mysuru": "Karnataka",
    "mysore": "Karnataka",
    "mangalore": "Karnataka",
    "mangaluru": "Karnataka",
    "belgaum": "Karnataka",
    "belagavi": "Karnataka",
    "bailhongal": "Karnataka",
    "ballari": "Karnataka",
    "bellary": "Karnataka",
    "karignoor": "Karnataka",
    "hospet": "Karnataka",
    "sankalapur": "Karnataka",
    # Tamil Nadu
    "chennai": "Tamil Nadu",
    "madras": "Tamil Nadu",
    "coimbatore": "Tamil Nadu",
    "madurai": "Tamil Nadu",
    "tiruchirappalli": "Tamil Nadu",
    "salem": "Tamil Nadu",
    "tiruppur": "Tamil Nadu",
    "erode": "Tamil Nadu",
    "nilakottai": "Tamil Nadu",
    "batlagundu": "Tamil Nadu",
    "dindigul": "Tamil Nadu",
    "ambattur": "Tamil Nadu",
    "sriperumbudur": "Tamil Nadu",
    "hosur": "Tamil Nadu",
    # Gujarat
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "vadodara": "Gujarat",
    "baroda": "Gujarat",
    "rajkot": "Gujarat",
    "bhavnagar": "Gujarat",
    "vapi": "Gujarat",
    "ankleshwar": "Gujarat",
    "sanand": "Gujarat",
    "anand": "Gujarat",
    "gandhinagar": "Gujarat",
    # Uttar Pradesh
    "noida": "Uttar Pradesh",
    "greater noida": "Uttar Pradesh",
    "ghaziabad": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh",
    "lucknow": "Uttar Pradesh",
    "agra": "Uttar Pradesh",
    "varanasi": "Uttar Pradesh",
    "meerut": "Uttar Pradesh",
    "bareilly": "Uttar Pradesh",
    "aligarh": "Uttar Pradesh",
    "gorakhpur": "Uttar Pradesh",
    # West Bengal
    "kolkata": "West Bengal",
    "calcutta": "West Bengal",
    "howrah": "West Bengal",
    "durgapur": "West Bengal",
    "asansol": "West Bengal",
    "siliguri": "West Bengal",
    # Himachal & Uttarakhand
    "baddi": "Himachal Pradesh",
    "solan": "Himachal Pradesh",
    "nalagarh": "Himachal Pradesh",
    "parwanoo": "Himachal Pradesh",
    "haridwar": "Uttarakhand",
    "dehradun": "Uttarakhand",
    "pantnagar": "Uttarakhand",
    "rudrapur": "Uttarakhand",
    "roorkee": "Uttarakhand",
    # Goa
    "cuncolim": "Goa",
    "salcete": "Goa",
    "panaji": "Goa",
    "margao": "Goa",
    "verna": "Goa",
    # Telangana & AP
    "hyderabad": "Telangana",
    "secunderabad": "Telangana",
    "warangal": "Telangana",
    "visakhapatnam": "Andhra Pradesh",
    "vizag": "Andhra Pradesh",
    "vijayawada": "Andhra Pradesh",
    "guntur": "Andhra Pradesh",
    # Kerala
    "kochi": "Kerala",
    "cochin": "Kerala",
    "thiruvananthapuram": "Kerala",
    "trivandrum": "Kerala",
    "kozhikode": "Kerala",
    "thrissur": "Kerala",
    # Rajasthan & Punjab
    "jaipur": "Rajasthan",
    "jodhpur": "Rajasthan",
    "kota": "Rajasthan",
    "bhiwadi": "Rajasthan",
    "alwar": "Rajasthan",
    "ludhiana": "Punjab",
    "amritsar": "Punjab",
    "jalandhar": "Punjab",
    "mohali": "Punjab",
    # MP & Bihar
    "indore": "Madhya Pradesh",
    "bhopal": "Madhya Pradesh",
    "pithampur": "Madhya Pradesh",
    "patna": "Bihar",
    "ranchi": "Jharkhand",
    "jamshedpur": "Jharkhand",
}

# International Countries & their subdivisions / states
INTERNATIONAL_REGIONS = {
    "united states": {
        "country": "United States",
        "keywords": [
            "usa", "u.s.a.", "united states", "california", "texas", "new york",
            "michigan", "battle creek", "illinois", "chicago", "florida", "ohio",
            "pennsylvania", "georgia", "atlanta", "washington", "massachusetts"
        ],
    },
    "united kingdom": {
        "country": "United Kingdom",
        "keywords": [
            "uk", "u.k.", "united kingdom", "great britain", "england", "scotland",
            "wales", "london", "manchester", "birmingham"
        ],
    },
    "canada": {
        "country": "Canada",
        "keywords": ["canada", "ontario", "quebec", "british columbia", "alberta", "toronto", "vancouver", "montreal"],
    },
    "germany": {
        "country": "Germany",
        "keywords": ["germany", "deutschland", "bavaria", "bayern", "berlin", "munich", "münchen", "frankfurt", "hamburg"],
    },
    "switzerland": {
        "country": "Switzerland",
        "keywords": ["switzerland", "suisse", "schweiz", "zurich", "zürich", "geneva", "basel", "vevey"],
    },
    "italy": {
        "country": "Italy",
        "keywords": ["italy", "italia", "milan", "milano", "rome", "roma", "turin", "torino", "alba"],
    },
    "france": {
        "country": "France",
        "keywords": ["france", "paris", "lyon", "marseille"],
    },
    "japan": {
        "country": "Japan",
        "keywords": ["japan", "nippon", "tokyo", "osaka", "kyoto", "yokohama"],
    },
    "china": {
        "country": "China",
        "keywords": ["china", "p.r.c.", "beijing", "shanghai", "shenzhen", "guangzhou"],
    },
    "australia": {
        "country": "Australia",
        "keywords": ["australia", "sydney", "melbourne", "brisbane", "victoria", "new south wales", "queensland"],
    },
    "singapore": {
        "country": "Singapore",
        "keywords": ["singapore"],
    },
    "thailand": {
        "country": "Thailand",
        "keywords": ["thailand", "bangkok"],
    },
    "malaysia": {
        "country": "Malaysia",
        "keywords": ["malaysia", "kuala lumpur"],
    },
    "united arab emirates": {
        "country": "United Arab Emirates",
        "keywords": ["uae", "u.a.e.", "dubai", "abu dhabi", "sharjah"],
    },
    "sri lanka": {
        "country": "Sri Lanka",
        "keywords": ["sri lanka", "colombo"],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Inference Engine
# ─────────────────────────────────────────────────────────────────────────────

def infer_country_from_text(raw_text: str) -> GeoInferenceResult | None:
    """
    Examines text (such as manufacturer address, plant details, or label declarations)
    and deduces the Country of Origin based on state, city, PIN code, or country indicators.
    """
    if not raw_text or not raw_text.strip():
        return None

    clean_text = raw_text.strip()
    lower_text = clean_text.lower()

    # 1. Direct explicit declaration check (e.g. "Made in India", "Country of Origin: India")
    m_exp = re.search(
        r"(?:Country\s+of\s+Origin|Made\s+in|Product\s+of)[\s:\-]*([A-Za-z\s]+)",
        clean_text,
        re.IGNORECASE,
    )
    if m_exp:
        found_c = m_exp.group(1).strip()
        found_c = re.split(r'[\n\r\,\;\.]', found_c)[0].strip()
        if found_c.lower() in ("india", "ind"):
            return GeoInferenceResult(
                country="India",
                inferred_from="Explicit declaration",
                evidence_type="explicit_label",
                confidence=0.98,
                full_declaration="Country of Origin: India",
            )
        for c_key, data in INTERNATIONAL_REGIONS.items():
            if found_c.lower() == c_key or found_c.lower() in data["keywords"]:
                return GeoInferenceResult(
                    country=data["country"],
                    inferred_from="Explicit declaration",
                    evidence_type="explicit_label",
                    confidence=0.98,
                    full_declaration=f"Country of Origin: {data['country']}",
                )

    # 2. Check for Indian States in text
    for state_key, state_name in INDIAN_STATES.items():
        if re.search(rf"\b{re.escape(state_key)}\b", lower_text):
            return GeoInferenceResult(
                country="India",
                inferred_from=f"State: {state_name}",
                evidence_type="state",
                confidence=0.95,
                full_declaration=f"Country of Origin: India (Inferred from Location: {state_name})",
            )

    # 3. Check for Indian State Code + 6-digit PIN code (e.g. "HR-123501", "KA - 581207", "KA 601125", "MH-400057")
    m_state_code = re.search(
        r"\b(AP|AR|AS|BR|CG|GA|GJ|HR|HP|JH|KA|KL|MP|MH|MN|ML|MZ|NL|OD|PB|RJ|SK|TN|TS|TR|UP|UK|UA|WB|DL|CH|PY|JK|LA)\s*[\-:\s]\s*([1-9][0-9]{5})\b",
        clean_text,
        re.IGNORECASE,
    )
    if m_state_code:
        code = m_state_code.group(1).upper()
        pin = m_state_code.group(2)
        state_name = INDIAN_STATE_CODES.get(code, code)
        return GeoInferenceResult(
            country="India",
            inferred_from=f"{state_name} ({code}-{pin})",
            evidence_type="state",
            confidence=0.95,
            full_declaration=f"Country of Origin: India (Inferred from Location: {state_name})",
        )

    # 4. Check for Indian Cities / Industrial Corridors
    for city_key, state_name in INDIAN_CITIES.items():
        if re.search(rf"\b{re.escape(city_key)}\b", lower_text):
            city_disp = city_key.title()
            return GeoInferenceResult(
                country="India",
                inferred_from=f"City: {city_disp}, {state_name}",
                evidence_type="city",
                confidence=0.92,
                full_declaration=f"Country of Origin: India (Inferred from Location: {city_disp}, {state_name})",
            )

    # 5. Check for Indian 6-digit PIN code in address context
    has_addr_context = any(
        k in lower_text
        for k in [
            "plot", "sector", "road", "street", "dist", "industrial", "area",
            "pvt", "ltd", "mfd", "marketed", "packed", "by", "pin", "office", "plant", "estate"
        ]
    )
    m_pin = re.search(r"\b([1-9][0-9]{2}\s?[0-9]{3})\b", clean_text)
    if has_addr_context and m_pin:
        pin = m_pin.group(1).replace(" ", "")
        return GeoInferenceResult(
            country="India",
            inferred_from=f"PIN Code: {pin}",
            evidence_type="pincode",
            confidence=0.88,
            full_declaration="Country of Origin: India (Inferred from Postal PIN Code)",
        )

    # 6. Check for International Regions / States
    for reg_key, data in INTERNATIONAL_REGIONS.items():
        for kw in data["keywords"]:
            if re.search(rf"\b{re.escape(kw)}\b", lower_text):
                matched_kw = kw.title()
                country_name = data["country"]
                return GeoInferenceResult(
                    country=country_name,
                    inferred_from=f"{matched_kw}, {country_name}",
                    evidence_type="state",
                    confidence=0.90,
                    full_declaration=f"Country of Origin: {country_name} (Inferred from Location: {matched_kw})",
                )

    # 7. Check for standalone "India" keyword
    if re.search(r"\bindia\b", lower_text):
        return GeoInferenceResult(
            country="India",
            inferred_from="India keyword",
            evidence_type="explicit_label",
            confidence=0.85,
            full_declaration="Country of Origin: India",
        )

    return None
