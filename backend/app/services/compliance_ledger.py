"""
Compliance Ledger Service
=========================
Aggregates scan verdicts and evidence by GTIN (and batch code where available).
Computes a rolling confidence score weighted higher for AR-verified and verified-inspector
scans than for anonymous/uncalibrated public scans, and determines aggregate consensus verdicts
('compliant', 'non_compliant', 'disputed').
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compliance_ledger import ComplianceLedger
from app.models.re_inspection_ticket import (
    ConflictType,
    ReInspectionTicket,
    TicketPriority,
    TicketStatus,
)
from app.models.scan import Scan, ScanStatus

logger = logging.getLogger(__name__)

# Calibration Tier Quality Weights (higher physical precision = higher trust weight)
CALIBRATION_TIER_WEIGHTS: dict[str, float] = {
    "ar_verified": 2.0,        # On-device WebXR / LiDAR / AR hit-test distance (+/-0.1mm)
    "reference_object": 1.4,   # Hough Circle reference coin/card detection (+/-0.2mm)
    "package_dimension": 1.1,  # User-supplied package millimeter dimension (+/-0.3mm)
    "dpi_estimated": 0.7,      # Default uncalibrated 300 DPI fallback (+/-0.5mm)
}

# User Authority Weights
USER_ROLE_WEIGHTS: dict[str, float] = {
    "inspector": 1.6,          # Official regulatory inspector audit
    "admin": 1.6,              # System / Lead compliance administrator
    "viewer": 0.9,             # Authenticated read/viewer scan
    "anonymous": 0.8,          # Public unauthenticated submission
}


# ─────────────────────────────────────────────────────────────────────────────
# Conflict Threshold Configuration & Result Types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConflictThresholdConfig:
    """Configurable thresholds for detecting discrepancies and spawning re-inspection tickets."""
    confidence_drop_threshold: float = 0.20  # Trigger if confidence drops by >= 20%
    ar_tier_escalation_enabled: bool = True  # Trigger CRITICAL when AR/Ref contradicts DPI
    verdict_flip_enabled: bool = True        # Trigger when aggregate verdict flips
    consensus_disputed_enabled: bool = True  # Trigger when verdict enters disputed state
    min_scans_for_conflict: int = 1          # Must have at least 1 prior scan to conflict

DEFAULT_CONFLICT_CONFIG = ConflictThresholdConfig()


@dataclass
class ConflictEvaluationResult:
    has_conflict: bool
    priority: str  # "critical" | "high" | "medium" | "low"
    conflict_type: str
    discrepancy_reason: str
    prior_tier: str


def evaluate_verdict_conflict(
    prior_verdict: str,
    prior_confidence: float,
    prior_calibration_tier_counts: dict[str, int],
    new_scan_status: str,
    new_calibration_tier: str,
    new_verdict: str,
    new_confidence: float,
    user_role: str = "anonymous",
    config: ConflictThresholdConfig = DEFAULT_CONFLICT_CONFIG,
) -> ConflictEvaluationResult | None:
    """
    Evaluates whether a new scan conflicts with the prior aggregate ledger consensus
    beyond the configured thresholds.
    """
    dominant_prior_tier = "dpi_estimated"
    if prior_calibration_tier_counts:
        dominant_prior_tier = max(prior_calibration_tier_counts.items(), key=lambda x: x[1])[0]

    prior_ar_count = prior_calibration_tier_counts.get("ar_verified", 0)
    prior_ref_count = prior_calibration_tier_counts.get("reference_object", 0)
    prior_dpi_count = prior_calibration_tier_counts.get("dpi_estimated", 0)
    prior_had_no_ar = (prior_ar_count == 0)

    # 1. Sensor Tier Escalation: High-precision sensor contradicts DPI/uncalibrated consensus
    if config.ar_tier_escalation_enabled and new_calibration_tier in ("ar_verified", "reference_object"):
        tier_label = "AR-Verified 3D Depth" if new_calibration_tier == "ar_verified" else "Reference-Object Calibrated"
        if prior_had_no_ar and prior_dpi_count > 0:
            if prior_verdict == "compliant" and new_scan_status == "non_compliant":
                return ConflictEvaluationResult(
                    has_conflict=True,
                    priority="critical",
                    conflict_type="sensor_tier_escalation",
                    discrepancy_reason=(
                        f"CRITICAL DISCREPANCY: High-precision {tier_label} audit flagged product as NON-COMPLIANT, "
                        f"overruling prior DPI-estimated compliant consensus (prior confidence: {prior_confidence:.2f})."
                    ),
                    prior_tier=dominant_prior_tier,
                )
            elif prior_verdict == "non_compliant" and new_scan_status == "compliant":
                return ConflictEvaluationResult(
                    has_conflict=True,
                    priority="high",
                    conflict_type="sensor_tier_escalation",
                    discrepancy_reason=(
                        f"High-precision {tier_label} audit verified product as COMPLIANT, "
                        f"disputing prior DPI-estimated non-compliant flags (prior confidence: {prior_confidence:.2f})."
                    ),
                    prior_tier=dominant_prior_tier,
                )

    # 2. Verdict Inversion / Flip
    if config.verdict_flip_enabled:
        if prior_verdict == "compliant" and (new_scan_status == "non_compliant" or new_verdict == "non_compliant"):
            is_critical = (
                user_role in ("inspector", "admin")
                or new_calibration_tier in ("ar_verified", "reference_object")
                or new_verdict == "non_compliant"
            )
            return ConflictEvaluationResult(
                has_conflict=True,
                priority="critical" if is_critical else "high",
                conflict_type="verdict_inversion",
                discrepancy_reason=(
                    f"VERDICT CONFLICT: Established COMPLIANT product received conflicting NON-COMPLIANT scan "
                    f"by {user_role.upper()} via {new_calibration_tier}. Aggregate status shifted to '{new_verdict}'."
                ),
                prior_tier=dominant_prior_tier,
            )
        elif prior_verdict == "non_compliant" and (new_scan_status == "compliant" or new_verdict == "compliant"):
            return ConflictEvaluationResult(
                has_conflict=True,
                priority="high",
                conflict_type="verdict_inversion",
                discrepancy_reason=(
                    f"VERDICT CONFLICT: Previously FLAGGED product received clean COMPLIANT scan "
                    f"by {user_role.upper()} via {new_calibration_tier}. Aggregate status shifted to '{new_verdict}'."
                ),
                prior_tier=dominant_prior_tier,
            )

    # 3. Consensus Disputed (deadlock)
    if config.consensus_disputed_enabled and new_verdict == "disputed" and prior_verdict != "disputed":
        return ConflictEvaluationResult(
            has_conflict=True,
            priority="high" if new_calibration_tier in ("ar_verified", "reference_object") else "medium",
            conflict_type="consensus_disputed",
            discrepancy_reason=(
                f"CONSENSUS DEADLOCK: Contradictory scan forced product status from '{prior_verdict}' "
                f"into 'disputed' state. Field re-inspection required to resolve evidence divergence."
            ),
            prior_tier=dominant_prior_tier,
        )

    # 4. Confidence Drop
    conf_drop = prior_confidence - new_confidence
    if conf_drop >= config.confidence_drop_threshold and new_scan_status != prior_verdict:
        return ConflictEvaluationResult(
            has_conflict=True,
            priority="high" if conf_drop >= 0.25 else "medium",
            conflict_type="confidence_drop",
            discrepancy_reason=(
                f"CONFIDENCE COLLAPSE: Product rolling confidence dropped by {conf_drop*100:.1f}% "
                f"(from {prior_confidence:.2f} to {new_confidence:.2f}) following contradictory scan."
            ),
            prior_tier=dominant_prior_tier,
        )

    return None


# User Authority Weights
USER_ROLE_WEIGHTS: dict[str, float] = {
    "inspector": 1.6,          # Official regulatory inspector audit
    "admin": 1.6,              # System / Lead compliance administrator
    "viewer": 0.9,             # Authenticated read/viewer scan
    "anonymous": 0.8,          # Public unauthenticated submission
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Rolling Confidence & Verdict Calculation
# ─────────────────────────────────────────────────────────────────────────────

def compute_rolling_verdict_and_confidence(
    evidence_items: list[dict[str, Any]],
) -> tuple[str, float]:
    """
    Compute aggregate consensus verdict ('compliant', 'non_compliant', 'disputed')
    and rolling confidence score (0.10 to 1.00) based on weighted evidence.

    Parameters
    ----------
    evidence_items : list[dict[str, Any]]
        List of scan evidence dictionaries with keys:
        - compliance_status: 'compliant' | 'non_compliant' | 'partial_review_needed'
        - calibration_tier: 'ar_verified' | 'reference_object' | 'package_dimension' | 'dpi_estimated'
        - user_role: 'inspector' | 'admin' | 'viewer' | 'anonymous'
        - confidence: float (0.0 to 1.0)

    Returns
    -------
    tuple[str, float]
        (verdict, rolling_confidence)
    """
    if not evidence_items:
        return "compliant", 1.0

    score_comp = 0.0
    score_non_comp = 0.0
    total_raw_weight = 0.0

    for item in evidence_items:
        tier = str(item.get("calibration_tier", "dpi_estimated")).lower()
        role = str(item.get("user_role", "anonymous")).lower()
        scan_conf = float(item.get("confidence", 0.95))

        w_tier = CALIBRATION_TIER_WEIGHTS.get(tier, CALIBRATION_TIER_WEIGHTS["dpi_estimated"])
        w_role = USER_ROLE_WEIGHTS.get(role, USER_ROLE_WEIGHTS["anonymous"])
        weight = w_tier * w_role
        total_raw_weight += weight

        status = str(item.get("compliance_status", "non_compliant")).lower()
        if status == "compliant":
            score_comp += weight * scan_conf
        else:
            score_non_comp += weight * scan_conf

    total_score = score_comp + score_non_comp
    if total_score <= 0.0:
        return "compliant", 0.50

    comp_ratio = score_comp / total_score
    n = len(evidence_items)

    # Verdict consensus threshold:
    # >= 75% compliant -> compliant
    # <= 25% compliant (>= 75% non-compliant) -> non_compliant
    # 25% < comp_ratio < 75% -> disputed (competing valid evidence)
    if comp_ratio >= 0.75:
        verdict = "compliant"
    elif comp_ratio <= 0.25:
        verdict = "non_compliant"
    else:
        verdict = "disputed"

    # Rolling Confidence Calculation:
    # 1. Consensus sharpness: Distance from 50/50 contention
    consensus_sharpness = abs(comp_ratio - 0.5) * 2.0  # 0.0 (even split) to 1.0 (unanimous)

    # 2. Average scan evidence quality relative to max possible weight (2.0 * 1.6 = 3.2)
    max_single_weight = CALIBRATION_TIER_WEIGHTS["ar_verified"] * USER_ROLE_WEIGHTS["inspector"]
    avg_quality = min(1.0, (total_raw_weight / n) / max_single_weight)

    # 3. Volume saturation factor (more independent audits = higher confidence)
    volume_factor = min(1.0, 0.40 + 0.15 * n)

    if verdict == "disputed":
        # Disputed records have lower confidence due to disagreement, but confidence in the DISPUTE rises with volume
        rolling_conf = 0.40 + 0.30 * avg_quality + 0.20 * volume_factor
    else:
        rolling_conf = (
            0.40 * consensus_sharpness +
            0.35 * avg_quality +
            0.25 * volume_factor
        )

    rolling_conf = max(0.10, min(1.00, round(rolling_conf, 4)))
    return verdict, rolling_conf


# ─────────────────────────────────────────────────────────────────────────────
# 2. Record / Update Scan in Ledger
# ─────────────────────────────────────────────────────────────────────────────

async def record_scan_in_ledger(
    db: AsyncSession,
    scan: Scan,
    gtin: str,
    batch_code: str | None,
    compliance_status: str,
    calibration_tier: str,
    user_role: str | None = None,
    scan_confidence: float = 0.95,
    product_name: str | None = None,
    category: str | None = None,
) -> ComplianceLedger:
    """
    Update or create a ComplianceLedger entry for the specified GTIN.
    Aggregates scan verdicts, calibration breakdown, batch stats, and recalculates
    the rolling confidence and consensus verdict.
    """
    clean_gtin = gtin.strip()
    role = user_role or "anonymous"
    tier = calibration_tier or "dpi_estimated"
    b_code = batch_code.strip() if batch_code else "unspecified"
    now_utc = datetime.now(timezone.utc)

    # 1. Query existing ledger entry
    stmt = select(ComplianceLedger).where(ComplianceLedger.gtin == clean_gtin)
    res = await db.execute(stmt)
    ledger_entry = res.scalars().first()

    is_compliant = compliance_status.lower() == "compliant"

    if not ledger_entry:
        # Initial scan for this GTIN -> Create new entry
        initial_verdict = "compliant" if is_compliant else "non_compliant"
        init_item = [{
            "compliance_status": compliance_status,
            "calibration_tier": tier,
            "user_role": role,
            "confidence": scan_confidence,
        }]
        v, initial_conf = compute_rolling_verdict_and_confidence(init_item)

        initial_batch_breakdown = {
            b_code: {
                "total_scans": 1,
                "compliant_scans": 1 if is_compliant else 0,
                "non_compliant_scans": 0 if is_compliant else 1,
                "ar_verified_count": 1 if tier == "ar_verified" else 0,
                "reference_object_count": 1 if tier == "reference_object" else 0,
                "package_dimension_count": 1 if tier == "package_dimension" else 0,
                "dpi_estimated_count": 1 if tier == "dpi_estimated" else 0,
                "current_verdict": initial_verdict,
                "last_scanned_at": now_utc.isoformat(),
            }
        }

        ledger_entry = ComplianceLedger(
            gtin=clean_gtin,
            product_name=product_name,
            category=category,
            total_scans=1,
            compliant_scans=1 if is_compliant else 0,
            non_compliant_scans=0 if is_compliant else 1,
            ar_verified_count=1 if tier == "ar_verified" else 0,
            reference_object_count=1 if tier == "reference_object" else 0,
            package_dimension_count=1 if tier == "package_dimension" else 0,
            dpi_estimated_count=1 if tier == "dpi_estimated" else 0,
            current_verdict=v,
            rolling_confidence=initial_conf,
            batch_breakdown=initial_batch_breakdown,
            last_scan_id=scan.id,
            last_scanned_at=now_utc,
        )
        db.add(ledger_entry)
        logger.info("Created new ComplianceLedger record for GTIN %s (verdict=%s, conf=%.2f)", clean_gtin, v, initial_conf)
    else:
        # Already-known GTIN -> Capture prior state for conflict evaluation
        prior_verdict = ledger_entry.current_verdict
        prior_conf = ledger_entry.rolling_confidence
        prior_tier_counts = {
            "ar_verified": ledger_entry.ar_verified_count or 0,
            "reference_object": ledger_entry.reference_object_count or 0,
            "package_dimension": ledger_entry.package_dimension_count or 0,
            "dpi_estimated": ledger_entry.dpi_estimated_count or 0,
        }

        # Update existing ledger record
        ledger_entry.total_scans = (ledger_entry.total_scans or 0) + 1
        if is_compliant:
            ledger_entry.compliant_scans = (ledger_entry.compliant_scans or 0) + 1
        else:
            ledger_entry.non_compliant_scans = (ledger_entry.non_compliant_scans or 0) + 1

        if tier == "ar_verified":
            ledger_entry.ar_verified_count = (ledger_entry.ar_verified_count or 0) + 1
        elif tier == "reference_object":
            ledger_entry.reference_object_count = (ledger_entry.reference_object_count or 0) + 1
        elif tier == "package_dimension":
            ledger_entry.package_dimension_count = (ledger_entry.package_dimension_count or 0) + 1
        else:
            ledger_entry.dpi_estimated_count = (ledger_entry.dpi_estimated_count or 0) + 1

        if product_name and (not ledger_entry.product_name or "GTIN-" in ledger_entry.product_name):
            ledger_entry.product_name = product_name
        if category and not ledger_entry.category:
            ledger_entry.category = category

        # Update batch breakdown
        batches = dict(ledger_entry.batch_breakdown or {})
        b_info = batches.get(b_code, {
            "total_scans": 0,
            "compliant_scans": 0,
            "non_compliant_scans": 0,
            "ar_verified_count": 0,
            "reference_object_count": 0,
            "package_dimension_count": 0,
            "dpi_estimated_count": 0,
            "current_verdict": "compliant",
            "last_scanned_at": now_utc.isoformat(),
        })

        b_info["total_scans"] += 1
        if is_compliant:
            b_info["compliant_scans"] += 1
        else:
            b_info["non_compliant_scans"] += 1

        if tier == "ar_verified":
            b_info["ar_verified_count"] += 1
        elif tier == "reference_object":
            b_info["reference_object_count"] += 1
        elif tier == "package_dimension":
            b_info["package_dimension_count"] += 1
        else:
            b_info["dpi_estimated_count"] += 1

        b_comp_ratio = b_info["compliant_scans"] / b_info["total_scans"]
        if b_comp_ratio >= 0.75:
            b_info["current_verdict"] = "compliant"
        elif b_comp_ratio <= 0.25:
            b_info["current_verdict"] = "non_compliant"
        else:
            b_info["current_verdict"] = "disputed"
        b_info["last_scanned_at"] = now_utc.isoformat()
        batches[b_code] = b_info
        ledger_entry.batch_breakdown = batches

        # Query all past scans for this GTIN to recompute rolling confidence & verdict
        history_stmt = (
            select(Scan)
            .where(Scan.gtin == clean_gtin)
            .order_by(Scan.created_at.desc())
            .limit(100)
        )
        h_res = await db.execute(history_stmt)
        past_scans = h_res.scalars().all()

        evidence_list = []
        for s in past_scans:
            # Check if scan had violations
            has_viols = len(s.violations) > 0 if hasattr(s, "violations") and s.violations else False
            s_status = "non_compliant" if has_viols else "compliant"
            evidence_list.append({
                "compliance_status": s_status,
                "calibration_tier": tier if s.id == scan.id else "dpi_estimated",
                "user_role": role,
                "confidence": scan_confidence,
            })

        # Include the current scan in evidence if not yet committed in query
        if not any(e for e in past_scans if e.id == scan.id):
            evidence_list.append({
                "compliance_status": compliance_status,
                "calibration_tier": tier,
                "user_role": role,
                "confidence": scan_confidence,
            })

        new_verdict, new_conf = compute_rolling_verdict_and_confidence(evidence_list)
        ledger_entry.current_verdict = new_verdict
        ledger_entry.rolling_confidence = new_conf
        ledger_entry.last_scan_id = scan.id
        ledger_entry.last_scanned_at = now_utc

        # Discrepancy / conflict detection
        conflict = evaluate_verdict_conflict(
            prior_verdict=prior_verdict,
            prior_confidence=prior_conf,
            prior_calibration_tier_counts=prior_tier_counts,
            new_scan_status="compliant" if is_compliant else "non_compliant",
            new_calibration_tier=tier,
            new_verdict=new_verdict,
            new_confidence=new_conf,
            user_role=role,
        )

        if conflict and conflict.has_conflict:
            ticket = await create_re_inspection_ticket(
                db=db,
                gtin=clean_gtin,
                trigger_scan_id=scan.id,
                prior_verdict=prior_verdict,
                prior_confidence=prior_conf,
                prior_calibration_tier=conflict.prior_tier,
                new_verdict=new_verdict,
                new_confidence=new_conf,
                new_calibration_tier=tier,
                conflict_type=conflict.conflict_type,
                discrepancy_reason=conflict.discrepancy_reason,
                priority=conflict.priority,
                product_name=ledger_entry.product_name or product_name,
                batch_code=b_code if b_code != "unspecified" else None,
            )
            setattr(ledger_entry, "re_inspection_ticket", ticket)

        logger.info(
            "Updated ComplianceLedger for GTIN %s: total=%d, verdict=%s, conf=%.2f (conflict=%s)",
            clean_gtin, ledger_entry.total_scans, new_verdict, new_conf, bool(conflict),
        )

    await db.flush()
    return ledger_entry


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fetch Ledger Details by GTIN
# ─────────────────────────────────────────────────────────────────────────────

async def get_ledger_for_gtin(
    db: AsyncSession,
    gtin: str,
) -> dict[str, Any] | None:
    """
    Fetch the aggregate ledger entry and detailed scan history for a given GTIN.
    """
    clean_gtin = gtin.strip()
    stmt = select(ComplianceLedger).where(ComplianceLedger.gtin == clean_gtin)
    res = await db.execute(stmt)
    entry = res.scalars().first()

    if not entry:
        return None

    # Fetch scan history for this GTIN
    scans_stmt = (
        select(Scan)
        .options(selectinload(Scan.violations))
        .where(Scan.gtin == clean_gtin)
        .order_by(Scan.created_at.desc())
        .limit(50)
    )
    scans_res = await db.execute(scans_stmt)
    scans = scans_res.scalars().all()

    history_items = []
    for s in scans:
        viols = [
            {
                "field_name": v.field_name,
                "violation_type": v.violation_type.value if hasattr(v.violation_type, "value") else str(v.violation_type),
                "severity": v.severity.value if hasattr(v.severity, "value") else str(v.severity),
                "details": v.details or "",
            }
            for v in s.violations
        ]
        comp_status = "compliant" if len(viols) == 0 else "non_compliant"

        history_items.append({
            "scan_id": s.id,
            "scan_type": s.scan_type.value if hasattr(s.scan_type, "value") else str(s.scan_type),
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "compliance_status": comp_status,
            "calibration_tier": "ar_verified" if entry.ar_verified_count > 0 else "dpi_estimated",
            "batch_code": s.batch_code,
            "violations_count": len(viols),
            "violations": viols,
            "created_at": s.created_at.isoformat() if s.created_at else "",
        })

    return {
        "gtin": entry.gtin,
        "product_name": entry.product_name,
        "category": entry.category,
        "total_scans": entry.total_scans,
        "compliant_scans": entry.compliant_scans,
        "non_compliant_scans": entry.non_compliant_scans,
        "current_verdict": entry.current_verdict,
        "rolling_confidence": entry.rolling_confidence,
        "calibration_breakdown": {
            "ar_verified": entry.ar_verified_count,
            "reference_object": entry.reference_object_count,
            "package_dimension": entry.package_dimension_count,
            "dpi_estimated": entry.dpi_estimated_count,
        },
        "batch_breakdown": entry.batch_breakdown or {},
        "last_scanned_at": entry.last_scanned_at,
        "scan_history": history_items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. List Ledger Entries
# ─────────────────────────────────────────────────────────────────────────────

async def list_ledger_entries(
    db: AsyncSession,
    verdict: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ComplianceLedger]:
    """
    Query all compliance ledger records with optional verdict filtering.
    """
    stmt = select(ComplianceLedger).order_by(ComplianceLedger.last_scanned_at.desc())
    if verdict:
        stmt = stmt.where(ComplianceLedger.current_verdict == verdict.lower())
    stmt = stmt.limit(limit).offset(offset)
    res = await db.execute(stmt)
    return list(res.scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# 5. Re-Inspection Ticket Management
# ─────────────────────────────────────────────────────────────────────────────

async def create_re_inspection_ticket(
    db: AsyncSession,
    gtin: str,
    trigger_scan_id: int,
    prior_verdict: str,
    prior_confidence: float,
    prior_calibration_tier: str | None,
    new_verdict: str,
    new_confidence: float,
    new_calibration_tier: str,
    conflict_type: str,
    discrepancy_reason: str,
    priority: str,
    product_name: str | None = None,
    batch_code: str | None = None,
) -> ReInspectionTicket:
    """
    Persist a newly generated re-inspection ticket for enforcement review.
    """
    clean_gtin = gtin.strip()
    now = datetime.now(timezone.utc)
    ts_str = now.strftime("%Y%m%d%H%M%S")
    gtin_suffix = clean_gtin[-6:] if len(clean_gtin) >= 6 else clean_gtin
    ticket_number = f"RIT-{gtin_suffix}-{ts_str}"

    ticket = ReInspectionTicket(
        ticket_number=ticket_number,
        gtin=clean_gtin,
        product_name=product_name,
        batch_code=batch_code,
        trigger_scan_id=trigger_scan_id,
        prior_verdict=prior_verdict,
        prior_confidence=round(prior_confidence, 4),
        prior_calibration_tier=prior_calibration_tier,
        new_verdict=new_verdict,
        new_confidence=round(new_confidence, 4),
        new_calibration_tier=new_calibration_tier,
        conflict_type=conflict_type,
        discrepancy_reason=discrepancy_reason,
        priority=priority,
        status="open",
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    await db.flush()
    logger.warning(
        "Auto-spawned ReInspectionTicket %s for GTIN %s [priority=%s, conflict_type=%s]: %s",
        ticket.ticket_number, clean_gtin, priority, conflict_type, discrepancy_reason,
    )
    return ticket


async def list_re_inspection_tickets(
    db: AsyncSession,
    status: str | None = None,
    priority: str | None = None,
    gtin: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReInspectionTicket]:
    """
    Query re-inspection tickets prioritized by urgency:
    Critical (1) -> High (2) -> Medium (3) -> Low (4), then newest created_at.
    """
    priority_order = case(
        (ReInspectionTicket.priority == "critical", 1),
        (ReInspectionTicket.priority == "high", 2),
        (ReInspectionTicket.priority == "medium", 3),
        (ReInspectionTicket.priority == "low", 4),
        else_=5,
    )
    stmt = (
        select(ReInspectionTicket)
        .options(selectinload(ReInspectionTicket.trigger_scan).selectinload(Scan.violations))
        .order_by(priority_order, ReInspectionTicket.created_at.desc())
    )
    if status and status.lower() != "all":
        stmt = stmt.where(ReInspectionTicket.status == status.lower())
    if priority and priority.lower() != "all":
        stmt = stmt.where(ReInspectionTicket.priority == priority.lower())
    if gtin:
        stmt = stmt.where(ReInspectionTicket.gtin == gtin.strip())

    stmt = stmt.limit(limit).offset(offset)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_re_inspection_ticket_by_id(
    db: AsyncSession,
    ticket_id: int,
) -> ReInspectionTicket | None:
    """
    Fetch a single ticket by its integer ID, including the triggering scan and violations.
    """
    stmt = (
        select(ReInspectionTicket)
        .options(selectinload(ReInspectionTicket.trigger_scan).selectinload(Scan.violations))
        .where(ReInspectionTicket.id == ticket_id)
    )
    res = await db.execute(stmt)
    return res.scalars().first()


async def update_re_inspection_ticket(
    db: AsyncSession,
    ticket_id: int,
    status: str | None = None,
    assigned_to: str | None = None,
    resolution_notes: str | None = None,
) -> ReInspectionTicket | None:
    """
    Update ticket status, assigned enforcement officer, and resolution notes.
    """
    ticket = await get_re_inspection_ticket_by_id(db, ticket_id)
    if not ticket:
        return None

    now = datetime.now(timezone.utc)
    if status:
        ticket.status = status.lower()
        if status.lower() in ("resolved", "dismissed"):
            ticket.resolved_at = now
    if assigned_to is not None:
        ticket.assigned_to = assigned_to
    if resolution_notes is not None:
        ticket.resolution_notes = resolution_notes

    ticket.updated_at = now
    await db.flush()
    return ticket


async def get_ticket_summary_stats(db: AsyncSession) -> dict[str, int]:
    """
    Compute KPI summary counts for the enforcement dashboard queue.
    """
    stmt = select(ReInspectionTicket.status, ReInspectionTicket.priority)
    res = await db.execute(stmt)
    rows = res.all()

    total = len(rows)
    open_count = sum(1 for s, _ in rows if s == "open")
    critical_count = sum(1 for s, p in rows if p == "critical" and s in ("open", "investigating"))
    high_count = sum(1 for s, p in rows if p == "high" and s in ("open", "investigating"))
    investigating_count = sum(1 for s, _ in rows if s == "investigating")
    resolved_count = sum(1 for s, _ in rows if s == "resolved")

    return {
        "total_tickets": total,
        "open_tickets": open_count,
        "critical_tickets": critical_count,
        "high_tickets": high_count,
        "investigating_tickets": investigating_count,
        "resolved_tickets": resolved_count,
    }

