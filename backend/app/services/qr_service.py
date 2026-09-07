"""
QR Code & Digital Product Verification Service
==============================================
Generates secure unique verification IDs, standard QR codes (PNG base64 Data URLs),
and prepares sanitized public digital product profiles for consumer verification
under Legal Metrology (Packaged Commodities) Rules, 2011.
"""

from __future__ import annotations

import base64
import io
import uuid
import logging
try:
    import qrcode
    from qrcode.image.pil import PilImage
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logger = logging.getLogger(__name__)

VERIFICATION_BASE_URL = "http://localhost:5173/?verify="



def generate_verification_id(scan_uid: str | None = None) -> str:
    """Generate a unique digital verification identifier."""
    if scan_uid and scan_uid.startswith("LM-"):
        # Map directly to the statutory scan UID for consistency
        suffix = scan_uid.replace("LM-", "").replace("2026-", "")
        return f"LM-VERIFY-2026-{suffix}"
    short_hash = uuid.uuid4().hex[:8].upper()
    return f"LM-VERIFY-{short_hash}"


def generate_qr_code_data_url(content: str) -> str:
    """
    Generate a standard QR code encoding the provided content string.
    Returns a PNG data URL (data:image/png;base64,...).
    """
    if not HAS_QRCODE:
        return f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={content}"
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(content)
        qr.make(fit=True)

        img: PilImage = qr.make_image(fill_color="#0b1120", back_color="#ffffff")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"
    except Exception as exc:
        logger.error("Failed to generate QR code data URL: %s", exc)
        return ""


def create_digital_product_profile(
    scan_data: dict[str, Any],
    base_url: str = VERIFICATION_BASE_URL,
) -> dict[str, Any]:
    """
    Build a complete, secure digital product verification record.
    Sanitizes private database keys and includes public statutory details.
    """
    scan_uid = scan_data.get("scan_uid") or str(scan_data.get("scan_id", "LM-2026-000001"))
    verification_id = scan_data.get("verification_id") or generate_verification_id(scan_uid)
    verification_url = f"{base_url}{verification_id}"

    qr_data_url = generate_qr_code_data_url(verification_url)

    # Resolve core product fields
    p_details = scan_data.get("product_details") or scan_data.get("ecommerce_data") or {}
    fields = scan_data.get("fields") or {}

    def _val(key: str, default: str = "Not Declared") -> str:
        if key in p_details and p_details[key]:
            return str(p_details[key])
        f_entry = fields.get(key)
        if isinstance(f_entry, dict) and f_entry.get("extracted_value"):
            return str(f_entry["extracted_value"])
        return default

    # Overall compliance status normalized
    raw_status = (scan_data.get("compliance_status") or "non_compliant").lower()
    if raw_status == "compliant":
        status_label = "COMPLIANT"
    elif "partial" in raw_status or "undetermined" in raw_status:
        status_label = "PARTIALLY COMPLIANT"
    else:
        status_label = "NON-COMPLIANT"

    # Score calculation
    violations = scan_data.get("violations") or []
    v_count = len(violations)
    compliance_score = max(10, 100 - (v_count * 20)) if status_label != "COMPLIANT" else 100

    # Public-safe violations explanation
    sanitized_violations = []
    for v in violations:
        field_name = v.get("field_name") or v.get("rule") or "Mandatory Declaration"
        details = v.get("details") or v.get("reason") or "Statutory requirement violation under Rule 6."
        severity = v.get("severity") or "high"
        sanitized_violations.append({
            "field": str(field_name).replace("_", " ").title(),
            "severity": severity,
            "explanation": details,
        })

    profile = {
        "verification_id": verification_id,
        "scan_uid": scan_uid,
        "verification_url": verification_url,
        "qr_code_data_url": qr_data_url,
        "product_name": scan_data.get("product_name") or _val("product_name", "Packaged Commodity"),
        "brand_manufacturer": _val("brand") if _val("brand") != "Not Declared" else _val("manufacturer_name", "Unknown Entity"),
        "manufacturer_address": _val("manufacturer_address", "Undeclared"),
        "net_quantity": _val("net_quantity"),
        "mrp": _val("mrp"),
        "selling_price": _val("selling_price", "N/A"),
        "manufacturing_date": _val("manufacture_date", _val("date", "Undeclared")),
        "expiry_date": _val("expiry_date", "Refer packaging declaration"),
        "batch_number": _val("batch_number", "Undeclared"),
        "consumer_care": _val("consumer_care", "Undeclared"),
        "country_of_origin": _val("country_of_origin", "India"),
        "compliance_status": status_label,
        "compliance_score": compliance_score,
        "violations_count": v_count,
        "detected_violations": sanitized_violations,
        "inspection_timestamp": scan_data.get("created_at") or scan_data.get("timestamp") or "2026-09-05T12:00:00Z",
        "regulatory_authority": "Department of Consumer Affairs, Legal Metrology Division, Govt. of India",
        "act_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    }
    return profile
