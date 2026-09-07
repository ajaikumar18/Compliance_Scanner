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
import hashlib
from pathlib import Path
from pydantic import BaseModel
import cv2
import numpy as np

# Persistent on-disk and in-memory audio cache for sub-millisecond TTS responses
_TTS_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".tts_cache"
_TTS_CACHE_DIR.mkdir(exist_ok=True)
_TTS_MEMORY_CACHE: dict[str, bytes] = {}

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

        cache_key = hashlib.md5(f"{lang_code}:{clean_text}".encode("utf-8")).hexdigest()

        # 1. Check in-memory cache (sub-millisecond return)
        if cache_key in _TTS_MEMORY_CACHE:
            return Response(
                content=_TTS_MEMORY_CACHE[cache_key],
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'inline; filename="speech_{lang_code}.mp3"',
                    "Cache-Control": "public, max-age=86400",
                },
            )

        # 2. Check on-disk cache
        cache_file = _TTS_CACHE_DIR / f"{lang_code}_{cache_key}.mp3"
        if cache_file.exists():
            try:
                audio_bytes = cache_file.read_bytes()
                _TTS_MEMORY_CACHE[cache_key] = audio_bytes
                return Response(
                    content=audio_bytes,
                    media_type="audio/mpeg",
                    headers={
                        "Content-Disposition": f'inline; filename="speech_{lang_code}.mp3"',
                        "Cache-Control": "public, max-age=86400",
                    },
                )
            except Exception as read_err:
                logger.debug(f"Failed to read disk cache: {read_err}")

        # 3. Synthesize via gTTS
        if lang_code == "en":
            tts = gTTS(text=clean_text, lang="en", tld="co.in", slow=False)
        else:
            tts = gTTS(text=clean_text, lang=lang_code, slow=False)

        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_bytes = fp.read()

        # Save to memory and disk cache
        _TTS_MEMORY_CACHE[cache_key] = audio_bytes
        try:
            cache_file.write_bytes(audio_bytes)
        except Exception as write_err:
            logger.debug(f"Failed to write disk cache: {write_err}")

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


class TTSRequest(BaseModel):
    text: str
    lang: str = "en"


@router.post("/tts", summary="Synthesize Multilingual Speech Audio (MP3) via POST")
async def synthesize_speech_post(payload: TTSRequest):
    return await synthesize_speech(text=payload.text, lang=payload.lang)


def warmup_tts_cache():
    """
    Pre-warm TTS in-memory cache from disk and pre-synthesize standard multilingual greetings.
    Runs asynchronously in background thread at server startup so user requests respond in <5ms.
    """
    try:
        loaded_count = 0
        for mp3_path in _TTS_CACHE_DIR.glob("*.mp3"):
            try:
                parts = mp3_path.stem.split("_", 1)
                if len(parts) == 2:
                    cache_key = parts[1]
                    if cache_key not in _TTS_MEMORY_CACHE:
                        _TTS_MEMORY_CACHE[cache_key] = mp3_path.read_bytes()
                        loaded_count += 1
            except Exception:
                pass
        logger.info(f"Loaded {loaded_count} pre-cached TTS audio snippets into memory.")

        standard_phrases = [
            ("ta", "வணக்கம்! நான் உங்கள் சட்ட அளவியல் AI குரல் வழிகாட்டி. இந்த பொட்டலப் பொருள் தொடர்பான விதிமுறைகள், MRP விலை, காலாவதி தேதி, தயாரிப்பாளர் விவரங்கள் அல்லது நுகர்வோர் உரிமை குறித்து எதையும் கேட்கலாம்."),
            ("ta", "வணக்கம்! நான் உங்கள் சட்ட அளவியல் AI குரல் வழிகாட்டி."),
            ("ta", "இந்த பொட்டலப் பொருள் சட்ட அளவியல் விதிகள் 2011-ன் படி முழுமையாக இணங்குகிறது."),
            ("ta", "அறிவிக்கப்பட்ட அதிகபட்ச சில்லறை விலை லேபிளில் குறிப்பிடப்பட்டுள்ளது. இது அனைத்து வரிகளையும் உள்ளடக்கியது."),
            ("ta", "அதிகபட்ச சில்லறை விலைக்கு மேல் கூடுதல் கட்டணம் வசூலித்தால் தேசிய நுகர்வோர் உதவி எண் 1915-ல் புகார் செய்யலாம்."),
            ("hi", "नमस्ते! मैं आपका विधिक मापविज्ञान AI वॉइस असिस्टेंट हूँ। इस डिब्बाबंद वस्तु के विधिक नियमों, MRP, निर्माण/एक्सपायरी तारीख, या उपभोक्ता अधिकारों के बारे में कुछ भी पूछें।"),
            ("en", "Hello! I am your Legal Metrology AI Voice Assistant. Ask me anything about statutory rules, declared MRP, expiry intelligence, packaging damage, or consumer rights."),
        ]

        from gtts import gTTS
        for lang_code, phrase in standard_phrases:
            cache_key = hashlib.md5(f"{lang_code}:{phrase}".encode("utf-8")).hexdigest()
            cache_file = _TTS_CACHE_DIR / f"{lang_code}_{cache_key}.mp3"
            if cache_key in _TTS_MEMORY_CACHE and cache_file.exists():
                continue
            if cache_file.exists():
                _TTS_MEMORY_CACHE[cache_key] = cache_file.read_bytes()
                continue
            try:
                tts = gTTS(text=phrase, lang=lang_code, slow=False)
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                data = fp.read()
                _TTS_MEMORY_CACHE[cache_key] = data
                cache_file.write_bytes(data)
                logger.info(f"Pre-cached TTS for lang={lang_code}")
            except Exception as e:
                logger.debug(f"TTS warm-up for phrase failed: {e}")
    except Exception as exc:
        logger.warning(f"TTS cache warm-up failed (non-fatal): {exc}")


