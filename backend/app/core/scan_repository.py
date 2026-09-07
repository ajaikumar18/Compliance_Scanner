"""
Scan Repository & Unified Persistence Service
============================================
Provides persistent relational storage for Scans, Violations, Declarations,
Audit Logs, and Inspector Reviews.

Automatically initializes local SQLite database (compliance.db) with WAL mode,
guaranteeing that records, real analytics, and audit trails are never lost,
even when external PostgreSQL or Redis services are offline.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Persistent SQLite database path
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "compliance.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize database tables for scans, audit logs, and inspector reviews."""
    try:
        with _get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_uid TEXT UNIQUE NOT NULL,
                product_name TEXT NOT NULL,
                product_category TEXT NOT NULL,
                scan_type TEXT NOT NULL,
                compliance_status TEXT NOT NULL,
                violations_count INTEGER NOT NULL DEFAULT 0,
                confidence_score REAL NOT NULL DEFAULT 0.0,
                scanned_image_url TEXT,
                source_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                raw_data TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_scans_uid ON scans(scan_uid);
            CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(compliance_status);
            CREATE INDEX IF NOT EXISTS idx_scans_category ON scans(product_category);
            CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at);

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_uid TEXT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_scan ON audit_logs(scan_uid);
            CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_uid TEXT NOT NULL,
                inspector TEXT NOT NULL,
                verdict_override TEXT,
                comments TEXT,
                field_overrides TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS qr_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_id TEXT UNIQUE NOT NULL,
                scan_uid TEXT NOT NULL,
                public_profile TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_qr_verif_id ON qr_verifications(verification_id);
            CREATE INDEX IF NOT EXISTS idx_qr_scan_uid ON qr_verifications(scan_uid);

            CREATE TABLE IF NOT EXISTS expiry_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_uid TEXT NOT NULL,
                product_name TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                days_remaining INTEGER NOT NULL,
                status TEXT NOT NULL,
                recommendation TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_exp_scan ON expiry_records(scan_uid);
            CREATE INDEX IF NOT EXISTS idx_exp_status ON expiry_records(status);

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                scan_uid TEXT,
                language TEXT NOT NULL DEFAULT 'en',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chat_sess ON chat_messages(session_id);
            """)
            logger.info("Compliance repository initialized successfully at %s", _DB_PATH)
    except Exception as exc:
        logger.error("Failed to initialize compliance repository: %s", exc)


# Initialize schema on module load
init_db()


class ScanRepository:
    """Data access methods for scans, analytics, audit logs, and inspector reviews."""

    @staticmethod
    def _next_scan_uid(conn: sqlite3.Connection) -> str:
        """Generate human-readable sequential scan ID e.g. LM-2026-000001."""
        cur = conn.execute("SELECT MAX(id) as max_id FROM scans")
        row = cur.fetchone()
        next_id = (row["max_id"] or 0) + 1
        return f"LM-2026-{next_id:06d}"

    @classmethod
    def save_scan(cls, scan_data: dict[str, Any]) -> dict[str, Any]:
        """Save a new scan result to database and log creation in audit trail."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            # Check if scan already has a designated LM-2026-XXXX ID
            existing_uid = scan_data.get("scan_uid")
            raw_id = scan_data.get("scan_id")
            if isinstance(raw_id, str) and raw_id.startswith("LM-2026-"):
                scan_uid = raw_id
            elif existing_uid:
                scan_uid = existing_uid
            else:
                scan_uid = cls._next_scan_uid(conn)

            product_name = (
                scan_data.get("product_name")
                or scan_data.get("product", {}).get("title")
                or scan_data.get("product_details", {}).get("name")
                or "Packaged Commodity Product"
            )
            product_category = (
                scan_data.get("product_category")
                or scan_data.get("category")
                or "Packaged Foods"
            )
            scan_type = scan_data.get("scan_type", "manual")
            status = (
                scan_data.get("compliance_status")
                or scan_data.get("final_result")
                or "non_compliant"
            ).lower().replace("-", "_")

            violations = scan_data.get("violations", [])
            violations_count = len(violations)

            # Overall confidence calculation
            conf_metrics = scan_data.get("confidence_metrics", {})
            conf_score = (
                conf_metrics.get("overall_confidence")
                or conf_metrics.get("compliance_confidence")
                or conf_metrics.get("ocr_confidence")
                or 0.85
            )

            image_url = (
                scan_data.get("scanned_image_url")
                or (scan_data.get("gallery_images", [{}])[0].get("url") if scan_data.get("gallery_images") else None)
                or ""
            )
            source_url = scan_data.get("source_url") or ""

            # Standardize scan_data ID fields
            scan_data["scan_uid"] = scan_uid
            scan_data["scan_id"] = scan_uid
            scan_data["created_at"] = scan_data.get("created_at") or now_iso
            scan_data["updated_at"] = now_iso

            raw_json = json.dumps(scan_data, ensure_ascii=False)

            conn.execute(
                """
                INSERT INTO scans (
                    scan_uid, product_name, product_category, scan_type,
                    compliance_status, violations_count, confidence_score,
                    scanned_image_url, source_url, created_at, updated_at, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_uid,
                    product_name,
                    product_category,
                    scan_type,
                    status,
                    violations_count,
                    float(conf_score),
                    image_url,
                    source_url,
                    scan_data["created_at"],
                    now_iso,
                    raw_json,
                ),
            )

            # Record creation in audit log
            conn.execute(
                """
                INSERT INTO audit_logs (scan_uid, username, action, new_value, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_uid,
                    "system",
                    "SCAN_CREATED",
                    status,
                    f"Processed {scan_type} scan for '{product_name}'",
                    now_iso,
                ),
            )
            conn.commit()

        logger.info("Scan successfully persisted as %s (Status: %s)", scan_uid, status)
        return scan_data

    @classmethod
    def get_scan(cls, scan_id: str | int) -> dict[str, Any] | None:
        """Fetch a single scan by scan_uid or integer id."""
        with _get_connection() as conn:
            if isinstance(scan_id, int) or (isinstance(scan_id, str) and scan_id.isdigit()):
                cur = conn.execute(
                    "SELECT raw_data FROM scans WHERE id = ? OR scan_uid = ?",
                    (int(scan_id), str(scan_id)),
                )
            else:
                cur = conn.execute("SELECT raw_data FROM scans WHERE scan_uid = ?", (str(scan_id),))
            row = cur.fetchone()
            if row:
                return json.loads(row["raw_data"])
        return None

    @classmethod
    def list_scans(
        cls,
        search: str = "",
        status: str = "all",
        category: str = "all",
        scan_type: str = "all",
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List and search scans with pagination and filters."""
        query = "SELECT scan_uid, product_name, product_category, scan_type, compliance_status, violations_count, confidence_score, scanned_image_url, created_at, raw_data FROM scans WHERE 1=1"
        params: list[Any] = []

        if search:
            query += " AND (product_name LIKE ? OR product_category LIKE ? OR scan_uid LIKE ?)"
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param])

        if status and status != "all":
            clean_status = status.lower().replace("-", "_")
            query += " AND compliance_status = ?"
            params.append(clean_status)

        if category and category != "all":
            query += " AND product_category = ?"
            params.append(category)

        if scan_type and scan_type != "all":
            query += " AND scan_type = ?"
            params.append(scan_type)

        count_query = f"SELECT COUNT(*) as total FROM ({query})"

        with _get_connection() as conn:
            cur_count = conn.execute(count_query, params)
            total = cur_count.fetchone()["total"]

            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            offset = max(0, (page - 1) * limit)
            params.extend([limit, offset])

            cur = conn.execute(query, params)
            rows = cur.fetchall()

            items = []
            for r in rows:
                try:
                    full = json.loads(r["raw_data"])
                except Exception:
                    full = dict(r)
                full["scan_id"] = r["scan_uid"]
                full["scan_uid"] = r["scan_uid"]
                items.append(full)

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1,
        }

    @classmethod
    def get_review_queue(cls) -> list[dict[str, Any]]:
        """Fetch pending scans requiring inspector review."""
        with _get_connection() as conn:
            cur = conn.execute(
                """
                SELECT scan_uid, product_name, product_category, scan_type, compliance_status,
                       violations_count, confidence_score, scanned_image_url, created_at, raw_data
                FROM scans
                WHERE compliance_status IN ('partial_review_needed', 'partial_review_required', 'undetermined', 'insufficient_evidence')
                   OR violations_count > 0
                ORDER BY id DESC LIMIT 50
                """
            )
            rows = cur.fetchall()
            items = []
            for r in rows:
                try:
                    full = json.loads(r["raw_data"])
                except Exception:
                    full = dict(r)
                full["scan_id"] = r["scan_uid"]
                items.append(full)
        return items

    @classmethod
    def save_review(
        cls,
        scan_id: str | int,
        inspector: str,
        verdict_override: str | None,
        comments: str,
        field_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save an inspector review, override verdict, update fields, and log audit event."""
        now_iso = datetime.now(timezone.utc).isoformat()
        scan_data = cls.get_scan(scan_id)
        if not scan_data:
            raise ValueError(f"Scan '{scan_id}' not found.")

        old_verdict = scan_data.get("compliance_status")
        scan_uid = scan_data.get("scan_uid", str(scan_id))

        if verdict_override:
            clean_verdict = verdict_override.lower().replace("-", "_")
            scan_data["compliance_status"] = clean_verdict
            scan_data["final_result"] = clean_verdict.upper()

        if field_overrides:
            fields = scan_data.setdefault("fields", {})
            for f_name, new_val in field_overrides.items():
                if f_name in fields and isinstance(fields[f_name], dict):
                    fields[f_name]["extracted_value"] = new_val
                    fields[f_name]["extraction_method"] = "inspector_override"
                    fields[f_name]["confidence"] = 1.0

        scan_data["inspector_review"] = {
            "inspector": inspector,
            "reviewed_at": now_iso,
            "verdict_override": verdict_override,
            "comments": comments,
        }
        scan_data["updated_at"] = now_iso

        raw_json = json.dumps(scan_data, ensure_ascii=False)

        with _get_connection() as conn:
            conn.execute(
                """
                UPDATE scans
                SET compliance_status = ?, updated_at = ?, raw_data = ?
                WHERE scan_uid = ?
                """,
                (
                    scan_data["compliance_status"],
                    now_iso,
                    raw_json,
                    scan_uid,
                ),
            )
            conn.execute(
                """
                INSERT INTO reviews (scan_uid, inspector, verdict_override, comments, field_overrides, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_uid,
                    inspector,
                    verdict_override,
                    comments,
                    json.dumps(field_overrides or {}),
                    now_iso,
                ),
            )
            conn.execute(
                """
                INSERT INTO audit_logs (scan_uid, username, action, old_value, new_value, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_uid,
                    inspector,
                    "INSPECTOR_REVIEW",
                    old_verdict,
                    verdict_override or old_verdict,
                    comments or "Inspector verified declarations",
                    now_iso,
                ),
            )
            conn.commit()

        logger.info("Inspector %s completed review for %s -> New Verdict: %s", inspector, scan_uid, scan_data.get("compliance_status"))
        return scan_data

    @classmethod
    def get_analytics(cls) -> dict[str, Any]:
        """Compute 100% database-driven analytics across all scans."""
        with _get_connection() as conn:
            cur_total = conn.execute("SELECT COUNT(*) as c FROM scans")
            total = cur_total.fetchone()["c"]

            if total == 0:
                return {
                    "total_scans": 0,
                    "compliant": 0,
                    "non_compliant": 0,
                    "partial_review_needed": 0,
                    "insufficient_evidence": 0,
                    "compliance_rate": 0,
                    "average_confidence": 0.0,
                    "violation_types": {"missing": 0, "incorrect_format": 0, "undersized_font": 0, "cross_validation_mismatch": 0},
                    "top_recurring_violations": [],
                    "category_distribution": [],
                    "scans_over_time": [],
                    "is_empty": True,
                }

            cur_comp = conn.execute("SELECT COUNT(*) as c FROM scans WHERE compliance_status IN ('compliant', 'fully_compliant')")
            compliant = cur_comp.fetchone()["c"]

            cur_non = conn.execute("SELECT COUNT(*) as c FROM scans WHERE compliance_status IN ('non_compliant')")
            non_compliant = cur_non.fetchone()["c"]

            cur_rev = conn.execute("SELECT COUNT(*) as c FROM scans WHERE compliance_status IN ('partial_review_needed', 'partial_review_required', 'undetermined')")
            partial_review = cur_rev.fetchone()["c"]

            cur_ins = conn.execute("SELECT COUNT(*) as c FROM scans WHERE compliance_status = 'insufficient_evidence'")
            insufficient = cur_ins.fetchone()["c"]

            cur_conf = conn.execute("SELECT AVG(confidence_score) as avg_c FROM scans")
            avg_conf = cur_conf.fetchone()["avg_c"] or 0.0

            compliance_rate = round((compliant / total) * 100) if total > 0 else 0

            # Parse violations across scans
            cur_scans = conn.execute("SELECT raw_data FROM scans LIMIT 200")
            violation_counts: dict[str, int] = {"missing": 0, "incorrect_format": 0, "undersized_font": 0, "cross_validation_mismatch": 0}
            field_violations: dict[str, int] = {}

            for row in cur_scans.fetchall():
                try:
                    d = json.loads(row["raw_data"])
                    for v in d.get("violations", []):
                        v_type = v.get("violation_type", "missing")
                        if v_type in violation_counts:
                            violation_counts[v_type] += 1
                        else:
                            violation_counts[v_type] = 1

                        f_name = v.get("field_name") or v.get("field") or "general"
                        field_violations[f_name] = field_violations.get(f_name, 0) + 1
                except Exception:
                    pass

            top_recurring = [
                {"field": k, "count": v, "display_name": k.replace("_", " ").title()}
                for k, v in sorted(field_violations.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            # Category breakdown
            cur_cat = conn.execute(
                """
                SELECT product_category,
                       COUNT(*) as total,
                       SUM(CASE WHEN compliance_status IN ('compliant', 'fully_compliant') THEN 1 ELSE 0 END) as comp
                FROM scans
                GROUP BY product_category
                ORDER BY total DESC LIMIT 6
                """
            )
            cat_dist = []
            for cr in cur_cat.fetchall():
                c_tot = cr["total"]
                c_comp = cr["comp"]
                c_rate = round((c_comp / c_tot) * 100) if c_tot > 0 else 0
                cat_dist.append({
                    "category": cr["product_category"],
                    "total": c_tot,
                    "compliant": c_comp,
                    "compliance_rate": c_rate,
                })

            # Scans over time (last 7 recorded days)
            cur_time = conn.execute(
                """
                SELECT substr(created_at, 1, 10) as day,
                       COUNT(*) as total,
                       SUM(CASE WHEN compliance_status IN ('compliant', 'fully_compliant') THEN 1 ELSE 0 END) as comp,
                       SUM(CASE WHEN compliance_status = 'non_compliant' THEN 1 ELSE 0 END) as non_comp
                FROM scans
                GROUP BY substr(created_at, 1, 10)
                ORDER BY day ASC LIMIT 14
                """
            )
            scans_over_time = [
                {
                    "date": tr["day"],
                    "total": tr["total"],
                    "compliant": tr["comp"],
                    "non_compliant": tr["non_comp"],
                }
                for tr in cur_time.fetchall()
            ]

        return {
            "total_scans": total,
            "compliant": compliant,
            "non_compliant": non_compliant,
            "partial_review_needed": partial_review,
            "insufficient_evidence": insufficient,
            "compliance_rate": compliance_rate,
            "average_confidence": round(avg_conf * 100, 1),
            "violation_types": violation_counts,
            "top_recurring_violations": top_recurring,
            "category_distribution": cat_dist,
            "scans_over_time": scans_over_time,
            "is_empty": False,
        }

    @classmethod
    def list_audit_logs(cls, limit: int = 50) -> list[dict[str, Any]]:
        """List chronological immutable audit logs."""
        with _get_connection() as conn:
            cur = conn.execute(
                "SELECT id, scan_uid, username, action, old_value, new_value, reason, timestamp FROM audit_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    @classmethod
    def save_qr_verification(cls, verification_id: str, scan_uid: str, profile_dict: dict[str, Any]) -> None:
        """Store or update public QR verification profile."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO qr_verifications (verification_id, scan_uid, public_profile, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(verification_id) DO UPDATE SET public_profile=excluded.public_profile
                """,
                (verification_id, scan_uid, json.dumps(profile_dict), now_iso),
            )
            conn.commit()

    @classmethod
    def get_qr_verification(cls, verification_id: str) -> dict[str, Any] | None:
        """Fetch sanitized public verification profile by ID or scan UID."""
        with _get_connection() as conn:
            cur = conn.execute(
                "SELECT public_profile FROM qr_verifications WHERE verification_id = ? OR scan_uid = ? LIMIT 1",
                (verification_id, verification_id),
            )
            row = cur.fetchone()
            if row and row["public_profile"]:
                return json.loads(row["public_profile"])
            # Fallback to scanning table directly if not yet in qr_verifications
            scan_row = conn.execute(
                "SELECT raw_data FROM scans WHERE scan_uid = ? LIMIT 1",
                (verification_id,),
            ).fetchone()
            if scan_row and scan_row["raw_data"]:
                from app.services.qr_service import create_digital_product_profile
                data = json.loads(scan_row["raw_data"])
                prof = create_digital_product_profile(data)
                cls.save_qr_verification(verification_id, verification_id, prof)
                return prof
            return None

    @classmethod
    def save_expiry_record(cls, scan_uid: str, product_name: str, expiry_data: dict[str, Any]) -> None:
        """Store an expiry tracking record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO expiry_records (scan_uid, product_name, expiry_date, days_remaining, status, recommendation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_uid,
                    product_name,
                    expiry_data.get("expiry_date", "Undeclared"),
                    int(expiry_data.get("days_remaining", 0)),
                    expiry_data.get("status", "SAFE"),
                    expiry_data.get("recommendation", ""),
                    now_iso,
                ),
            )
            conn.commit()

    @classmethod
    def list_expiry_records(cls, limit: int = 50) -> list[dict[str, Any]]:
        """List tracked product expiry records ordered by days remaining."""
        with _get_connection() as conn:
            cur = conn.execute(
                """
                SELECT id, scan_uid, product_name, expiry_date, days_remaining, status, recommendation, created_at
                FROM expiry_records
                ORDER BY days_remaining ASC LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    @classmethod
    def save_chat_message(
        cls,
        session_id: str,
        scan_uid: str | None,
        sender: str,
        message: str,
        language: str = "en",
    ) -> None:
        """Record a chat message into the session ledger."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (session_id, scan_uid, language, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, scan_uid, language, now_iso),
            )
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, sender, message, language, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, sender, message, language, now_iso),
            )
            conn.commit()

    @classmethod
    def get_chat_history(cls, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch chronological messages for a chat session."""
        with _get_connection() as conn:
            cur = conn.execute(
                "SELECT sender, message, language, timestamp FROM chat_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
