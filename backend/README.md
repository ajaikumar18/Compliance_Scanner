# Compliance Scanner – Backend

FastAPI + SQLAlchemy async backend for AI-powered product label compliance scanning.

## Tech Stack
| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.115 |
| ASGI Server | Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| DB Driver | asyncpg |
| Migrations | Alembic |
| Database | PostgreSQL 15 (Docker) |
| Config | pydantic-settings |

## Project Structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app, lifespan, router registration
│   ├── core/
│   │   ├── config.py      # Settings (reads .env)
│   │   └── database.py    # Async engine, session, Base, get_db()
│   ├── models/
│   │   ├── user.py        # User (id, username, hashed_password, role)
│   │   ├── product.py     # Product (id, name, category, scanned_image_url)
│   │   ├── scan.py        # Scan (id, product_id, scan_type, status, ...)
│   │   ├── violation.py   # Violation (id, scan_id, field_name, type, severity)
│   │   └── inspection_history.py  # InspectionHistory
│   ├── schemas/           # Pydantic request/response schemas
│   ├── routers/
│   │   └── health.py      # GET /health
│   └── services/          # Business logic (to be implemented)
├── alembic/               # Migration scripts
│   ├── env.py             # Async Alembic environment
│   └── versions/          # Generated migration files
├── alembic.ini
└── requirements.txt
```

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- venv at `../venv/`

### 2. Start PostgreSQL
```powershell
# From workspace root (e:\compliance-scanner)
docker compose up -d postgres
```
> ⚠️ Docker Postgres maps to **port 5433** (avoids conflict with any local PG on 5432).

### 3. Install dependencies
```powershell
e:\compliance-scanner\venv\Scripts\pip.exe install -r requirements.txt
```

### 4. Configure environment
Ensure `.env` at workspace root contains:
```env
DATABASE_URL=postgresql://admin:Anchal%4018@localhost:5433/compliance_db
```
> Note: `@` in the password must be URL-encoded as `%40`.

### 5. Run Alembic migrations
```powershell
# From backend/ directory
e:\compliance-scanner\venv\Scripts\python.exe -m alembic upgrade head
```

### 6. Start the API server
```powershell
# From backend/ directory
e:\compliance-scanner\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 7. Verify
- **Health check**: `GET http://localhost:8000/health`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Database Schema

```
users ──────────────────────────────────────────────┐
  id, username, hashed_password, role (enum)        │ InspectionHistory
                                                     │   user_id → users.id
products ──────┐                                     │   scan_id → scans.id
  id, name,   │                                     │
  category,   │ scans ─────────────────────────────┘
  scanned_     │   id, product_id, scan_type (enum),
  image_url   │   raw_image_url, processed_at, status
               │
               └──────── violations
                            id, scan_id, field_name,
                            violation_type (enum),
                            severity (enum), details
```

## Generating a new migration
```powershell
# After modifying a model:
e:\compliance-scanner\venv\Scripts\python.exe -m alembic revision --autogenerate -m "description"
e:\compliance-scanner\venv\Scripts\python.exe -m alembic upgrade head
```
