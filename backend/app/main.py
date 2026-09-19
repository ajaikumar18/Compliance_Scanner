"""
FastAPI application entry point.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.core.database import engine
from app.routers import auth, health, intelligence, ledger, reports, scans, tickets


# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("🚀  Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    # Verify DB connection on startup
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("✅  Database connection verified")
    except Exception as exc:
        logger.error("❌  Database connection failed: %s", exc)


    # ── Pre-warm PaddleOCR GPU engine in background ───────────────────────────
    # Loads CUDA models into VRAM at startup so the FIRST scan request
    # is not penalised by the 25-30s cold initialization delay.
    async def _warmup_paddle():
        try:
            from app.services.field_classifier import LaptopLayoutClassifier
            logger.info("🔥  Pre-warming PaddleOCR GPU engine in background...")
            await asyncio.to_thread(LaptopLayoutClassifier.get_paddle_engine)
            logger.info("✅  PaddleOCR GPU engine warm and ready in VRAM.")
        except Exception as exc:
            logger.warning("⚠️  PaddleOCR warm-up failed (non-fatal): %s", exc)

    asyncio.create_task(_warmup_paddle())

    # ── Pre-warm Multilingual TTS Cache in background ────────────────────────
    async def _warmup_tts():
        try:
            from app.routers.intelligence import warmup_tts_cache
            await asyncio.to_thread(warmup_tts_cache)
        except Exception as exc:
            logger.warning("⚠️  TTS warm-up failed (non-fatal): %s", exc)

    asyncio.create_task(_warmup_tts())

    yield  # ← app is running

    logger.info("🛑  Shutting down %s", settings.APP_NAME)
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered compliance scanning platform for product label analysis. "
        "Detects missing fields, format violations, and undersized fonts."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── GZip ──────────────────────────────────────────────────────────────────────
# Compress responses larger than 1 KB — scan payloads with base64 QR images
# can be 20-100 KB; GZip reduces transfer size by ~70%.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(intelligence.router)
app.include_router(ledger.router)
app.include_router(reports.router)
app.include_router(scans.router)
app.include_router(tickets.router)



# ── Root redirect ─────────────────────────────────────────────────────────────
_startup_time: str = datetime.now(timezone.utc).isoformat()

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}. Visit /docs for the API reference.",
        "version": settings.APP_VERSION,
        "startup_time": _startup_time,
    }
