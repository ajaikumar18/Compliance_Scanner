# 🚀 ComplianceScanner AI – Software Architecture & Deployment Documentation

> **Official Technical Documentation & Deployment Framework**  
> Comprehensive guide describing the multi-tier containerized software architecture, system component interactions, environment configuration, and Docker Compose orchestration for evaluators and judges.

---

## 🏛️ System Architecture Overview

`ComplianceScanner AI` is an automated, AI-powered Legal Metrology (Packaged Commodities) Rules 2011 compliance inspection platform. It processes product label images through OpenCV computer vision, dual-engine OCR, GenAI Vision fallbacks, scale calibration, and Legal Metrology rule validation.

```mermaid
graph TD
    subgraph Client Layer
        A[React Dashboard\n(Nginx :3000)] -->|HTTP / API| C[FastAPI Backend\n(:8000)]
        B[Flutter Mobile App\n(Camera & Offline Queue)] -->|REST API| C
    end

    subgraph API & Microservices Layer
        C --> D[OpenCV Preprocessing\nDeskew & CLAHE]
        D --> E[Dual OCR Engine\nTesseract + EasyOCR]
        E --> F[Regex & Keyword\nField Classifier]
        F -->|Low Confidence / Unmatched| G[Gemini Vision GenAI\nFallback Service]
        G --> H[OpenCV Scale Calibration\n& Font Analyzer]
        H --> I[Legal Metrology\nRule Engine]
    end

    subgraph Data & Async Queue Layer
        C -->|ORM Queries| J[(PostgreSQL DB\n:5433 / :5432)]
        C -->|Enqueue URL Scans| K[Redis Broker\n:6379]
        K --> L[Celery Task Worker]
        L -->|Batch Processing| C
        C -->|Blob Storage| M[(MinIO Object Storage\n:9000)]
    end
```

---

## 🧩 Component Architecture Breakdown

| Component | Technology Stack | Primary Responsibility |
| :--- | :--- | :--- |
| **FastAPI Backend Server** | Python 3.11, FastAPI, Pydantic, SQLAlchemy, AsyncPG | REST API entrypoint, lifecycle management, CORS, and endpoint routing. |
| **Preprocessing Module** | OpenCV, NumPy | Hough transform text deskew, quad perspective warp, CLAHE contrast & glare suppression. |
| **Dual OCR Engine** | Tesseract OCR 5.0, EasyOCR | Dual-engine text extraction with IoU bounding box merging and confidence arbitration. |
| **Field Classifier** | Regex, Keyword Pattern Matcher | Classifies text into 6 mandatory declarations (MRP, Net Qty, Mfg Date, Mfr Address, Care, Country). |
| **GenAI Vision Extraction** | Google Gemini Vision API / Groq Vision | Vision LLM fallback targeting cropped image regions for low-confidence or unclassified fields. |
| **Font Size Analyzer** | OpenCV Hough Circles | Measures text height in real-world millimeters using coin reference markers or package dimensions. |
| **Legal Metrology Rule Engine**| Rule JSON Config | Evaluates presence (`missing`), format validity (`incorrect_format`), and font height (`undersized_font`). |
| **Asynchronous Task Queue** | Celery 5.4, Redis 7 | Background async batch processing and live task progress polling (`45/100 processed`). |
| **E-Commerce Scraper** | Scrapy 2.11 | Multi-platform category scraper for Amazon, Flipkart, and BigBasket with image staging. |
| **Web Dashboard** | React 18, TypeScript, TailwindCSS, Recharts, Nginx | Sleek inspector dashboard with bounding box overlays, statistics charts, and report generation. |
| **Mobile Application** | Flutter 3.35, Dart | Field inspector mobile app with in-app camera, continuous store aisle capture, and offline queue. |
| **Database & Object Storage** | PostgreSQL 15, MinIO (S3 Compatible) | Relational persistence for Products, Scans, and Violations + object storage for raw images & reports. |

---

## 🔐 Environment Variables Matrix

Create a `.env` file in the project root directory or supply environment variables via Docker Compose:

| Variable Name | Description | Default / Example Value | Required? |
| :--- | :--- | :--- | :---: |
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://admin:Anchal%4018@postgres:5432/compliance_db` | Yes |
| `REDIS_URL` | Redis broker and result backend URL | `redis://redis:6379/0` | Yes |
| `GEMINI_API_KEY` | Google Gemini Vision API key | `AIzaSy...` | Optional |
| `GROQ_API_KEY` | Groq Vision API key fallback | `gsk_...` | Optional |
| `MINIO_ENDPOINT` | MinIO server address | `minio:9000` | Yes |
| `MINIO_ACCESS_KEY` | MinIO root access key | `minioadmin` | Yes |
| `MINIO_SECRET_KEY` | MinIO root secret password | `minioadminpassword` | Yes |
| `JWT_SECRET_KEY` | Secret key for signing JWT tokens | `compliance-scanner-super-secret-jwt-key-2026` | Yes |

---

## 🐳 Quickstart & Deployment Guide (Docker Compose)

### 1. Prerequisites
Ensure the following tools are installed on your host system:
- **Docker Engine** v24.0+
- **Docker Compose** v2.20+

### 2. Build and Launch Container Stack
Run the following command from the workspace root directory:

```bash
docker-compose up -d --build
```

This starts all 6 orchestrating services in background detached mode:
- `compliance-postgres` (PostgreSQL 15 on port `5433`)
- `compliance-redis` (Redis 7 on port `6379`)
- `compliance-minio` (MinIO Storage on ports `9000` & `9001`)
- `compliance-backend` (FastAPI Server on port `8000`)
- `compliance-celery-worker` (Background Async Worker)
- `compliance-frontend` (React Dashboard on port `3000`)

### 3. Apply Database Migrations (Alembic)
To initialize or update the PostgreSQL database schema:

```bash
docker-compose exec backend alembic upgrade head
```

---

## 🩺 Health Verification & Access Endpoints

Once the stack is running, access the services via the following URLs:

| Service / Interface | URL Access Point | Health Verification Check |
| :--- | :--- | :--- |
| **React Web Dashboard** | `http://localhost:3000` | Open in browser, sign in with Inspector Demo |
| **FastAPI Swagger API Docs** | `http://localhost:8000/docs` | Interactive OpenAPI documentation |
| **Backend Health Endpoint** | `http://localhost:8000/health` | Returns `{"status": "healthy", "database": "connected"}` |
| **MinIO Storage Console** | `http://localhost:9001` | Sign in with `minioadmin` / `minioadminpassword` |
| **PostgreSQL Database** | `localhost:5433` | Connect via psql (`admin` / `Anchal@18` / `compliance_db`) |

---

## 🧪 Automated Testing & Verification Commands

To execute the backend pytest test suite (unit tests, integration tests, and 150+ image accuracy benchmarks):

```bash
# Run unit & integration test suite (211 passing tests)
docker-compose exec backend pytest tests/ -v --ignore=tests/test_full_pipeline_benchmark.py

# Run 150+ image accuracy & pitch deck benchmark evaluation
docker-compose exec backend pytest tests/test_full_pipeline_benchmark.py -v
```
