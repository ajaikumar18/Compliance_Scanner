"""
Product Intelligence & Verification Router
==========================================
Provides public digital product verification (QR code endpoints),
context-aware multilingual AI compliance chatbot, interactive package damage analysis,
consumption frequency forecasting, and grocery expiry intelligence.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import Response
import io
from pydantic import BaseModel
import cv2
import numpy as np

from app.core.scan_repository import ScanRepository
from app.services.qr_service import create_digital_product_profile
from app.services.ai_chatbot import query_compliance_chatbot, SUPPORTED_LANGUAGES
from app.services.damage_detector import analyze_package_damage
from app.services.consumption_predictor import predict_consumption
from app.services.expiry_intelligence import analyze_expiry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Product Intelligence & Verification"])


# ── Pydantic Request Models ───────────────────────────────────────────────────

class ChatQueryRequest(BaseModel):
    message: str
    scan_id: str | None = None
    language: str = "en"
    session_id: str | None = None


class ConsumptionPredictRequest(BaseModel):
    category: str = "Packaged Foods"
    net_quantity: str | float = 75.0
    household_size: int = 2
    expiry_date: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/verify/{verification_id}", summary="Get Public Digital Product Verification Profile")
async def get_digital_product_verification(verification_id: str):
    """
    Public digital verification endpoint accessed via printed QR codes.
    Returns sanitized compliance dossier and statutory declarations without exposing internal keys.
    """
    profile = ScanRepository.get_qr_verification(verification_id)
    if not profile:
        # Check if ID is a scan UID
        scan_record = ScanRepository.get_scan_by_id(verification_id)
        if scan_record:
            profile = create_digital_product_profile(scan_record)
            ScanRepository.save_qr_verification(verification_id, verification_id, profile)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Digital product profile '{verification_id}' was not found in the national registry.",
            )
    return profile


@router.post("/chat", summary="Context-Aware Multilingual AI Compliance Assistant")
async def post_chat_query(req: ChatQueryRequest):
    """
    Consult the AI Compliance Assistant on Legal Metrology rules, packaging declarations,
    MRP, expiry dates, or reasons for compliance scores.
    Supports English, Tamil, Hindi, Telugu, Kannada, and Malayalam.
    """
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:10]}"
    scan_context = None

    if req.scan_id:
        scan_context = ScanRepository.get_scan_by_id(req.scan_id)

    # Save user message to chat ledger
    ScanRepository.save_chat_message(session_id, req.scan_id, "user", req.message, req.language)

    # Query chatbot
    result = query_compliance_chatbot(req.message, scan_context, req.language)
    result["session_id"] = session_id

    # Save bot response to chat ledger
    ScanRepository.save_chat_message(session_id, req.scan_id, "assistant", result["reply"], req.language)

    return result


@router.get("/chat/{session_id}/history", summary="Get Chat Message History")
async def get_chat_session_history(session_id: str):
    """Retrieve chronological messages for an active chat session."""
    history = ScanRepository.get_chat_history(session_id)
    return {"session_id": session_id, "messages": history}


@router.get("/chat/languages", summary="Get List of Supported Indian Languages")
async def get_supported_languages():
    """Returns supported multilingual codes and localized display names."""
    return {"languages": SUPPORTED_LANGUAGES}


@router.post("/damage-check", summary="Computer-Vision Package Damage Self-Check")
async def post_damage_check(
    file: UploadFile = File(...),
):
    """
    Analyze uploaded packaging image for external visible damages:
    tears, punctures, crushing, leaks, moisture stains, or obscured labels.
    """
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None or img_bgr.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode uploaded image file. Please provide a valid PNG or JPEG.",
        )

    res = analyze_package_damage(img_bgr)
    return res


@router.post("/consumption/predict", summary="Predict Household Consumption Frequency & Depletion Timeline")
async def post_consumption_predict(req: ConsumptionPredictRequest):
    """
    Calculate estimated consumption duration, daily household usage,
    and verify if depletion will happen before product expiry.
    """
    prediction = predict_consumption(
        category=req.category,
        net_quantity=req.net_quantity,
        household_size=req.household_size,
        expiry_date_str=req.expiry_date,
    )
    return prediction


@router.get("/expiry/records", summary="Get Tracked Product Expiry Registry")
async def get_expiry_records(limit: int = 50):
    """
    Returns list of scanned commodities tracked in the grocery expiry intelligence system,
    ordered by days remaining until statutory expiry.
    """
    records = ScanRepository.list_expiry_records(limit=limit)
    return {"total": len(records), "records": records}


@router.get("/tts", summary="Synthesize Multilingual Speech Audio (MP3)")
async def synthesize_speech(text: str, lang: str = "en"):
    """
    Synthesize high-fidelity native speech audio for Indian languages (Tamil 'ta',
    Hindi 'hi', Telugu 'te', Kannada 'kn', Malayalam 'ml', and English 'en').
    Returns an audio/mpeg binary stream for immediate browser playback.
    """
    try:
        from gtts import gTTS

        # Extract 2-letter ISO code
        lang_code = lang.split("-")[0].lower()
        supported = {"en", "hi", "ta", "te", "kn", "ml", "mr", "bn", "gu"}
        if lang_code not in supported:
            lang_code = "en"

        clean_text = text.replace("*", "").replace("#", "").replace("_", "").replace("`", "").strip()
        if not clean_text:
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Limit text length to 1000 characters to ensure sub-second latency
        if len(clean_text) > 1000:
            clean_text = clean_text[:1000]

        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_bytes = fp.read()

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'inline; filename="speech_{lang_code}.mp3"',
                "Cache-Control": "public, max-age=86400",
            },
        )
    except Exception as exc:
        logger.error(f"TTS synthesis error for lang={lang}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize speech: {str(exc)}",
        )

